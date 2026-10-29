"""Relations must only disclose targets in actively joined projects."""

import json
from uuid import uuid4

import pytest

from plane.db.models import Issue, IssueRelation, Project, ProjectMember, State, Workspace
from plane.utils.issue_relation_mapper import get_actual_relation

CLIENT = "session_client"
ACTIVITY = "plane.app.views.issue.relation.issue_activity.delay"
URL = "/api/workspaces/{slug}/projects/{project}/issues/{source}/issue-relation/"
ID_FIELD = "id"

pytestmark = [pytest.mark.contract, pytest.mark.django_db]


@pytest.fixture
def relation_scope(request, workspace, create_user, mocker):
    client = request.getfixturevalue(CLIENT)
    activity = mocker.patch(ACTIVITY)
    project = Project.objects.create(name="Source", identifier="SRC", workspace=workspace)
    ProjectMember.objects.create(project=project, workspace=workspace, member=create_user, role=20)

    def issue(project, name):
        state, _ = State.objects.get_or_create(
            name="Todo", group="unstarted", project=project, workspace=project.workspace
        )
        return Issue.objects.create(name=name, project=project, workspace=project.workspace, state=state)

    source = issue(project, "Source")
    return client, activity, project, source, issue


def relation_url(workspace, project, source):
    return URL.format(slug=workspace.slug, project=project.id, source=source.id)


@pytest.mark.parametrize("target_scope", ["hidden", "inactive", "foreign", "unknown"])
@pytest.mark.parametrize("relation_type", ["blocked_by", "blocking"])
def test_create_ignores_inaccessible_targets(relation_scope, workspace, create_user, target_scope, relation_type):
    client, activity, project, source, make_issue = relation_scope
    target_id = uuid4()
    if target_scope != "unknown":
        target_workspace = workspace
        if target_scope == "foreign":
            target_workspace = Workspace.objects.create(name="Foreign", slug="foreign", owner=create_user)
        hidden = Project.objects.create(name="Private", identifier="PRIV", workspace=target_workspace, network=0)
        if target_scope in ("inactive", "foreign"):
            ProjectMember.objects.create(
                project=hidden,
                workspace=target_workspace,
                member=create_user,
                role=20,
                is_active=target_scope != "inactive",
            )
        target_id = make_issue(hidden, "Confidential acquisition").id
    response = client.post(
        relation_url(workspace, project, source),
        {"relation_type": relation_type, "issues": [str(target_id)]},
        format="json",
    )
    assert response.status_code == 201, response.data
    assert response.data == []
    assert "Confidential acquisition" not in response.content.decode()
    assert not IssueRelation.objects.exists()
    payload = json.loads(activity.call_args.kwargs["requested_data"])
    assert payload == {"relation_type": relation_type, "issues": []}


@pytest.mark.parametrize("cross_project", [False, True])
@pytest.mark.parametrize(
    "relation_type",
    [
        "blocked_by",
        "blocking",
        "duplicate",
        "relates_to",
        "start_before",
        "start_after",
        "finish_before",
        "finish_after",
    ],
)
def test_accessible_targets_created_and_listed(relation_scope, workspace, create_user, cross_project, relation_type):
    client, activity, project, source, make_issue = relation_scope
    target_project = project
    if cross_project:
        target_project = Project.objects.create(name="Joined", identifier="JOIN", workspace=workspace)
        ProjectMember.objects.create(project=target_project, workspace=workspace, member=create_user, role=15)
    target = make_issue(target_project, "Visible target")
    url = relation_url(workspace, project, source)
    response = client.post(url, {"relation_type": relation_type, "issues": [str(target.id)]}, format="json")
    assert response.status_code == 201, response.data
    assert [str(row["id"]) for row in response.data] == [str(target.id)]
    assert response.data[0]["name"] == target.name
    assert IssueRelation.objects.count() == 1
    payload = json.loads(activity.call_args.kwargs["requested_data"])
    assert payload == {"relation_type": relation_type, "issues": [str(target.id)]}
    listing = client.get(url)
    assert listing.status_code == 200, listing.data
    rows = listing.data[relation_type]
    assert len(rows) == 1
    assert str(rows[0][ID_FIELD]) == str(target.id)


