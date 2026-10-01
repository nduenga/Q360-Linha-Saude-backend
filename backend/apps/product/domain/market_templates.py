"""Modelos de produto/plano do PDF "Seguro de Saúde — Coberturas e Capitais".

Pontos de partida **editáveis** para o GTE (nunca regra do motor): a matriz
B/O/— por plano, os capitais "Base/Médio/Superior" (Individual) e
"Colaboradores/Quadros/Administração" (Grupo), a participação e as carências
"indicativas" por cobertura, as opções de participação A–E e as definições
de grupo. O PDF avisa que os valores em Kz são indicativos e variam por
seguradora: tudo aqui leva `indicative: true`.

Onde o PDF não dá número (p. ex. capital de Psicologia, nº de serviços de
Assistência 24h, dias do subsídio), **não se inventa**: a configuração fica
sem limite e a validação do plano devolve o aviso correspondente para o GTE
preencher.

Discrepâncias do PDF (documentadas, não escondidas):
  - Medicamentos: a tabela de capitais (p.3) dá 150.000 Kz ao plano Base, mas
    a matriz comparativa (p.6) e a tabela de benefícios (p.9) marcam-no "—"
    (não disponível). Seguiu-se a matriz.
  - Parto: a tabela p.3 mostra o capital por evento (1.000.000 / 2.500.000 =
    cesariana); a tabela p.9 separa parto normal / cesariana. Seguiu-se a p.9.
"""
from __future__ import annotations

from typing import Any

# Colunas da matriz comparativa (PDF p.6-7)
IB, IM, IS, GRP = "INDIVIDUAL_BASE", "INDIVIDUAL_MEDIUM", "INDIVIDUAL_SUPERIOR", "GROUP"

# código -> (Individual Base, Individual Médio, Individual Superior, Grupo); B/O/-
MATRIX: dict[str, tuple[str, str, str, str]] = {
    "HOSPITALIZATION": ("B", "B", "B", "B"),
    "AMBULATORY_SURGERY": ("B", "B", "B", "B"),
    "EMERGENCY": ("B", "B", "B", "B"),
    "OUTPATIENT": ("O", "B", "B", "B"),
    "PHARMACY": ("-", "O", "B", "O"),
    "MATERNITY": ("-", "O", "B", "B"),
    "DENTAL": ("-", "O", "B", "O"),
    "OPTICAL": ("-", "O", "B", "O"),
    "MEDICAL_EVACUATION": ("-", "O", "B", "O"),
    "CRITICAL_ILLNESS": ("O", "O", "B", "O"),
    "DIALYSIS_ONCOLOGY": ("-", "O", "B", "O"),
    "PHYSIOTHERAPY": ("-", "B", "B", "B"),  # B (sublimite) no Médio e no Grupo
    "PSYCHOLOGY_PSYCHIATRY": ("-", "O", "B", "O"),
    "CHECKUP_PREVENTIVE": ("-", "O", "B", "O"),
    "VACCINATION": ("-", "O", "O", "O"),
    "ALTERNATIVE_MEDICINE": ("-", "-", "O", "O"),
    "PROSTHESIS": ("-", "O", "B", "O"),
    "HOSPITAL_DAILY_ALLOWANCE": ("O", "O", "O", "O"),
    "ASSISTANCE_24H": ("B", "B", "B", "O"),
    "SECOND_OPINION": ("-", "O", "B", "O"),
    "PRE_EXISTING_CONDITIONS": ("-", "-", "O", "B"),  # Superior: O com carência; Grupo: B (adesão obrigatória)
    # Só na lista de coberturas do Grupo (PDF p.5-6): opcionais.
    "ENDEMIC_DISEASES": ("-", "-", "-", "O"),
    "OCCUPATIONAL_MEDICINE": ("-", "-", "-", "O"),
}

# Plano-chave -> capitais (PDF p.3, p.5, p.8-9). Valores em Kz, por pessoa/ano
# salvo indicação. `None` = o PDF não indica número.
_ANNUAL = "ANNUAL_PER_PERSON"


def _lim(kind: str, amount: int | None = None, label: str | None = None, **extra: Any) -> dict[str, Any]:
    limit: dict[str, Any] = {"kind": kind}
    if amount is not None:
        limit["amount"] = str(amount)
    if label:
        limit["label"] = label
    limit.update(extra)
    return limit


