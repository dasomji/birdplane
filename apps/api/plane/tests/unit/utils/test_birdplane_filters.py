"""Birdplane operators: active relation membership, complements, emptiness and API scope."""

import json
from datetime import datetime, timezone as datetime_timezone
from types import SimpleNamespace

import pytest
from django.utils import timezone
from django.urls import resolve
from freezegun import freeze_time
from rest_framework.test import APIClient
from plane.db.models import (
    User,
    Workspace,
    WorkspaceMember,
    Project,
    ProjectMember,
    State,
    Issue,
    Label,
    IssueLabel,
    IssueAssignee,
    APIToken,
)
from plane.utils.filters.filterset import IssueFilterSet
from plane.utils.filters.filter_backend import ComplexFilterBackend


@pytest.fixture
def data(db):
    user = User.objects.create(email="filters@example.test", username="filters")
    workspace = Workspace.objects.create(name="Filters", slug="filters", owner=user)
    project = Project.objects.create(name="Filters", identifier="FILT", workspace=workspace)
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=20)
    ProjectMember.objects.create(workspace=workspace, project=project, member=user, role=20)
    state = State.objects.create(workspace=workspace, project=project, name="Todo", group="unstarted", default=True)
    common = dict(workspace=workspace, project=project)
    labels = [Label.objects.create(**common, name=name) for name in ["Blog", "Other"]]
    issues = [Issue.objects.create(**common, state=state, name=name) for name in ["both", "other", "empty", "removed"]]
    for issue, label in [(issues[0], labels[0]), (issues[0], labels[1]), (issues[1], labels[1])]:
        IssueLabel.objects.create(**common, issue=issue, label=label)
    IssueLabel.objects.create(**common, issue=issues[3], label=labels[0], deleted_at=timezone.now())
    # A removed assignment of the excluded label must not mask an active assignment.
    IssueLabel.objects.create(**common, issue=issues[0], label=labels[0], deleted_at=timezone.now())
    IssueAssignee.objects.create(**common, issue=issues[0], assignee=user)
    IssueAssignee.objects.create(**common, issue=issues[3], assignee=user, deleted_at=timezone.now())
    Issue.objects.filter(pk=issues[0].pk).update(priority="high", target_date="2026-09-20")
    return SimpleNamespace(user=user, workspace=workspace, project=project, labels=labels, issues=issues)


def apply(data, expression):
    request = SimpleNamespace(query_params={"filters": json.dumps(expression)})
    result = ComplexFilterBackend().filter_queryset(
        request, Issue.objects.filter(project=data.project), SimpleNamespace(filterset_class=IssueFilterSet)
    )
    names = list(result.values_list("name", flat=True))
    assert len(names) == len(set(names)), "relation joins must not duplicate tickets"
    return set(names)


def test_relations_is_not_and_empty(data):
    blog, other = [str(label.pk) for label in data.labels]
    assert apply(data, {"label_id__in": blog}) == {"both"}
    assert apply(data, {"label_id__not_in": blog}) == {"other", "empty", "removed"}
    assert apply(data, {"label_id__not_in": f"{blog},{other}"}) == {"empty", "removed"}
    assert apply(data, {"label_id__not_in": [blog, other]}) == {"empty", "removed"}
    assert apply(data, {"label_id__is_empty": True}) == {"empty", "removed"}
    assert apply(data, {"and": [{"label_id__in": blog}, {"label_id__in": other}]}) == {"both"}
    assert apply(data, {"assignee_id__is_empty": True}) == {"other", "empty", "removed"}
    assert apply(data, {"assignee_id__not_in": str(data.user.pk)}) == {"other", "empty", "removed"}


