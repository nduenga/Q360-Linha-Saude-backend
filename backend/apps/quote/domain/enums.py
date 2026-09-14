"""ART-005 `ck_quote_status`/`ck_quote_member_status`/`ck_quote_snapshot_type`
(ART-012 V019/V020); ART-006 `Quote.status`; ART-009 "Quote Machine" sheet.
Do not add a value not in both.
"""
from __future__ import annotations

from enum import Enum


class QuoteStatus(str, Enum):
    DRAFT = "DRAFT"
    READY = "READY"
    IN_REVIEW = "IN_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class QuoteMemberStatus(str, Enum):
    INCLUDED = "INCLUDED"
    EXCLUDED = "EXCLUDED"
    REFERRAL = "REFERRAL"


class QuoteSnapshotType(str, Enum):
    PRICING = "PRICING"
    SUBMISSION = "SUBMISSION"
    APPROVAL = "APPROVAL"
    DOCUMENT = "DOCUMENT"


class ReviewTaskStatus(str, Enum):
    """ART-005 `ck_review_status` (ART-012 V022); ART-006 `ReviewTask.status`;
    ART-009 "Review Machine" sheet."""

    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    DECIDED = "DECIDED"
    RETURNED = "RETURNED"


class QuoteDecisionType(str, Enum):
    """ART-005 `ck_quote_decision` (ART-012 V023); ART-006 `DecisionRequest.decision`."""

    APPROVE = "APPROVE"
    REJECT = "REJECT"
    RETURN = "RETURN"
