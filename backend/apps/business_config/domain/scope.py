"""Âmbito de uma configuração de negócio: geral (seguradora) ou de um produto.

A configuração segue uma cascata **seguradora → produto → plano**:

- **geral**: a chave de sempre (`pricing.factors`), vale para todos os
  produtos da seguradora;
- **produto**: a mesma chave com o id do produto (`pricing.factors@<id>`).
  Quando o produto tem a sua versão publicada e vigente, ela **substitui por
  inteiro** a geral nesse produto; sem ela, o produto herda a geral;
- **plano**: dentro de cada configuração, as linhas com `plan` preenchido só
  valem para esse plano e prevalecem sobre as linhas sem plano.

Só as chaves de `PRODUCT_SCOPED_KEYS` aceitam versão de produto. O que é
política da empresa ou da lei (impostos e encargos, aprovações, renovação,
endossos, documentos, atendimento) fica sempre geral. As chaves
`product.pricing_setup:<id>` (opções, campos e fórmulas) já são só de um
produto e não passam por aqui.
"""
from __future__ import annotations

import uuid
from typing import Any

SEPARATOR = "@"

PRODUCT_SCOPED_KEYS = (
    # Produto e coberturas
    "product.plans",
    "product.coverages",
    "product.capitals_sublimits",
    "product.member_participation",
    "product.waiting_periods",
    "product.age_limits",
    "product.exclusions",
    "product.minimum_premium",
    "network.rules",
    "foreign_coverage.rules",
    # Tarifa
    "pricing.reference_premiums",
    "pricing.factors",
    "pricing.adjustments",
    "pricing.actuarial_model",
    "pricing.formulas",
    "pricing.fractionation",
    # Aceitação e elegibilidade
    "underwriting.acceptance_rules",
    "underwriting.pre_existing_conditions",
    "underwriting.medical_review",
    "group.rules",
    "rules.custom",
)


def product_key(base: str, product_id: Any) -> str:
    return f"{base}{SEPARATOR}{product_id}"


def split_key(key: str) -> tuple[str, str | None]:
    """`pricing.factors@<id>` -> (`pricing.factors`, `<id>`); chave geral -> (chave, None)."""
    if not isinstance(key, str) or SEPARATOR not in key:
        return key, None
    base, _, product_id = key.partition(SEPARATOR)
    return base, product_id


def base_key(key: str) -> str:
    return split_key(key)[0]


def is_product_scoped(key: str) -> bool:
    return split_key(key)[1] is not None


def is_scopable(base: str) -> bool:
    return base in PRODUCT_SCOPED_KEYS


def valid_product_id(raw: str | None) -> bool:
    try:
        uuid.UUID(str(raw))
    except (TypeError, ValueError):
        return False
    return True