def test_scalar_dates_and_combinations(data):
    assert apply(data, {"priority__not_in": "high,urgent"}) == {"other", "empty", "removed"}
    assert apply(data, {"priority__is_empty": True}) == {"other", "empty", "removed"}
    assert apply(data, {"target_date__not_exact": "2026-09-20"}) == {"other", "empty", "removed"}
    assert apply(data, {"target_date__is_empty": True}) == {"other", "empty", "removed"}
    assert apply(data, {"target_date__exact": "2026-09-20"}) == {"both"}
    assert apply(data, {"and": [{"priority__not_in": "high"}, {"label_id__in": str(data.labels[1].pk)}]}) == {"other"}


def test_public_api_filters_before_pagination_and_rejects_invalid(data):
    token = APIToken.objects.create(user=data.user, label="Filters", token="filter-test-token")
    client = APIClient()
    client.credentials(HTTP_X_API_KEY=token.token)
    path = f"/api/v1/workspaces/{data.workspace.slug}/projects/{data.project.id}/work-items/"
    expression = {"label_id__not_in": str(data.labels[0].pk)}
    response = client.get(path, {"filters": json.dumps(expression), "per_page": 1})
    assert response.status_code == 200, response.data
    assert len(response.data["results"]) == 1
    assert response.data["results"][0]["name"] != "both"
    assert response.data["total_results"] == 3
    for expression in [
        {"label_id__not_in": "not-a-uuid"},
        {"target_date__not_exact": "invalid"},
        {"password__is_empty": True},
    ]:
        response = client.get(path, {"filters": json.dumps(expression)})
        assert response.status_code == 400, response.data
    outsider = User.objects.create(email="outsider@example.test", username="outsider")
    token = APIToken.objects.create(user=outsider, label="Outsider", token="outsider-token")
    client.credentials(HTTP_X_API_KEY=token.token)
    assert client.get(path, {"filters": json.dumps({"label_id__is_empty": True})}).status_code in (403, 404)


def test_public_api_evaluates_relative_dates_in_the_users_timezone(data, mocker):
    data.user.user_timezone = "America/Los_Angeles"
    data.user.save(update_fields=["user_timezone"])
    Issue.objects.filter(pk=data.issues[0].pk).update(
        created_at=datetime(2026, 9, 14, 3, 0, tzinfo=datetime_timezone.utc)
    )
    Issue.objects.filter(pk=data.issues[1].pk).update(
        created_at=datetime(2026, 9, 14, 8, 0, tzinfo=datetime_timezone.utc)
    )
    Issue.objects.filter(pk__in=[data.issues[2].pk, data.issues[3].pk]).update(
        created_at=datetime(2026, 9, 10, 12, 0, tzinfo=datetime_timezone.utc)
    )
    token = APIToken.objects.create(user=data.user, label="PQL", token="pql-test-token")
    client = APIClient()
    client.credentials(HTTP_X_API_KEY=token.token)
    path = f"/api/v1/workspaces/{data.workspace.slug}/projects/{data.project.id}/work-items/"
    # Import the URL graph before freezegun replaces ``datetime.date``. Some optional
    # dependencies define date subclasses at import time and cannot do so afterwards.
    resolve(path)
    mocker.patch("plane.middleware.logger.process_logs.delay")

    with freeze_time("2026-09-14 06:30:00"):
        response = client.get(path, {"pql": "createdAt = today()"})

    assert response.status_code == 200, response.data
    assert [item["name"] for item in response.data["results"]] == ["both"]


