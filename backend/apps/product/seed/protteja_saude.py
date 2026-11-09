"""Gama Seguro de Saúde Protteja — valores tirados das propostas comerciais de
exemplo (`Protteja_Propostas_Saude_v2`, 07.11.2026).

**Provisório.** As propostas são simulações ilustrativas: o próprio documento
avisa que capitais, comparticipações e prémios são fictícios e não vinculativos.
Antes de produção, substitua estes valores pela Tabela de Benefícios, pelas
Condições Particulares e pela tarifa oficiais da Protteja. O comando
`seed_protteja_products` lê só este ficheiro, por isso basta corrigir aqui.

O que as propostas NÃO dão e por isso não se inventa:
  - prémios individuais acima dos 50 anos (as propostas só mostram os escalões
    0–17, 18–35 e 36–50; a adesão vai até aos 65): quem tenha 51–65 anos fica
    sem tarifa e o cálculo recusa, em vez de usar um valor inventado;
  - descontos de grupo até 100 pessoas (só se conhece o de mais de 100).

Erro encontrado no exemplo Business Individual: 5% de 785.000 Kz são
39.250 Kz (total 745.750 Kz), não os 39.500 Kz (745.500 Kz) impressos.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

SOURCE = "Propostas comerciais Protteja Saúde v2 (07.11.2026) — valores de exemplo, por confirmar"
CURRENCY = "AOA"

INDIVIDUAL_PRODUCT = {
    "code": "PROTTEJA-SAUDE-IND",
    "name": "Seguro de Saúde Protteja — Individual e Familiar",
    "description": "Seguro Individual com inclusão obrigatória de todo o Agregado Familiar (Art. 3.º e 13.º).",
}
GROUP_PRODUCT = {
    "code": "PROTTEJA-SAUDE-GRP",
    "name": "Seguro de Saúde Protteja — Grupo",
    "description": "Seguro de Grupo, não contributivo, Apólice Aberta, para colaboradores e Agregado Familiar.",
}

# Níveis da gama: código, nome, descrição curta, âmbito territorial.
LEVELS: list[dict[str, Any]] = [
    {"key": "BUS", "name": "Business", "level": 1, "positioning": "Essencial",
     "description": "Coberturas base de Hospitalização e Ambulatório com acesso à Rede de Prestadores Protteja.",
     "territory": ["Angola"]},
    {"key": "BPL", "name": "Business Plus", "level": 2, "positioning": "Equilibrado",
     "description": "Mais capital e evacuação médica de emergência.", "territory": ["Angola"]},
    {"key": "PRE", "name": "Premium", "level": 3, "positioning": "Avançado",
     "description": "Condição médica crónica e extensão à África do Sul e Namíbia.",
     "territory": ["Angola", "África do Sul", "Namíbia"]},
    {"key": "PPL", "name": "Premium Plus", "level": 4, "positioning": "Excelência",
     "description": "Comparticipação a 100%, sem co-pagamentos, com acesso a cuidados também em Portugal.",
     "territory": ["Angola", "África do Sul", "Namíbia", "Portugal"]},
]

# Coberturas por nível: (capital, comparticipação %, co-pagamento por consulta, regime).
# None = não disponível nesse nível. Regime: NETWORK, NETWORK_REIMBURSEMENT, REIMBURSEMENT, ASSISTANCE.
_C = tuple
COVERAGES: dict[str, dict[str, Any]] = {
    # Hospitalização — BASE · CE B: internamento, honorários, MCDT, quimio e radioterapia.
    "HOSPITALIZATION": {"inclusion": "INCLUDED", "regime": "NETWORK", "waiting": "DISEASE_AND_LISTED_SURGERY",
                        "by_level": {"BUS": (5_000_000, 100, None), "BPL": (10_000_000, 100, None),
                                     "PRE": (25_000_000, 100, None), "PPL": (50_000_000, 100, None)}},
    # Ambulatório — BASE · CE A: consultas, exames, tratamentos.
    "OUTPATIENT": {"inclusion": "INCLUDED", "regime": "NETWORK_REIMBURSEMENT", "waiting": "DISEASE",
                   "by_level": {"BUS": (750_000, 90, 2_500), "BPL": (1_500_000, 90, 2_000),
                                "PRE": (3_000_000, 95, 1_000), "PPL": (6_000_000, 100, None)}},
    # Medicamentos — CE D, rede de farmácias.
    "PHARMACY": {"inclusion": "INCLUDED", "regime": "NETWORK", "waiting": "DISEASE",
                 "by_level": {"BUS": (150_000, 80, None), "BPL": (300_000, 85, None),
                              "PRE": (600_000, 90, None), "PPL": (1_200_000, 100, None)}},
    # Parto, Cesariana e IIG — OPCIONAL.
    "MATERNITY": {"inclusion": "OPTIONAL", "regime": "NETWORK", "waiting": "MATERNITY",
                  "by_level": {"BUS": (400_000, 100, None), "BPL": (750_000, 100, None),
                               "PRE": (1_500_000, 100, None), "PPL": (3_000_000, 100, None)}},
    # Estomatologia — CE C.
    "DENTAL": {"inclusion": "INCLUDED", "regime": "NETWORK", "waiting": "DENTAL",
               "by_level": {"BUS": (100_000, 80, 2_500), "BPL": (200_000, 85, 2_000),
                            "PRE": (400_000, 90, 1_000), "PPL": (750_000, 100, None)}},
    # Óculos, Próteses e Ortóteses — CE E, um só capital, por reembolso.
    "OPTICAL": {"inclusion": "INCLUDED", "regime": "REIMBURSEMENT", "waiting": "DISEASE",
                "notes": "Inclui óculos, próteses e ortóteses externas, com um capital comum.",
                "by_level": {"BUS": (50_000, 100, None), "BPL": (100_000, 100, None),
                             "PRE": (150_000, 100, None), "PPL": (250_000, 100, None)}},
    # Evacuação Médica de Emergência — OPCIONAL, a partir do Business Plus.
    "MEDICAL_EVACUATION": {"inclusion": "OPTIONAL", "regime": "ASSISTANCE", "waiting": "DISEASE",
                           "by_level": {"BUS": None, "BPL": (1_500_000, 100, None),
                                        "PRE": (10_000_000, 100, None), "PPL": (25_000_000, 100, None)}},
    # Condição Médica Crónica — OPCIONAL, a partir do Premium.
    "CHRONIC_CONDITION": {"inclusion": "OPTIONAL", "regime": "NETWORK", "waiting": "DISEASE",
                          "by_level": {"BUS": None, "BPL": None,
                                       "PRE": (750_000, 100, None), "PPL": (1_500_000, 100, None)}},
    # Despesas de Funeral — OPCIONAL, por reembolso.
    "FUNERAL_EXPENSES": {"inclusion": "OPTIONAL", "regime": "REIMBURSEMENT", "waiting": "DISEASE",
                         "capital_kind": "FIXED_AMOUNT",
                         "by_level": {"BUS": (250_000, 100, None), "BPL": (400_000, 100, None),
                                      "PRE": (600_000, 100, None), "PPL": (1_000_000, 100, None)}},
}

# Art. 21.º — carências em dias; acidente ou doença súbita com internamento: sem carência.
WAITING_DAYS = {
    "DISEASE": {"days": 30},
    "DENTAL": {"days": 60},
    "MATERNITY": {"days": 365},
    # Hérnias, varizes, vesícula, cataratas, ORL (Art. 21.º, n.º 4): 365 dias.
    "DISEASE_AND_LISTED_SURGERY": {"days": 30, "scheduledSurgery": 365},
}

# Prémio anual por pessoa (Kz). Individual: por escalão etário; Grupo: por categoria.
INDIVIDUAL_PREMIUMS: dict[str, list[tuple[int, int, int]]] = {
    "BUS": [(0, 17, 145_000), (18, 35, 210_000), (36, 50, 285_000)],
    "BPL": [(0, 17, 260_000), (18, 35, 380_000), (36, 50, 510_000)],
    "PRE": [(0, 17, 520_000), (18, 35, 760_000), (36, 50, 1_020_000)],
    "PPL": [(0, 17, 980_000), (18, 35, 1_420_000), (36, 50, 1_900_000)],
}
# Grupo: titulares e cônjuges pagam o mesmo; filhos (até 18, ou 24 se estudantes) menos.
# A tarifa tem uma linha «filho 0–24» que prevalece sobre a de adulto; o comprovativo
# de estudante para os 18–24 anos é verificado na elegibilidade, não na tarifa.
GROUP_PREMIUMS: dict[str, dict[str, int]] = {
    "BUS": {"adult": 247_500, "child": 145_000},
    "BPL": {"adult": 445_000, "child": 260_000},
    "PRE": {"adult": 890_000, "child": 520_000},
    "PPL": {"adult": 1_660_000, "child": 980_000},
}
MAX_ENTRY_AGE = 65

FAMILY_DISCOUNT = {"min_members": 3, "percent": "5"}
GROUP_DISCOUNT = {"more_than": 100, "percent": "12"}
GROUP_MIN_INSURED = 10
FRACTIONATION = {"ANUAL": "0", "SEMESTRAL": "0.03", "TRIMESTRAL": "0.05", "MENSAL": "0.07"}

PRIOR_AUTHORIZATION_NOTE = "Exigida para TAC, ressonância e actos acima do equivalente a USD 200; resposta em 24 h úteis (Art. 29.º)."
REIMBURSEMENT_NOTE = "Fora da Rede, reembolso em Kwanzas em 30 dias após entrega da documentação (Art. 30.º)."


def plan_code(level_key: str, group: bool) -> str:
    return f"PROTTEJA-{level_key}-{'GRP' if group else 'IND'}"


def _participation(regime: str, pct: int, copay: int | None) -> dict[str, Any]:
    network: dict[str, Any] = {"type": "COPAY_FIXED", "copayAmount": str(copay)} if copay else {"type": "NONE"}
    reimbursement = {"type": "COINSURANCE", "insurerPct": str(pct)}
    if regime in ("NETWORK", "ASSISTANCE"):
        return {"NETWORK": network}
    if regime == "REIMBURSEMENT":
        return {"REIMBURSEMENT": reimbursement}
    return {"NETWORK": network, "REIMBURSEMENT": reimbursement}


def coverage_config(code: str, level_key: str) -> dict[str, Any] | None:
    spec = COVERAGES[code]
    values = spec["by_level"][level_key]
    if values is None:
        return None
    capital, pct, copay = values
    waiting = WAITING_DAYS[spec["waiting"]]
    limits = [{"kind": spec.get("capital_kind", "ANNUAL_PER_PERSON"), "amount": str(capital)}]
    if pct < 100:
        limits.append({"kind": "COINSURANCE_PCT", "pct": str(pct)})
    config: dict[str, Any] = {
        "inclusion": spec["inclusion"],
        "currency": CURRENCY,
        "limits": limits,
        "participation": _participation(spec["regime"], pct, copay),
        "waitingDays": {
            "individual": waiting["days"], "group": waiting["days"], "accidentWaived": True,
            **({"scheduledSurgery": waiting["scheduledSurgery"]} if "scheduledSurgery" in waiting else {}),
        },
        "indicative": True,
    }
    if code == "MEDICAL_EVACUATION":
        config["requiresPriorApproval"] = True
        config["destinations"] = [t for t in _level(level_key)["territory"] if t != "Angola"] or ["A definir"]
    if spec.get("notes"):
        config["notes"] = spec["notes"]
    return config


def _level(level_key: str) -> dict[str, Any]:
    return next(level for level in LEVELS if level["key"] == level_key)


def plan_settings(level_key: str, group: bool) -> dict[str, Any]:
    level = _level(level_key)
    territory = ", ".join(level["territory"])
    common: dict[str, Any] = {
        "tier": "CUSTOM",
        "level": level["level"],
        "accessSystem": "MIXED",
        "currency": CURRENCY,
        "indicative": True,
        "source": SOURCE,
        "entryAge": {"min": 0, "max": MAX_ENTRY_AGE},
        # Art. 22.º: as garantias cessam aos 65 anos (titular e cônjuge).
        "permanenceAge": {"max": 65},
        "priorAuthorization": {"internments": False, "highCostExams": True, "scheduledSurgeries": False},
        "waitingRules": {"accidentWaived": True},
        "preExistingTreatment": {"mode": "SPECIFIC_EXCLUSION"},
        "network": {"regions": ["LUANDA", "PROVINCES"]},
        "notes": (
            f"Nível {level['level']}/4 · {level['positioning']}. Âmbito territorial: {territory}. "
            f"{PRIOR_AUTHORIZATION_NOTE} {REIMBURSEMENT_NOTE}"
        ),
    }
    if group:
        return {
            **common,
            "segment": "GROUP",
            "category": "Colaboradores",
            "clinicalQuestionnaire": {"required": False},
            "group": {
                "minInsured": GROUP_MIN_INSURED,
                "adhesion": "MANDATORY",
                "premiumBasis": "FIXED_PER_PERSON",
                "premiumPayer": "COMPANY",
                "familyExtension": True,
                "monthlyInclusionsExclusions": True,
                "annualPremiumAdjustment": True,
            },
        }
    return {
        **common,
        "segment": "INDIVIDUAL_FAMILY",
        "clinicalQuestionnaire": {"required": True},
        # Art. 1.º: filhos até aos 18, ou até aos 24 se estudantes (com comprovativo).
        "household": {"spouse": True, "dependentChildMaxAge": 24, "childrenMustBeStudents": True},
    }


def plans() -> list[dict[str, Any]]:
    rows = []
    for group in (False, True):
        product = GROUP_PRODUCT if group else INDIVIDUAL_PRODUCT
        for level in LEVELS:
            coverages = [
                {"code": code, "config": config}
                for code in COVERAGES
                if (config := coverage_config(code, level["key"])) is not None
            ]
            rows.append({
                "product": product["code"],
                "code": plan_code(level["key"], group),
                "name": f"{level['name']} {'Grupo' if group else 'Individual'}",
                "description": level["description"],
                "settings": plan_settings(level["key"], group),
                "coverages": coverages,
            })
    return rows


def reference_premiums(group: bool) -> dict[str, Any]:
    rows = []
    for level in LEVELS:
        code = plan_code(level["key"], group)
        if group:
            prices = GROUP_PREMIUMS[level["key"]]
            rows += [
                {"plan": code, "age_from": 0, "age_to": 17, "annual_premium": str(prices["child"])},
                {"plan": code, "age_from": 18, "age_to": MAX_ENTRY_AGE, "annual_premium": str(prices["adult"])},
                {"plan": code, "age_from": 0, "age_to": 24, "relationship": "CHILD", "annual_premium": str(prices["child"])},
            ]
        else:
            rows += [
                {"plan": code, "age_from": lo, "age_to": hi, "annual_premium": str(amount)}
                for lo, hi, amount in INDIVIDUAL_PREMIUMS[level["key"]]
            ]
    return {"currency_code": CURRENCY, "premiums": rows}


def custom_rules(group: bool) -> dict[str, Any]:
    if group:
        rule = {
            "name": f"Desconto comercial de grupo — mais de {GROUP_DISCOUNT['more_than']} pessoas seguras",
            "active": True, "scope": "QUOTE", "field": "members_count", "operator": "GT",
            "value": str(GROUP_DISCOUNT["more_than"]), "field_2": "segment", "operator_2": "EQ", "value_2": "GROUP",
            "action": "DISCOUNT_PERCENT", "amount": GROUP_DISCOUNT["percent"], "order": 10,
            "message": f"Desconto comercial de grupo de {GROUP_DISCOUNT['percent']}%.", "code": "PROTTEJA-GRP-100",
        }
    else:
        rule = {
            "name": f"Desconto comercial — agregado com {FAMILY_DISCOUNT['min_members']} ou mais pessoas",
            "active": True, "scope": "QUOTE", "field": "members_count", "operator": "GTE",
            "value": str(FAMILY_DISCOUNT["min_members"]), "field_2": "segment", "operator_2": "EQ",
            "value_2": "INDIVIDUAL_FAMILY", "action": "DISCOUNT_PERCENT", "amount": FAMILY_DISCOUNT["percent"],
            "order": 10, "message": f"Desconto comercial de {FAMILY_DISCOUNT['percent']}% para o agregado.",
            "code": "PROTTEJA-FAM-3",
        }
    return {"rules": [rule]}


def fractionation() -> dict[str, Any]:
    return {"installments": [{"frequency": f, "loading": v} for f, v in FRACTIONATION.items()]}


def product_configurations(group: bool) -> dict[str, dict[str, Any]]:
    """Configurações de negócio do produto (`<chave>@<id do produto>`)."""
    return {
        "pricing.reference_premiums": reference_premiums(group),
        # Os prémios das propostas já são finais por escalão: sem fatores nem ajustes gerais.
        "pricing.factors": {"factors": []},
        "pricing.adjustments": {"rules": []},
        "pricing.fractionation": fractionation(),
        "rules.custom": custom_rules(group),
    }


# Casos de teste: as propostas de exemplo, que a tarifa tem de reproduzir.
# Idades na data da simulação; total anual depois do desconto.
INDIVIDUAL_EXAMPLE_AGES = [38, 35, 12, 8]
INDIVIDUAL_EXAMPLE_TOTALS = {
    "BUS": Decimal("745750"),  # a proposta imprime 745.500 por erro de conta (ver docstring)
    "BPL": Decimal("1339500"),
    "PRE": Decimal("2679000"),
    "PPL": Decimal("5016000"),
}
