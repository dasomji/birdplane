# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db.models import Q
from rest_framework.exceptions import ParseError

from plane.api.serializers.workspace import WorkspaceLiteSerializer
from plane.api.views.base import BaseAPIView
from plane.db.models import Workspace


class WorkspaceListAPIEndpoint(BaseAPIView):
    """Discover active workspace memberships for the API key's user."""

    serializer_class = WorkspaceLiteSerializer

    def get_per_page(self, request, default_per_page=10, max_per_page=50):
        limit = super().get_per_page(request, default_per_page, max_per_page)
        if limit < 1:
            raise ParseError(detail="per_page must be at least 1.")
        return limit

    def get(self, request):
        workspaces = Workspace.objects.filter(
            workspace_member__member=request.user,
            workspace_member__is_active=True,
            workspace_member__deleted_at__isnull=True,
        ).order_by("name", "id")
        query = request.GET.get("query", "").strip()
        if query:
            workspaces = workspaces.filter(Q(name__icontains=query) | Q(slug__icontains=query))
        return self.paginate(
            request=request,
            queryset=workspaces,
            default_per_page=10,
            max_per_page=50,
            on_results=lambda rows: WorkspaceLiteSerializer(rows, many=True).data,
        )
