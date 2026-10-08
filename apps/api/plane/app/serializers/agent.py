# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from plane.db.models import AgentProfile, AgentScope, IssueAssignee, Project, User, Workspace


class AgentScopeSerializer(serializers.ModelSerializer):
    workspace = serializers.PrimaryKeyRelatedField(queryset=Workspace.objects.all())
    projects = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all(), many=True, required=False)

    class Meta:
        model = AgentScope
        fields = ["workspace", "all_projects", "projects"]

    def validate(self, data):
        projects = data.get("projects", [])
        if any(project.workspace_id != data["workspace"].id for project in projects):
            raise serializers.ValidationError("Every selected project must belong to its workspace.")
        if data.get("all_projects") and projects:
            raise serializers.ValidationError("Choose all projects or individual projects.")
        return data


class AgentProfileSerializer(serializers.ModelSerializer):
    scopes = AgentScopeSerializer(many=True)
    assigners = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(is_active=True, is_bot=False), many=True, required=False
    )

    class Meta:
        model = AgentProfile
        fields = ["id", "name", "description", "owner", "assigners", "scopes", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "owner", "created_at", "updated_at"]

    def validate_scopes(self, value):
        workspaces = [scope["workspace"].id for scope in value]
        if len(set(workspaces)) != len(workspaces):
            raise serializers.ValidationError("Select each workspace only once.")
        return value

    @transaction.atomic
    def create(self, validated_data):
        scopes = validated_data.pop("scopes")
        agent = super().create(validated_data)
        self.save_scopes(agent, scopes)
        return agent

    @transaction.atomic
    def update(self, instance, validated_data):
        scopes = validated_data.pop("scopes", None)
        agent = super().update(instance, validated_data)
        if scopes is not None:
            agent.scopes.all().delete()
            self.save_scopes(agent, scopes)
        return agent

    def save_scopes(self, agent, scopes):
        for data in scopes:
            projects = data.pop("projects", [])
            scope = AgentScope.objects.create(agent=agent, **data)
            scope.projects.set(projects)


class AgentAssignmentMixin(serializers.Serializer):
    """Shared write validation for session, API-key, and MCP assignment."""

    agent_id = serializers.PrimaryKeyRelatedField(
        source="agent", queryset=AgentProfile.objects.all(), required=False, allow_null=True
    )

    def validate_agent_assignment(self, attrs):
        # Reject the model field alias: all writes must use the validated agent_id.
        if "agent" in self.initial_data:
            raise serializers.ValidationError({"agent": "Use agent_id."})
        effective_agent = attrs.get("agent", self.instance.agent if self.instance else None)
        assignees = attrs.get("assignee_ids", attrs.get("assignees"))
        if assignees is None:
            has_humans = bool(self.instance and IssueAssignee.objects.filter(issue=self.instance).exists())
        else:
            has_humans = bool(assignees)
        if effective_agent and has_humans:
            raise serializers.ValidationError({"agent_id": "Choose human assignees or an AI agent, not both."})
        if "agent" not in attrs:
            return
        request = self.context.get("request")
        user = request.user if request else None
        previous = self.instance.agent if self.instance and self.instance.agent_id else None
        agent = attrs["agent"]
        for profile in (previous, agent):
            if profile and not profile.can_assign(user):
                raise PermissionDenied("You do not have permission to change this agent assignment.")
        project_id = self.context.get("project_id") or (self.instance.project_id if self.instance else None)
        if agent and not agent.enabled_in(project_id):
            raise serializers.ValidationError({"agent_id": "This agent is not enabled in this project."})
