# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from plane.app.permissions import ProjectEntityPermission
from plane.app.views.base import BaseAPIView
from plane.api.views.base import BaseAPIView as APIKeyAPIView
from plane.app.serializers.agent import AgentProfileSerializer
from plane.db.models import AgentProfile, Project, ProjectMember, User, Workspace, WorkspaceMember
from plane.license.api.permissions import InstanceAdminPermission


class AgentAdminEndpoint(BaseAPIView):
    permission_classes = [InstanceAdminPermission]

    def get(self, request, pk=None):
        agents = AgentProfile.objects.prefetch_related("assigners", "scopes__projects")
        if pk:
            return Response(AgentProfileSerializer(get_object_or_404(agents, pk=pk)).data)
        return Response(AgentProfileSerializer(agents, many=True).data)

    def post(self, request):
        serializer = AgentProfileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(owner=request.user)
        return Response(serializer.data, status=201)

    def patch(self, request, pk):
        agent = get_object_or_404(AgentProfile, pk=pk)
        # Assignment grants belong to the creator, even when other admins exist.
        if agent.owner_id != request.user.id:
            raise PermissionDenied("Only the creator can edit this agent profile.")
        serializer = AgentProfileSerializer(agent, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class AgentAdminOptionsEndpoint(BaseAPIView):
    permission_classes = [InstanceAdminPermission]

    def get(self, request):
        return Response(
            {
                "workspaces": list(Workspace.objects.values("id", "name")),
                "projects": list(Project.objects.filter(archived_at__isnull=True).values("id", "name", "workspace_id")),
                "members": list(
                    User.objects.filter(is_active=True, is_bot=False).values("id", "display_name", "email")
                ),
            }
        )


def project_agents(request, slug, project_id):
    project = get_object_or_404(Project, id=project_id, workspace__slug=slug)
    # Match project read access, including public projects for workspace members.
    if not WorkspaceMember.objects.filter(
        workspace_id=project.workspace_id, member=request.user, is_active=True
    ).exists():
        raise PermissionDenied()
    if (
        project.network != 2
        and not ProjectMember.objects.filter(project=project, member=request.user, is_active=True).exists()
    ):
        raise PermissionDenied()
    agents = (
        AgentProfile.objects.filter(
            Q(scopes__workspace_id=project.workspace_id, scopes__all_projects=True)
            | Q(scopes__workspace_id=project.workspace_id, scopes__projects=project)
            | Q(issues__project=project)
        )
        .distinct()
        .prefetch_related("assigners")
    )
    return [
        {
            "id": str(agent.id),
            "name": agent.name,
            "description": agent.description,
            "is_active": agent.is_active,
            "can_assign": agent.can_assign(request.user) and agent.enabled_in(project_id),
            "can_unassign": agent.can_assign(request.user),
        }
        for agent in agents
    ]


class ProjectAgentsEndpoint(BaseAPIView):
    def get(self, request, slug, project_id):
        return Response(project_agents(request, slug, project_id))


class ProjectAgentsAPIEndpoint(APIKeyAPIView):
    permission_classes = [ProjectEntityPermission]

    def get(self, request, slug, project_id):
        return Response(project_agents(request, slug, project_id))
