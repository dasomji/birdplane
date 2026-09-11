"""Birdplane-owned tables; upstream issue models remain unchanged."""

import uuid
from django.conf import settings
from django.db import models


class Schedule(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey("db.Project", on_delete=models.CASCADE)
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    template = models.JSONField(default=dict)
    frequency = models.CharField(max_length=10)
    interval = models.PositiveIntegerField(default=1)
    timezone = models.CharField(max_length=64, default="UTC")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, default="active")
    next_run_at = models.DateTimeField(null=True, db_index=True)
    last_run_at = models.DateTimeField(null=True)
    last_issue = models.ForeignKey("db.Issue", null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Occurrence(models.Model):
    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE)
    scheduled_at = models.DateTimeField()
    issue = models.ForeignKey("db.Issue", null=True, on_delete=models.SET_NULL)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["schedule", "scheduled_at"], name="birdplane_occurrence_once")]
