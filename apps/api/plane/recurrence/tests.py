from datetime import datetime, timedelta, timezone as tz
from types import SimpleNamespace
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
import pytest
from django.db import close_old_connections
from django.utils import timezone
from rest_framework.test import APIClient
from plane.db.models import User, Workspace, WorkspaceMember, Project, ProjectMember, State, Issue, APIToken
from .calendar import occurrence, latest_index
from .models import Schedule, Occurrence
from .tasks import generate


def anchor(start, frequency="daily", zone="Europe/Vienna"):
    return SimpleNamespace(starts_at=datetime.fromisoformat(start), frequency=frequency, interval=1, timezone=zone)


def test_calendar_dst_and_month_ends():
    s = anchor("2026-01-31T08:00:00+01:00", "monthly")
    assert occurrence(s, 1).isoformat() == "2026-02-28T07:00:00+00:00"
    assert occurrence(s, 2).isoformat() == "2026-03-31T06:00:00+00:00"
    s = anchor("2026-03-28T02:30:00+01:00")
    assert occurrence(s, 1).isoformat() == "2026-03-29T01:30:00+00:00"
    assert occurrence(s, 2).isoformat() == "2026-03-30T00:30:00+00:00"
    s = anchor("2026-10-24T02:30:00+02:00")
    assert occurrence(s, 1).isoformat() == "2026-10-25T00:30:00+00:00"
    s = anchor("2024-02-29T10:00:00+00:00", "yearly", "UTC")
    assert occurrence(s, 1).day == 28
    assert occurrence(s, 4).day == 29
    assert latest_index(s, datetime(2028, 3, 1, tzinfo=tz.utc)) == 4


@pytest.fixture
def setup(db):
    user = User.objects.create(email="recurring@example.test", username="recurring")
    ws = Workspace.objects.create(name="Recurrence", slug="recurrence", owner=user)
    project = Project.objects.create(name="Tasks", identifier="TEST", workspace=ws)
    WorkspaceMember.objects.create(workspace=ws, member=user, role=20)
    ProjectMember.objects.create(workspace=ws, project=project, member=user, role=20)
    state = State.objects.create(project=project, workspace=ws, name="Todo", group="unstarted", default=True)
    issue = Issue.objects.create(
        project=project,
        workspace=ws,
        state=state,
        name="Recurring template",
        description_html="<p>Snapshot</p>",
        start_date=timezone.now().date(),
        target_date=timezone.now().date() + timedelta(days=2),
    )
    client = APIClient()
    token = APIToken.objects.create(user=user, label="Test", token="recurrence-test-token")
    client.credentials(HTTP_X_API_KEY=token.token)
    path = f"/api/v1/workspaces/{ws.slug}/projects/{project.id}/recurring-tasks/"
    return SimpleNamespace(user=user, ws=ws, project=project, issue=issue, client=client, path=path)


def create(s, **extra):
    response = s.client.post(
        s.path,
        {
            "template_issue": str(s.issue.id),
            "frequency": "daily",
            "starts_at": (timezone.now() + timedelta(minutes=5)).isoformat(),
            **extra,
        },
        format="json",
    )
    assert response.status_code == 201, response.data
    return Schedule.objects.get(pk=response.data["id"])


@pytest.mark.django_db
def test_snapshot_generation_and_retry(setup):
    s = create(setup)
    setup.issue.name = "Changed later"
    setup.issue.save()
    now = s.starts_at + timedelta(days=4, minutes=1)
    iid = generate(s.id, now)
    generated = Issue.objects.get(pk=iid)
    assert generated.name == "Recurring template"
    assert (generated.target_date - generated.start_date).days == 2
    assert generated.created_by_id == setup.user.id
    assert generate(s.id, now) is None
    assert Occurrence.objects.filter(schedule=s).count() == 1
    s.refresh_from_db()
    assert s.next_run_at == s.starts_at + timedelta(days=5)
    # Deleting a generated issue must not recreate that occurrence.
    generated.delete()
    assert generate(s.id, now) is None


