"""Configuração de negócio de referência (Angola), derivada dos documentos do projecto.

Fontes:
  - Modelo_Actuarial_Saude_SAU_SAG_Angola.xlsx, folhas `Regras_Ajustes` (agravamentos por idade e
    pré-existências, descontos de agregado) e `Dashboard_Premissas` (encargos, inflação, câmbio);
  - source_configuration_seed.json (planos, coberturas, rede, estrangeiro, documentos da proposta).

Cada entrada tem a forma `{config_key: value}` validada pelo esquema de `form_schemas`. Valores que os
documentos não definem (prazos de renovação, textos legais) estão marcados `ASSUNCAO` e devem ser
confirmados pelo negócio antes de produção real.

O que NÃO está aqui de propósito: capitais, carências e participações de cada cobertura já vivem nas
definições dos planos (importadas do PDF «Coberturas e Capitais») e são espelhados em runtime por
`seed_full_database` a partir da base de dados, para nunca divergirem.
"""
from __future__ import annotations

from typing import Any

PLAN_ROWS = [
    {"code": "IND-BASE", "name": "Individual Base", "description": "Plano Base — Saúde Individual e Familiar (SAU).", "active": True},
    {"code": "IND-MEDIO", "name": "Individual Médio", "description": "Plano Conforto — Saúde Individual e Familiar (SAU).", "active": True},
    {"code": "IND-SUPERIOR", "name": "Individual Superior", "description": "Plano Premium — Saúde Individual e Familiar (SAU).", "active": True},
    {"code": "GRP-COLABORADORES", "name": "Grupo — Colaboradores", "description": "Saúde Grupo (SAG) — restantes colaboradores.", "active": True},
    {"code": "GRP-QUADROS", "name": "Grupo — Quadros", "description": "Saúde Grupo (SAG) — quadros médios.", "active": True},
    {"code": "GRP-ADMINISTRACAO", "name": "Grupo — Administração", "description": "Saúde Grupo (SAG) — administração.", "active": True},
]

COVERAGE_ROWS = [
    {"code": "HOSPITALIZATION", "name": "Internamento Hospitalar", "optional": False, "enabled": True,
     "description": "Cobertura base: internamento, cirurgia e cuidados intensivos."},
    {"code": "OUTPATIENT", "name": "Ambulatório", "optional": False, "enabled": True,
     "description": "Cobertura base: consultas, meios complementares de diagnóstico e tratamentos."},
    {"code": "MATERNITY", "name": "Maternidade e Parto", "optional": False, "enabled": True,
     "description": "Cobertura base: assistência na gravidez, parto e pós-parto."},
    {"code": "EMERGENCY", "name": "Urgência e Emergência Médica", "optional": False, "enabled": True,
     "description": "Cobertura base: sem período de carência."},
    {"code": "DENTAL", "name": "Estomatologia", "optional": True, "enabled": True, "description": "Cobertura opcional."},
    {"code": "OPTICAL", "name": "Óptica", "optional": True, "enabled": True, "description": "Cobertura opcional."},
    {"code": "CHECKUP_PREVENTIVE", "name": "Medicina Preventiva / Check-up Anual", "optional": True, "enabled": True,
     "description": "Cobertura opcional."},
    {"code": "MEDICAL_EVACUATION", "name": "Cobertura no Estrangeiro", "optional": True, "enabled": True,
     "description": "Cobertura opcional, sujeita a aprovação prévia."},
]

