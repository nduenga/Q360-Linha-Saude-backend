"""Dev-only convenience: mint a Bearer JWT without a running OIDC provider.

Uses the same `OIDC_STATIC_VERIFICATION_KEY` escape hatch already wired
into `JwtActorAdapter` (apps/foundation/infrastructure/jwt_actor_adapter.py)
for tests - this command just lets a human get an equivalent token to
paste into curl/Postman/the frontend while manually exercising the API
locally. `config/settings/production.py` refuses to start at all if this
key is set, so this command is structurally unusable in production.

Not an ART-006 endpoint, not a replacement for OD-009 (real IdP
integration) - purely local tooling.
"""
from __future__ import annotations

import time

import jwt
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.foundation.domain.permissions import Role
from apps.foundation.domain.scopes import Scope
from apps.foundation.infrastructure.models import Tenant


class Command(BaseCommand):
    help = "Mint a local dev Bearer token signed with OIDC_STATIC_VERIFICATION_KEY."

    def add_arguments(self, parser):
        parser.add_argument("--tenant-code", default="dev-tenant")
        parser.add_argument("--actor-id", default="dev-user")
        parser.add_argument(
            "--roles",
            default="ADMIN",
            help=f"Comma-separated, from: {', '.join(r.value for r in Role)}",
        )
        parser.add_argument(
            "--scopes",
            default="q360.read q360.write q360.admin q360.approve q360.audit",
            help=f"Space-separated, from: {', '.join(s.value for s in Scope)}",
        )
        parser.add_argument("--ttl-seconds", type=int, default=3600)

    def handle(self, *args, **options):
        if not settings.OIDC_STATIC_VERIFICATION_KEY:
            raise CommandError(
                "OIDC_STATIC_VERIFICATION_KEY is not set. Add it to your .env "
                "(dev-only - see .env.example) before minting local tokens."
            )
        if "HS256" not in settings.OIDC_ALGORITHMS:
            raise CommandError(
                "OIDC_ALGORITHMS must include HS256 to verify a token signed "
                "with a static shared secret (it currently only lists "
                f"{settings.OIDC_ALGORITHMS})."
            )

        try:
            tenant = Tenant.objects.get(code=options["tenant_code"])
        except Tenant.DoesNotExist as exc:
            raise CommandError(
                f"No tenant with code '{options['tenant_code']}'. Run "
                f"`manage.py seed_dev_tenant --code {options['tenant_code']}` first."
            ) from exc

        claims = {
            "sub": options["actor_id"],
            settings.OIDC_TENANT_CLAIM: str(tenant.id),
            settings.OIDC_ROLES_CLAIM: [r.strip() for r in options["roles"].split(",") if r.strip()],
            settings.OIDC_SCOPE_CLAIM: options["scopes"],
            "exp": int(time.time()) + options["ttl_seconds"],
        }
        token = jwt.encode(claims, settings.OIDC_STATIC_VERIFICATION_KEY, algorithm="HS256")
        self.stdout.write(token)