# CAPITALS[code][plan_key] -> lista de limites. plan_key: BASE/MEDIUM/SUPERIOR/COLAB/QUADROS/ADMIN
CAPITALS: dict[str, dict[str, list[dict[str, Any]]]] = {
    "HOSPITALIZATION": {
        "BASE": [_lim(_ANNUAL, 5_000_000), _lim("PER_ACT_OR_DAY", 30_000, "Quarto por dia (partilhado)"), _lim("SUBLIMIT", 500_000, "Próteses intra-operatórias")],
        "MEDIUM": [_lim(_ANNUAL, 15_000_000), _lim("PER_ACT_OR_DAY", 50_000, "Quarto por dia"), _lim("SUBLIMIT", 1_500_000, "Próteses intra-operatórias")],
        "SUPERIOR": [_lim(_ANNUAL, 40_000_000), _lim("PER_ACT_OR_DAY", 100_000, "Quarto por dia (individual)"), _lim("SUBLIMIT", 4_000_000, "Próteses intra-operatórias")],
        "COLAB": [_lim(_ANNUAL, 10_000_000)],
        "QUADROS": [_lim(_ANNUAL, 25_000_000)],
        "ADMIN": [_lim(_ANNUAL, 60_000_000)],
    },
    "OUTPATIENT": {
        "BASE": [_lim(_ANNUAL, 1_000_000), _lim("PER_ACT_OR_DAY", 15_000, "Por consulta")],
        "MEDIUM": [_lim(_ANNUAL, 3_000_000), _lim("PER_ACT_OR_DAY", 25_000, "Por consulta")],
        "SUPERIOR": [_lim(_ANNUAL, 8_000_000), _lim("PER_ACT_OR_DAY", 40_000, "Por consulta")],
        "COLAB": [_lim(_ANNUAL, 2_000_000)],
        "QUADROS": [_lim(_ANNUAL, 5_000_000)],
        "ADMIN": [_lim(_ANNUAL, 12_000_000)],
    },
    "PHARMACY": {
        "MEDIUM": [_lim(_ANNUAL, 400_000, "Sublimite anual")],
        "SUPERIOR": [_lim(_ANNUAL, 1_000_000, "Sublimite anual")],
        "COLAB": [_lim(_ANNUAL, 300_000, "Sublimite anual")],
        "QUADROS": [_lim(_ANNUAL, 750_000, "Sublimite anual")],
        "ADMIN": [_lim(_ANNUAL, 1_500_000, "Sublimite anual")],
    },
    "MATERNITY": {
        "MEDIUM": [_lim("PER_EVENT", 600_000, "Parto normal"), _lim("PER_EVENT", 1_000_000, "Cesariana")],
        "SUPERIOR": [_lim("PER_EVENT", 1_500_000, "Parto normal"), _lim("PER_EVENT", 2_500_000, "Cesariana")],
        "COLAB": [_lim("PER_EVENT", 800_000, "Parto")],
        "QUADROS": [_lim("PER_EVENT", 1_500_000, "Parto")],
        "ADMIN": [_lim("PER_EVENT", 3_000_000, "Parto")],
    },
    "DENTAL": {
        "MEDIUM": [_lim(_ANNUAL, 250_000)],
        "SUPERIOR": [_lim(_ANNUAL, 750_000)],
        "COLAB": [_lim(_ANNUAL, 200_000)],
        "QUADROS": [_lim(_ANNUAL, 500_000)],
        "ADMIN": [_lim(_ANNUAL, 1_000_000)],
    },
    "OPTICAL": {
        "MEDIUM": [_lim(_ANNUAL, 100_000)],
        "SUPERIOR": [_lim(_ANNUAL, 300_000)],
        "COLAB": [_lim(_ANNUAL, 80_000)],
        "QUADROS": [_lim(_ANNUAL, 200_000)],
        "ADMIN": [_lim(_ANNUAL, 400_000)],
    },
    "MEDICAL_EVACUATION": {
        "MEDIUM": [_lim(_ANNUAL, 20_000_000)],
        "SUPERIOR": [_lim(_ANNUAL, 100_000_000)],
        "QUADROS": [_lim(_ANNUAL, 30_000_000)],
        "ADMIN": [_lim(_ANNUAL, 150_000_000)],
    },
    "CRITICAL_ILLNESS": {
        "BASE": [_lim("FIXED_AMOUNT", 5_000_000)],
        "MEDIUM": [_lim("FIXED_AMOUNT", 10_000_000)],
        "SUPERIOR": [_lim("FIXED_AMOUNT", 20_000_000)],
    },
    "HOSPITAL_DAILY_ALLOWANCE": {
        "BASE": [_lim("FIXED_AMOUNT", 10_000, unit="PER_DAY")],
        "MEDIUM": [_lim("FIXED_AMOUNT", 15_000, unit="PER_DAY")],
        "SUPERIOR": [_lim("FIXED_AMOUNT", 25_000, unit="PER_DAY")],
    },
    "PHYSIOTHERAPY": {
        "MEDIUM": [_lim("QUANTITY", None, "Fisioterapia (sessões por ano)", count=20, unit="SESSION")],
        "SUPERIOR": [_lim("QUANTITY", None, "Fisioterapia (sessões por ano)", count=40, unit="SESSION")],
    },
}


