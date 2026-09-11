import logging
from datetime import timedelta
from zoneinfo import ZoneInfo
from celery import shared_task
from django.db import transaction
from django.utils import timezone
from plane.db.models import Issue, IssueAssignee, IssueLabel, ProjectMember, WorkspaceMember, State, Label
from .calendar import occurrence, latest_index
from .models import Schedule, Occurrence

logger = logging.getLogger(__name__)


def permitted(schedule):
    return (
        schedule.creator.is_active
        and schedule.project.archived_at is None
        and schedule.project.deleted_at is None
        and WorkspaceMember.objects.filter(
            workspace_id=schedule.project.workspace_id, member=schedule.creator, is_active=True, role__gte=15
        ).exists()
        and ProjectMember.objects.filter(
            project=schedule.project, member=schedule.creator, is_active=True, role__gte=15
        ).exists()
    )


@transaction.atomic
def generate(schedule_id, now=None):
    now = now or timezone.now()
    s = Schedule.objects.select_for_update().get(pk=schedule_id)
    if s.status != "active" or s.next_run_at is None or s.next_run_at > now:
        return None
    if not permitted(s):
        s.status = "paused"
        s.save()
        return None
    cutoff = min(now, s.ends_at) if s.ends_at else now
    index = latest_index(s, cutoff)
    if index < 0:
        return None
    due = occurrence(s, index)
    if due < s.next_run_at:
        s.status, s.next_run_at = "ended", None
        s.save()
        return None
    record, new = Occurrence.objects.get_or_create(schedule=s, scheduled_at=due)
    if new:
        template = s.template
        state = State.objects.filter(project=s.project, pk=template.get("state"), is_triage=False).first()
        if state is None or state.group in ("completed", "cancelled"):
            state = (
                State.objects.filter(project=s.project, group__in=["backlog", "unstarted"], is_triage=False)
                .order_by("sequence")
                .first()
            )
        if state is None:
            raise ValueError("Project needs an open state for recurring tasks")
        date = due.astimezone(ZoneInfo(s.timezone)).date()
        issue = Issue(
            project=s.project,
            workspace_id=s.project.workspace_id,
            name=template["name"],
            description_html=template["description_html"],
            priority=template["priority"],
            state=state,
            start_date=date,
            target_date=date + timedelta(days=template["due_after_days"])
            if template.get("due_after_days") is not None
            else None,
        )
        issue.save(created_by_id=s.creator_id)
        members = ProjectMember.objects.filter(
            project=s.project, member_id__in=template.get("assignees", []), is_active=True
        ).values_list("member_id", flat=True)
        for member in members:
            IssueAssignee.objects.create(
                issue=issue, assignee_id=member, project=s.project, workspace_id=s.project.workspace_id
            )
        for label in Label.objects.filter(project=s.project, pk__in=template.get("labels", [])):
            IssueLabel.objects.create(issue=issue, label=label, project=s.project, workspace_id=s.project.workspace_id)
        record.issue = issue
        record.save()
    s.last_run_at, s.last_issue = due, record.issue
    try:
        s.next_run_at = occurrence(s, index + 1)
    except (OverflowError, ValueError):
        s.next_run_at = None
    if s.next_run_at is None or (s.ends_at and s.next_run_at > s.ends_at):
        s.status, s.next_run_at = "ended", None
    s.save()
    return str(record.issue_id) if record.issue_id else None


@shared_task
def generate_due():
    # Bound each sweep; failures do not prevent other schedules from running.
    ids = (
        Schedule.objects.filter(status="active", next_run_at__lte=timezone.now())
        .order_by("next_run_at")
        .values_list("id", flat=True)[:100]
    )
    for pk in list(ids):
        try:
            generate(pk)
        except Schedule.DoesNotExist:
            pass
        except Exception:
            logger.exception("Recurring schedule %s failed", pk)
