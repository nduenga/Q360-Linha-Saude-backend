"""Dev-only convenience: create a Tenant row to test against locally.

Not an ART-006 endpoint and not part of any Sprint story - tenants are
provisioned by whatever real onboarding process eventually implements
OD-009's Identity Provider integration. This command exists only so a
developer running the backend without Docker/OIDC has *something* to point
a Bearer token's `tenant_id` claim at (see `issue_dev_token`).
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.foundation.infrastructure.models import Tenant


class Command(BaseCommand):
    help = "Create (or reuse) a local dev Tenant row and print its id."

    def add_arguments(self, parser):
        parser.add_argument("--code", default="dev-tenant")
        parser.add_argument("--name", default="Dev Tenant")

    def handle(self, *args, **options):
        tenant, created = Tenant.objects.get_or_create(
            code=options["code"], defaults={"name": options["name"]}
        )
        verb = "Created" if created else "Reusing existing"
        self.stdout.write(self.style.SUCCESS(f"{verb} tenant '{tenant.code}' -> {tenant.id}"))
