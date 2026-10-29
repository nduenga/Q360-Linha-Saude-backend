def f(name,label,type_,required=False,options=None,labels=None,help=None):
    x={"name":name,"label":label,"type":type_,"required":required}
    if options:x["options"]=options
    if labels:x["optionLabels"]=labels
    if help:x["help"]=help
    return x
from apps.business_config.domain import custom_rules as cr
from apps.customer_portal.domain import requests as portal_requests
from apps.foundation.domain.permissions import Permission, Role
PLANS=["Base","Conforto","Premium"]
ROLES=[r.value for r in Role]
PERMISSIONS=[p.value for p in Permission]
COV=["Internamento Hospitalar","Ambulatório","Maternidade e Parto","Urgência e Emergência Médica","Estomatologia","Óptica","Medicina Preventiva / Check-up Anual","Cobertura no Estrangeiro"]

FORM_SCHEMAS={
"product.plans":{"sections":[{"key":"plans","label":"Planos","repeatable":True,"fields":[f("code","Código","text",True),f("name","Nome","text",True),f("description","Descrição","textarea"),f("active","Ativo","boolean",True),f("default_copayment_percent","Co-participação padrão (%)","decimal")]}]},
"product.coverages":{"sections":[{"key":"coverages","label":"Coberturas","repeatable":True,"fields":[f("code","Código","text",True),f("name","Cobertura","text",True),f("included_in_plans","Planos","multiselect",options=PLANS),f("optional","Opcional","boolean"),f("enabled","Disponível","boolean",True),f("description","Descrição","textarea")]}]},
"product.capitals_sublimits":{"sections":[{"key":"items","label":"Capitais","repeatable":True,"fields":[f("plan","Plano","select",True,PLANS),f("coverage","Cobertura","select",True,COV),f("annual_capital","Capital anual","money"),f("sublimit","Sublimite","money"),f("per_event_limit","Limite por evento","money"),f("per_day_limit","Limite por dia","money"),f("quantity_limit","Limite de quantidade","integer")]}]},
"product.member_participation":{"sections":[{"key":"items","label":"Co-participações","repeatable":True,"fields":[f("plan","Plano","select",True,PLANS),f("coverage","Cobertura","select",True,COV),f("fixed_copayment","Copagamento fixo","money"),f("reimbursement_percent","Comparticipação (%)","decimal"),f("annual_deductible","Franquia anual","money"),f("event_deductible","Franquia por evento","money"),f("annual_cap","Teto anual","money")]}]},
"product.waiting_periods":{"sections":[{"key":"items","label":"Carências","repeatable":True,"fields":[f("plan","Plano (vazio = todos os planos)","select",False,PLANS,help="Uma linha com plano prevalece sobre a linha sem plano da mesma cobertura"),f("coverage","Cobertura","select",True,COV),f("individual_days","Individual (dias)","integer"),f("group_days","Grupo (dias)","integer"),f("accident_exempt","Dispensa em acidente","boolean")]}]},
"product.age_limits":{"sections":[{"key":"items","label":"Idades","repeatable":True,"fields":[f("plan","Plano (vazio = todos os planos)","select",False,PLANS,help="Uma linha com plano prevalece sobre a linha sem plano"),f("entry_min_age","Entrada mínima","integer"),f("entry_max_age","Entrada máxima","integer"),f("renewal_max_age","Renovação máxima","integer")]}]},
"product.exclusions":{"sections":[{"key":"items","label":"Exclusões","repeatable":True,"fields":[f("code","Código","text"),f("text","Texto","textarea",True),f("active","Ativa","boolean",True),f("applies_to","Planos","multiselect",options=PLANS)]}]},
"pricing.reference_premiums":{"sections":[{"key":"settings","label":"Configuração","fields":[f("currency_code","Moeda","select",True,["AOA","USD"])]},{"key":"premiums","label":"Prémios","repeatable":True,"fields":[f("age_from","Idade inicial","integer",True),f("age_to","Idade final","integer"),f("plan","Plano","select",True,PLANS),f("annual_premium","Prémio anual","money",True)]}]},
"pricing.factors":{"sections":[{"key":"factors","label":"Fatores","repeatable":True,"fields":[f("code","Código","text",True),f("dimension","Dimensão","text",True),f("condition","Condição","text",True),f("factor","Multiplicador","decimal",True)]}]},
"pricing.adjustments":{"sections":[{"key":"rules","label":"Agravamentos/descontos","repeatable":True,"fields":[f("code","Código","text",True),f("description","Descrição","text",True),f("type","Tipo","select",True,["PERCENTAGE","FIXED"]),f("value","Valor","decimal",True),f("sign","Efeito","select",True,["SURCHARGE","DISCOUNT"]),f("application_stage","Momento","select",options=["SUBSCRIPTION","RENEWAL","QUOTE"]),f("max_value","Limite máximo","decimal")]}]},
"pricing.taxes_fees":{"sections":[{"key":"charges","label":"Impostos/taxas","repeatable":True,"fields":[f("code","Código","text",True),f("description","Descrição","text",True),f("category","Categoria","select",True,["TAX","FEE"]),f("type","Tipo","select",True,["PERCENTAGE","FIXED"]),f("value","Valor","decimal",True),f("included_in_premium","Incluído no prémio","boolean",True)]}]},
"underwriting.acceptance_rules":{"sections":[{"key":"rules","label":"Aceitação","repeatable":True,"fields":[f("condition","Condição","text",True),f("age_from","Idade a partir de","integer"),f("age_to","Idade até","integer"),f("relationship","Relação (código)","text"),f("decision","Decisão","select",True,["AUTO_ACCEPT","MEDICAL_REVIEW","TECHNICAL_REVIEW","DECLINE"]),f("notes","Observações","textarea")]}]},
"underwriting.pre_existing_conditions":{"sections":[{"key":"rules","label":"Pré-existentes","repeatable":True,"fields":[f("severity","Gravidade","select",True,["LOW","MODERATE","MODERATE_HIGH","HIGH"]),f("treatment","Tratamento","select",True,["EXCLUSION_TOTAL","EXCLUSION_SPECIFIC","WAITING_PERIOD","SURCHARGE","SUBLIMIT","FULL_ACCEPTANCE"]),f("waiting_days","Carência adicional","integer"),f("surcharge_percent","Agravamento (%)","decimal"),f("sublimit","Sublimite","money")]}]},
"underwriting.medical_review":{"sections":[{"key":"thresholds","label":"Análise médica","fields":[f("automatic_acceptance_max_age","Idade máxima automática","integer"),f("capital_review_threshold","Capital para análise","money"),f("questionnaire_required","Questionário obrigatório","boolean",True),f("clinical_documentation_required","Documentação clínica","boolean",True)]}]},
"group.rules":{"sections":[{"key":"group","label":"Grupo","fields":[f("minimum_members","Mínimo de pessoas","integer",True),f("below_minimum_behavior","Abaixo do mínimo","select",True,["INDIVIDUAL","DECLINE"]),f("mandatory_enrolment","Adesão obrigatória","boolean"),f("questionnaire_exemption_threshold","Dispensa de questionário acima de","integer"),f("experience_loss_ratio_threshold","Limite de sinistralidade (%)","decimal"),f("profit_share_percent","Quota devolvida (%)","decimal")]}]},
"renewal.rules":{"sections":[{"key":"renewal","label":"Renovação","fields":[f("automatic_renewal","Renovação automática","boolean",True),f("medical_inflation_percent","Inflação médica (%)","decimal"),f("update_capitals","Atualizar capitais","boolean"),f("update_tables","Atualizar tabelas","boolean"),f("loss_ratio_adjustment_enabled","Ajustar por sinistralidade","boolean"),f("continuity_without_new_waiting_period","Manter carências cumpridas","boolean")]}]},
"policy.endorsements":{"sections":[{"key":"endorsements","label":"Endosso de inclusão","fields":[f("day_count_basis","Base dos dias do pro-rata","select",options=["ACTUAL_PERIOD","FIXED_366","FIXED_365","FIXED_360"],labels={"ACTUAL_PERIOD":"Dias reais do período da apólice (366 em ano bissexto)","FIXED_366":"366 dias","FIXED_365":"365 dias","FIXED_360":"360 dias"}),f("minimum_premium","Prémio mínimo do endosso (Kz)","money"),f("apply_fractionation_loading","Aplicar encargo de fracionamento às prestações","boolean"),f("newborn_auto_inclusion_days","Recém-nascidos: inclusão automática até (dias após o nascimento; 0 = desligado)","integer"),f("acceptance_days","Prazo para o cliente aceitar (dias)","integer"),f("prepaid_period_charge","Período já pago pelas prestações anteriores","select",options=["IMMEDIATE","SPREAD"],labels={"IMMEDIATE":"Cobrar logo, na data de inclusão, a parte até à próxima prestação","SPREAD":"Repartir tudo pelas prestações que ainda vão vencer"})]}]},
"renewal.deadlines":{"sections":[{"key":"deadlines","label":"Prazos","fields":[f("prepare_days_before","Preparar proposta (dias)","integer"),f("acceptance_days","Prazo de aceitação (dias)","integer"),f("previous_policy_close","Fecho da anterior","select",options=["ON_RENEWAL_ACTIVATION","ON_RENEWAL_ISSUANCE","ON_EFFECTIVE_DATE","MANUAL"])]}]},
"proposal.documents":{"sections":[{"key":"documents","label":"Documentos","repeatable":True,"fields":[f("document_type","Tipo","select",True,["PROPOSAL","GENERAL_CONDITIONS","SPECIAL_CONDITIONS","BENEFITS_TABLE","POLICY","HEALTH_QUESTIONNAIRE","PRODUCT_MANUAL"]),f("required","Obrigatório","boolean",True),f("description","Descrição","textarea")]}]},
"proposal.texts":{"sections":[{"key":"texts","label":"Textos","repeatable":True,"fields":[f("code","Código","text",True),f("title","Título","text",True),f("text","Texto","textarea",True),f("active","Ativo","boolean",True)]}]},
"network.rules":{"sections":[{"key":"network","label":"Rede","fields":[f("network_enabled","Rede convencionada","boolean",True),f("free_choice_enabled","Livre escolha/reembolso","boolean",True),f("geographical_scope","Âmbito geográfico","text"),f("pre_authorization_required","Pré-autorização","boolean")]}]},
"foreign_coverage.rules":{"sections":[{"key":"foreign","label":"Estrangeiro","fields":[f("enabled","Disponível","boolean",True),f("countries","Países","multiselect",options=["Portugal","África do Sul","Brasil","Namíbia"]),f("currency","Moeda","select",options=["KZ","USD"]),f("prior_approval","Aprovação prévia","boolean",True),f("fx_rule","Regra cambial","textarea")]}]},
"security.approval_rules":{"sections":[{"key":"approval","label":"Aprovação","fields":[f("four_eyes_required","Dupla aprovação","boolean",True),f("editable_roles","Perfis que editam configuração (ADMIN sempre pode)","multiselect",options=ROLES),f("approval_roles","Perfis que aprovam (ADMIN sempre pode)","multiselect",options=ROLES)]}]}
,"security.role_permissions":{"sections":[{"key":"roles","label":"Permissões por perfil","repeatable":True,"fields":[f("role","Perfil","select",True,ROLES),f("permissions","Permissões","multiselect",True,PERMISSIONS)]}]}
,"proposal.branding":{"sections":[{"key":"branding","label":"Identidade visual","fields":[f("company_name","Nome da empresa","text",True),f("primary_color","Cor principal (#RRGGBB)","text"),f("tagline","Lema","text"),f("footer_text","Rodapé","textarea")]}]}
}
FORM_SCHEMAS["pricing.fractionation"]={"sections":[{"key":"installments","label":"Fracionamento","repeatable":True,"fields":[
    f("frequency","Periodicidade","select",True,["ANUAL","SEMESTRAL","TRIMESTRAL","MENSAL"]),
    f("loading","Encargo (fração, ex.: 0.04 = 4 %)","decimal",True,help="Acréscimo ao prémio anual quando pago nesta periodicidade; aplica-se a todas as apólices"),
]}]}