def _network(ptype: str, **fields: Any) -> dict[str, Any]:
    return {"type": ptype, **{k: str(v) for k, v in fields.items()}}


# Participação "indicativa" e carências por cobertura (PDF p.10-11), escolha
# dentro dos intervalos do PDF. `insurerPct` = % paga pela seguradora (o PDF
# dá a % a cargo do segurado na rede).
BASELINE: dict[str, dict[str, Any]] = {
    "HOSPITALIZATION": {
        "participation": {
            "NETWORK": {"type": "NONE", "perEventDeductible": "100000"},
            "REIMBURSEMENT": _network("COINSURANCE", insurerPct=85),
        },
        "waitingDays": {"individual": 90, "group": 0, "scheduledSurgery": 180, "accidentWaived": True},
    },
    "AMBULATORY_SURGERY": {
        "participation": {"NETWORK": _network("COPAY_FIXED", copayAmount=25_000), "REIMBURSEMENT": _network("COINSURANCE", insurerPct=80)},
        "waitingDays": {"individual": 90, "group": 0, "accidentWaived": True},
    },
    "EMERGENCY": {
        "participation": {"NETWORK": _network("COPAY_FIXED", copayAmount=10_000), "REIMBURSEMENT": _network("COINSURANCE", insurerPct=80)},
        "waitingDays": {"individual": 30, "group": 0, "accidentWaived": True},
    },
    "OUTPATIENT": {
        "participation": {
            "NETWORK": _network("COPAY_FIXED", copayAmount=5_000),
            "REIMBURSEMENT": _network("COINSURANCE", insurerPct=80),
        },
        "waitingDays": {"individual": 30, "group": 0, "accidentWaived": True},
        "notes": "Consultas: carência 30–60 dias; exames e análises 30–90; exames de alto custo (TAC, RM) 90 dias e 20% ou 15.000 Kz na rede.",
    },
    "PHARMACY": {
        "participation": {"NETWORK": _network("COINSURANCE", insurerPct=70), "REIMBURSEMENT": _network("COINSURANCE", insurerPct=65)},
        "waitingDays": {"individual": 30, "group": 0, "accidentWaived": True},
        "excludedItems": ["Vitaminas", "Cosméticos"],
    },
    "MATERNITY": {
        "participation": {"NETWORK": _network("COPAY_FIXED", copayAmount=50_000), "REIMBURSEMENT": _network("COINSURANCE", insurerPct=80)},
        "waitingDays": {"individual": 365, "group": 0},
    },
    "DENTAL": {
        "participation": {"NETWORK": _network("COINSURANCE", insurerPct=65), "REIMBURSEMENT": _network("COINSURANCE", insurerPct=60)},
        "waitingDays": {"individual": 90, "group": 0, "accidentWaived": True},
        "notes": "Próteses dentárias: carência de 180 dias; próteses e ortodontia com sublimite ou excluídas.",
    },
    "OPTICAL": {
        "participation": {"NETWORK": _network("COINSURANCE", insurerPct=80), "REIMBURSEMENT": _network("COINSURANCE", insurerPct=70)},
        "waitingDays": {"individual": 180, "group": 0},
        "notes": "1 par de óculos a cada 1 ou 2 anos.",
    },
    "MEDICAL_EVACUATION": {
        "participation": {"NETWORK": {"type": "NONE"}, "REIMBURSEMENT": _network("COINSURANCE", insurerPct=100)},
        "waitingDays": {"individual": 180, "group": 0},
        "requiresPriorApproval": True,
        "destinations": ["Portugal", "África do Sul", "Brasil", "Namíbia"],
    },
    "CRITICAL_ILLNESS": {
        "waitingDays": {"individual": 90, "group": 0},
        "closedDiseaseList": ["Cancro", "AVC", "Enfarte", "Insuficiência renal", "Transplante"],
    },
    "PHYSIOTHERAPY": {
        "participation": {"NETWORK": _network("COPAY_FIXED", copayAmount=3_000), "REIMBURSEMENT": _network("COINSURANCE", insurerPct=70)},
        "waitingDays": {"individual": 90, "group": 30, "accidentWaived": True},
    },
    "HOSPITAL_DAILY_ALLOWANCE": {
        "participation": {"NETWORK": {"type": "NONE"}},
        "waitingDays": {"individual": 90, "group": 30},
        "timeDeductibleDays": 2,
    },
    "ASSISTANCE_24H": {
        "participation": {"NETWORK": {"type": "NONE"}},
        "waitingDays": {"individual": 0, "group": 0},
    },
}

