"""Bootstrap convenience: create the first staff account (normally an
ADMIN) directly via the ORM, bypassing the admin-only
`POST /api/v1/admin/staff-accounts` endpoint - that endpoint requires an
already-authenticated ADMIN to call it, so *something* has to create the
first one. Same role as `manage.py seed_dev_tenant`/`issue_dev_token`, just
for this app. Safe to also use afterwards for any account; the admin UI is
just the normal way once at least one ADMIN exists.
"""
from __future__ import annotations

import secrets
import uuid

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError

from apps.foundation.domain.permissions import Role
from apps.foundation.infrastructure.models import Tenant
from apps.staff_accounts.infrastructure.models import StaffAccount, StaffAccountRole


class Command(BaseCommand):
    help = "Create a staff account directly (bootstrap - normally used once, for the first ADMIN)."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--name", required=True)
        parser.add_argument("--tenant-code", default="dev-tenant")
        parser.add_argument(
            "--roles", default="ADMIN", help=f"Comma-separated, from: {', '.join(r.value for r in Role)}"
        )
        parser.add_argument(
            "--password",
            default=None,
            help="Omit to have one generated and printed (never logged elsewhere).",
        )

    def handle(self, *args, **options):
        try:
            tenant = Tenant.objects.get(code=options["tenant_code"])
        except Tenant.DoesNotExist as exc:
            raise CommandError(
                f"No tenant with code '{options['tenant_code']}'. Run "
                f"`manage.py seed_dev_tenant --code {options['tenant_code']}` first."
            ) from exc

        roles = [r.strip() for r in options["roles"].split(",") if r.strip()]
        for role in roles:
            try:
                Role(role)
            except ValueError as exc:
                raise CommandError(f"Unknown role '{role}'. Valid: {', '.join(r.value for r in Role)}") from exc

        if StaffAccount.all_tenants.filter(tenant_id=tenant.id, email__iexact=options["email"]).exists():
            raise CommandError(f"A staff account for '{options['email']}' already exists in tenant '{tenant.code}'.")

        password = options["password"] or secrets.token_urlsafe(12)
        account = StaffAccount.all_tenants.create(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            email=options["email"],
            name=options["name"],
            password_hash=make_password(password),
        )
        StaffAccountRole.all_tenants.bulk_create(
            [
                StaffAccountRole(id=uuid.uuid4(), tenant_id=tenant.id, staff_account_id=account.id, role=role)
                for role in roles
            ]
        )

        self.stdout.write(self.style.SUCCESS(f"Created staff account {account.email} ({account.id}) - roles: {roles}"))
        if not options["password"]:
            self.stdout.write(f"Generated password: {password}")
