"""Catálogo de coberturas de Saúde do mercado angolano.

Fonte: `Seguro de Saúde — Coberturas e Capitais.pdf` (1-Out-2026), secções
"Estrutura de um produto de saúde", "Coberturas base/opcionais" (Individual
e Grupo), "Descrição dos capitais" e "Participação e carência por cobertura".
O PDF diz que os valores em Kz são **indicativos** e que a composição de cada
plano varia por seguradora — por isso tudo o que aqui é número é
`indicative: True` e serve só de ponto de partida editável pelo GTE
(`Benefit.definition_json`), nunca de regra de negócio hardcoded no motor.

`category` (`Benefit.benefit_type`):
  - `BASE`: presente em **todos** os planos, em todas as colunas da matriz
    comparativa do PDF (Individual Base/Médio/Superior e Grupo = "B") —
    Hospitalização, Cirurgia de ambulatório e Urgências/ambulância. Nunca
    se remove nem se desativa.
  - `COMPLEMENTARY`: o resto. Se um plano a inclui de origem ("B") ou só a
    oferece como facultativa ("O") é decisão **do plano**
    (`PlanBenefit.configuration_json.inclusion`), não da cobertura — é o que
    a matriz "base vs opcional" do PDF descreve (o Ambulatório, por
    exemplo, é "O" no Individual Base e "B" no Médio).
"""
from __future__ import annotations

from typing import Any

BASE = "BASE"
COMPLEMENTARY = "COMPLEMENTARY"

# Formas de garantia dos capitais (PDF "Formas de garantia dos capitais").
GUARANTEE_FORMS: dict[str, str] = {
    "ANNUAL_PER_PERSON": "Capital anual por pessoa segura",
    "HOUSEHOLD_SHARED": "Capital por agregado ou partilhado",
    "SUBLIMIT": "Sublimite dentro de uma cobertura",
    "PER_ACT_OR_DAY": "Limite por ato ou por dia",
    "QUANTITY": "Limite de quantidade (número máximo de atos)",
    "COINSURANCE_PCT": "Percentagem de comparticipação",
    "FIXED_AMOUNT": "Capital fixo (forfetário)",
    "PER_EVENT": "Capital por evento",
    "BIENNIAL": "Capital por 2 anos",
    "PER_SERVICE": "Limite por serviço",
}

EVACUATION_DESTINATIONS = ["Portugal", "África do Sul", "Brasil", "Namíbia"]
CRITICAL_ILLNESS_LIST = ["Cancro", "AVC", "Enfarte", "Insuficiência renal", "Transplante"]

# Exclusões habituais (PDF "Exclusões habituais") — nível produto.
STANDARD_EXCLUSIONS: list[dict[str, Any]] = [
    {"code": "PRE_EXISTING_CONGENITAL", "text": "Doenças preexistentes e malformações congénitas conhecidas (salvo aceitação)"},
    {"code": "AESTHETIC_SURGERY", "text": "Cirurgia plástica ou estética, salvo reconstrutiva após acidente ou doença coberta"},
    {"code": "INFERTILITY", "text": "Tratamentos de infertilidade e procriação medicamente assistida"},
    {"code": "UNPRESCRIBED_CHECKUPS", "text": "Check-ups e tratamentos sem indicação médica (salvo cobertura de medicina preventiva)"},
    {"code": "ADDICTIONS_SELF_HARM", "text": "Alcoolismo, toxicodependência e lesões intencionais"},
    {"code": "WAR_TERRORISM_RADIATION", "text": "Doenças ou acidentes resultantes de guerra, terrorismo ou radiações"},
    {"code": "HIGH_RISK_SPORTS", "text": "Desportos de alto risco e competições profissionais"},
    {"code": "WORK_TRAFFIC_ACCIDENTS", "text": "Acidentes de trabalho e de viação cobertos por seguro obrigatório próprio"},
    {"code": "EXPERIMENTAL_TREATMENTS", "text": "Tratamentos experimentais ou não reconhecidos"},
    {"code": "OFFICIAL_EPIDEMICS", "text": "Epidemias declaradas oficialmente (em alguns produtos)", "productDependent": True},
    {
        "code": "HIV_DIALYSIS_TRANSPLANT",
        "text": "VIH/SIDA, hemodiálise crónica e transplantes (excluídos ou com sublimite, conforme o produto)",
        "productDependent": True,
        "alternative": "SUBLIMIT",
    },
    {"code": "ABROAD_WITHOUT_APPROVAL", "text": "Tratamentos no estrangeiro sem aprovação prévia"},
    {"code": "LONG_TERM_CARE", "text": "Internamentos em lares ou para cuidados continuados de longa duração"},
]


