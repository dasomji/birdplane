# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from types import SimpleNamespace

import pytest
from rest_framework.exceptions import PermissionDenied

from plane.app.serializers.agent import AgentProfileSerializer
from plane.app.serializers.issue import IssueCreateSerializer
from plane.api.serializers.issue import IssueSerializer as ExternalIssueSerializer
from plane.db.models import (
    AgentProfile,
    AgentScope,
    Issue,
    IssueAssignee,
    Project,
    ProjectMember,
    User,
    Workspace,
    WorkspaceMember,
)


pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.fixture
def agent_setup(workspace, create_user):
    project = Project.objects.create(name="Agent project", identifier="AGENT", workspace=workspace)
    ProjectMember.objects.create(project=project, workspace=workspace, member=create_user, role=20)
    agent = AgentProfile.objects.create(name="My agent", owner=create_user)
    scope = AgentScope.objects.create(agent=agent, workspace=workspace)
    scope.projects.add(project)
    colleague = User.objects.create(email="colleague@example.com", username="agent-colleague")
    return project, agent, colleague


def serializer_for(serializer_class, project, user, data, instance=None):
    return serializer_class(
        instance,
        data=data,
        partial=bool(instance),
        context={
            "request": SimpleNamespace(user=user),
            "project_id": project.id,
            "workspace_id": project.workspace_id,
            "default_assignee_id": user.id,
        },
    )


@pytest.mark.parametrize("serializer_class", [IssueCreateSerializer, ExternalIssueSerializer])
def test_creator_can_assign_and_default_human_is_not_added(agent_setup, create_user, serializer_class):
    project, agent, _ = agent_setup
    serializer = serializer_for(
        serializer_class, project, create_user, {"name": "Agent task", "agent_id": str(agent.id)}
    )
    assert serializer.is_valid(), serializer.errors
    issue = serializer.save()
    assert issue.agent_id == agent.id
    assert not IssueAssignee.objects.filter(issue=issue).exists()
    assert str(serializer.data["agent_id"]) == str(agent.id)


@pytest.mark.parametrize("serializer_class", [IssueCreateSerializer, ExternalIssueSerializer])
def test_colleague_requires_explicit_grant(agent_setup, serializer_class):
    project, agent, colleague = agent_setup
    serializer = serializer_for(serializer_class, project, colleague, {"name": "Task", "agent_id": str(agent.id)})
    with pytest.raises(PermissionDenied):
        serializer.is_valid(raise_exception=True)
    agent.assigners.add(colleague)
    serializer = serializer_for(serializer_class, project, colleague, {"name": "Task", "agent_id": str(agent.id)})
    assert serializer.is_valid(), serializer.errors
    agent.assigners.remove(colleague)
    with pytest.raises(PermissionDenied):
        serializer_for(serializer_class, project, colleague, {"name": "Task", "agent_id": str(agent.id)}).is_valid(
            raise_exception=True
        )


@pytest.mark.parametrize("serializer_class", [IssueCreateSerializer, ExternalIssueSerializer])
def test_unassign_and_replace_require_access_to_previous_agent(agent_setup, create_user, serializer_class):
    project, agent, colleague = agent_setup
    issue = Issue.objects.create(name="Task", project=project, workspace_id=project.workspace_id, agent=agent)
    other_agent = AgentProfile.objects.create(name="Colleague agent", owner=colleague)
    other_scope = AgentScope.objects.create(agent=other_agent, workspace_id=project.workspace_id, all_projects=True)
    assert other_scope
    for value in [None, str(other_agent.id)]:
        with pytest.raises(PermissionDenied):
            serializer_for(serializer_class, project, colleague, {"agent_id": value}, issue).is_valid(
                raise_exception=True
            )
    serializer = serializer_for(serializer_class, project, create_user, {"agent_id": None}, issue)
    assert serializer.is_valid(), serializer.errors
    assert serializer.save().agent_id is None


