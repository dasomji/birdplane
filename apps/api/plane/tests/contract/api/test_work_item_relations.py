"""Public API relation discovery and directed deletion contracts (BIRD-1)."""

from uuid import uuid4

import pytest

from plane.db.models import Issue, IssueRelation, Project, ProjectMember, State


@pytest.fixture
def relation_items(db, workspace, create_user, monkeypatch):
    monkeypatch.setattr("plane.api.views.issue.issue_activity.delay", lambda **kwargs: None)
    project = Project.objects.create(name="Relations", identifier="REL", workspace=workspace)
    ProjectMember.objects.create(project=project, workspace=workspace, member=create_user, role=20)
    state = State.objects.create(name="Todo", project=project, workspace=workspace, group="unstarted")
    items = [
        Issue.objects.create(name=name, project=project, workspace=workspace, state=state)
        for name in ("Dependent", "Blocker")
    ]
    return project, items


def url(workspace, project, issue_id):
    return f"/api/v1/workspaces/{workspace.slug}/projects/{project.id}/work-items/{issue_id}/relations/"


@pytest.mark.contract
@pytest.mark.django_db
def test_relation_definitions(api_key_client, workspace, relation_items):
    project, (dependent, _) = relation_items
    response = api_key_client.options(url(workspace, project, dependent.id))
    assert response.status_code == 200
    definitions = {row["relation_type"]: row for row in response.data["relation_types"]}
    assert definitions["blocked_by"]["inverse"] == "blocking"
    assert definitions["blocking"]["inverse"] == "blocked_by"
    assert definitions["relates_to"]["inverse"] == "relates_to"
    assert "DELETE" in response["Allow"]


@pytest.mark.contract
@pytest.mark.django_db
def test_directed_blocked_by_lifecycle(api_key_client, workspace, relation_items):
    project, (dependent, blocker) = relation_items
    dependent_url = url(workspace, project, dependent.id)
    blocker_url = url(workspace, project, blocker.id)
    body = {"relation_type": "blocked_by", "issues": [str(blocker.id)]}
    assert api_key_client.post(dependent_url, body, format="json").status_code == 201
    assert api_key_client.get(dependent_url).data["blocked_by"] == [
        {"project_id": str(project.id), "issue_id": str(blocker.id)}
    ]
    assert api_key_client.get(blocker_url).data["blocking"] == [
        {"project_id": str(project.id), "issue_id": str(dependent.id)}
    ]
    # Removing the opposite direction must not erase the real dependency.
    delete_body = {"relation_type": "blocking", "related_issue": str(blocker.id)}
    assert api_key_client.delete(dependent_url, delete_body, format="json").status_code == 404
    assert IssueRelation.objects.filter(issue=dependent, related_issue=blocker).exists()
    # The inverse view removes the same edge.
    delete_body["related_issue"] = str(dependent.id)
    assert api_key_client.delete(blocker_url, delete_body, format="json").status_code == 204
    assert api_key_client.get(dependent_url).data["blocked_by"] == []
    assert api_key_client.get(blocker_url).data["blocking"] == []


@pytest.mark.contract
@pytest.mark.django_db
@pytest.mark.parametrize("method", ["options", "get", "post", "delete"])
def test_missing_source_is_not_a_capability(api_key_client, workspace, relation_items, method):
    project, (_, blocker) = relation_items
    body = {"relation_type": "blocked_by", "issues": [str(blocker.id)], "related_issue": str(blocker.id)}
    response = getattr(api_key_client, method)(url(workspace, project, uuid4()), body, format="json")
    assert response.status_code == 404
    assert not IssueRelation.objects.exists()


@pytest.mark.contract
@pytest.mark.django_db
@pytest.mark.parametrize("relation_type", ["blocked_by", "start_before", "finish_before", "relates_to", "duplicate"])
def test_deletion_preserves_other_edges(api_key_client, workspace, relation_items, relation_type):
    project, (source, target) = relation_items
    edge = IssueRelation.objects.create(
        workspace=workspace, project=project, issue=source, related_issue=target, relation_type=relation_type
    )
    unrelated = IssueRelation.objects.create(
        workspace=workspace, project=project, issue=target, related_issue=source, relation_type="blocked_by"
    )
    body = {"relation_type": relation_type, "related_issue": str(target.id)}
    assert api_key_client.delete(url(workspace, project, source.id), body, format="json").status_code == 204
    assert not IssueRelation.objects.filter(pk=edge.id).exists()
    # Symmetric types remove only their type; directed types remove only their direction.
    assert IssueRelation.objects.filter(pk=unrelated.id).exists()


@pytest.mark.contract
@pytest.mark.django_db
@pytest.mark.parametrize(
    "body", [{}, {"related_issue": "invalid"}, {"relation_type": "unknown", "related_issue": str(uuid4())}]
)
def test_delete_validates_body(api_key_client, workspace, relation_items, body):
    project, (source, _) = relation_items
    assert api_key_client.delete(url(workspace, project, source.id), body, format="json").status_code == 400


@pytest.mark.contract
@pytest.mark.django_db
def test_guest_cannot_delete(api_key_client, workspace, relation_items, create_user):
    project, (source, target) = relation_items
    ProjectMember.objects.filter(project=project, member=create_user).update(role=5)
    assert api_key_client.options(url(workspace, project, source.id)).status_code == 200
    response = api_key_client.delete(
        url(workspace, project, source.id),
        {"relation_type": "blocked_by", "related_issue": str(target.id)},
        format="json",
    )
    assert response.status_code == 403


@pytest.mark.contract
@pytest.mark.django_db
@pytest.mark.parametrize("method", ["get", "options", "delete"])
def test_source_in_another_project_is_rejected(api_key_client, workspace, relation_items, method):
    project, (source, target) = relation_items
    other_project = Project.objects.create(name="Other", identifier="OTHER", workspace=workspace)
    Issue.objects.filter(pk=source.pk).update(project=other_project)
    body = {"relation_type": "blocked_by", "related_issue": str(target.id)}
    assert getattr(api_key_client, method)(url(workspace, project, source.id), body, format="json").status_code == 404


@pytest.mark.contract
@pytest.mark.django_db
def test_delete_rejects_inaccessible_target(api_key_client, workspace, relation_items):
    project, (source, target) = relation_items
    edge = IssueRelation.objects.create(
        workspace=workspace, project=project, issue=source, related_issue=target, relation_type="blocked_by"
    )
    hidden = Project.objects.create(name="Hidden", identifier="HIDDEN", workspace=workspace)
    Issue.objects.filter(pk=target.pk).update(project=hidden)
    body = {"relation_type": "blocked_by", "related_issue": str(target.id)}
    assert api_key_client.delete(url(workspace, project, source.id), body, format="json").status_code == 404
    assert IssueRelation.objects.filter(pk=edge.id).exists()