# Políticas de negócio que usam o ciclo versionado de BusinessConfiguration.
# Os valores são editáveis; o backend valida os limites e a forma do contrato.
FORM_SCHEMAS["quote.discount_approval"]={"sections":[{"key":"discount_approval","label":"Aprovação de descontos","fields":[
    f("approval_threshold_percent","A partir de que desconto exige aprovação (% do prémio)","decimal",True),
    f("approver_permission","Permissão de aprovação","select",True,["quote:discount:approve"]),
    f("approval_required_above_threshold","Exigir aprovação acima do limite","boolean",True),
]}]}
FORM_SCHEMAS["service.sla"]={"sections":[
    {"key":"calendar","label":"Calendário de atendimento","fields":[
        f("time_zone","Fuso horário IANA","text",True,help="Ex.: Africa/Luanda"),
        f("business_days","Dias úteis","multiselect",True,["MON","TUE","WED","THU","FRI","SAT","SUN"]),
        f("business_start","Abertura (HH:MM)","text",True),
        f("business_end","Fecho (HH:MM)","text",True),
        f("holidays","Feriados (uma data AAAA-MM-DD por linha)","textarea"),
    ]},
    {"key":"targets","label":"Metas por prioridade","repeatable":True,"fields":[
        f("priority","Prioridade","select",True,["LOW","NORMAL","HIGH","URGENT"]),
        f("first_response_minutes","Meta de primeira resposta (minutos)","integer",True),
        f("resolution_minutes","Meta de resolução (minutos)","integer",True),
        f("business_hours_only","Contar apenas horário de expediente","boolean",True),
        f("pause_while_awaiting_customer","Pausar relógio enquanto aguarda resposta do cliente","boolean",True),
    ]},
    {"key":"request_priorities","label":"Prioridade por tipo de pedido","repeatable":True,"fields":[
        f("request_type","Tipo de pedido","select",True,sorted(portal_requests.REQUEST_TYPES)),
        f("priority","Prioridade","select",True,["LOW","NORMAL","HIGH","URGENT"]),
    ]},
]}
FORM_SCHEMAS["service.satisfaction"]={"sections":[{"key":"satisfaction","label":"Escala de satisfação","fields":[
    f("enabled","Recolher avaliação","boolean",True),
    f("minimum_score","Pontuação mínima","integer",True),
    f("maximum_score","Pontuação máxima","integer",True),
    f("question","Pergunta apresentada","text",True),
    f("survey_trigger","Momento de envio","select",True,["ON_RESOLUTION","MANUAL"]),
]}]}
FORM_SCHEMAS["pricing.experience_rating"]={"sections":[{"key":"experience_rating","label":"Tarifação pela experiência de sinistralidade","fields":[
    f("enabled","Ativo","boolean",True),
    f("lookback_months","Meses de histórico","integer",True),
    f("metric","Métrica","select",True,["LOSS_RATIO","CLAIMS_FREQUENCY","CLAIMS_SEVERITY"]),
    f("target_value","Valor de referência da métrica","decimal",True),
    f("weight_percent","Peso no ajuste (%)","decimal",True),
    f("minimum_factor","Fator mínimo","decimal",True),
    f("maximum_factor","Fator máximo","decimal",True),
]}]}
FORM_SCHEMAS["quote.scenario_comparison"]={"sections":[{"key":"scenario_comparison","label":"Comparação de cenários","fields":[
    f("margin_method","Método da margem","select",True,["PREMIUM_MINUS_EXPECTED_CLAIMS"]),
    f("expense_ratio_percent","Despesas (%)","decimal"),
    f("commission_percent","Comissão (%)","decimal"),
    f("radar_dimensions","Dimensões do radar","multiselect",True,["PREMIUM","COVERAGE","DEDUCTIBLE","COPAYMENT","MARGIN","LOSS_RATIO"]),
]}]}
FORM_SCHEMAS["claims.projections"]={"sections":[{"key":"projections","label":"Projeções","fields":[
    f("method","Método de projeção","select",True,["TREND","CONFIGURED_GROWTH","ACTUARIAL_MODEL"]),
    f("horizon_months","Horizonte (meses)","integer",True),
    f("period","Agregação","select",True,["MONTHLY","QUARTERLY"]),
    f("annual_trend_percent","Tendência anual (%)","decimal"),
]}]}

