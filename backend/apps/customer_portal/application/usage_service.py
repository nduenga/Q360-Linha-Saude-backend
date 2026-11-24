"""Métricas de uso da app (roadmap_mobile.md, Fase 4): ativações, entradas,
ecrãs mais usados e pushes abertos. Só guarda o nome do evento e o ecrã — nada
de dados pessoais nem de saúde. Os crashes vão para o Sentry, não para aqui."""
from __future__ import annotations

import datetime
import re

from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.customer_portal.infrastructure.models import CustomerDeviceSession, PortalUsageEvent
from apps.foundation.application.context import CurrentTenantProvider

EVENT_NAMES = ("APP_OPEN", "SCREEN_VIEW", "PUSH_OPENED", "BIOMETRIC_UNLOCK", "CARD_OFFLINE_VIEW", "DOCUMENT_UPLOAD")
_SCREEN = re.compile(r"^[A-Za-z0-9_/\-\[\]\.]{0,80}$")
MAX_BATCH = 50


def record(*, account_id, events: list[dict], platform: str, app_version: str) -> int:
    """Grava os eventos válidos do lote; os inválidos são ignorados em silêncio."""
    tenant_id = CurrentTenantProvider.require().value
    rows = [
        PortalUsageEvent(
            tenant_id=tenant_id, customer_account_id=account_id, name=e["name"], screen=e.get("screen", ""),
            platform=platform, app_version=app_version[:30],
        )
        for e in events[:MAX_BATCH]
        if e.get("name") in EVENT_NAMES and _SCREEN.match(e.get("screen", ""))
    ]
    PortalUsageEvent.objects.bulk_create(rows)
    return len(rows)


def metrics(*, days: int = 30) -> dict:
    since = timezone.now() - datetime.timedelta(days=days)
    events = PortalUsageEvent.objects.filter(created_at__gte=since)
    sessions = CustomerDeviceSession.objects.all()
    live = sessions.filter(revoked_at__isnull=True, expires_at__gt=timezone.now())
    return {
        "days": days,
        "activations": sessions.values("customer_account_id").distinct().count(),
        "activeDevices": live.count(),
        "logins": sessions.filter(created_at__gte=since).count(),
        "devicesByPlatform": list(live.values("platform").annotate(count=Count("id")).order_by("-count")),
        "appVersions": list(
            live.exclude(app_version="").values("app_version").annotate(count=Count("id")).order_by("-count")
        ),
        "events": list(events.values("name").annotate(count=Count("id")).order_by("-count")),
        "topScreens": list(
            events.filter(name="SCREEN_VIEW").exclude(screen="").values("screen")
            .annotate(count=Count("id")).order_by("-count")[:10]
        ),
        "opensByDay": [
            {"date": row["day"].isoformat(), "count": row["count"]}
            for row in events.filter(name="APP_OPEN").annotate(day=TruncDate("created_at")).values("day")
            .annotate(count=Count("id")).order_by("day")
        ],
    }