def test_public_api_combines_rolling_days_with_calendar_week_boundaries(data, mocker):
    data.user.user_timezone = "America/Los_Angeles"
    data.user.save(update_fields=["user_timezone"])
    Issue.objects.filter(pk=data.issues[0].pk).update(
        created_at=datetime(2026, 9, 10, 12, 0, tzinfo=datetime_timezone.utc),
        target_date="2026-09-20",
    )
    Issue.objects.filter(pk=data.issues[1].pk).update(
        created_at=datetime(2026, 9, 15, 12, 0, tzinfo=datetime_timezone.utc),
        target_date="2026-09-21",
    )
    Issue.objects.filter(pk=data.issues[2].pk).update(
        created_at=datetime(2026, 9, 1, 12, 0, tzinfo=datetime_timezone.utc),
        target_date="2026-09-16",
    )
    token = APIToken.objects.create(user=data.user, label="PQL week", token="pql-week-token")
    client = APIClient()
    client.credentials(HTTP_X_API_KEY=token.token)
    path = f"/api/v1/workspaces/{data.workspace.slug}/projects/{data.project.id}/work-items/"
    resolve(path)
    mocker.patch("plane.middleware.logger.process_logs.delay")
    query = (
        "createdAt >= daysAgo(7) AND "
        "dueDate BETWEEN startOfWeek() AND endOfWeek()"
    )

    with freeze_time("2026-09-16 19:00:00"):
        response = client.get(path, {"pql": query})

    assert response.status_code == 200, response.data
    assert [item["name"] for item in response.data["results"]] == ["both"]


@pytest.mark.parametrize(
    ("query", "field", "values"),
    [
        (
            "createdAt = today()",
            "created_at",
            (
                datetime(2024, 3, 31, 15, tzinfo=datetime_timezone.utc),
                datetime(2024, 3, 30, 15, tzinfo=datetime_timezone.utc),
                datetime(2024, 3, 30, 15, tzinfo=datetime_timezone.utc),
                datetime(2024, 3, 30, 15, tzinfo=datetime_timezone.utc),
            ),
        ),
        (
            "updatedAt != today()",
            "updated_at",
            (
                datetime(2024, 3, 30, 15, tzinfo=datetime_timezone.utc),
                datetime(2024, 3, 31, 15, tzinfo=datetime_timezone.utc),
                datetime(2024, 3, 31, 15, tzinfo=datetime_timezone.utc),
                datetime(2024, 3, 31, 15, tzinfo=datetime_timezone.utc),
            ),
        ),
        (
            "createdAt >= startOfDay() AND createdAt <= endOfDay()",
            "created_at",
            (
                datetime(2024, 3, 31, 12, tzinfo=datetime_timezone.utc),
                datetime(2024, 3, 30, 23, tzinfo=datetime_timezone.utc),
                datetime(2024, 4, 1, 0, tzinfo=datetime_timezone.utc),
                datetime(2024, 4, 1, 0, tzinfo=datetime_timezone.utc),
            ),
        ),
        (
            "updatedAt > daysAgo(7) AND updatedAt < daysFromNow(7)",
            "updated_at",
            (
                datetime(2024, 3, 31, 12, tzinfo=datetime_timezone.utc),
                datetime(2024, 3, 24, 0, tzinfo=datetime_timezone.utc),
                datetime(2024, 4, 7, 23, tzinfo=datetime_timezone.utc),
                datetime(2024, 4, 7, 23, tzinfo=datetime_timezone.utc),
            ),
        ),
        (
            "startDate BETWEEN startOfMonth() AND endOfMonth()",
            "start_date",
            ("2024-03-15", "2024-02-29", "2024-04-01", "2024-04-01"),
        ),
        (
            "dueDate BETWEEN startOfYear() AND endOfYear()",
            "target_date",
            ("2024-12-31", "2023-12-31", "2025-01-01", "2025-01-01"),
        ),
        (
            "startDate >= weeksAgo(1) AND startDate <= weeksFromNow(1)",
            "start_date",
            ("2024-03-31", "2024-03-23", "2024-04-08", "2024-04-08"),
        ),
        (
            "startDate = monthsAgo(1)",
            "start_date",
            ("2024-02-29", "2024-02-28", "2024-03-01", "2024-03-01"),
        ),
        (
            "dueDate = monthsFromNow(1)",
            "target_date",
            ("2024-04-30", "2024-04-29", "2024-05-01", "2024-05-01"),
        ),
        (
            "updatedAt <= now()",
            "updated_at",
            (
                datetime(2024, 3, 31, 23, tzinfo=datetime_timezone.utc),
                datetime(2024, 4, 1, 13, tzinfo=datetime_timezone.utc),
                datetime(2024, 4, 1, 13, tzinfo=datetime_timezone.utc),
                datetime(2024, 4, 1, 13, tzinfo=datetime_timezone.utc),
            ),
        ),
        (
            "startDate IS NULL",
            "start_date",
            (None, "2024-03-31", "2024-03-31", "2024-03-31"),
        ),
        (
            "dueDate IS NOT NULL",
            "target_date",
            ("2024-03-31", None, None, None),
        ),
    ],
)
def test_public_api_supports_documented_relative_date_queries(data, mocker, query, field, values):
    for issue, value in zip(data.issues, values):
        Issue.objects.filter(pk=issue.pk).update(**{field: value})
    token = APIToken.objects.create(user=data.user, label="PQL dates", token="pql-dates-token")
    client = APIClient()
    client.credentials(HTTP_X_API_KEY=token.token)
    path = f"/api/v1/workspaces/{data.workspace.slug}/projects/{data.project.id}/work-items/"
    resolve(path)
    mocker.patch("plane.middleware.logger.process_logs.delay")

    with freeze_time("2024-03-31 12:00:00"):
        response = client.get(path, {"pql": query})

    assert response.status_code == 200, response.data
    assert {item["name"] for item in response.data["results"]} == {"both"}


