import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("db", "0122_alter_draftissue_assignees_alter_issue_assignees_and_more")]

    operations = [
        migrations.CreateModel(
            name="AgentProfile",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True, default="")),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="owned_agents",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "assigners",
                    models.ManyToManyField(blank=True, related_name="assignable_agents", to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={"db_table": "agent_profiles", "ordering": ["name", "id"]},
        ),
        migrations.CreateModel(
            name="AgentScope",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("all_projects", models.BooleanField(default=False)),
                (
                    "agent",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="scopes", to="db.agentprofile"
                    ),
                ),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="agent_scopes", to="db.workspace"
                    ),
                ),
                ("projects", models.ManyToManyField(blank=True, related_name="agent_scopes", to="db.project")),
            ],
            options={
                "db_table": "agent_scopes",
                "constraints": [models.UniqueConstraint(fields=("agent", "workspace"), name="unique_agent_workspace")],
            },
        ),
        migrations.AddField(
            model_name="issue",
            name="agent",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="issues",
                to="db.agentprofile",
            ),
        ),
    ]