@pytest.mark.parametrize(
    "relation_type",
    [
        "blocked_by",
        "blocking",
        "duplicate",
        "relates_to",
        "start_before",
        "start_after",
        "finish_before",
        "finish_after",
    ],
)
def test_listing_hides_existing_inaccessible_relations(relation_scope, workspace, create_user, relation_type):
    client, _, project, source, make_issue = relation_scope
    hidden = Project.objects.create(name="Hidden", identifier="HIDE", workspace=workspace)
    membership = ProjectMember.objects.create(project=hidden, workspace=workspace, member=create_user, role=20)
    target = make_issue(hidden, "Confidential acquisition")
    reverse = relation_type in ("blocking", "start_after", "finish_after")
    IssueRelation.objects.create(
        issue=target if reverse else source,
        related_issue=source if reverse else target,
        relation_type=get_actual_relation(relation_type),
        project=project,
        workspace=workspace,
    )
    membership.is_active = False
    membership.save()
    response = client.get(relation_url(workspace, project, source))
    assert response.status_code == 200, response.data
    assert all(not rows for rows in response.data.values())
    assert str(target.id) not in response.content.decode()
    assert str(hidden.id) not in response.content.decode()
    assert target.name not in response.content.decode()


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("accessible", [False, True])
def test_expanded_issue_list_scopes_related_fields(relation_scope, workspace, create_user, reverse, accessible):
    client, _, project, source, make_issue = relation_scope
    hidden = Project.objects.create(name="Other", identifier="OTHER", workspace=workspace)
    if accessible:
        ProjectMember.objects.create(project=hidden, workspace=workspace, member=create_user, role=20)
    target = make_issue(hidden, "Confidential acquisition")
    IssueRelation.objects.create(
        issue=target if reverse else source,
        related_issue=source if reverse else target,
        relation_type="blocked_by",
        project=project,
        workspace=workspace,
    )
    field = "issue_related" if reverse else "issue_relation"
    response = client.get(f"/api/workspaces/{workspace.slug}/projects/{project.id}/issues-detail/?expand={field}")
    assert response.status_code == 200, response.data
    rows = response.data["results"]
    row = next(row for row in rows if str(row["id"]) == str(source.id))
    assert [str(item["id"]) for item in row[field]] == ([str(target.id)] if accessible else [])
    if not accessible:
        assert target.name not in response.content.decode()


@pytest.mark.parametrize("accessible", [False, True])
def test_remove_relation_requires_target_membership(relation_scope, workspace, create_user, accessible):
    client, activity, project, source, make_issue = relation_scope
    hidden = Project.objects.create(name="Other", identifier="OTHER", workspace=workspace)
    if accessible:
        ProjectMember.objects.create(project=hidden, workspace=workspace, member=create_user, role=20)
    target = make_issue(hidden, "Confidential acquisition")
    edge = IssueRelation.objects.create(
        issue=source,
        related_issue=target,
        relation_type="blocked_by",
        project=project,
        workspace=workspace,
    )
    url = relation_url(workspace, project, source).replace("issue-relation/", "remove-relation/")
    response = client.post(url, {"related_issue": str(target.id)}, format="json")
    assert response.status_code == (204 if accessible else 404), response.data
    assert IssueRelation.objects.filter(pk=edge.pk).exists() is not accessible
    assert activity.called is accessible


def test_mixed_targets_filter_response_and_activity(relation_scope, workspace):
    client, activity, project, source, make_issue = relation_scope
    visible = make_issue(project, "Visible")
    hidden_project = Project.objects.create(name="Hidden", identifier="HIDE", workspace=workspace)
    hidden = make_issue(hidden_project, "Confidential acquisition")
    response = client.post(
        relation_url(workspace, project, source),
        {"relation_type": "blocked_by", "issues": [str(visible.id), str(hidden.id), str(uuid4())]},
        format="json",
    )
    assert response.status_code == 201, response.data
    assert [str(row["id"]) for row in response.data] == [str(visible.id)]
    assert hidden.name not in response.content.decode()
    assert IssueRelation.objects.count() == 1
    assert json.loads(activity.call_args.kwargs["requested_data"]) == {
        "relation_type": "blocked_by",
        "issues": [str(visible.id)],
    }


def test_remove_relation_to_archived_target_in_joined_project(relation_scope, workspace):
    client, activity, project, source, make_issue = relation_scope
    target = make_issue(project, "Archived target")
    Issue.objects.filter(pk=target.pk).update(archived_at="2026-10-01")
    edge = IssueRelation.objects.create(
        issue=source,
        related_issue=target,
        relation_type="blocked_by",
        project=project,
        workspace=workspace,
    )
    url = relation_url(workspace, project, source).replace("issue-relation/", "remove-relation/")
    response = client.post(url, {"related_issue": str(target.id)}, format="json")
    assert response.status_code == 204, response.data
    assert not IssueRelation.objects.filter(pk=edge.pk).exists()