@pytest.mark.parametrize(
    ("query", "field", "values"),
    [
        (
            "createdAt >= hoursAgo(24)",
            "created_at",
            (
                datetime(2024, 3, 30, 13, 0, tzinfo=datetime_timezone.utc),
                datetime(2024, 3, 30, 11, 59, tzinfo=datetime_timezone.utc),
                datetime(2024, 3, 1, 12, 0, tzinfo=datetime_timezone.utc),
                datetime(2024, 3, 1, 12, 0, tzinfo=datetime_timezone.utc),
            ),
        ),
        (
            "createdAt < hoursAgo(24)",
            "created_at",
            (
                datetime(2024, 3, 30, 11, 59, tzinfo=datetime_timezone.utc),
                datetime(2024, 3, 30, 13, 0, tzinfo=datetime_timezone.utc),
                datetime(2024, 3, 30, 13, 0, tzinfo=datetime_timezone.utc),
                datetime(2024, 3, 30, 13, 0, tzinfo=datetime_timezone.utc),
            ),
        ),
        (
            "updatedAt > hoursAgo(24)",
            "updated_at",
            (
                datetime(2024, 3, 30, 13, 0, tzinfo=datetime_timezone.utc),
                datetime(2024, 3, 30, 12, 0, tzinfo=datetime_timezone.utc),
                datetime(2024, 3, 30, 12, 0, tzinfo=datetime_timezone.utc),
                datetime(2024, 3, 30, 12, 0, tzinfo=datetime_timezone.utc),
            ),
        ),
        (
            "updatedAt <= hoursFromNow(1)",
            "updated_at",
            (
                datetime(2024, 3, 31, 12, 30, tzinfo=datetime_timezone.utc),
                datetime(2024, 3, 31, 14, 0, tzinfo=datetime_timezone.utc),
                datetime(2024, 3, 31, 14, 0, tzinfo=datetime_timezone.utc),
                datetime(2024, 3, 31, 14, 0, tzinfo=datetime_timezone.utc),
            ),
        ),
    ],
)
def test_public_api_supports_rolling_hour_windows(data, mocker, query, field, values):
    for issue, value in zip(data.issues, values):
        Issue.objects.filter(pk=issue.pk).update(**{field: value})
    token = APIToken.objects.create(user=data.user, label="PQL hours", token="pql-hours-token")
    client = APIClient()
    client.credentials(HTTP_X_API_KEY=token.token)
    path = f"/api/v1/workspaces/{data.workspace.slug}/projects/{data.project.id}/work-items/"
    resolve(path)
    mocker.patch("plane.middleware.logger.process_logs.delay")

    with freeze_time("2024-03-31 12:00:00"):
        response = client.get(path, {"pql": query})

    assert response.status_code == 200, response.data
    assert {item["name"] for item in response.data["results"]} == {"both"}


