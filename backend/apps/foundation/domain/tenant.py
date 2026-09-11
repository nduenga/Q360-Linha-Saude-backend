"""Tenant identity value object.

Source: Q360-MVP-DOC-004 s6.1 ("TenantId | Identidade do tenant") and the
physical column `q360.tenant.id` (ART-005 / ART-012 V002).
"""
from __future__ import annotations

import dataclasses
import uuid


@dataclasses.dataclass(frozen=True, slots=True)
class TenantId:
    value: uuid.UUID

    @classmethod
    def parse(cls, raw: str | uuid.UUID) -> "TenantId":
        return cls(raw if isinstance(raw, uuid.UUID) else uuid.UUID(str(raw)))

    def __str__(self) -> str:
        return str(self.value)