@pytest.mark.parametrize("serializer_class", [IssueCreateSerializer, ExternalIssueSerializer])
def test_scope_and_disabled_profiles_fail_closed(agent_setup, create_user, serializer_class):
    project, agent, _ = agent_setup
    other = Project.objects.create(name="Other", identifier="OTHER", workspace=project.workspace)
    for target in [other]:
        serializer = serializer_for(serializer_class, target, create_user, {"name": "Task", "agent_id": str(agent.id)})
        assert not serializer.is_valid()
        assert "agent_id" in serializer.errors
    agent.scopes.update(all_projects=True)
    assert agent.enabled_in(other.id)
    foreign_workspace = Workspace.objects.create(name="Other workspace", slug="other", owner=create_user)
    foreign = Project.objects.create(name="Foreign", identifier="FOREIGN", workspace=foreign_workspace)
    assert not agent.enabled_in(foreign.id)
    agent.is_active = False
    agent.save()
    serializer = serializer_for(serializer_class, project, create_user, {"name": "Task", "agent_id": str(agent.id)})
    assert not serializer.is_valid()


@pytest.mark.parametrize(
    "serializer_class,human_field", [(IssueCreateSerializer, "assignee_ids"), (ExternalIssueSerializer, "assignees")]
)
def test_human_agent_exclusivity_and_atomic_switch(agent_setup, create_user, serializer_class, human_field):
    project, agent, colleague = agent_setup
    issue = Issue.objects.create(name="Human task", project=project, workspace=project.workspace)
    IssueAssignee.objects.create(issue=issue, project=project, workspace=project.workspace, assignee=create_user)
    serializer = serializer_for(serializer_class, project, create_user, {"agent_id": str(agent.id)}, issue)
    assert not serializer.is_valid()
    serializer = serializer_for(
        serializer_class, project, create_user, {"agent_id": str(agent.id), human_field: []}, issue
    )
    assert serializer.is_valid(), serializer.errors
    issue = serializer.save()
    assert not IssueAssignee.objects.filter(issue=issue).exists()
    assert issue.agent_id == agent.id
    serializer = serializer_for(serializer_class, project, colleague, {human_field: [str(create_user.id)]}, issue)
    assert not serializer.is_valid()
    serializer = serializer_for(
        serializer_class, project, create_user, {"agent_id": None, human_field: [str(create_user.id)]}, issue
    )
    assert serializer.is_valid(), serializer.errors
    issue = serializer.save()
    assert issue.agent_id is None
    assert IssueAssignee.objects.filter(issue=issue, assignee=create_user).exists()


def test_profile_rejects_duplicate_workspaces_and_cross_workspace_projects(agent_setup, create_user):
    project, _, _ = agent_setup
    workspace = Workspace.objects.create(name="Other", slug="other", owner=create_user)
    bad_scope = {"workspace": str(workspace.id), "projects": [str(project.id)]}
    serializer = AgentProfileSerializer(data={"name": "Agent", "scopes": [bad_scope]})
    assert not serializer.is_valid()
    scope = {"workspace": str(workspace.id), "all_projects": True}
    serializer = AgentProfileSerializer(data={"name": "Agent", "scopes": [scope, scope]})
    assert not serializer.is_valid()


@pytest.mark.parametrize("serializer_class", [IssueCreateSerializer, ExternalIssueSerializer])
def test_model_alias_cannot_bypass_assignment_permissions(agent_setup, serializer_class):
    project, agent, colleague = agent_setup
    serializer = serializer_for(serializer_class, project, colleague, {"name": "Task", "agent": str(agent.id)})
    assert not serializer.is_valid()
    assert "agent" in serializer.errors


def test_admin_creation_and_owner_only_editing(agent_setup, create_user, api_client):
    from django.utils import timezone
    from plane.license.models import Instance, InstanceAdmin

    project, _, colleague = agent_setup
    instance = Instance.objects.create(
        instance_name="Test", instance_id="agents-test", current_version="test", last_checked_at=timezone.now()
    )
    InstanceAdmin.objects.create(instance=instance, user=create_user)
    api_client.force_authenticate(user=create_user)
    response = api_client.post(
        "/api/instances/agents/",
        {
            "name": "New agent",
            "owner": str(colleague.id),
            "scopes": [{"workspace": str(project.workspace_id), "all_projects": True}],
        },
        format="json",
    )
    assert response.status_code == 201, response.data
    agent = AgentProfile.objects.get(id=response.data["id"])
    assert agent.owner_id == create_user.id
    assert not agent.assigners.exists()
    assert agent.enabled_in(project.id)
    api_client.force_authenticate(user=colleague)
    assert api_client.get("/api/instances/agents/").status_code == 403
    InstanceAdmin.objects.create(instance=instance, user=colleague)
    assert (
        api_client.patch(
            f"/api/instances/agents/{agent.id}/", {"assigners": [str(colleague.id)]}, format="json"
        ).status_code
        == 403
    )
    assert not agent.assigners.exists()


