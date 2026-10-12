"""Validation and normalisation rules for Angolan AGT NIFs.

The format check is deliberately limited to the published structural rules:
it does not assert that a NIF belongs to a real person or organisation. That
requires a separate integration with the AGT taxpayer service.

REGRA DE NEGÓCIO (2026-10): o formato depende do tipo de proponente.
  - INDIVIDUAL   -> exatamente 14 caracteres: 9 dígitos + 2 letras + 3 dígitos
                    (ex.: 123456789LA042). Nem mais, nem menos.
  - ORGANISATION -> exatamente 10 dígitos. Nem mais, nem menos.
"""
from __future__ import annotations

import re


COLLECTIVE_NIF_PATTERN = re.compile(r"^\d{10}$")
SINGULAR_NIF_PATTERN = re.compile(r"^\d{9}[A-Z]{2}\d{3}$")

INDIVIDUAL_NIF_LENGTH = 14
ORGANISATION_NIF_LENGTH = 10

NIF_FORMAT_ERROR = (
    "O NIF deve ter 10 dígitos (empresa) ou 14 caracteres no formato "
    "999999999AA999 (cidadão)."
)
INDIVIDUAL_NIF_ERROR = (
    "O NIF de um proponente individual deve ter exatamente 14 caracteres "
    "no formato 999999999AA999 (9 dígitos, 2 letras e 3 dígitos)."
)
ORGANISATION_NIF_ERROR = "O NIF de uma empresa deve ter exatamente 10 dígitos."


class NifFormatError(ValueError):
    """The supplied value does not have a valid AGT NIF structure."""


def normalise_nif(value: str) -> str:
    """Remove all whitespace and store the NIF in upper case."""
    return "".join(value.split()).upper()


def validate_agt_nif(value: str, proposer_type: str | None = None) -> str:
    """Return a canonical NIF or raise :class:`NifFormatError`.

    `proposer_type` ("INDIVIDUAL" | "ORGANISATION") decides which single
    format is accepted. Without it (legacy callers) either format is
    accepted — new code must always pass the type.
    """
    nif = normalise_nif(value or "")

    if proposer_type == "INDIVIDUAL":
        if len(nif) != INDIVIDUAL_NIF_LENGTH:
            raise NifFormatError(
                f"{INDIVIDUAL_NIF_ERROR} Foram introduzidos {len(nif)} caracteres."
            )
        if not SINGULAR_NIF_PATTERN.fullmatch(nif):
            raise NifFormatError(INDIVIDUAL_NIF_ERROR)
        return nif

    if proposer_type == "ORGANISATION":
        if not nif.isdigit():
            raise NifFormatError(ORGANISATION_NIF_ERROR)
        if len(nif) != ORGANISATION_NIF_LENGTH:
            raise NifFormatError(
                f"{ORGANISATION_NIF_ERROR} Foram introduzidos {len(nif)}."
            )
        return nif

    if COLLECTIVE_NIF_PATTERN.fullmatch(nif) or SINGULAR_NIF_PATTERN.fullmatch(nif):
        return nif

    if nif.isdigit():
        raise NifFormatError(
            f"O NIF numérico para empresas deve ter exatamente 10 dígitos. "
            f"Foram introduzidos {len(nif)}."
        )

    raise NifFormatError(NIF_FORMAT_ERROR)
