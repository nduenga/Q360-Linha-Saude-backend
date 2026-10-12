"""Regras puras (sem Django/BD) sobre pessoas seguras de um proponente.

Regras de negócio (2026-10):
  R1. A data de nascimento é obrigatória (e não pode estar no futuro).
  R2. Tem de existir sempre um TITULAR antes de qualquer outra relação.
  R3. Filho(a) vs titular e titular vs ascendente: diferença de idade
      mínima de 13 anos (o filho nunca pode ter a mesma idade ou mais do
      que o pai/mãe).
  R4. Proponente individual: número máximo de beneficiários (dependentes,
      sem contar o titular) configurável pelo GTE
      (parâmetro `client.individual_max_beneficiaries`).
  R5. Proponente individual: um único titular ativo.

As regras R3-R5 só se aplicam a proponentes INDIVIDUAIS: numa empresa há um
titular por colaborador, pelo que "o pai/titular" não é inequívoco.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Iterable

from apps.client.domain.enums import RelationshipCategory
from apps.client.domain.errors import (
    BeneficiaryLimitExceededError,
    DateOfBirthRequiredError,
    DuplicateTitularError,
    GenerationGapError,
    IncoherentDateError,
    TitularRequiredError,
)

MIN_GENERATION_GAP_YEARS = 13


@dataclass(frozen=True, slots=True)
class Person:
    """Uma pessoa segura reduzida ao que as regras precisam."""

    category: str  # RelationshipCategory value
    # None só em registos antigos (anteriores à obrigatoriedade): contam para
    # titular/limite mas ficam fora das regras de idade.
    date_of_birth: datetime.date | None
    label: str = ""


def require_date_of_birth(
    date_of_birth: datetime.date | None, *, today: datetime.date | None = None, who: str = "pessoa segura"
) -> datetime.date:
    """R1."""
    if date_of_birth is None:
        raise DateOfBirthRequiredError(f"A data de nascimento é obrigatória ({who}).")
    if date_of_birth > (today or datetime.date.today()):
        raise IncoherentDateError(f"A data de nascimento {date_of_birth} está no futuro")
    return date_of_birth


def add_years(value: datetime.date, years: int) -> datetime.date:
    try:
        return value.replace(year=value.year + years)
    except ValueError:  # 29 de fevereiro -> 28 de fevereiro
        return value.replace(year=value.year + years, day=28)


def check_generation_gap(
    *, parent_dob: datetime.date, child_dob: datetime.date, parent_label: str, child_label: str
) -> None:
    """R3: `child_dob` tem de ser >= `parent_dob` + 13 anos."""
    if child_dob < add_years(parent_dob, MIN_GENERATION_GAP_YEARS):
        raise GenerationGapError(
            f"{child_label} ({child_dob}) tem de ser pelo menos {MIN_GENERATION_GAP_YEARS} anos mais novo(a) "
            f"do que {parent_label} ({parent_dob}); não pode ter a mesma idade nem ser mais velho(a)."
        )


def validate_household(
    people: Iterable[Person],
    *,
    individual: bool,
    max_beneficiaries: int | None,
) -> None:
    """Valida o conjunto FINAL de pessoas seguras ativas de um proponente.

    Chamado depois de aplicar a alteração pedida à lista atual, por isso
    cobre criar, editar, desativar e importar com a mesma lógica.
    """
    people = list(people)
    titulars = [p for p in people if p.category == RelationshipCategory.TITULAR.value]
    dependents = [p for p in people if p.category != RelationshipCategory.TITULAR.value]

    if dependents and not titulars:  # R2
        raise TitularRequiredError(
            "É obrigatório existir um titular antes de adicionar outras relações "
            "(cônjuge, filho(a), ascendente, outro)."
        )
    if not individual:
        return

    if len(titulars) > 1:  # R5
        raise DuplicateTitularError("Um proponente individual só pode ter um titular ativo.")

    if max_beneficiaries is not None and len(dependents) > max_beneficiaries:  # R4
        raise BeneficiaryLimitExceededError(
            f"Limite de beneficiários excedido: um proponente individual pode ter no máximo "
            f"{max_beneficiaries} beneficiário(s) além do titular (existiriam {len(dependents)})."
        )

    if not titulars:
        return
    titular = titulars[0]
    for person in dependents:  # R3
        if person.date_of_birth is None or titular.date_of_birth is None:
            continue
        if person.category == RelationshipCategory.CHILD.value:
            check_generation_gap(
                parent_dob=titular.date_of_birth,
                child_dob=person.date_of_birth,
                parent_label=f"o titular {titular.label}".strip(),
                child_label=f"O filho(a) {person.label}".strip(),
            )
        elif person.category == RelationshipCategory.ASCENDANT.value:
            check_generation_gap(
                parent_dob=person.date_of_birth,
                child_dob=titular.date_of_birth,
                parent_label=f"o ascendente {person.label}".strip(),
                child_label=f"O titular {titular.label}".strip(),
            )
