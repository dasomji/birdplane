"""Only called after verify_settings has checked the destination."""

import json
import os
from pathlib import Path

from django.conf import settings
from django.utils import timezone
from plane.db.models import (
    APIToken,
    Profile,
    Project,
    ProjectMember,
    User,
    Workspace,
    WorkspaceMember,
)
from plane.license.models import Instance, InstanceAdmin

if settings.SETTINGS_MODULE != "plane.settings.kitchen_verify":
    raise RuntimeError("Seeding requires disposable test settings")
if User.objects.exists():
    raise RuntimeError("Seeding requires an empty disposable database")
admin = User.objects.create_user(
    username="admin",
    email="admin@test.com",
    password="password",
    first_name="Admin",
    is_password_autoset=False,
)
user = User.objects.create_user(
    username="user",
    email="user@test.com",
    password="password",
    first_name="User",
    is_password_autoset=False,
)
workspace = Workspace.objects.create(
    name="Kitchen Verification", slug="kitchen-test", owner=admin
)
for member, role in [(admin, 20), (user, 15)]:
    WorkspaceMember.objects.create(workspace=workspace, member=member, role=role)
    Profile.objects.update_or_create(
        user=member,
        defaults={
            "is_onboarded": True,
            "is_tour_completed": True,
            "last_workspace_id": workspace.id,
        },
    )
instance = Instance.objects.create(
    instance_name="Disposable verification",
    instance_id=os.environ["VERIFY_PROJECT"],
    current_version="1.4.3",
    last_checked_at=timezone.now(),
    is_setup_done=True,
    is_test=True,
    is_telemetry_enabled=False,
    is_support_required=False,
)
InstanceAdmin.objects.create(instance=instance, user=admin)
project = Project.objects.create(
    workspace=workspace,
    name="Joined project",
    identifier="JOIN",
    network=0,
    created_by=admin,
)
for member, role in [(admin, 20), (user, 15)]:
    ProjectMember.objects.create(project=project, member=member, role=role)
tokens = {
    role: APIToken.objects.create(
        user=member, workspace=workspace, allowed_rate_limit="600/min"
    ).token
    for role, member in [("admin", admin), ("user", user)]
}
path = Path("/runtime/seed.json")
path.write_text(json.dumps({**tokens, "joinedProject": str(project.id)}))
path.chmod(0o600)
print("Seeded D12 accounts, workspace and one private joined project (tokens withheld)")
