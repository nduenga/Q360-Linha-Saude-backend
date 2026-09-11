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

from apps.foundation.application.context import CurrentTenantProvider


class TenantScopedManager(models.Manager):
    def get_queryset(self):
        tenant_id = CurrentTenantProvider.require()
        return super().get_queryset().filter(tenant_id=tenant_id.value)


class TenantScopedModel(models.Model):
    objects = TenantScopedManager()
    all_tenants = models.Manager()

    class Meta:
        abstract = True
