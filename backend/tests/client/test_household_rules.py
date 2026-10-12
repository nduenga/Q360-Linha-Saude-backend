"""Regras puras (sem BD): NIF por tipo, data de nascimento, titular primeiro,
diferença de 13 anos e limite de beneficiários."""
from __future__ import annotations

import datetime

import pytest

from apps.client.domain.errors import (
    BeneficiaryLimitExceededError,
    DateOfBirthRequiredError,
    DuplicateTitularError,
    GenerationGapError,
    IncoherentDateError,
    TitularRequiredError,
)
from apps.client.domain.nif import NifFormatError, validate_agt_nif
from apps.client.domain.rules import Person, require_date_of_birth, validate_household

D = datetime.date


# ---------------------------------------------------------------- NIF
@pytest.mark.parametrize("nif", ["123456789LA042", " 123456789la042 "])
def test_individual_nif_accepts_exactly_14_chars(nif):
    assert validate_agt_nif(nif, "INDIVIDUAL") == "123456789LA042"


@pytest.mark.parametrize(
    "nif", ["5402132186", "123456789LA04", "123456789LA0421", "12345678LA0421", "123456789L1042", "12345678901234"]
)
def test_individual_nif_rejects_anything_else(nif):
    with pytest.raises(NifFormatError):
        validate_agt_nif(nif, "INDIVIDUAL")


def test_organisation_nif_accepts_exactly_10_digits():
    assert validate_agt_nif("5402132186", "ORGANISATION") == "5402132186"


@pytest.mark.parametrize("nif", ["540213218", "54021321860", "123456789LA042", "540213218A"])
def test_organisation_nif_rejects_anything_else(nif):
    with pytest.raises(NifFormatError):
        validate_agt_nif(nif, "ORGANISATION")


# ------------------------------------------------------- data de nascimento
def test_date_of_birth_is_required():
    with pytest.raises(DateOfBirthRequiredError):
        require_date_of_birth(None)


def test_date_of_birth_in_the_future_is_rejected():
    with pytest.raises(IncoherentDateError):
        require_date_of_birth(D(2999, 1, 1), today=D(2026, 10, 12))


# ------------------------------------------------------------- agregado
def _p(category, dob, label=""):
    return Person(category, dob, label)


def test_dependent_without_titular_is_rejected():
    with pytest.raises(TitularRequiredError):
        validate_household([_p("SPOUSE", D(1990, 1, 1))], individual=True, max_beneficiaries=5)


def test_dependent_without_titular_is_rejected_for_organisations_too():
    with pytest.raises(TitularRequiredError):
        validate_household([_p("CHILD", D(2010, 1, 1))], individual=False, max_beneficiaries=None)


def test_titular_alone_is_fine():
    validate_household([_p("TITULAR", D(1990, 1, 1))], individual=True, max_beneficiaries=0)


def test_individual_cannot_have_two_titulars():
    with pytest.raises(DuplicateTitularError):
        validate_household(
            [_p("TITULAR", D(1990, 1, 1)), _p("TITULAR", D(1991, 1, 1))], individual=True, max_beneficiaries=5
        )


def test_organisation_may_have_many_titulars():
    validate_household(
        [_p("TITULAR", D(1990, 1, 1)), _p("TITULAR", D(1991, 1, 1)), _p("CHILD", D(2015, 1, 1))],
        individual=False,
        max_beneficiaries=None,
    )


def test_child_needs_13_years_or_more_than_titular():
    titular = _p("TITULAR", D(2000, 6, 15))
    validate_household([titular, _p("CHILD", D(2013, 6, 15))], individual=True, max_beneficiaries=5)  # exactly 13
    for child_dob in (D(2013, 6, 14), D(2000, 6, 15), D(1995, 1, 1)):  # < 13 anos, igual, mais velho
        with pytest.raises(GenerationGapError):
            validate_household([titular, _p("CHILD", child_dob)], individual=True, max_beneficiaries=5)


def test_titular_needs_13_years_or_more_than_ascendant():
    titular = _p("TITULAR", D(1990, 1, 1))
    validate_household([titular, _p("ASCENDANT", D(1977, 1, 1))], individual=True, max_beneficiaries=5)
    for parent_dob in (D(1977, 1, 2), D(1990, 1, 1), D(1995, 1, 1)):
        with pytest.raises(GenerationGapError):
            validate_household([titular, _p("ASCENDANT", parent_dob)], individual=True, max_beneficiaries=5)


def test_spouse_has_no_age_gap_rule():
    validate_household([_p("TITULAR", D(1990, 1, 1)), _p("SPOUSE", D(1990, 1, 1))], individual=True, max_beneficiaries=5)


def test_leap_day_birth_is_handled():
    validate_household(
        [_p("TITULAR", D(2000, 2, 29)), _p("CHILD", D(2013, 2, 28))], individual=True, max_beneficiaries=5
    )


def test_beneficiary_limit_counts_dependents_not_the_titular():
    titular = _p("TITULAR", D(1980, 1, 1))
    kids = [_p("CHILD", D(2005 + i, 1, 1)) for i in range(3)]
    validate_household([titular, *kids], individual=True, max_beneficiaries=3)
    with pytest.raises(BeneficiaryLimitExceededError):
        validate_household([titular, *kids], individual=True, max_beneficiaries=2)


def test_limit_does_not_apply_to_organisations():
    people = [_p("TITULAR", D(1980, 1, 1))] + [_p("OTHER", D(1990, 1, 1)) for _ in range(20)]
    validate_household(people, individual=False, max_beneficiaries=2)


def test_legacy_members_without_birth_date_are_skipped_by_age_rules():
    validate_household([_p("TITULAR", None), _p("CHILD", D(2000, 1, 1))], individual=True, max_beneficiaries=5)