# Opções de participação do Individual Médio (PDF p.11-12) — "indicativo".
PARTICIPATION_OPTIONS: list[dict[str, Any]] = [
    {"code": "A", "name": "Sem participação", "annualDeductible": "0", "copayPerConsultation": "0", "reimbursementPct": "90", "premiumAdjustmentPct": "15"},
    {"code": "B", "name": "Standard", "annualDeductible": "0", "copayPerConsultation": "5000", "reimbursementPct": "80", "premiumAdjustmentPct": "0"},
    {"code": "C", "name": "Participação moderada", "annualDeductible": "25000", "copayPerConsultation": "7500", "reimbursementPct": "80", "premiumAdjustmentPct": "-7"},
    {"code": "D", "name": "Participação elevada", "annualDeductible": "50000", "copayPerConsultation": "10000", "reimbursementPct": "70", "premiumAdjustmentPct": "-12"},
    {
        "code": "E",
        "name": "Só hospitalização",
        "hospitalOnly": True,
        "perEventDeductible": "100000",
        "reimbursementPct": "80",
        "premiumAdjustmentPct": "-40",
        "premiumAdjustmentRangePct": ["-45", "-35"],
    },
]

_COMMON_SETTINGS: dict[str, Any] = {
    "accessSystem": "MIXED",  # rede em Angola; reembolso fora da rede ou no estrangeiro
    "currency": "AOA",
    "indicative": True,
    "source": "PDF Coberturas e Capitais (1-Out-2026)",
    "priorAuthorization": {"internments": True, "highCostExams": True, "scheduledSurgeries": True},
    "capitalIndexation": {"reviewOnRenewal": True},
    "waitingRules": {"accidentWaived": True},
    "network": {"regions": []},
}

PLAN_KEYS = {
    "IND-BASE": ("BASE", IB),
    "IND-MEDIO": ("MEDIUM", IM),
    "IND-SUPERIOR": ("SUPERIOR", IS),
    "GRP-COLABORADORES": ("COLAB", GRP),
    "GRP-QUADROS": ("QUADROS", GRP),
    "GRP-ADMINISTRACAO": ("ADMIN", GRP),
}


def _individual_settings(tier: str) -> dict[str, Any]:
    ages = {"BASE": (60, 70), "MEDIUM": (65, 75), "SUPERIOR": (65, 75)}[tier]
    settings: dict[str, Any] = {
        **_COMMON_SETTINGS,
        "segment": "INDIVIDUAL_FAMILY",
        "tier": tier,
        "entryAge": {"min": 0, "max": ages[0]},
        "permanenceAge": {"max": ages[1]},
        "household": {"spouse": True, "dependentChildMaxAge": 25, "childrenMustBeStudents": True},
        "clinicalQuestionnaire": {"required": True, "medicalExamAboveAge": 55},
        "preExistingTreatment": {"mode": "TOTAL_EXCLUSION"},
    }
    if tier == "SUPERIOR":
        settings["preExistingTreatment"] = {"mode": "ACCEPTED_WITH_WAITING", "waitingMonths": 12}
    if tier == "MEDIUM":
        settings["participationOptions"] = PARTICIPATION_OPTIONS
        settings["participationOption"] = "B"
    return settings


