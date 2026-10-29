CONFIG_CATALOG=[
{"key":"product.plans","category":"PRODUCT","label":"Planos de Saúde","priority":"HIGH","value_type":"object"},
{"key":"product.coverages","category":"PRODUCT","label":"Coberturas e extensões","priority":"HIGH","value_type":"object"},
{"key":"product.capitals_sublimits","category":"PRODUCT","label":"Capitais e sublimites","priority":"HIGH","value_type":"object"},
{"key":"product.member_participation","category":"PRODUCT","label":"Co-participações","priority":"HIGH","value_type":"object"},
{"key":"product.waiting_periods","category":"PRODUCT","label":"Períodos de carência","priority":"HIGH","value_type":"object"},
{"key":"product.age_limits","category":"PRODUCT","label":"Limites de idade","priority":"HIGH","value_type":"object"},
{"key":"product.minimum_premium","category":"PRODUCT","label":"Prémio mínimo","priority":"HIGH","value_type":"object"},
{"key":"product.exclusions","category":"PRODUCT","label":"Exclusões","priority":"HIGH","value_type":"object"},
{"key":"pricing.reference_premiums","category":"PRICING","label":"Prémios de referência","priority":"HIGH","value_type":"object"},
{"key":"pricing.factors","category":"PRICING","label":"Fatores de tarifação","priority":"HIGH","value_type":"object"},
{"key":"pricing.adjustments","category":"PRICING","label":"Agravamentos e descontos","priority":"HIGH","value_type":"object"},
{"key":"pricing.taxes_fees","category":"PRICING","label":"Impostos, taxas e encargos","priority":"HIGH","value_type":"object"},
{"key":"pricing.actuarial_model","category":"PRICING","label":"Modelo atuarial SAU/SAG (rascunho)","priority":"HIGH","value_type":"object"},
{"key":"underwriting.acceptance_rules","category":"UNDERWRITING","label":"Regras de aceitação","priority":"HIGH","value_type":"object"},
{"key":"underwriting.pre_existing_conditions","category":"UNDERWRITING","label":"Doenças pré-existentes","priority":"HIGH","value_type":"object"},
{"key":"underwriting.medical_review","category":"UNDERWRITING","label":"Análise médica reforçada","priority":"HIGH","value_type":"object"},
{"key":"group.rules","category":"GROUP","label":"Regras de grupo","priority":"MEDIUM","value_type":"object"},
{"key":"renewal.rules","category":"RENEWAL","label":"Regras de renovação","priority":"MEDIUM","value_type":"object"},
{"key":"renewal.deadlines","category":"RENEWAL","label":"Prazos de renovação","priority":"LOW","value_type":"object"},
{"key":"proposal.documents","category":"DOCUMENTS","label":"Documentos e modelos","priority":"HIGH","value_type":"object"},
{"key":"proposal.texts","category":"DOCUMENTS","label":"Textos e cláusulas","priority":"HIGH","value_type":"object"},
{"key":"network.rules","category":"NETWORK","label":"Rede convencionada e livre escolha","priority":"MEDIUM","value_type":"object"},
{"key":"foreign_coverage.rules","category":"NETWORK","label":"Cobertura no estrangeiro","priority":"MEDIUM","value_type":"object"},
{"key":"security.approval_rules","category":"SECURITY","label":"Aprovação e autonomia","priority":"HIGH","value_type":"object"},
{"key":"security.role_permissions","category":"SECURITY","label":"Permissões por perfil","priority":"HIGH","value_type":"object"},
{"key":"rules.custom","category":"RULES","label":"Regras personalizadas (Quando… então…)","priority":"HIGH","value_type":"object"},
{"key":"proposal.branding","category":"PROPOSAL","label":"Identidade visual dos documentos","priority":"MEDIUM","value_type":"object"},
{"key": "pricing.formulas", "category": "PRICING","label": "Fórmulas de tarifação","priority": "HIGH","value_type":"object",},
{"key":"pricing.fractionation","category":"PRICING","label":"Encargos de fracionamento do prémio","priority":"MEDIUM","value_type":"object"},
{"key":"quote.discount_approval","category":"APPROVALS","label":"Aprovação de descontos","priority":"HIGH","value_type":"object"},
{"key":"service.sla","category":"SERVICE","label":"Metas de atendimento (SLA)","priority":"HIGH","value_type":"object"},
{"key":"service.satisfaction","category":"SERVICE","label":"Avaliação de satisfação","priority":"MEDIUM","value_type":"object"},
{"key":"pricing.experience_rating","category":"PRICING","label":"Tarifação pela experiência de sinistralidade","priority":"HIGH","value_type":"object"},
{"key":"quote.scenario_comparison","category":"PRICING","label":"Comparação de cenários","priority":"MEDIUM","value_type":"object"},
{"key":"claims.projections","category":"CLAIMS","label":"Projeções de sinistralidade","priority":"MEDIUM","value_type":"object"},
{"key":"policy.endorsements","category":"POLICY","label":"Endossos de inclusão (pro-rata, recém-nascidos, aceitação)","priority":"HIGH","value_type":"object"},
]
CATALOG_BY_KEY={x["key"]:x for x in CONFIG_CATALOG}

# Área da Administração do tenant onde cada tipo de configuração é editado
# (as 7 áreas: ORGANIZATION, APPROVALS, PRODUCTS, TARIFF, RULES, PARAMETERS,
# DOCUMENTS). Nenhum tipo fica sem ecrã de assunto.
AREAS = ("ORGANIZATION", "APPROVALS", "PRODUCTS", "TARIFF", "RULES", "PARAMETERS", "DOCUMENTS")
AREA_LABELS = {
    "ORGANIZATION": "Organização · Utilizadores e perfis",
    "APPROVALS": "Organização · Aprovações pendentes",
    "PRODUCTS": "Negócio · Produtos e planos",
    "TARIFF": "Negócio · Tarifação",
    "RULES": "Negócio · Regras",
    "PARAMETERS": "Negócio · Parâmetros",
    "DOCUMENTS": "Comunicação · Documentos e marca",
}
_AREA_BY_KEY = {
    "product.minimum_premium": "TARIFF",
    "group.rules": "RULES",
    "renewal.rules": "RULES",
    "renewal.deadlines": "RULES",
    "rules.custom": "RULES",
    "network.rules": "PRODUCTS",
    "foreign_coverage.rules": "PRODUCTS",
}
_AREA_BY_CATEGORY = {
    "PRODUCT": "PRODUCTS",
    "PRICING": "TARIFF",
    "UNDERWRITING": "RULES",
    "GROUP": "RULES",
    "RENEWAL": "RULES",
    "NETWORK": "PRODUCTS",
    "SECURITY": "ORGANIZATION",
    "RULES": "RULES",
    "DOCUMENTS": "DOCUMENTS",
    "PROPOSAL": "DOCUMENTS",
    "APPROVALS": "APPROVALS",
    "SERVICE": "PARAMETERS",
    "CLAIMS": "PARAMETERS",
    "POLICY": "RULES",
}


def area_of(config_key: str) -> str:
    from apps.business_config.domain.scope import base_key

    if config_key.startswith("product.pricing_setup:"):
        return "TARIFF"
    config_key = base_key(config_key)
    if config_key in _AREA_BY_KEY:
        return _AREA_BY_KEY[config_key]
    entry = CATALOG_BY_KEY.get(config_key)
    return _AREA_BY_CATEGORY.get(entry["category"], "PARAMETERS") if entry else "PARAMETERS"