@pytest.mark.django_db
def test_pause_resume_end_and_delete(setup):
    s = create(setup, status="paused")
    now = s.starts_at + timedelta(days=2)
    assert generate(s.id, now) is None
    response = setup.client.patch(setup.path + str(s.id) + "/", {"status": "active"}, format="json")
    assert response.status_code == 200
    iid = generate(s.id, now)
    response = setup.client.patch(setup.path + str(s.id) + "/", {"status": "ended"}, format="json")
    assert response.status_code == 200
    assert generate(s.id, now + timedelta(days=1)) is None
    assert setup.client.patch(setup.path + str(s.id) + "/", {"status": "active"}, format="json").status_code == 400
    assert setup.client.delete(setup.path + str(s.id) + "/").status_code == 204
    assert Issue.objects.filter(pk=iid).exists()


@pytest.mark.django_db
def test_end_inclusive_and_rollback(setup):
    start = timezone.now() + timedelta(minutes=5)
    s = create(setup, starts_at=start.isoformat(), ends_at=(start + timedelta(days=1)).isoformat())
    with patch.object(Issue, "save", side_effect=RuntimeError("failure")):
        with pytest.raises(RuntimeError):
            generate(s.id, start + timedelta(days=3))
    assert not Occurrence.objects.filter(schedule=s).exists()
    assert generate(s.id, start + timedelta(days=3))
    s.refresh_from_db()
    assert s.last_run_at == s.ends_at
    assert s.status == "ended"


@pytest.mark.django_db
def test_validation_scope_and_catalog(setup):
    s = create(setup)
    assert setup.client.get(f"/api/v1/workspaces/{setup.ws.slug}/recurring-catalog/").status_code == 200
    assert setup.client.get(f"/api/v1/workspaces/{setup.ws.slug}/recurring-catalog/?project={setup.project.id}").data[
        0
    ]["id"] == str(setup.issue.id)
    assert (
        setup.client.patch(setup.path + str(s.id) + "/", {"timezone": "Invalid/Zone"}, format="json").status_code == 400
    )
    assert setup.client.patch(setup.path + str(s.id) + "/", {"interval": 0}, format="json").status_code == 400
    assert setup.client.patch(setup.path + str(s.id) + "/", {"template": {}}, format="json").status_code == 400
    assert (
        setup.client.post(
            setup.path,
            {"template_issue": str(setup.issue.id), "frequency": "daily", "starts_at": "2020-01-01T00:00:00Z"},
            format="json",
        ).status_code
        == 400
    )
    other = Project.objects.create(workspace=setup.ws, name="Other", identifier="OTHER")
    other_issue = Issue.objects.create(project=other, workspace=setup.ws, name="Private")
    assert (
        setup.client.patch(
            setup.path + str(s.id) + "/", {"template_issue": str(other_issue.id)}, format="json"
        ).status_code
        == 404
    )
    ProjectMember.objects.filter(project=setup.project, member=setup.user).update(role=5)
    assert setup.client.get(setup.path).status_code == 403
    assert setup.client.patch(setup.path + str(s.id) + "/", {"status": "paused"}, format="json").status_code == 403
    assert generate(s.id, s.starts_at + timedelta(minutes=1)) is None
    s.refresh_from_db()
    assert s.status == "paused"


@pytest.mark.django_db(transaction=True)
def test_concurrent_workers_generate_once(setup):
    s = create(setup)

    def run():
        close_old_connections()
        try:
            return generate(s.id, s.starts_at + timedelta(seconds=1))
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        result = list(pool.map(lambda _: run(), range(2)))
    assert len([x for x in result if x]) == 1
    assert Occurrence.objects.filter(schedule=s).count() == 1


@pytest.mark.django_db
def test_session_csrf_and_anonymous_access(setup):
    client = APIClient(enforce_csrf_checks=True)
    assert client.get(setup.path).status_code == 401
    client.force_login(setup.user)
    assert client.get(setup.path).status_code == 200
    assert client.post(setup.path, {}, format="json").status_code == 403
    page = client.get("/api/birdplane/recurring/")
    assert page.status_code == 200
    assert b"New schedule" in page.content
    csrf = client.cookies["csrftoken"].value
    assert client.post(setup.path, {}, format="json", HTTP_X_CSRFTOKEN=csrf).status_code == 400
