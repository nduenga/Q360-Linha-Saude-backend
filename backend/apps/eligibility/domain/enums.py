"""ART-005 `ck_eligibility_decision`; ART-006 `EligibilityResponse.decision`
and DOC-004 s9 `EligibilityDecision`. Do not add a value not in both."""
from __future__ import annotations

from enum import Enum


class EligibilityDecision(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    WARNING = "WARNING"
    REFERRAL = "REFERRAL"
    HARD_STOP = "HARD_STOP"
    CONFIG_ERROR = "CONFIG_ERROR"
