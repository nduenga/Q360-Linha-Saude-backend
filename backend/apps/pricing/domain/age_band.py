"""Cálculo da idade e do escalão etário a partir da data de nascimento."""

from __future__ import annotations

import datetime

from django.utils import timezone


_AGE_BAND_BUCKETS: list[tuple[int | None, str]] = [
    (17, "0-17"),
    (29, "18-29"),
    (39, "30-39"),
    (49, "40-49"),
    (59, "50-59"),
    (69, "60-69"),
    (None, "70+"),
]


def compute_age(date_of_birth: datetime.date) -> int:
    """Calcula a idade atual com base na data de nascimento."""
    today = timezone.localdate()

    age = today.year - date_of_birth.year

    if (today.month, today.day) < (
        date_of_birth.month,
        date_of_birth.day,
    ):
        age -= 1

    return age


def compute_age_band(
    date_of_birth: datetime.date | None,
) -> str | None:
    """Determina o escalão etário sem exigir uma data de referência."""
    if date_of_birth is None:
        return None

    age = compute_age(date_of_birth)

    for max_age, band in _AGE_BAND_BUCKETS:
        if max_age is None or age <= max_age:
            return band

    return None