def test_public_api_expands_saved_pql_and_combines_it_with_basic_filters(data, mocker):
    Issue.objects.filter(pk__in=[data.issues[0].pk, data.issues[1].pk]).update(
        created_at=datetime(2024, 3, 29, 12, 0, tzinfo=datetime_timezone.utc)
    )
    Issue.objects.filter(pk__in=[data.issues[2].pk, data.issues[3].pk]).update(
        created_at=datetime(2024, 3, 1, 12, 0, tzinfo=datetime_timezone.utc)
    )
    Issue.objects.filter(pk=data.issues[0].pk).update(priority="high")
    Issue.objects.filter(pk=data.issues[1].pk).update(priority="low")
    Issue.objects.filter(pk=data.issues[2].pk).update(priority="high")
    token = APIToken.objects.create(user=data.user, label="Saved PQL", token="saved-pql-token")
    client = APIClient()
    client.credentials(HTTP_X_API_KEY=token.token)
    path = f"/api/v1/workspaces/{data.workspace.slug}/projects/{data.project.id}/work-items/"
    resolve(path)
    mocker.patch("plane.middleware.logger.process_logs.delay")
    saved_filters = {
        "AND": [
            {"pql__exact": "createdAt >= daysAgo(7)"},
            {"priority__exact": "high"},
        ]
    }

    with freeze_time("2024-03-31 12:00:00"):
        response = client.get(path, {"filters": json.dumps(saved_filters)})

    assert response.status_code == 200, response.data
    assert {item["name"] for item in response.data["results"]} == {"both"}


def test_authenticated_workspace_pql_endpoint_validates_queries(data, mocker):
    client = APIClient()
    client.force_authenticate(user=data.user)
    path = f"/api/workspaces/{data.workspace.slug}/pql/"
    mocker.patch("plane.middleware.logger.process_logs.delay")

    valid_response = client.post(path, {"query": "createdAt >= daysAgo(7)"}, format="json")
    invalid_response = client.post(path, {"query": "createdAt ="}, format="json")

    assert valid_response.status_code == 200, valid_response.content
    assert valid_response.json() == {"filters": {"created_at__gte": "daysAgo(7)"}}
    assert invalid_response.status_code == 400, invalid_response.content
    assert invalid_response.json()["code"] == "invalid_pql"


def test_pql_endpoints_reject_unsafe_input_and_unauthorized_users(data, mocker):
    mocker.patch("plane.middleware.logger.process_logs.delay")
    validation_path = f"/api/workspaces/{data.workspace.slug}/pql/"
    list_path = f"/api/v1/workspaces/{data.workspace.slug}/projects/{data.project.id}/work-items/"
    resolve(validation_path)
    resolve(list_path)

    session_client = APIClient()
    session_client.force_authenticate(user=data.user)
    session_client.raise_request_exception = False
    malformed_payload = session_client.post(validation_path, [], format="json")
    assert malformed_payload.status_code == 400, malformed_payload.content

    for username, is_active in (("pql-outsider", None), ("pql-inactive", False)):
        user = User.objects.create(email=f"{username}@example.test", username=username)
        if is_active is not None:
            WorkspaceMember.objects.create(
                workspace=data.workspace,
                member=user,
                role=20,
                is_active=is_active,
            )
        session_client.force_authenticate(user=user)
        response = session_client.post(validation_path, {"query": "createdAt = today()"}, format="json")
        assert response.status_code in (403, 404), response.content

    token = APIToken.objects.create(user=data.user, label="PQL safety", token="pql-safety-token")
    api_client = APIClient()
    api_client.credentials(HTTP_X_API_KEY=token.token)
    api_client.raise_request_exception = False
    invalid_query = api_client.get(list_path, {"pql": "createdAt ="})
    assert invalid_query.status_code == 400, invalid_query.content
    assert invalid_query.data["code"] == "invalid_pql"
    overflowing_date = api_client.get(list_path, {"pql": "dueDate = monthsAgo(100000)"})
    assert overflowing_date.status_code == 400, overflowing_date.content
    assert overflowing_date.data["code"] == "invalid_pql"

    deeply_nested = {"pql__exact": "createdAt = today()"}
    for _ in range(20):
        deeply_nested = {"AND": [deeply_nested]}
    nested_response = api_client.get(list_path, {"filters": json.dumps(deeply_nested)})
    assert nested_response.status_code == 400, nested_response.content


