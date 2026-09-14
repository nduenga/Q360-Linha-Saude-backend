"""Server-side mirror of the frontend's age-band convention
(`Q360-Linha-Sa-de-frontend/src/domains/pricing/services/ageBand.ts`,
`backend/DECISIONS_TAKEN.md#age-band-buckets`) — needed here too because
Quote pricing (Q360-S6-03) has no client-supplied context at all
(ART-006 `QuotePriceRequest` is just `{recalculate: bool}`), so age bands
must be computed server-side from each member's real `date_of_birth`.
Not a business-approved actuarial banding — see DECISIONS_TAKEN.md.
"""
from __future__ import annotations

import datetime

_AGE_BAND_BUCKETS: list[tuple[int | None, str]] = [
    (17, "0-17"),
    (29, "18-29"),
    (39, "30-39"),
    (49, "40-49"),
    (59, "50-59"),
    (69, "60-69"),
    (None, "70+"),
]


def compute_age(date_of_birth: datetime.date, reference_date: datetime.date) -> int:
    age = reference_date.year - date_of_birth.year
    if (reference_date.month, reference_date.day) < (date_of_birth.month, date_of_birth.day):
        age -= 1
    return age


def compute_age_band(date_of_birth: datetime.date | None, reference_date: datetime.date) -> str | None:
    if date_of_birth is None:
        return None
    age = compute_age(date_of_birth, reference_date)
    for max_age, band in _AGE_BAND_BUCKETS:
        if max_age is None or age <= max_age:
            return band
    return None
