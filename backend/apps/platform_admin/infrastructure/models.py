from __future__ import annotations
import uuid
from django.db import models

class PlatformAdmin(models.Model):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    STATUS_CHOICES = [(ACTIVE, "Active"), (DISABLED, "Disabled")]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(max_length=320, unique=True)
    name = models.CharField(max_length=200)
    password_hash = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=ACTIVE)
    failed_login_attempts = models.IntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    last_login_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        managed = False
        db_table = "platform_admin"

class PlatformAuditEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor_id = models.CharField(max_length=200)
    action = models.CharField(max_length=120)
    entity_type = models.CharField(max_length=120)
    entity_id = models.CharField(max_length=200, null=True, blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True)
    correlation_id = models.CharField(max_length=100, null=True, blank=True)
    metadata_json = models.JSONField(default=dict)
    class Meta:
        managed = False
        db_table = "platform_audit_event"
