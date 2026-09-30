"""Validation and normalisation rules for Angolan AGT NIFs.

The format check is deliberately limited to the published structural rules:
it does not assert that a NIF belongs to a real person or organisation. That
requires a separate integration with the AGT taxpayer service.
"""
from __future__ import annotations

import re


COLLECTIVE_NIF_PATTERN = re.compile(r"^\d{10}$")
SINGULAR_NIF_PATTERN = re.compile(r"^\d{9}[A-Z]{2}\d{3}$")
NIF_FORMAT_ERROR = (
    "O NIF deve ter 10 dígitos (empresa) ou 14 caracteres no formato "
    "999999999AA999 (cidadão)."
)


class NifFormatError(ValueError):
    """The supplied value does not have a valid AGT NIF structure."""


def normalise_nif(value: str) -> str:
    """Remove all whitespace and store the NIF in upper case."""
    return "".join(value.split()).upper()


def validate_agt_nif(value: str) -> str:
    """Return a canonical NIF or raise :class:`NifFormatError`.

    Accepted formats are 10 numeric characters for collective taxpayers and
    nine digits, two letters and three digits for singular taxpayers.
    """
    nif = normalise_nif(value)

    if COLLECTIVE_NIF_PATTERN.fullmatch(nif) or SINGULAR_NIF_PATTERN.fullmatch(nif):
        return nif

    if nif.isdigit():
        raise NifFormatError(
            f"O NIF numérico para empresas deve ter exatamente 10 dígitos. "
            f"Foram introduzidos {len(nif)}."
        )

    raise NifFormatError(NIF_FORMAT_ERROR)