def test_metadata_and_api_filter_and_permission_enforcement(
    agent_setup, create_user, api_key_client, api_client, mocker
):
    project, agent, colleague = agent_setup
    from plane.db.models.api import APIToken

    WorkspaceMember.objects.create(workspace=project.workspace, member=colleague, role=15)
    ProjectMember.objects.create(project=project, workspace=project.workspace, member=colleague, role=15)
    assigned = Issue.objects.create(name="Agent task", project=project, workspace=project.workspace, agent=agent)
    Issue.objects.create(name="Human task", project=project, workspace=project.workspace)
    root = f"/api/v1/workspaces/{project.workspace.slug}/projects/{project.id}"
    response = api_key_client.get(f"{root}/work-items/", {"agent_id": str(agent.id)})
    assert response.status_code == 200, response.data
    assert [str(item["id"]) for item in response.data["results"]] == [str(assigned.id)]
    assert str(response.data["results"][0]["agent_id"]) == str(agent.id)
    token = APIToken.objects.create(user=colleague, label="Colleague", token="colleague-test-token")
    api_client.credentials(HTTP_X_API_KEY=token.token)
    response = api_client.get(f"{root}/agents/")
    assert response.status_code == 200, response.data
    assert response.data[0]["can_assign"] is False
    mocker.patch("plane.api.views.issue.issue_activity.delay")
    mocker.patch("plane.api.views.issue.model_activity.delay")
    for payload in [{"agent_id": None}, {"agent_id": str(agent.id)}, {"agent": str(agent.id)}]:
        response = api_client.patch(f"{root}/work-items/{assigned.id}/", payload, format="json")
        assert response.status_code in [400, 403], response.data
    assigned.refresh_from_db()
    assert assigned.agent_id == agent.id
    agent.is_active = False
    agent.save()
    assert api_key_client.get(f"{root}/work-items/", {"agent_id": str(agent.id)}).data["results"] == []

    agent.is_active = True
    agent.save()
    agent.scopes.all().delete()
    assert api_key_client.get(f"{root}/work-items/", {"agent_id": str(agent.id)}).data["results"] == []


def test_session_assignment_and_read_projections(agent_setup, create_user, session_client, mocker):
    project, agent, colleague = agent_setup
    issue = Issue.objects.create(name="Task", project=project, workspace=project.workspace)
    root = f"/api/workspaces/{project.workspace.slug}/projects/{project.id}"
    mocker.patch("plane.app.views.issue.base.issue_activity.delay")
    mocker.patch("plane.app.views.issue.base.model_activity.delay")
    mocker.patch("plane.app.views.issue.base.issue_description_version_task.delay")
    response = session_client.patch(
        f"{root}/issues/{issue.id}/", {"agent_id": str(agent.id), "assignee_ids": []}, format="json"
    )
    assert response.status_code == 204, response.data
    response = session_client.get(f"{root}/issues/{issue.id}/")
    assert response.status_code == 200, response.data
    assert str(response.data["agent_id"]) == str(agent.id)
    assert response.data["agent_name"] == agent.name
    for path in ["issues", "issues-detail", "v2/issues"]:
        response = session_client.get(f"{root}/{path}/")
        assert response.status_code == 200, response.data
        rows = response.data["results"]
        assert str(rows[0]["agent_id"]) == str(agent.id)
        assert rows[0]["agent_name"] == agent.name
    WorkspaceMember.objects.create(workspace=project.workspace, member=colleague, role=15)
    ProjectMember.objects.create(project=project, workspace=project.workspace, member=colleague, role=15)
    session_client.force_authenticate(user=colleague)
    response = session_client.patch(f"{root}/issues/{issue.id}/", {"agent_id": None}, format="json")
    assert response.status_code == 403, response.data