def _entry(
    code: str,
    name: str,
    category: str,
    group: str,
    description: str,
    *,
    guarantee_form: str,
    sublimits: list[str] | None = None,
    participation: dict[str, str] | None = None,
    waiting_days: dict[str, list[int]] | None = None,
    prior_approval: bool = False,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    definition: dict[str, Any] = {
        "group": group,
        "guaranteeForm": guarantee_form,
        "typicalSublimits": sublimits or [],
        "typicalParticipation": participation or {},
        "typicalWaitingDays": waiting_days or {},
        "requiresPriorApproval": prior_approval,
        "exclusions": [],
        "indicative": True,
        "source": "PDF Coberturas e Capitais (1-Out-2026)",
    }
    if extra:
        definition.update(extra)
    return {
        "code": code,
        "name": name,
        "benefit_type": category,
        "description": description,
        "definition": definition,
    }


CATALOG: list[dict[str, Any]] = [
    # ------------------------------------------------------------------ BASE
    _entry(
        "HOSPITALIZATION",
        "Hospitalização",
        BASE,
        "INTERNMENT",
        "Internamento médico e cirúrgico, quarto (individual ou partilhado, conforme o plano), bloco operatório, "
        "anestesia, honorários médicos, meios complementares de diagnóstico e medicamentos durante o internamento.",
        guarantee_form="ANNUAL_PER_PERSON",
        sublimits=["Quarto por dia", "Próteses intra-operatórias", "Acompanhante de menor internado", "UCI"],
        participation={
            "network": "0% a 10%; ou franquia 50.000–150.000 Kz por internamento",
            "reimbursement": "80% a 90%",
        },
        waiting_days={"individual": [90, 90], "group": [0, 30]},
        extra={"scheduledSurgeryWaitingDays": 180, "mandatoryInEveryPlan": True},
    ),
    _entry(
        "AMBULATORY_SURGERY",
        "Cirurgia de ambulatório (hospital de dia)",
        BASE,
        "INTERNMENT",
        "Cirurgia de ambulatório / hospital de dia, incluída na cobertura de hospitalização.",
        guarantee_form="ANNUAL_PER_PERSON",
        participation={"network": "10% ou 25.000 Kz", "reimbursement": "80%"},
        waiting_days={"individual": [90, 90], "group": [0, 30]},
        extra={"mandatoryInEveryPlan": True, "sharesCapitalWith": "HOSPITALIZATION"},
    ),
    _entry(
        "EMERGENCY",
        "Urgências e transporte em ambulância",
        BASE,
        "EMERGENCY",
        "Urgências hospitalares e transporte em ambulância para o hospital.",
        guarantee_form="PER_EVENT",
        participation={"network": "5.000–15.000 Kz por episódio", "reimbursement": "80%"},
        waiting_days={"individual": [0, 30], "group": [0, 0]},
        extra={"accidentWaitingDays": 0, "illnessWaitingDays": 30, "mandatoryInEveryPlan": True},
    ),
    # --------------------------------------------------------- COMPLEMENTARY
    _entry(
        "OUTPATIENT",
        "Ambulatório",
        COMPLEMENTARY,
        "OUTPATIENT",
        "Consultas de clínica geral e especialidade, exames de diagnóstico, análises, tratamentos e pequena cirurgia.",
        guarantee_form="ANNUAL_PER_PERSON",
        sublimits=["Por consulta", "Fisioterapia (n.º de sessões)", "Exames de imagem de alto custo (TAC, RM)"],
        participation={
            "network": "Consultas 3.000–10.000 Kz por consulta; exames e análises 10% a 20%; alto custo 20% ou 15.000 Kz",
            "reimbursement": "70% a 80%, até ao limite por consulta (alto custo 70%)",
            "coinsurance": "70% a 90%",
        },
        waiting_days={"individual": [30, 90], "group": [0, 30]},
        extra={"canBeHouseholdShared": True, "highCostImagingWaitingDays": 90},
    ),
    _entry(
        "PHARMACY",
        "Medicamentos em farmácia",
        COMPLEMENTARY,
        "SUPPORT",
        "Medicamentos com receita médica, em farmácia.",
        guarantee_form="SUBLIMIT",
        sublimits=["Por receita"],
        participation={"network": "20% a 50%", "reimbursement": "50% a 80%"},
        waiting_days={"individual": [30, 30], "group": [0, 0]},
        extra={"excludedItems": ["Vitaminas", "Cosméticos"]},
    ),
    _entry(
        "MATERNITY",
        "Parto e assistência pré e pós-natal",
        COMPLEMENTARY,
        "SPECIALTY",
        "Parto normal ou cesariana, IVG legal, complicações, ecografias pré-natais e recém-nascido nos primeiros dias.",
        guarantee_form="PER_EVENT",
        sublimits=["Parto normal < cesariana", "Ecografias pré-natais"],
        participation={"network": "10% ou 50.000 Kz", "reimbursement": "80%"},
        waiting_days={"individual": [300, 365], "group": [0, 270]},
        extra={"antiSelectionWaiting": True, "groupMandatoryAdhesionWaiting": "sem carência ou carência reduzida"},
    ),
    _entry(
        "DENTAL",
        "Estomatologia e ortodontia",
        COMPLEMENTARY,
        "SPECIALTY",
        "Consultas, higiene oral, destartarização, obturações, tratamentos, extrações e próteses dentárias.",
        guarantee_form="ANNUAL_PER_PERSON",
        sublimits=["Próteses e ortodontia (sublimite ou excluídas)"],
        participation={"network": "20% a 50%", "reimbursement": "50% a 70%", "coinsurance": "50% a 80%"},
        waiting_days={"individual": [90, 90], "group": [0, 90]},
        extra={"prosthesisWaitingDays": 180, "antiSelectionWaiting": True},
    ),
    _entry(
        "OPTICAL",
        "Oftalmologia (óculos e lentes)",
        COMPLEMENTARY,
        "SPECIALTY",
        "Consulta, armações, lentes e lentes de contacto.",
        guarantee_form="ANNUAL_PER_PERSON",
        sublimits=["1 par a cada 1 ou 2 anos"],
        participation={"network": "20%", "reimbursement": "70%"},
        waiting_days={"individual": [180, 180], "group": [0, 90]},
        extra={"alternativeGuaranteeForm": "BIENNIAL"},
    ),
    _entry(
        "MEDICAL_EVACUATION",
        "Evacuação e tratamento no estrangeiro",
        COMPLEMENTARY,
        "INTERNATIONAL",
        "Transporte médico, bilhete do acompanhante, tratamento e internamento fora do país.",
        guarantee_form="ANNUAL_PER_PERSON",
        participation={"network": "0% (se aprovada)", "reimbursement": "80% a 100% dos custos aprovados"},
        waiting_days={"individual": [180, 180], "group": [0, 90]},
        prior_approval=True,
        extra={
            "allowedCurrencies": ["AOA", "USD"],
            "destinations": EVACUATION_DESTINATIONS,
            "reimbursementOfApprovedCostsPct": 100,
            "fxRiskNote": "Definir destinos, moeda do capital e processo de aprovação prévia; considerar o risco cambial.",
        },
    ),
    _entry(
        "CRITICAL_ILLNESS",
        "Doenças graves",
        COMPLEMENTARY,
        "FIXED_CAPITAL",
        "Diagnóstico de doença grave: capital fixo pago uma vez, ou capital de tratamento.",
        guarantee_form="FIXED_AMOUNT",
        sublimits=["Lista fechada de doenças"],
        participation={"network": "— (capital fixo)"},
        waiting_days={"individual": [90, 180], "group": [0, 90]},
        extra={"closedDiseaseList": CRITICAL_ILLNESS_LIST},
    ),
    _entry(
        "DIALYSIS_ONCOLOGY",
        "Hemodiálise, oncologia, VIH/SIDA e doenças crónicas (reforço)",
        COMPLEMENTARY,
        "SPECIALTY",
        "Hemodiálise e tratamentos oncológicos (quimioterapia e radioterapia), VIH/SIDA e doenças crónicas "
        "acima do limite base.",
        guarantee_form="ANNUAL_PER_PERSON",
        extra={"exclusionAlternative": "VIH/SIDA, hemodiálise crónica e transplantes: excluídos ou com sublimite, conforme o produto"},
    ),
    _entry(
        "ENDEMIC_DISEASES",
        "Malária e doenças endémicas",
        COMPLEMENTARY,
        "SPECIALTY",
        "Malária e doenças endémicas: sublimite próprio ou excluídas em alguns produtos.",
        guarantee_form="SUBLIMIT",
    ),
    _entry(
        "PHYSIOTHERAPY",
        "Fisioterapia e medicina física e de reabilitação",
        COMPLEMENTARY,
        "SUPPORT",
        "Fisioterapia e medicina física e de reabilitação, com limite de sessões.",
        guarantee_form="QUANTITY",
        sublimits=["Número de sessões por ano"],
        participation={"network": "3.000 Kz por sessão", "reimbursement": "70%"},
        waiting_days={"individual": [90, 90], "group": [30, 30]},
    ),
    _entry(
        "PSYCHOLOGY_PSYCHIATRY",
        "Psicologia e psiquiatria",
        COMPLEMENTARY,
        "SUPPORT",
        "Psicologia, psiquiatria e saúde mental.",
        guarantee_form="ANNUAL_PER_PERSON",
    ),
    _entry(
        "CHECKUP_PREVENTIVE",
        "Check-up anual e medicina preventiva",
        COMPLEMENTARY,
        "PREVENTION",
        "Check-up anual e medicina preventiva.",
        guarantee_form="PER_EVENT",
    ),
    _entry(
        "VACCINATION",
        "Vacinação e programas de prevenção",
        COMPLEMENTARY,
        "PREVENTION",
        "Vacinação e programas de prevenção.",
        guarantee_form="ANNUAL_PER_PERSON",
    ),
    _entry(
        "ALTERNATIVE_MEDICINE",
        "Medicinas alternativas",
        COMPLEMENTARY,
        "SUPPORT",
        "Acupunctura e osteopatia.",
        guarantee_form="QUANTITY",
    ),
    _entry(
        "PROSTHESIS",
        "Próteses e ortóteses externas",
        COMPLEMENTARY,
        "SUPPORT",
        "Próteses e ortóteses externas (cadeira de rodas, aparelhos auditivos).",
        guarantee_form="SUBLIMIT",
    ),
    _entry(
        "HOSPITAL_DAILY_ALLOWANCE",
        "Subsídio diário de internamento",
        COMPLEMENTARY,
        "FIXED_CAPITAL",
        "Valor diário por dia de internamento.",
        guarantee_form="FIXED_AMOUNT",
        sublimits=["Máximo de dias por ano (ex.: 30 ou 60)"],
        participation={"network": "Franquia temporal: 2–3 dias de internamento"},
        waiting_days={"individual": [90, 90], "group": [30, 30]},
        extra={"typicalMaxDaysPerYear": [30, 60], "timeDeductibleDays": [2, 3]},
    ),
    _entry(
        "ASSISTANCE_24H",
        "Assistência médica 24h / teleconsulta",
        COMPLEMENTARY,
        "ASSISTANCE",
        "Aconselhamento telefónico, médico ao domicílio, entrega de medicamentos e teleconsulta.",
        guarantee_form="PER_SERVICE",
        sublimits=["N.º de serviços por ano", "Limite por serviço"],
        participation={"network": "Sem participação"},
        waiting_days={"individual": [0, 0], "group": [0, 0]},
        extra={"noParticipation": True},
    ),
    _entry(
        "SECOND_OPINION",
        "Segunda opinião médica internacional",
        COMPLEMENTARY,
        "ASSISTANCE",
        "Segunda opinião médica internacional.",
        guarantee_form="PER_EVENT",
    ),
    _entry(
        "OCCUPATIONAL_MEDICINE",
        "Medicina no trabalho",
        COMPLEMENTARY,
        "PREVENTION",
        "Medicina no trabalho e check-up anual (Grupo).",
        guarantee_form="ANNUAL_PER_PERSON",
        extra={"segments": ["GROUP"]},
    ),
    _entry(
        "PRE_EXISTING_CONDITIONS",
        "Doenças preexistentes",
        COMPLEMENTARY,
        "UNDERWRITING",
        "Aceitação de doenças preexistentes: opcional com carência no Individual Superior; base no Grupo com "
        "adesão obrigatória e dimensão suficiente.",
        guarantee_form="ANNUAL_PER_PERSON",
        extra={"acceptanceModes": "ver preExistingTreatment em plan.settings_json"},
    ),
    _entry(
        "TRAVEL_ASSISTANCE",
        "Assistência em Viagem",
        COMPLEMENTARY,
        "INTERNATIONAL",
        "Assistência médica urgente em deslocações temporárias ao estrangeiro (tipicamente ≤60 dias).",
        guarantee_form="PER_EVENT",
        extra={"legacy": True},
    ),
]

CATALOG_BY_CODE: dict[str, dict[str, Any]] = {entry["code"]: entry for entry in CATALOG}
BASE_CODES: frozenset[str] = frozenset(e["code"] for e in CATALOG if e["benefit_type"] == BASE)
