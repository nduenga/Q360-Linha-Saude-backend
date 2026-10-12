"""Definições dos parâmetros globais do sistema (R7 — "distinguir entre
parâmetros operacionais e alterações estruturais").

  - `OPERATIONAL`: o GTE altera sozinho (com motivo, histórico e rollback).
  - `STRUCTURAL`: fazem parte do motor (fórmulas, política de arredondamento,
    regras como "não há rateio"); aparecem para consulta mas só mudam por
    evolução do sistema (fornecedor). Tentar alterá-los devolve 403.

Só existem aqui parâmetros que o sistema **efetivamente usa** — nada de
valores decorativos. Cada operacional documenta onde é lido.
"""
from __future__ import annotations

import dataclasses
from decimal import Decimal, InvalidOperation
from typing import Any

from apps.foundation.domain.problem import DomainProblem

OPERATIONAL = "OPERATIONAL"
STRUCTURAL = "STRUCTURAL"


class InvalidSystemParameterError(DomainProblem):
    http_status = 400
    problem_code = "VALIDATION-400"


class StructuralParameterError(DomainProblem):
    http_status = 403
    problem_code = "SEC-403"


@dataclasses.dataclass(frozen=True, slots=True)
class ParameterDefinition:
    code: str
    value_type: str  # INTEGER | DECIMAL | TEXT | BOOLEAN
    category: str
    default: Any
    description: str
    minimum: int | str | None = None
    maximum: int | str | None = None
    unit: str | None = None
    used_by: str | None = None

    def constraints(self) -> dict[str, Any]:
        return {"minimum": self.minimum, "maximum": self.maximum}


DEFINITIONS: dict[str, ParameterDefinition] = {
    d.code: d
    for d in (
        ParameterDefinition(
            code="quote.validity_days",
            value_type="INTEGER",
            category=OPERATIONAL,
            default=30,
            minimum=1,
            maximum=365,
            unit="dias",
            description="Validade por omissão de uma cotação, em dias a partir da data de início.",
            used_by="Cotações: `valid_until` ao criar/alterar a data de início.",
        ),
        ParameterDefinition(
            code="client.individual_max_beneficiaries",
            value_type="INTEGER",
            category=OPERATIONAL,
            default=10,
            minimum=0,
            maximum=100,
            unit="beneficiários",
            description=(
                "Número máximo de beneficiários (dependentes, sem contar o titular) que um proponente "
                "individual pode ter."
            ),
            used_by="Clientes: POST/PUT /members e importação de pessoas seguras (proponente INDIVIDUAL).",
        ),
        ParameterDefinition(
            code="documents.signed_url_ttl_seconds",
            value_type="INTEGER",
            category=OPERATIONAL,
            default=900,
            minimum=60,
            maximum=86400,
            unit="segundos",
            description="Validade das ligações assinadas para descarregar propostas e outros documentos.",
            used_by="Documentos: POST /documents/{id}/signed-url.",
        ),
        ParameterDefinition(
            code="renewal.default_medical_inflation_pct",
            value_type="DECIMAL",
            category=OPERATIONAL,
            default=None,
            minimum="0",
            maximum="1000",
            unit="%",
            description=(
                "Inflação dos custos médicos usada na indexação de capitais de uma renovação quando o plano não "
                "define a sua própria percentagem."
            ),
            used_by="Renovações: POST /quotes/{id}/renewal/indexation.",
        ),
        ParameterDefinition(
            code="pricing.rounding_policy",
            value_type="TEXT",
            category=STRUCTURAL,
            default="OD-006-OFFICIAL-HALF-UP-2DP",
            description="Política oficial de arredondamento dos valores monetários (meio para cima, 2 casas).",
        ),
        ParameterDefinition(
            code="pricing.formula",
            value_type="TEXT",
            category=STRUCTURAL,
            default="BASE × Π(fatores) + ajustes aditivos, arredondado a cada passo",
            description="Estrutura do cálculo do prémio. Os valores (fatores, tarifas, ajustes) são parâmetros do GTE; a estrutura é do motor.",
        ),
        ParameterDefinition(
            code="capital.pro_rata_rule",
            value_type="BOOLEAN",
            category=STRUCTURAL,
            default=False,
            description="Não há regra de rateio no seguro de saúde: esgotado o capital anual, a seguradora deixa de pagar até à anuidade seguinte.",
        ),
    )
}


def validate_value(definition: ParameterDefinition, raw: Any) -> Any:
    """Returns the value normalised for storage (decimals as strings)."""
    vt = definition.value_type
    if vt == "INTEGER":
        if isinstance(raw, bool) or not isinstance(raw, int):
            raise InvalidSystemParameterError(f"{definition.code} tem de ser um número inteiro")
        if definition.minimum is not None and raw < int(definition.minimum):
            raise InvalidSystemParameterError(f"{definition.code} tem de ser maior ou igual a {definition.minimum}")
        if definition.maximum is not None and raw > int(definition.maximum):
            raise InvalidSystemParameterError(f"{definition.code} tem de ser menor ou igual a {definition.maximum}")
        return raw
    if vt == "DECIMAL":
        if isinstance(raw, bool) or not isinstance(raw, (str, int)):
            raise InvalidSystemParameterError(f"{definition.code} tem de ser um decimal escrito como texto")
        try:
            value = Decimal(str(raw))
        except InvalidOperation as exc:
            raise InvalidSystemParameterError(f"{definition.code} não é um decimal válido") from exc
        if not value.is_finite():
            raise InvalidSystemParameterError(f"{definition.code} não é um decimal finito")
        if definition.minimum is not None and value < Decimal(str(definition.minimum)):
            raise InvalidSystemParameterError(f"{definition.code} tem de ser maior ou igual a {definition.minimum}")
        if definition.maximum is not None and value > Decimal(str(definition.maximum)):
            raise InvalidSystemParameterError(f"{definition.code} tem de ser menor ou igual a {definition.maximum}")
        return format(value.normalize(), "f")
    if vt == "BOOLEAN":
        if not isinstance(raw, bool):
            raise InvalidSystemParameterError(f"{definition.code} tem de ser verdadeiro ou falso")
        return raw
    if not isinstance(raw, str) or not raw.strip():
        raise InvalidSystemParameterError(f"{definition.code} tem de ser um texto não vazio")
    return raw.strip()
