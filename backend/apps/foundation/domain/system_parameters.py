"""Definições dos parâmetros globais do sistema (R7 — "distinguir entre
parâmetros operacionais e alterações estruturais").

Categoria (o que o parâmetro é):
  - `OPERATIONAL`: o GTE altera sozinho (com motivo, histórico e rollback).
  - `STRUCTURAL`: fazem parte do motor (fórmulas, política de arredondamento,
    regras como "não há rateio"); só tomam valores que o código já sabe
    executar (`allowed_values`) e só mudam por evolução do sistema.
  - `LEGAL`: valores fixados por lei, iguais para todas as seguradoras
    (imposto do selo, taxa de supervisão ARSEG, maioridade). Cada versão
    tem de indicar a fonte legal (`legal_reference`).
  - `MARKET`: dados de mercado de referência (câmbio do BNA, inflação do
    INE), iguais para todos; o tenant usa-os nas fórmulas ou usa os seus.
  - `LIMIT`: tetos que o fornecedor impõe a todos os tenants sobre a
    configuração de negócio (comissão de mediação, idade dos dependentes
    com prova de estudos). Validados ao submeter e ao aprovar.

Nível (quem manda no valor — camada geral do fornecedor vs. tenant):
  - `PLATFORM_MANDATORY`: o fornecedor (contas da plataforma) define o valor,
    com versões, aprovação por outra pessoa e vigência; o tenant só consulta
    (alterar devolve 403). Estruturais e legais.
  - `PLATFORM_DEFAULT`: o fornecedor define o valor por omissão e pode
    estreitar os limites; cada tenant ajusta-o dentro desses limites. Sem
    ajuste do tenant aplica-se o valor geral. Operacionais.

Os estruturais, legais e tetos são todos PLATFORM_MANDATORY.

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
LEGAL = "LEGAL"
LIMIT = "LIMIT"
MARKET = "MARKET"

PLATFORM_MANDATORY = "PLATFORM_MANDATORY"
PLATFORM_DEFAULT = "PLATFORM_DEFAULT"


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
    # Valores que o motor sabe executar (estruturais). None = qualquer valor válido.
    allowed_values: tuple[Any, ...] | None = None
    # Nome com que o valor em vigor aparece nas fórmulas dos tenants (constante
    # do fornecedor, só leitura). None = não está disponível nas fórmulas.
    formula_name: str | None = None

    @property
    def level(self) -> str:
        return PLATFORM_DEFAULT if self.category == OPERATIONAL else PLATFORM_MANDATORY

    @property
    def tenant_editable(self) -> bool:
        return self.level == PLATFORM_DEFAULT

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
            used_by="Cotações: data «Válida até» de cada cotação nova ou reaberta.",
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
            used_by="Clientes: ao registar ou importar pessoas seguras de um cliente individual.",
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
            used_by="Documentos: ligações para descarregar propostas e outros documentos.",
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
            used_by="Renovações: atualização dos capitais pela inflação médica.",
        ),
        ParameterDefinition(
            code="pricing.rounding_policy",
            value_type="TEXT",
            category=STRUCTURAL,
            default="OD-006-OFFICIAL-HALF-UP-2DP",
            description="Política oficial de arredondamento dos valores monetários (meio para cima, 2 casas).",
            allowed_values=("OD-006-OFFICIAL-HALF-UP-2DP",),
            used_by="Cálculo do prémio: cada parcela é arredondada a 2 casas decimais, meio para cima.",
        ),
        ParameterDefinition(
            code="pricing.formula",
            value_type="TEXT",
            category=STRUCTURAL,
            default="BASE × Π(fatores) + ajustes aditivos, arredondado a cada passo",
            description="Estrutura do cálculo do prémio. Os valores (fatores, tarifas, ajustes) são configurados por cada seguradora; a estrutura é igual para todas.",
            allowed_values=("BASE × Π(fatores) + ajustes aditivos, arredondado a cada passo",),
            used_by="Cálculo do prémio: ordem das etapas (texto informativo; alterá-lo não muda o cálculo).",
        ),
        ParameterDefinition(
            code="capital.pro_rata_rule",
            value_type="BOOLEAN",
            category=STRUCTURAL,
            default=False,
            description="Não há regra de rateio no seguro de saúde: esgotado o capital anual, a seguradora deixa de pagar até à anuidade seguinte.",
            allowed_values=(False,),
        ),
        ParameterDefinition(
            code="tax.stamp_duty_pct",
            value_type="DECIMAL",
            category=LEGAL,
            default="0",
            minimum="0",
            maximum="100",
            unit="%",
            description=(
                "Imposto do selo sobre o prémio comercial líquido. Valor legal, igual para todas as seguradoras; "
                "prevalece sobre o valor do modelo atuarial e sobre o encargo de imposto do selo configurado pela seguradora."
            ),
            used_by="Cálculo do prémio: linha «Imposto do selo». Nas fórmulas: taxa_selo_pct.",
            formula_name="taxa_selo_pct",
        ),
        ParameterDefinition(
            code="tax.arseg_levy_pct",
            value_type="DECIMAL",
            category=LEGAL,
            default="1",
            minimum="0",
            maximum="100",
            unit="%",
            description=(
                "Taxa de supervisão da ARSEG sobre o prémio comercial líquido. Valor legal, igual para todas as "
                "seguradoras; prevalece sobre o valor do modelo atuarial e sobre o encargo da taxa ARSEG configurado pela seguradora."
            ),
            used_by="Cálculo do prémio: linha «Taxa de supervisão ARSEG». Nas fórmulas: taxa_arseg_pct.",
            formula_name="taxa_arseg_pct",
        ),
        ParameterDefinition(
            code="legal.age_of_majority",
            value_type="INTEGER",
            category=LEGAL,
            default=18,
            minimum=14,
            maximum=25,
            unit="anos",
            description=(
                "Maioridade (art. 130.º do Código Civil). Um filho até esta idade é dependente sem prova; acima dela "
                "só com prova de estudos e até ao teto de idade com prova."
            ),
            used_by="Elegibilidade: idade máxima dos filhos sem prova de estudos; nenhuma seguradora a pode exceder.",
            formula_name="maioridade",
        ),
        ParameterDefinition(
            code="market.usd_aoa",
            value_type="DECIMAL",
            category=MARKET,
            default="931.27",
            minimum="0.0001",
            maximum="1000000",
            unit="Kz por USD",
            description=(
                "Câmbio de referência do dólar (BNA). Valor inicial do modelo atuarial (30/06/2026); o fornecedor "
                "atualiza-o."
            ),
            used_by="Fórmulas das seguradoras: cambio_usd_aoa (custos em dólares, evacuação, medicamentos).",
            formula_name="cambio_usd_aoa",
        ),
        ParameterDefinition(
            code="market.inflation_pct",
            value_type="DECIMAL",
            category=MARKET,
            default="10.9",
            minimum="-100",
            maximum="1000",
            unit="%",
            description=(
                "Inflação geral anual de referência (INE). Valor inicial do modelo atuarial (30/06/2026); o "
                "fornecedor atualiza-o."
            ),
            used_by="Fórmulas das seguradoras: inflacao_geral_pct (indexação, renovações).",
            formula_name="inflacao_geral_pct",
        ),
        ParameterDefinition(
            code="limits.dependent_max_age_with_proof",
            value_type="INTEGER",
            category=LIMIT,
            default=27,
            minimum=18,
            maximum=35,
            unit="anos",
            description=(
                "Idade máxima de um filho dependente com prova de estudos que qualquer seguradora pode aceitar "
                "(inclui exceções corporativas)."
            ),
            used_by="Elegibilidade: teto da idade dos filhos com prova de estudos, também nas exceções de empresas.",
        ),
        ParameterDefinition(
            code="limits.max_acquisition_commission_pct",
            value_type="DECIMAL",
            category=LIMIT,
            default="100",
            minimum="0",
            maximum="100",
            unit="%",
            description=(
                "Comissão de mediação máxima que uma seguradora pode carregar no prémio. 100 % significa que ainda "
                "não há teto (até haver norma que o fixe)."
            ),
            used_by="Modelo atuarial: comissão de mediação de cada segmento (verificada ao submeter e ao aprovar).",
        ),
    )
}

# Constantes do fornecedor disponíveis nas fórmulas: nome na fórmula -> código.
PLATFORM_CONSTANTS: dict[str, str] = {d.formula_name: d.code for d in DEFINITIONS.values() if d.formula_name}

# Códigos de encargo que correspondem a impostos legais (a taxa vem sempre da
# camada geral; o tenant não a define).
LEGAL_TAX_CODES: dict[str, str] = {
    "STAMP_DUTY": "tax.stamp_duty_pct",
    "STAMP-DUTY": "tax.stamp_duty_pct",
    "IMPOSTO_SELO": "tax.stamp_duty_pct",
    "ARSEG": "tax.arseg_levy_pct",
    "ARSEG_LEVY": "tax.arseg_levy_pct",
    "ARSEG-LEVY": "tax.arseg_levy_pct",
}


def validate_platform_value(definition: ParameterDefinition, raw: Any) -> Any:
    """Validation for a value set by the platform: the definition's hard
    limits plus, for structural parameters, the values the engine executes."""
    clean = validate_value(definition, raw)
    if definition.allowed_values is not None and clean not in definition.allowed_values:
        raise InvalidSystemParameterError(
            f"{definition.code} só aceita os valores que o motor sabe executar: "
            + ", ".join(repr(v) for v in definition.allowed_values)
            + ". Outro valor exige uma nova versão do sistema."
        )
    return clean


def validate_limits(definition: ParameterDefinition, minimum: Any, maximum: Any) -> tuple[Any, Any]:
    """Limits the platform imposes on tenants (PLATFORM_DEFAULT): numeric,
    inside the definition's hard limits, minimum <= maximum."""
    if definition.value_type not in {"INTEGER", "DECIMAL"}:
        if minimum is not None or maximum is not None:
            raise InvalidSystemParameterError(f"{definition.code} não é numérico: não aceita limites")
        return None, None
    lo = validate_value(definition, minimum) if minimum is not None else definition.minimum
    hi = validate_value(definition, maximum) if maximum is not None else definition.maximum
    if lo is not None and hi is not None and Decimal(str(lo)) > Decimal(str(hi)):
        raise InvalidSystemParameterError(f"{definition.code}: o mínimo não pode ser maior do que o máximo")
    return lo, hi


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
