"""Reativa as seguradoras suspensas cuja data de reativação já chegou
(faz parte de `run_daily_jobs`). Idempotente."""
from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.platform_admin.application.tenant_service import reactivate_due_tenants


class Command(BaseCommand):
    help = "Reativa as seguradoras com a suspensão terminada."

    def handle(self, *args, **options):
        codes = reactivate_due_tenants()
        self.stdout.write(f"Seguradoras reativadas: {', '.join(codes) if codes else 'nenhuma'}.")
