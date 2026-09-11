from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from django.db import transaction
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils import timezone
from rest_framework import serializers
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from plane.api.views.base import BaseAPIView
from plane.api.middleware.api_authentication import APIKeyAuthentication
from plane.db.models import Project, ProjectMember, WorkspaceMember, Issue
from .models import Schedule
from .calendar import occurrence


class ScheduleInput(serializers.Serializer):
    template_issue = serializers.UUIDField(required=False)
    frequency = serializers.ChoiceField(choices=["daily", "weekly", "monthly", "yearly"], required=False)
    interval = serializers.IntegerField(min_value=1, max_value=365, required=False)
    timezone = serializers.CharField(max_length=64, required=False)
    starts_at = serializers.DateTimeField(required=False)
    ends_at = serializers.DateTimeField(required=False, allow_null=True)
    status = serializers.ChoiceField(choices=["active", "paused", "ended"], required=False)

    def validate_timezone(self, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise serializers.ValidationError("Use an IANA timezone such as Europe/Vienna.")
        return value

    def to_internal_value(self, data):
        unknown = set(data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError({key: "Unknown field" for key in unknown})
        return super().to_internal_value(data)


def project_for(user, slug, project_id):
    project = get_object_or_404(Project, pk=project_id, workspace__slug=slug, archived_at__isnull=True)
    if not (
        WorkspaceMember.objects.filter(workspace=project.workspace, member=user, is_active=True, role__gte=15).exists()
        and ProjectMember.objects.filter(project=project, member=user, is_active=True, role__gte=15).exists()
    ):
        raise PermissionDenied("Active workspace and project membership is required.")
    return project


def summary(s):
    return {
        "id": str(s.id),
        "title": s.template["name"],
        "frequency": s.frequency,
        "interval": s.interval,
        "timezone": s.timezone,
        "starts_at": s.starts_at,
        "ends_at": s.ends_at,
        "status": s.status,
        "next_run_at": s.next_run_at,
        "last_run_at": s.last_run_at,
        "last_issue": str(s.last_issue_id) if s.last_issue_id else None,
    }


class ScheduleView(BaseAPIView):
    authentication_classes = [APIKeyAuthentication, SessionAuthentication]

    def get(self, request, slug, project_id, pk=None):
        project = project_for(request.user, slug, project_id)
        rows = Schedule.objects.filter(project=project)
        if pk:
            return Response(summary(get_object_or_404(rows, pk=pk)))
        page = serializers.IntegerField(min_value=0, max_value=1000000)
        offset = page.run_validation(request.query_params.get("offset", 0))
        rows = list(rows.order_by("created_at", "id")[offset : offset + 21])
        return Response(
            {"results": [summary(s) for s in rows[:20]], "next_offset": offset + 20 if len(rows) > 20 else None}
        )

    @transaction.atomic
    def post(self, request, slug, project_id):
        return self.save_schedule(request, slug, project_id)

    @transaction.atomic
    def patch(self, request, slug, project_id, pk):
        return self.save_schedule(request, slug, project_id, pk)

    def save_schedule(self, request, slug, project_id, pk=None):
        project = project_for(request.user, slug, project_id)
        s = (
            get_object_or_404(Schedule.objects.select_for_update(), pk=pk, project=project)
            if pk
            else Schedule(project=project, creator=request.user)
        )
        data = ScheduleInput(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        if not pk:
            for field in ("template_issue", "frequency", "starts_at"):
                if field not in values:
                    raise serializers.ValidationError({field: "Required when creating a schedule."})
        if pk and s.status == "ended":
            raise serializers.ValidationError("An ended schedule cannot be restarted; create a new one.")
        if "template_issue" in values:
            issue = get_object_or_404(
                Issue.issue_objects, pk=values.pop("template_issue"), project=project, is_draft=False
            )
            s.template = {
                "name": issue.name,
                "description_html": issue.description_html,
                "priority": issue.priority,
                "state": str(issue.state_id) if issue.state_id else None,
                "assignees": [str(v) for v in issue.assignees.values_list("id", flat=True)],
                "labels": [str(v) for v in issue.labels.values_list("id", flat=True)],
                "due_after_days": max(0, (issue.target_date - issue.start_date).days)
                if issue.target_date and issue.start_date
                else None,
            }
        timing_changed = bool(set(values) & {"frequency", "interval", "timezone", "starts_at"})
        for key, value in values.items():
            setattr(s, key, value)
        if s.ends_at and s.ends_at < s.starts_at:
            raise serializers.ValidationError({"ends_at": "Must be at or after starts_at."})
        if not pk or timing_changed:
            if s.starts_at < timezone.now():
                raise serializers.ValidationError(
                    {"starts_at": "Choose a future first run when creating or changing timing."}
                )
            if occurrence(s, 0) != s.starts_at:
                raise serializers.ValidationError({"starts_at": "For repeated DST times choose the first occurrence."})
            s.next_run_at = s.starts_at
        if s.status == "ended" or (s.ends_at and s.next_run_at and s.next_run_at > s.ends_at):
            s.status, s.next_run_at = "ended", None
        s.save()
        return Response(summary(s), status=200 if pk else 201)

    @transaction.atomic
    def delete(self, request, slug, project_id, pk):
        project = project_for(request.user, slug, project_id)
        get_object_or_404(Schedule.objects.select_for_update(), pk=pk, project=project).delete()
        return Response(status=204)


@ensure_csrf_cookie
def manager(request):
    return render(request, "recurrence/manager.html")


class CatalogView(BaseAPIView):
    authentication_classes = [APIKeyAuthentication, SessionAuthentication]

    def get(self, request, slug):
        project_id = request.query_params.get("project")
        if project_id:
            project_id = serializers.UUIDField().run_validation(project_id)
            project = project_for(request.user, slug, project_id)
            rows = Issue.issue_objects.filter(
                project=project, name__icontains=request.query_params.get("q", "")[:255]
            ).order_by("-created_at")[:50]
            return Response(
                [{"id": str(i.id), "name": f"{project.identifier}-{i.sequence_id}: {i.name}"} for i in rows]
            )
        ids = ProjectMember.objects.filter(member=request.user, is_active=True, role__gte=15).values("project_id")
        rows = Project.objects.filter(
            pk__in=ids,
            workspace__slug=slug,
            archived_at__isnull=True,
            workspace__workspace_member__member=request.user,
            workspace__workspace_member__is_active=True,
            workspace__workspace_member__role__gte=15,
        ).order_by("name")[:100]
        return Response([{"id": str(p.id), "name": p.name} for p in rows])