STATIC_CONFIGS: dict[str, dict[str, Any]] = {
    "product.plans": {"plans": PLAN_ROWS},
    "product.coverages": {"coverages": COVERAGE_ROWS},
    # Idades de entrada/permanência = as do PDF de mercado (Base 60/70; Médio e Superior 65/75).
    "product.age_limits": {"items": [
        {"plan": "IND-BASE", "entry_max_age": 60, "renewal_max_age": 70},
        {"plan": "IND-MEDIO", "entry_max_age": 65, "renewal_max_age": 75},
        {"plan": "IND-SUPERIOR", "entry_max_age": 65, "renewal_max_age": 75},
    ]},
    # Regras_Ajustes §3 e Dashboard_Premissas: encargos do modelo (informativos, já incluídos no prémio actuarial).
    "pricing.taxes_fees": {"charges": [
        {"code": "ARSEG-LEVY", "description": "Taxa de supervisão ARSEG (1%) — já incluída no prémio actuarial",
         "category": "TAX", "type": "PERCENTAGE", "value": "1", "included_in_premium": False},
        {"code": "STAMP-DUTY", "description": "Imposto do selo (0% no modelo actuarial)",
         "category": "TAX", "type": "PERCENTAGE", "value": "0", "included_in_premium": False},
    ]},
    # Regras_Ajustes §2: gravidade da pré-existência -> tratamento.
    "underwriting.pre_existing_conditions": {"rules": [
        {"severity": "LOW", "treatment": "SURCHARGE", "surcharge_percent": "15"},
        {"severity": "MODERATE", "treatment": "SURCHARGE", "surcharge_percent": "30", "waiting_days": 180},
        {"severity": "HIGH", "treatment": "EXCLUSION_SPECIFIC"},
    ]},
    # Regras_Ajustes §2: idade na 1.ª adesão.
    "underwriting.acceptance_rules": {"rules": [
        {"condition": "Idade até 55 anos: aceitação normal", "age_from": 0, "age_to": 55, "decision": "AUTO_ACCEPT"},
        {"condition": "56 a 60 anos: questionário e análises de rotina (+15%)", "age_from": 56, "age_to": 60,
         "decision": "MEDICAL_REVIEW"},
        {"condition": "61 a 65 anos: exame médico completo (+30%)", "age_from": 61, "age_to": 65,
         "decision": "MEDICAL_REVIEW"},
        {"condition": "66 a 70 anos: parecer do Médico Assessor (+50%)", "age_from": 66, "age_to": 70,
         "decision": "TECHNICAL_REVIEW"},
        {"condition": "71 ou mais anos: fora da idade máxima de entrada", "age_from": 71, "decision": "DECLINE",
         "notes": "Apenas renovação/conversão em SAG."},
    ]},
    "underwriting.medical_review": {
        "automatic_acceptance_max_age": 55, "questionnaire_required": True, "clinical_documentation_required": True,
    },
    "group.rules": {
        "minimum_members": 5, "below_minimum_behavior": "INDIVIDUAL", "mandatory_enrolment": True,
        "questionnaire_exemption_threshold": 20, "experience_loss_ratio_threshold": "65",
    },
    # inflação médica = inflação geral 10,9% + excesso médico 4,0% (Dashboard_Premissas).
    "renewal.rules": {
        "automatic_renewal": False, "medical_inflation_percent": "14.9", "update_capitals": True,
        "update_tables": True, "loss_ratio_adjustment_enabled": True, "continuity_without_new_waiting_period": True,
    },
    # ASSUNCAO: prazos não definidos nos documentos.
    "renewal.deadlines": {"prepare_days_before": 60, "acceptance_days": 30, "previous_policy_close": "ON_RENEWAL_ACTIVATION"},
    "network.rules": {
        "network_enabled": True, "free_choice_enabled": True, "geographical_scope": "Angola",
        "pre_authorization_required": True,
    },
    "foreign_coverage.rules": {
        "enabled": True, "countries": ["Portugal", "África do Sul", "Brasil", "Namíbia"], "currency": "USD",
        "prior_approval": True,
        "fx_rule": "Reembolso em Kz à taxa de referência do modelo actuarial (1 USD = 931,27 Kz) na data de pagamento.",
    },
    "proposal.documents": {"documents": [
        {"document_type": "PROPOSAL", "required": True, "description": "Proposta de Seguro"},
        {"document_type": "HEALTH_QUESTIONNAIRE", "required": True, "description": "Questionário de Saúde — SAU"},
        {"document_type": "BENEFITS_TABLE", "required": True, "description": "Tabela de Taxas e Regras de Subscrição"},
        {"document_type": "GENERAL_CONDITIONS", "required": True, "description": "Condições Gerais e Guia da Rede / Reembolso"},
        {"document_type": "SPECIAL_CONDITIONS", "required": True, "description": "Condições Particulares"},
        {"document_type": "POLICY", "required": True, "description": "Apólice e cartão de beneficiário"},
        {"document_type": "PRODUCT_MANUAL", "required": False, "description": "Manual do Produto"},
    ]},
    # ASSUNCAO: textos genéricos, inactivos até validação jurídica (os documentos exigem-na).
    "proposal.texts": {"texts": [
        {"code": "VALIDADE-PROPOSTA", "title": "Validade da proposta",
         "text": "Esta proposta é válida pelo prazo indicado e sujeita à aceitação do risco pela seguradora.", "active": False},
        {"code": "PROTECCAO-DADOS", "title": "Protecção de dados de saúde",
         "text": "Os dados de saúde são tratados com confidencialidade para efeitos de subscrição e gestão do contrato.",
         "active": False},
    ]},
    "proposal.branding": {"company_name": "Q360 Saúde", "primary_color": "#0B6E4F",
                          "tagline": "Seguros de saúde em Angola", "footer_text": "Q360 Saúde — Luanda, Angola"},
}

