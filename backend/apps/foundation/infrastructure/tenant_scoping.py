"""Reusable tenant-scoping primitives for future business models
(Q360-S1-04, DOC-001 s20: "Tenant é uma fronteira de segurança, não apenas
um filtro de UI").

From Sprint 2 onward, every business aggregate model (Product, Quote, ...)
must inherit `TenantScopedModel` so its default manager transparently
filters by the authenticated actor's tenant — callers cannot forget the
filter, and it cannot be bypassed by a client-supplied parameter because the
tenant comes from `CurrentTenantProvider`, which is only ever bound from a
validated JWT (see application/context.py).

`all_tenants` is an explicit escape hatch for system/admin jobs that must
legitimately cross tenants (e.g. platform-level maintenance); it must never
be exposed through a tenant-facing API.
"""
from __future__ import annotations

from django.db import models
from django.utils import timezone

from apps.foundation.application.context import CurrentTenantProvider


class TouchingQuerySet(models.QuerySet):
    """`QuerySet.update()` não passa por `save()`, por isso o `auto_now` de
    `updated_at` não corria: uma cotação submetida ou aprovada ficava com
    `updatedAt` igual a `createdAt`. Aqui o campo é sempre atualizado, a menos
    que quem chama o indique explicitamente."""

    def update(self, **kwargs):
        field = next((f for f in self.model._meta.concrete_fields if f.name == "updated_at"), None)
        if field is not None and getattr(field, "auto_now", False) and "updated_at" not in kwargs:
            kwargs["updated_at"] = timezone.now()
        return super().update(**kwargs)


class TenantScopedManager(models.Manager.from_queryset(TouchingQuerySet)):
    def get_queryset(self):
        tenant_id = CurrentTenantProvider.require()
        return super().get_queryset().filter(tenant_id=tenant_id.value)


class TenantScopedModel(models.Model):
    objects = TenantScopedManager()
    all_tenants = models.Manager.from_queryset(TouchingQuerySet)()

    class Meta:
        abstract = True
