# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Assignment identities for external agents; these are never login accounts."""

import uuid

from django.conf import settings
from django.db import models


class AgentProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_agents")
    assigners = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="assignable_agents")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "agent_profiles"
        ordering = ["name", "id"]

    def can_assign(self, user):
        return bool(
            user and user.is_authenticated and (self.owner_id == user.id or self.assigners.filter(id=user.id).exists())
        )

    def enabled_in(self, project_id):
        return (
            self.is_active
            and self.scopes.filter(
                models.Q(all_projects=True) | models.Q(projects__id=project_id),
                workspace__workspace_project__id=project_id,
            ).exists()
        )


class AgentScope(models.Model):
    agent = models.ForeignKey(AgentProfile, on_delete=models.CASCADE, related_name="scopes")
    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="agent_scopes")
    all_projects = models.BooleanField(default=False)
    projects = models.ManyToManyField("db.Project", blank=True, related_name="agent_scopes")

    class Meta:
        db_table = "agent_scopes"
        constraints = [models.UniqueConstraint(fields=["agent", "workspace"], name="unique_agent_workspace")]
