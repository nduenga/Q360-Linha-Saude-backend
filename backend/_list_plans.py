"""List plan codes in tenant."""
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
import django; django.setup()

from apps.foundation.infrastructure.models import Tenant
from apps.foundation.domain.actor import Actor
from apps.foundation.domain.tenant import TenantId
from apps.foundation.domain.permissions import Role, Scope
from apps.foundation.application.context import CurrentActorProvider
from apps.product.infrastructure.models import Plan

t = Tenant.objects.get(code="dev-tenant")
actor = Actor(
    actor_id="cli-list-plans",
    tenant_id=TenantId(t.id),
    roles=frozenset([Role.ADMIN]),
    scopes=frozenset([Scope.READ]),
    actor_type="SYSTEM",
)
tok = CurrentActorProvider.bind(actor)
try:
    for p in Plan.objects.filter(tenant_id=t.id).values("id", "code", "name", "status"):
        print(f"  code={str(p['code']):25s} status={str(p['status']):8s} name={p['name']}")
finally:
    CurrentActorProvider.reset(tok)
