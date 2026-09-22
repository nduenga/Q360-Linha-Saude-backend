"""ART-005 `ck_eligibility_decision`; ART-006 `EligibilityResponse.decision`
and DOC-004 s9 `EligibilityDecision`. Do not add a value not in both.

The last 3 values (ELIGIBLE_WITH_LOADING, PENDING_DOCUMENT,
PENDING_MEDICAL_BOARD) are a MOTOR_ELEGIBILIDADE.md Fase A addition — see
`apps/eligibility/infrastructure/migrations/0002_angola_category_rules.py`
for the matching `ck_eligibility_decision` widening. None of the three is
a definitive rejection: the frontend maps all of them (and ELIGIBLE) to a
non-red state per MOTOR_ELEGIBILIDADE.md secção 1's table — only
HARD_STOP is "Não Elegível" in red.
"""
from __future__ import annotations

from enum import Enum


class EligibilityDecision(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    WARNING = "WARNING"
    REFERRAL = "REFERRAL"
    HARD_STOP = "HARD_STOP"
    CONFIG_ERROR = "CONFIG_ERROR"
    ELIGIBLE_WITH_LOADING = "ELIGIBLE_WITH_LOADING"
    PENDING_DOCUMENT = "PENDING_DOCUMENT"
    PENDING_MEDICAL_BOARD = "PENDING_MEDICAL_BOARD"