def _condition_fields(suffix,optional):
    n=" (2.ª condição, opcional)" if suffix else ""
    return [
        f("field"+suffix,"Quando"+n,"select",not optional,list(cr.FIELDS),cr.FIELD_LABELS),
        f("operator"+suffix,"Comparação","select",not optional,list(cr.OPERATORS),cr.OPERATOR_LABELS),
        f("value"+suffix,"Valor","text",not optional,help="Número (ex.: 60), ou a opção escolhida (ex.: Premium, GROUP, SPOUSE)"),
        f("value_to"+suffix,"Até (só para 'está entre')","text"),
    ]

RULES_CUSTOM={"sections":[{"key":"rules","label":"Regras (Quando… então…)","repeatable":True,"fields":[
    f("name","Nome da regra","text",True,help="Ex.: Agravamento para maiores de 60 anos"),
    f("active","Ativa","boolean",True),
    f("scope","Aplica-se a","select",True,list(cr.SCOPES),cr.SCOPE_LABELS),
    *_condition_fields("",False),
    *_condition_fields("_2",True),
    f("stage","Etapa","select",False,list(cr.STAGES),cr.STAGE_LABELS,help="Deduzida da ação (elegibilidade, preço, aceitação, validação ou fluxo); se indicada, tem de coincidir"),
    f("action","Então","select",True,list(cr.ACTIONS),cr.ACTION_LABELS),
    f("amount","Valor da ação","decimal",help="Percentagem, multiplicador ou valor em moeda, conforme a ação; não é preciso para análise/recusa/aviso"),
    f("role","Perfil que aprova","select",False,list(cr.APPROVAL_ROLES),{"SUBSCRIPTION_MANAGER":"Gestor de subscrição","ADMIN":"Administrador"},help="Só para 'Aprovação só por um perfil'"),
    f("message","Mensagem para o utilizador","textarea",help="Aparece nos requisitos da cotação e no histórico do cálculo"),
    f("products","Aplica-se aos produtos (vazio = todos)","multiselect",help="Códigos dos produtos a que a regra se aplica"),
    f("order","Ordem de aplicação","integer",help="As regras de prémio aplicam-se por esta ordem (1, 2, 3…)"),
    f("code","Código (opcional)","text",help="Identificador curto; se vazio é gerado"),
]}]}
RULES_CUSTOM["meta"]=cr.field_catalog()
FORM_SCHEMAS["rules.custom"]=RULES_CUSTOM

FORM_SCHEMAS["product.minimum_premium"]={"sections":[{"key":"items","label":"Prémio mínimo","repeatable":True,"fields":[
    f("plan","Plano (vazio = todos os planos)","select",False,PLANS,help="Uma linha com plano prevalece sobre a linha sem plano"),
    f("annual_minimum","Prémio mínimo anual da apólice (Kz)","money",help="O prémio anual total nunca fica abaixo deste valor"),
    f("per_person_minimum","Prémio mínimo anual por pessoa segura (Kz)","money",help="Multiplica-se pelo número de pessoas seguras"),
]}]}

def get_form_schema(key):
    from apps.business_config.domain.scope import base_key

    key=base_key(key)
    return FORM_SCHEMAS.get(key,{"sections":[{"key":"value","label":"Configuração","fields":[f("value","Valor","json",True)]}]})
