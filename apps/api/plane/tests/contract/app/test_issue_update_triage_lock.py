"""Update locks must include intake issues hidden by the default issue manager."""

import pytest

from plane.api.serializers.issue import IssueSerializer
from plane.app.serializers.issue import IssueCreateSerializer
from plane.db.models import Intake, IntakeIssue, Issue, Project, ProjectMember, State

pytestmark = [pytest.mark.contract, pytest.mark.django_db]


@pytest.fixture
def lock_issue(workspace, create_user, request):
    project = Project.objects.create(name="Intake", identifier="INT", workspace=workspace, intake_view=True)
    ProjectMember.objects.create(project=project, workspace=workspace, member=create_user, role=20)
    triage = request.param == "triage"
    state = State.triage_objects.create(
        name="Triage" if triage else "Todo",
        group="triage" if triage else "unstarted",
        is_triage=triage,
        project=project,
        workspace=workspace,
    )
    issue = Issue.objects.create(name="Original", project=project, workspace=workspace, state=state)
    assert Issue.issue_objects.filter(pk=issue.pk).exists() is not triage
    return issue


@pytest.mark.parametrize("lock_issue", ["triage", "normal"], indirect=True)
@pytest.mark.parametrize("serializer_class", [IssueCreateSerializer, IssueSerializer])
def test_serializer_update_locks_triage_and_normal_issues(lock_issue, serializer_class):
    serializer = serializer_class(
        lock_issue,
        data={"name": "Updated"},
        partial=True,
        context={
            "project_id": lock_issue.project_id,
            "workspace_id": lock_issue.workspace_id,
            "allow_triage_state": True,
        },
    )
    assert serializer.is_valid(), serializer.errors
    serializer.save()
    lock_issue.refresh_from_db()
    assert lock_issue.name == "Updated"


@pytest.mark.parametrize("lock_issue", ["triage"], indirect=True)
@pytest.mark.parametrize("client_name", ["session_client", "api_key_client"])
def test_intake_endpoint_updates_triage_issue(lock_issue, client_name, request, monkeypatch):
    client = request.getfixturevalue(client_name)
    module = "plane.app.views.intake.base" if client_name == "session_client" else "plane.api.views.intake"
    monkeypatch.setattr(f"{module}.issue_activity.delay", lambda **kwargs: None)
    intake = Intake.objects.create(
        name="Intake", project=lock_issue.project, workspace=lock_issue.workspace, is_default=True
    )
    IntakeIssue.objects.create(
        intake=intake, issue=lock_issue, project=lock_issue.project, workspace=lock_issue.workspace
    )
    prefix = "/api" if client_name == "session_client" else "/api/v1"
    url = (
        f"{prefix}/workspaces/{lock_issue.workspace.slug}/projects/{lock_issue.project_id}/"
        f"intake-issues/{lock_issue.id}/"
    )
    response = client.patch(url, {"issue": {"name": "Updated intake"}}, format="json")
    assert response.status_code == 200, response.data
    lock_issue.refresh_from_db()
    assert lock_issue.name == "Updated intake"