# Regras "Quando… então…" (rules.custom) derivadas de Regras_Ajustes §2 e §3.
CUSTOM_RULES: dict[str, list[dict[str, Any]]] = {"rules": [
    {"name": "Agravamento 56-60 anos (adesão)", "active": True, "scope": "PERSON", "field": "age", "operator": "BETWEEN",
     "value": "56", "value_to": "60", "action": "INCREASE_PERCENT", "amount": "15", "order": 1,
     "message": "Agravamento de 15% por idade na 1.ª adesão.", "code": "AGE-56-60"},
    {"name": "Agravamento 61-65 anos (adesão)", "active": True, "scope": "PERSON", "field": "age", "operator": "BETWEEN",
     "value": "61", "value_to": "65", "action": "INCREASE_PERCENT", "amount": "30", "order": 2,
     "message": "Agravamento de 30% por idade na 1.ª adesão; exame médico completo.", "code": "AGE-61-65"},
    {"name": "Agravamento 66-70 anos (adesão)", "active": True, "scope": "PERSON", "field": "age", "operator": "BETWEEN",
     "value": "66", "value_to": "70", "action": "INCREASE_PERCENT", "amount": "50", "order": 3,
     "message": "Agravamento de 50% por idade na 1.ª adesão; parecer do Médico Assessor.", "code": "AGE-66-70"},
    {"name": "Desconto de agregado — 3 pessoas", "active": True, "scope": "QUOTE", "field": "members_count",
     "operator": "EQ", "value": "3", "field_2": "segment", "operator_2": "EQ", "value_2": "INDIVIDUAL_FAMILY",
     "action": "DISCOUNT_PERCENT", "amount": "5", "order": 10, "message": "Desconto de agregado de 5%.", "code": "FAM-3"},
    {"name": "Desconto de agregado — 4 pessoas", "active": True, "scope": "QUOTE", "field": "members_count",
     "operator": "EQ", "value": "4", "field_2": "segment", "operator_2": "EQ", "value_2": "INDIVIDUAL_FAMILY",
     "action": "DISCOUNT_PERCENT", "amount": "7.5", "order": 11, "message": "Desconto de agregado de 7,5%.", "code": "FAM-4"},
    {"name": "Desconto de agregado — 5 ou mais pessoas", "active": True, "scope": "QUOTE", "field": "members_count",
     "operator": "GTE", "value": "5", "field_2": "segment", "operator_2": "EQ", "value_2": "INDIVIDUAL_FAMILY",
     "action": "DISCOUNT_PERCENT", "amount": "10", "order": 12, "message": "Desconto de agregado de 10%.", "code": "FAM-5"},
]}
