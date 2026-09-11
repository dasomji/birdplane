"""Birdplane operators: active relation membership, complements, emptiness and API scope."""

import json
from types import SimpleNamespace

import pytest
from django.utils import timezone
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
