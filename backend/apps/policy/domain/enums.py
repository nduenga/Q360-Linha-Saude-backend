"""Status/type enumerations for the policy module — ROADMAP_APOLICES.md
Fase 2. Not yet backed by an approved artifact (there is no ART-005/
ART-012 equivalent for `apps.policy`, since it postdates ART-005/ART-012):
this project's own new source of truth is `ROADMAP_APOLICES.md` +
`DECISIONS_TAKEN.md#S09-POLICY-001`, the same authority DOC-000 s12
requires for any Change Request against the earlier artifacts.
"""
from __future__ import annotations

from enum import Enum


class PolicyType(str, Enum):
    """Derived from `Proposer.proposer_type` at issuance, never chosen
    independently by the caller."""

    INDIVIDUAL = "INDIVIDUAL"
    GROUP = "GROUP"


class PolicyStatus(str, Enum):
    """ROADMAP_APOLICES.md Fase 2 state machine. No `SUSPENDED` yet — that
    is PO-APO-5/Fase 7 (falta de pagamento), built once `premium_
    installment`/`premium_default_notice` exist (Fase 2 continuation)."""

    PENDING_FIRST_PREMIUM = "PENDING_FIRST_PREMIUM"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    TERMINATED = "TERMINATED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    RENEWED = "RENEWED"


class PolicyMemberStatus(str, Enum):
    """PO-APO-2: a member's own eligibility outcome never blocks the rest
    of the policy — it only ever affects this member's own row."""

    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    EXCLUDED = "EXCLUDED"
    REJECTED = "REJECTED"


class SignatureMethod(str, Enum):
    """`DIGITAL` is reserved (ROADMAP_APOLICES.md OD-APO-001) — no
    qualified e-signature integration exists, so no code path may set it
    yet; kept here so the column's shape is stable when that integration
    lands."""

    PRESENCIAL = "PRESENCIAL"
    DIGITAL = "DIGITAL"


class SignatoryCapacity(str, Enum):
    TOMADOR = "TOMADOR"
    REPRESENTANTE_LEGAL = "REPRESENTANTE_LEGAL"
    PROCURADOR = "PROCURADOR"


class SignatoryDocumentType(str, Enum):
    """Same accepted set as `apps.eligibility`'s Angola `compliance.
    acceptedDocumentTypes` default (MOTOR_ELEGIBILIDADE.md) — BCFT-aligned
    (Lei n.º 5/20)."""

    BI = "BI"
    CARTAO_RESIDENTE = "CARTAO_RESIDENTE"
    PASSAPORTE_VISTO_TRABALHO = "PASSAPORTE_VISTO_TRABALHO"


class EndorsementType(str, Enum):
    """ROADMAP_APOLICES.md Fase 4 — not yet acted on by any use case in
    Fase 2, but the closed set is declared here so the table's CHECK
    constraint has a fixed vocabulary from the start."""

    ACTIVATE_MEMBER = "ACTIVATE_MEMBER"
    ADD_MEMBER = "ADD_MEMBER"
    EXCLUDE_MEMBER = "EXCLUDE_MEMBER"
    CANCEL_POLICY = "CANCEL_POLICY"