def _group_settings(category: str) -> dict[str, Any]:
    return {
        **_COMMON_SETTINGS,
        "segment": "GROUP",
        "tier": "CUSTOM",
        "category": category,
        "group": {
            "minInsured": 5,
            "adhesion": "MANDATORY",
            "questionnaireWaivedAboveInsured": 20,
            "premiumBasis": "PER_AGE_BAND",
            "premiumPayer": "COMPANY",
            "categories": ["Colaboradores", "Quadros", "Administração"],
            "includesRetirees": False,
            "familyExtension": True,
            "continuityAfterLeaving": True,
            "monthlyInclusionsExclusions": True,
            "annualPremiumAdjustment": True,
            "profitSharing": {"lossRatioThresholdPct": "65"},
        },
        "waitingRules": {"accidentWaived": True, "groupMandatoryEliminatesWaiting": True},
        "preExistingTreatment": {"mode": "FULL_ACCEPTANCE"},
    }


def _coverage_config(code: str, letter: str, plan_key: str, segment_group: bool) -> dict[str, Any]:
    baseline = BASELINE.get(code, {})
    config: dict[str, Any] = {"inclusion": "INCLUDED" if letter == "B" else "OPTIONAL", "indicative": True}
    limits = CAPITALS.get(code, {}).get(plan_key)
    if limits:
        config["limits"] = limits
    for key, value in baseline.items():
        config[key] = value
    if code == "PRE_EXISTING_CONDITIONS":
        config["notes"] = (
            "Grupo com adesão obrigatória e dimensão suficiente: aceitação integral."
            if segment_group
            else "Individual Superior: opcional, com carência de 12 a 24 meses."
        )
    return config


def build_templates() -> list[dict[str, Any]]:
    """Two products (Individual/Familiar and Grupo) with their plans and the
    per-coverage configuration derived from the PDF."""

    def plan(code: str, name: str, description: str, settings: dict[str, Any]) -> dict[str, Any]:
        plan_key, column = PLAN_KEYS[code]
        column_index = {IB: 0, IM: 1, IS: 2, GRP: 3}[column]
        coverages = []
        for benefit_code, letters in MATRIX.items():
            letter = letters[column_index]
            if letter == "-":
                continue
            # Colaboradores não têm evacuação (PDF p.5: "—").
            if benefit_code == "MEDICAL_EVACUATION" and plan_key == "COLAB":
                continue
            coverages.append(
                {"code": benefit_code, "config": _coverage_config(benefit_code, letter, plan_key, column == GRP)}
            )
        return {"code": code, "name": name, "description": description, "settings": settings, "coverages": coverages}

    return [
        {
            "code": "SAUDE-INDIVIDUAL",
            "name": "Saúde Individual e Familiar",
            "description": "Contratado por uma pessoa para si e para o seu agregado (cônjuge ou unido de facto e filhos).",
            "plans": [
                plan("IND-BASE", "Individual Base", "Plano Base", _individual_settings("BASE")),
                plan("IND-MEDIO", "Individual Médio", "Plano Médio", _individual_settings("MEDIUM")),
                plan("IND-SUPERIOR", "Individual Superior", "Plano Superior", _individual_settings("SUPERIOR")),
            ],
        },
        {
            "code": "SAUDE-GRUPO",
            "name": "Saúde Grupo (Empresas)",
            "description": "Contratado por uma empresa ou instituição para os trabalhadores e, opcionalmente, os familiares.",
            "plans": [
                plan("GRP-COLABORADORES", "Grupo — Colaboradores", "Restantes colaboradores", _group_settings("Colaboradores")),
                plan("GRP-QUADROS", "Grupo — Quadros", "Quadros", _group_settings("Quadros")),
                plan("GRP-ADMINISTRACAO", "Grupo — Administração", "Administração", _group_settings("Administração")),
            ],
        },
    ]