@pytest.mark.parametrize("scope", ["project", "workspace"])
def test_saved_views_preserve_and_recalculate_relative_pql(data, mocker, scope):
    query = "createdAt BETWEEN daysAgo(7) AND today()"
    raw_filters = {"pql__exact": query}
    Issue.objects.filter(pk=data.issues[0].pk).update(
        created_at=datetime(2024, 3, 29, 12, 0, tzinfo=datetime_timezone.utc)
    )
    Issue.objects.filter(pk=data.issues[1].pk).update(
        created_at=datetime(2024, 4, 8, 12, 0, tzinfo=datetime_timezone.utc)
    )
    Issue.objects.filter(pk__in=[data.issues[2].pk, data.issues[3].pk]).update(
        created_at=datetime(2024, 2, 1, 12, 0, tzinfo=datetime_timezone.utc)
    )
    mocker.patch("plane.middleware.logger.process_logs.delay")
    mocker.patch("plane.app.views.view.base.recent_visited_task.delay")
    session_client = APIClient()
    session_client.force_authenticate(user=data.user)
    if scope == "project":
        collection_path = f"/api/workspaces/{data.workspace.slug}/projects/{data.project.id}/views/"
    else:
        collection_path = f"/api/workspaces/{data.workspace.slug}/views/"

    create_response = session_client.post(
        collection_path,
        {
            "name": f"Relative dates {scope}",
            "description": "",
            "filters": {},
            "rich_filters": raw_filters,
        },
        format="json",
    )
    assert create_response.status_code == 201, create_response.data
    detail_path = f"{collection_path}{create_response.data['id']}/"
    retrieve_response = session_client.get(detail_path)
    assert retrieve_response.status_code == 200, retrieve_response.data
    assert retrieve_response.data["rich_filters"] == raw_filters

    token = APIToken.objects.create(user=data.user, label=f"Saved {scope}", token=f"saved-{scope}-token")
    api_client = APIClient()
    api_client.credentials(HTTP_X_API_KEY=token.token)
    issue_path = f"/api/v1/workspaces/{data.workspace.slug}/projects/{data.project.id}/work-items/"
    with freeze_time("2024-03-31 12:00:00"):
        first_response = api_client.get(issue_path, {"filters": json.dumps(retrieve_response.data["rich_filters"])})
    with freeze_time("2024-04-10 12:00:00"):
        second_response = api_client.get(issue_path, {"filters": json.dumps(retrieve_response.data["rich_filters"])})

    assert first_response.status_code == 200, first_response.data
    assert {item["name"] for item in first_response.data["results"]} == {"both"}
    assert second_response.status_code == 200, second_response.data
    assert {item["name"] for item in second_response.data["results"]} == {"other"}
    assert retrieve_response.data["rich_filters"] == raw_filters


def test_saved_views_reject_invalid_pql_before_persistence(data, mocker):
    mocker.patch("plane.middleware.logger.process_logs.delay")
    client = APIClient()
    client.force_authenticate(user=data.user)
    collection_path = f"/api/workspaces/{data.workspace.slug}/projects/{data.project.id}/views/"

    response = client.post(
        collection_path,
        {
            "name": "Invalid relative dates",
            "description": "",
            "filters": {},
            "rich_filters": {"pql__exact": "createdAt ="},
        },
        format="json",
    )

    assert response.status_code == 400, response.data
