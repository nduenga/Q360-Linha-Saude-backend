"""Documentation-only serializers for the endpoints whose `Response` is built
from a plain dict (so the static analysis cannot see a serializer). They are
never used to validate or render anything at runtime: they only describe, in
the OpenAPI contract, exactly what those endpoints return/accept. Keep them in
step with the services that build the dicts — `tests/integration/
test_openapi_contract.py` guards that every route is documented."""
from __future__ import annotations

from rest_framework import serializers as s

from apps.product.interfaces.serializers import PlanBenefitSerializer
from apps.quote.interfaces.serializers import QuoteAdjustmentSerializer, QuoteSerializer

Money = lambda **kw: s.CharField(help_text="Valor monetário/decimal exato serializado como string (ex.: '1200.00').", **kw)  # noqa: E731


class Warning(s.Serializer):  # noqa: A001 - OpenAPI component name
    code = s.CharField()
    message = s.CharField()
    scope = s.CharField(required=False)


# ---------------------------------------------------------------- generic
class StatusOk(s.Serializer):
    status = s.CharField(help_text="'ok' ou 'unavailable'.")


class ConfigurationHeader(s.Serializer):
    id = s.UUIDField()
    code = s.CharField()
    versionNo = s.IntegerField()
    effectiveFrom = s.DateField()
    effectiveTo = s.DateField(allow_null=True)
    status = s.ChoiceField(choices=["DRAFT", "PUBLISHED", "RETIRED"])
    checksum = s.CharField(allow_null=True)


class ConfigurationVersion(ConfigurationHeader):
    publishedAt = s.DateTimeField(allow_null=True)
    publishedBy = s.CharField(allow_null=True)
    createdAt = s.DateTimeField(allow_null=True)


class ConfigurationChange(s.Serializer):
    kind = s.ChoiceField(choices=["ADDED", "REMOVED", "CHANGED"])
    key = s.CharField()
    before = s.JSONField(allow_null=True)
    after = s.JSONField(allow_null=True)


ConfigurationDiff = type(
    "ConfigurationDiff",
    (s.Serializer,),
    {"from": ConfigurationHeader(), "to": ConfigurationHeader(), "changes": ConfigurationChange(many=True),
     "__doc__": "Diferenças entre duas versões do mesmo código."},
)


class ConfigurationRollbackResult(s.Serializer):
    restoredFrom = ConfigurationHeader()
    current = ConfigurationHeader()
    retired = ConfigurationHeader(many=True)


class ImpactRow(s.Serializer):
    quoteId = s.UUIDField()
    quoteNumber = s.CharField(allow_null=True)
    before = Money()
    after = Money()
    delta = Money()
    deltaPercent = s.CharField(allow_null=True)


class ImpactSimulationRequest(s.Serializer):
    limit = s.IntegerField(required=False, min_value=1, max_value=200, default=50, help_text="N.º de cotações recentes a repreciar.")


class ImpactSimulation(s.Serializer):
    configType = s.CharField()
    candidate = ConfigurationHeader()
    sampled = s.IntegerField()
    compared = s.IntegerField()
    skipped = s.ListField(child=s.DictField(child=s.CharField()))
    totals = s.DictField(child=s.CharField(allow_null=True), help_text="before, after, delta, deltaPercent.")
    deltaPercent = s.DictField(child=s.CharField(allow_null=True), help_text="average, max, min.")
    mostAffected = ImpactRow(many=True)


# ------------------------------------------------------ system parameters
class SystemParameter(s.Serializer):
    code = s.CharField()
    valueType = s.ChoiceField(choices=["INTEGER", "DECIMAL", "TEXT", "BOOLEAN"])
    category = s.ChoiceField(
        choices=["OPERATIONAL", "STRUCTURAL", "LEGAL", "LIMIT", "MARKET"],
        help_text="OPERATIONAL: o GTE altera; STRUCTURAL: só por evolução do sistema; LEGAL: valor legal; LIMIT: teto do "
                  "fornecedor; MARKET: dado de mercado (fornecedor).",
    )
    level = s.ChoiceField(
        choices=["PLATFORM_MANDATORY", "PLATFORM_DEFAULT"],
        help_text="PLATFORM_MANDATORY: vale o valor do fornecedor; PLATFORM_DEFAULT: o tenant ajusta dentro dos limites.",
    )
    value = s.JSONField(allow_null=True)
    source = s.ChoiceField(choices=["TENANT", "PLATFORM", "CODE_DEFAULT"], help_text="De onde vem o valor em vigor.")
    default = s.JSONField(allow_null=True, help_text="Valor geral (do fornecedor ou do código) usado sem ajuste do tenant.")
    platformVersionNo = s.IntegerField(help_text="Versão geral em vigor (0 = valor do código).")
    isDefault = s.BooleanField()
    tenantValueOutOfLimits = s.BooleanField(help_text="O valor do tenant ficou fora dos limites do fornecedor e não se aplica.")
    description = s.CharField()
    unit = s.CharField(allow_null=True)
    constraints = s.DictField(child=s.JSONField(allow_null=True))
    usedBy = s.CharField(allow_null=True)
    editable = s.BooleanField()
    rowVersion = s.IntegerField()
    updatedBy = s.CharField(allow_null=True)
    updatedAt = s.DateTimeField(allow_null=True)


class SystemParameterUpdate(s.Serializer):
    value = s.JSONField()
    rowVersion = s.IntegerField(min_value=0)
    reason = s.CharField(help_text="Motivo obrigatório (mínimo 10 caracteres).")


class SystemParameterRollbackRequest(s.Serializer):
    revisionNo = s.IntegerField(min_value=1)
    reason = s.CharField(help_text="Motivo obrigatório (mínimo 10 caracteres).")


class SystemParameterRevision(s.Serializer):
    revisionNo = s.IntegerField()
    action = s.CharField()
    value = s.JSONField(allow_null=True)
    reason = s.CharField(allow_null=True)
    changedBy = s.CharField()
    createdAt = s.DateTimeField()


class PlatformParameterVersion(s.Serializer):
    code = s.CharField()
    versionNo = s.IntegerField()
    status = s.ChoiceField(choices=["PENDING_APPROVAL", "PUBLISHED", "REJECTED"])
    action = s.CharField(help_text="CREATED ou ROLLBACK_TO_<n>.")
    value = s.JSONField(allow_null=True)
    minimum = s.JSONField(allow_null=True, help_text="Limite mínimo imposto aos tenants (só PLATFORM_DEFAULT).")
    maximum = s.JSONField(allow_null=True, help_text="Limite máximo imposto aos tenants (só PLATFORM_DEFAULT).")
    effectiveFrom = s.DateTimeField(allow_null=True)
    inEffect = s.BooleanField()
    reason = s.CharField()
    legalReference = s.CharField(allow_null=True, help_text="Fonte legal (parâmetros LEGAL).")
    sourceUrl = s.CharField(allow_null=True)
    createdBy = s.CharField()
    createdAt = s.DateTimeField(allow_null=True)
    decidedBy = s.CharField(allow_null=True)
    decidedAt = s.DateTimeField(allow_null=True)
    decisionNote = s.CharField(allow_null=True)


class PlatformParameter(s.Serializer):
    code = s.CharField()
    valueType = s.ChoiceField(choices=["INTEGER", "DECIMAL", "TEXT", "BOOLEAN"])
    category = s.ChoiceField(choices=["OPERATIONAL", "STRUCTURAL", "LEGAL", "LIMIT", "MARKET"])
    level = s.ChoiceField(choices=["PLATFORM_MANDATORY", "PLATFORM_DEFAULT"])
    value = s.JSONField(allow_null=True, help_text="Valor geral em vigor.")
    codeDefault = s.JSONField(allow_null=True)
    isCodeDefault = s.BooleanField()
    versionNo = s.IntegerField()
    effectiveFrom = s.DateTimeField(allow_null=True)
    legalReference = s.CharField(allow_null=True, help_text="Fonte da versão em vigor.")
    sourceUrl = s.CharField(allow_null=True)
    requiresLegalReference = s.BooleanField(help_text="true nos parâmetros LEGAL: propor exige legalReference.")
    description = s.CharField()
    unit = s.CharField(allow_null=True)
    usedBy = s.CharField(allow_null=True)
    hardLimits = s.DictField(child=s.JSONField(allow_null=True))
    tenantLimits = s.DictField(child=s.JSONField(allow_null=True), allow_null=True)
    allowedValues = s.ListField(child=s.JSONField(), allow_null=True, help_text="Valores que o motor sabe executar.")
    tenantEditable = s.BooleanField()
    pendingVersions = PlatformParameterVersion(many=True)
    tenantOverrides = s.DictField(child=s.IntegerField(), required=False, help_text="count, outOfLimits.")


class PlatformParameterProposal(s.Serializer):
    value = s.JSONField()
    minimum = s.JSONField(required=False, allow_null=True)
    maximum = s.JSONField(required=False, allow_null=True)
    effectiveFrom = s.DateTimeField(required=False, allow_null=True, help_text="Vigência; por omissão, a aprovação.")
    reason = s.CharField(help_text="Motivo obrigatório (mínimo 10 caracteres).")


class PlatformParameterDecision(s.Serializer):
    note = s.CharField(required=False, allow_null=True, help_text="Obrigatória (mínimo 10 caracteres) ao rejeitar.")


class PlatformParameterRollbackRequest(s.Serializer):
    versionNo = s.IntegerField(min_value=1)
    reason = s.CharField(help_text="Motivo obrigatório (mínimo 10 caracteres).")


class PlatformParameterProposalWithSource(PlatformParameterProposal):
    legalReference = s.CharField(required=False, allow_null=True,
                                 help_text="Fonte legal (diploma, artigo). Obrigatória nos parâmetros LEGAL.")
    sourceUrl = s.CharField(required=False, allow_null=True, help_text="Ligação https para o texto da fonte.")


class ReferenceTableColumn(s.Serializer):
    code = s.CharField()
    label = s.CharField(required=False)
    type = s.ChoiceField(choices=["NUMBER", "TEXT"])


class ReferenceTableVersion(s.Serializer):
    code = s.CharField()
    versionNo = s.IntegerField()
    status = s.ChoiceField(choices=["PENDING_APPROVAL", "PUBLISHED", "REJECTED"])
    name = s.CharField()
    description = s.CharField(allow_null=True)
    keyColumn = s.CharField()
    columns = ReferenceTableColumn(many=True)
    rowCount = s.IntegerField()
    rows = s.ListField(child=s.DictField(), required=False, help_text="Só no detalhe.")
    source = s.CharField(allow_null=True)
    effectiveFrom = s.DateTimeField(allow_null=True)
    inEffect = s.BooleanField()
    reason = s.CharField()
    createdBy = s.CharField()
    createdAt = s.DateTimeField(allow_null=True)
    decidedBy = s.CharField(allow_null=True)
    decidedAt = s.DateTimeField(allow_null=True)
    decisionNote = s.CharField(allow_null=True)


class ReferenceTableProposal(s.Serializer):
    code = s.CharField(help_text="Minúsculas, números e '_' (ex.: provincias).")
    name = s.CharField()
    description = s.CharField(required=False, allow_null=True)
    keyColumn = s.CharField()
    columns = ReferenceTableColumn(many=True)
    rows = s.ListField(child=s.DictField(), help_text="Até 5000 linhas; chaves únicas.")
    source = s.CharField(required=False, allow_null=True)
    effectiveFrom = s.DateTimeField(required=False, allow_null=True)
    reason = s.CharField(help_text="Motivo obrigatório (mínimo 10 caracteres).")


class TemplateVersion(s.Serializer):
    code = s.CharField()
    versionNo = s.IntegerField()
    status = s.ChoiceField(choices=["PENDING_APPROVAL", "PUBLISHED", "REJECTED"])
    kind = s.ChoiceField(choices=["PRODUCT", "ACTUARIAL_MODEL", "FORMULA_SET", "COVERAGE_LIBRARY"])
    kindLabel = s.CharField()
    name = s.CharField()
    description = s.CharField(allow_null=True)
    segment = s.CharField(allow_null=True)
    configKeys = s.ListField(child=s.CharField())
    marketProducts = s.BooleanField()
    content = s.DictField(required=False, help_text="configurations {configKey: valor} e marketProducts (só no detalhe).")
    source = s.CharField(allow_null=True)
    isLatestPublished = s.BooleanField()
    reason = s.CharField()
    createdBy = s.CharField()
    createdAt = s.DateTimeField(allow_null=True)
    decidedBy = s.CharField(allow_null=True)
    decidedAt = s.DateTimeField(allow_null=True)
    decisionNote = s.CharField(allow_null=True)


class TemplateProposal(s.Serializer):
    code = s.CharField()
    kind = s.ChoiceField(choices=["PRODUCT", "ACTUARIAL_MODEL", "FORMULA_SET", "COVERAGE_LIBRARY"])
    name = s.CharField()
    description = s.CharField(required=False, allow_null=True)
    segment = s.ChoiceField(choices=["SAU", "SAG"], required=False, allow_null=True)
    content = s.DictField(help_text="{configurations: {configKey: valor}, marketProducts: bool}")
    source = s.CharField(required=False, allow_null=True)
    reason = s.CharField(help_text="Motivo obrigatório (mínimo 10 caracteres).")


class TemplateAdoptRequest(s.Serializer):
    effectiveFrom = s.DateField(required=False, allow_null=True, help_text="Vigência dos rascunhos; por omissão hoje.")


# ------------------------------------------------- fórmulas: teste e catálogo
class FormulaExplanationStep(s.Serializer):
    step = s.IntegerField()
    expression = s.CharField(help_text="Subexpressão calculada neste passo.")
    operation = s.CharField(help_text="VARIABLE, CONSTANT, tabela, + - * / **, min, max, abs, round.")
    operands = s.ListField(child=s.CharField())
    result = s.CharField()


class FormulaTestResult(s.Serializer):
    valid = s.BooleanField()
    result = s.CharField(required=False, help_text="Só quando valid=true.")
    variables = s.ListField(child=s.CharField(), required=False)
    steps = FormulaExplanationStep(many=True, required=False, help_text="Cálculo passo a passo.")
    error = s.CharField(required=False, help_text="Só quando valid=false (HTTP 400).")


class FormulaVariable(s.Serializer):
    token = s.CharField(help_text="Nome a usar na expressão.")
    label = s.CharField()
    source = s.ChoiceField(choices=["SYSTEM", "PARAMETER", "AUXILIARY", "PLATFORM_CONSTANT", "RULE_FIELD", "PRODUCT_GROUP",
                                    "PRODUCT_OPTION", "PRODUCT_FIELD", "PRODUCT_FORMULA", "PRODUCT_SYSTEM"])
    usableIn = s.ListField(child=s.CharField(), help_text="PRICING_FORMULAS:PERSON|QUOTE, PRODUCT_FORMULAS, RULE_CONDITIONS.")
    unit = s.CharField(required=False, allow_null=True)
    value = s.CharField(required=False, allow_null=True, help_text="Parâmetros e constantes do fornecedor.")
    parameter = s.CharField(required=False, help_text="Constantes: código do parâmetro do fornecedor.")
    readOnly = s.BooleanField(required=False)
    expression = s.CharField(required=False, help_text="Valores auxiliares.")


class FormulaReferenceTable(s.Serializer):
    code = s.CharField()
    name = s.CharField()
    versionNo = s.IntegerField()
    keyColumn = s.CharField()
    columns = s.ListField(child=s.DictField())
    example = s.CharField()


class FormulaVariablesCatalog(s.Serializer):
    variables = FormulaVariable(many=True)
    functions = s.ListField(child=s.DictField(child=s.CharField()))
    operators = s.ListField(child=s.CharField())
    referenceTables = FormulaReferenceTable(many=True)
    sources = s.DictField(child=s.JSONField(allow_null=True),
                          help_text="pricingFormulas, pricingFormulasError, productSetup, productSetupError.")


class PlatformFormulaEngine(s.Serializer):
    pricingFormulas = s.DictField(help_text="Catálogo do motor de fórmulas de tarifação (fases, funções, variáveis…).")
    productFormulas = s.DictField(help_text="systemVariables das fórmulas de produto.")
    rules = s.DictField(help_text="Campos, operadores, etapas e ações das regras «Quando… então…».")
    platformConstants = s.ListField(child=s.DictField(), help_text="name, parameter, unit, description.")
    limits = s.DictField(child=s.IntegerField())


# ------------------------------------------- camada geral: listas e detalhes
class ReferenceTableSummary(s.Serializer):
    code = s.CharField()
    name = s.CharField()
    inEffect = ReferenceTableVersion(allow_null=True)
    pendingVersions = ReferenceTableVersion(many=True)


class ReferenceTableDetail(s.Serializer):
    code = s.CharField()
    inEffect = ReferenceTableVersion(allow_null=True, help_text="Com as linhas.")
    pendingVersions = ReferenceTableVersion(many=True)


class TemplateSummary(s.Serializer):
    code = s.CharField()
    name = s.CharField()
    kind = s.CharField()
    published = TemplateVersion(allow_null=True)
    pendingVersions = TemplateVersion(many=True)


class TemplateDetail(s.Serializer):
    code = s.CharField()
    published = TemplateVersion(allow_null=True, help_text="Com o conteúdo.")
    pendingVersions = TemplateVersion(many=True)


class TemplateAdoptDraft(s.Serializer):
    configKey = s.CharField()
    configurationId = s.UUIDField()
    versionNo = s.IntegerField()
    status = s.CharField()


class TemplateAdoptResult(s.Serializer):
    template = s.DictField(help_text="code, versionNo, name.")
    effectiveFrom = s.DateField()
    createdDrafts = TemplateAdoptDraft(many=True)
    marketProducts = s.DictField(allow_null=True, help_text="Relatório da criação dos produtos de mercado, se pedida.")
    next = s.CharField()


# ------------------------------------------------------- tarifa por produto
class TariffConfigVersion(s.Serializer):
    configurationId = s.UUIDField()
    versionNo = s.IntegerField()
    status = s.CharField()
    effectiveFrom = s.DateField(allow_null=True)
    effectiveTo = s.DateField(allow_null=True)
    createdBy = s.CharField(allow_null=True)
    rowVersion = s.IntegerField()


class TariffConfigState(s.Serializer):
    configKey = s.CharField()
    published = TariffConfigVersion(allow_null=True, help_text="Em vigor hoje.")
    draft = TariffConfigVersion(allow_null=True)
    pending = TariffConfigVersion(allow_null=True)
    scheduled = TariffConfigVersion(allow_null=True, help_text="Publicada com vigência futura.")


class TariffStage(s.Serializer):
    order = s.IntegerField()
    code = s.ChoiceField(choices=["PURE_PREMIUM", "RISK_FACTORS", "PERSON_RULES", "PERSON_FORMULAS", "LOADINGS",
                                  "ADJUSTMENTS", "LEGAL_TAXES", "CHARGES", "QUOTE_FORMULAS", "PRODUCT_SETUP",
                                  "FRACTIONATION"])
    label = s.CharField()
    owner = s.ChoiceField(choices=["CODE", "PLATFORM", "TENANT"])
    editable = s.BooleanField()
    scope = s.ChoiceField(choices=["TENANT", "PRODUCT"], help_text="TENANT: a chave vale para todos os produtos.")
    configurations = TariffConfigState(many=True)
    platformParameters = s.ListField(child=s.DictField(), help_text="code, value, versionNo, unit.")
    summary = s.DictField(help_text="Resumo do passo (depende do passo).")


class ProductTariff(s.Serializer):
    productId = s.UUIDField()
    productCode = s.CharField()
    productName = s.CharField()
    plans = s.ListField(child=s.DictField(), help_text="id, code, name, status.")
    engine = s.DictField(help_text="owner=CODE, order, rounding, structure.")
    stages = TariffStage(many=True)
    openDrafts = TariffConfigVersion(many=True)
    platformVersions = s.DictField(child=s.IntegerField())


class TariffSimulationStep(s.Serializer):
    sequence = s.IntegerField()
    stepCode = s.CharField()
    ruleCode = s.CharField(allow_null=True)
    owner = s.ChoiceField(choices=["CODE", "PLATFORM", "TENANT"])
    input = s.JSONField(allow_null=True)
    output = s.JSONField(allow_null=True)
    message = s.CharField(allow_null=True)


class TariffSimulationResult(s.Serializer):
    productId = s.UUIDField()
    planId = s.UUIDField()
    referenceDate = s.DateField()
    currencyCode = s.CharField()
    totalAmount = s.CharField()
    installments = s.DictField(child=s.CharField(), help_text="Prestação por frequência (ANUAL, SEMESTRAL…).")
    components = s.ListField(child=s.DictField(), help_text="Componentes do cálculo, cada um com owner.")
    appliedDrafts = TariffConfigVersion(many=True)
    versions = s.DictField()
    steps = TariffSimulationStep(many=True)
    persisted = s.BooleanField(help_text="Sempre false: a simulação não grava nada.")


# ------------------------------------------------------------- aprovações
class PendingApprovalItem(s.Serializer):
    configurationId = s.UUIDField()
    configKey = s.CharField()
    label = s.CharField()
    area = s.ChoiceField(choices=["ORGANIZATION", "PRODUCTS", "TARIFF", "RULES", "PARAMETERS", "DOCUMENTS"])
    areaLabel = s.CharField()
    versionNo = s.IntegerField()
    effectiveFrom = s.DateField(allow_null=True)
    createdBy = s.CharField(allow_null=True)
    submittedAt = s.DateTimeField(allow_null=True)
    againstVersionNo = s.IntegerField(allow_null=True, help_text="Versão publicada com que se compara.")
    changeCount = s.IntegerField(allow_null=True)
    changes = s.ListField(child=s.DictField(), help_text="path, change (ADDED/REMOVED/CHANGED), before, after; até 50.")
    isNew = s.BooleanField()
    canApprove = s.BooleanField()
    cannotApproveReason = s.CharField(allow_null=True)


class PendingApprovals(s.Serializer):
    total = s.IntegerField()
    byArea = s.DictField(child=s.IntegerField())
    items = PendingApprovalItem(many=True)


class PendingApprovalsCount(s.Serializer):
    total = s.IntegerField()
    canApprove = s.IntegerField()
    byArea = s.DictField(child=s.IntegerField())


# ------------------------------------------------------------ benefits/plans
class BenefitImportRequest(s.Serializer):
    file = s.FileField(help_text="CSV ou XLSX com as colunas code, name, category, description, status, definition_json.")
    dryRun = s.BooleanField(required=False, default=False)


class BenefitImportError(s.Serializer):
    row = s.IntegerField()
    code = s.CharField(allow_null=True)
    message = s.CharField()


class BenefitImportResult(s.Serializer):
    dryRun = s.BooleanField()
    created = s.ListField(child=s.CharField())
    updated = s.ListField(child=s.CharField())
    errors = BenefitImportError(many=True)


class BenefitUsagePlan(s.Serializer):
    planId = s.UUIDField()
    planCode = s.CharField()
    planName = s.CharField()
    planStatus = s.CharField()
    productId = s.UUIDField()
    productCode = s.CharField()
    inclusion = s.ChoiceField(choices=["INCLUDED", "OPTIONAL"])


class BenefitUsage(s.Serializer):
    benefitId = s.UUIDField()
    plansUsingBenefit = s.IntegerField()
    plans = BenefitUsagePlan(many=True)


class PlanValidationIssue(s.Serializer):
    code = s.CharField()
    message = s.CharField()
    scope = s.CharField()


class PlanValidation(s.Serializer):
    planId = s.UUIDField()
    valid = s.BooleanField()
    errors = PlanValidationIssue(many=True)
    warnings = PlanValidationIssue(many=True)


class MarketTemplatePlanReport(s.Serializer):
    planCode = s.CharField()
    valid = s.BooleanField()
    errors = PlanValidationIssue(many=True)
    warningCount = s.IntegerField()
    warnings = PlanValidationIssue(many=True)


class MarketTemplatesResult(s.Serializer):
    createdProducts = s.ListField(child=s.CharField())
    createdPlans = s.ListField(child=s.CharField())
    skippedPlans = s.ListField(child=s.CharField())
    plans = MarketTemplatePlanReport(many=True)
    indicative = s.BooleanField(help_text="Valores do PDF 'Coberturas e Capitais' são indicativos.")


class MemberImportRequest(s.Serializer):
    file = s.FileField(help_text="CSV ou XLSX com a população a importar.")
    proposerId = s.UUIDField(required=False, help_text="Proponente a que os membros pertencem.")


class EmptyRequest(s.Serializer):
    """Corpo vazio (`{}`) ou ausente."""


class ClaimsMethodology(s.Serializer):
    method = s.CharField()
    indicative = s.BooleanField()
    note = s.CharField()
    formulas = s.ListField(child=s.CharField())
    assumptionsRequired = s.ListField(child=s.CharField())
    scenarios = s.ListField(child=s.CharField())
    importFormats = s.JSONField()
    dateFormats = s.ListField(child=s.CharField())
    currencies = s.ListField(child=s.CharField())


class SignedUrl(s.Serializer):
    url = s.CharField(help_text="Caminho relativo; abre sem iniciar sessão até expirar.")
    expiresAt = s.DateTimeField()
    expiresInSeconds = s.IntegerField()


# ------------------------------------------------------------------ pricing
class PricingPreviewResponse(s.Serializer):
    pricingRunId = s.UUIDField(allow_null=True, help_text="Sempre null numa pré-visualização.")
    preview = s.BooleanField(help_text="Sempre true: nada foi gravado.")
    status = s.CharField()
    currencyCode = s.CharField()
    totalAmount = Money()
    components = s.ListField(child=s.DictField(), help_text="Mesmos componentes de PricingResponse.components (incluem memberId).")
    versions = s.DictField(child=s.CharField(allow_null=True))
    calculatedAt = s.DateTimeField(allow_null=True)
    warnings = Warning(many=True)


class ImpactSummary(s.Serializer):
    previousTotal = Money()
    newTotal = Money()
    delta = Money()
    deltaPercent = s.CharField(allow_null=True)
    currencyCode = s.CharField(allow_null=True)


class QuotePreviewRequest(s.Serializer):
    selection = s.JSONField(required=False, allow_null=True, help_text="Escolhas a simular (substitui as da cotação).")
    adjustments = s.ListField(child=s.DictField(), required=False, help_text="Ajustes extra: {kind, value, scope, memberId?}.")


class QuotePreviewResponse(PricingPreviewResponse):
    baseline = s.DictField(child=s.CharField(allow_null=True), help_text="totalAmount/currencyCode do estado gravado.")
    impact = ImpactSummary()


# ---------------------------------------------------------------- quote sim.
class QuoteSelectionRead(s.Serializer):
    selection = s.JSONField()
    rowVersion = s.IntegerField()


class AdjustmentDryRun(ImpactSummary):
    dryRun = s.BooleanField()
    requiresApproval = s.BooleanField(help_text="true se excede o limite da AuthorityPolicy e o utilizador não pode aprovar.")


class PreExistingResult(s.Serializer):
    memberId = s.UUIDField()
    preExisting = s.JSONField()
    quote = QuoteSerializer()
    warnings = Warning(many=True)


class AdjustmentApplied(s.Serializer):
    adjustment = QuoteAdjustmentSerializer()
    quote = QuoteSerializer()
    impact = ImpactSummary()


class AdjustmentRemoved(s.Serializer):
    adjustment = QuoteAdjustmentSerializer()
    quote = QuoteSerializer()


class QuoteWithWarnings(QuoteSerializer):
    warnings = Warning(many=True)


class PlanBenefitConfigured(PlanBenefitSerializer):
    warnings = Warning(many=True)


class VersionDiffChange(s.Serializer):
    field = s.CharField()
    before = s.JSONField(allow_null=True)
    after = s.JSONField(allow_null=True)


class VersionDiff(s.Serializer):
    versionNo = s.IntegerField()
    against = s.CharField(help_text="Número da outra versão ou 'current'.")
    changes = VersionDiffChange(many=True)


class VersionRestoreResult(s.Serializer):
    quote = QuoteSerializer()
    addedMembers = s.ListField(child=s.CharField())
    removedMembers = s.ListField(child=s.CharField())
    skippedMembers = s.ListField(child=s.CharField())
    newVersionNo = s.IntegerField()


class RequirementItem(s.Serializer):
    severity = s.ChoiceField(choices=["ERROR", "WARNING", "INFO"])
    code = s.CharField()
    message = s.CharField()
    scope = s.ChoiceField(choices=["QUOTE", "MEMBER"])
    memberId = s.UUIDField(required=False)
    memberName = s.CharField(required=False, help_text="Nome da pessoa segura, quando o requisito é de uma pessoa.")


class RequirementsMember(s.Serializer):
    memberId = s.UUIDField()
    memberName = s.CharField(allow_null=True)
    ageAtQuoteDate = s.IntegerField(allow_null=True, help_text="Idade na data de criação da cotação (a cotação não tem data de efeito).")
    relationshipCategory = s.CharField(allow_null=True)
    clinicalQuestionnaireRequired = s.BooleanField()
    medicalExamRequired = s.BooleanField()
    blocking = s.BooleanField()


class WaitingPeriod(s.Serializer):
    coverage = s.CharField()
    days = s.IntegerField(allow_null=True)
    scheduledSurgeryDays = s.IntegerField(allow_null=True)
    accidentWaived = s.BooleanField()


class ExclusionItem(s.Serializer):
    code = s.CharField()
    text = s.CharField()
    productDependent = s.BooleanField()


class Requirements(s.Serializer):
    quoteId = s.UUIDField()
    segment = s.CharField(allow_null=True)
    blocking = s.BooleanField(help_text="true impede o envio para revisão.")
    errors = RequirementItem(many=True)
    warnings = RequirementItem(many=True)
    info = RequirementItem(many=True)
    members = s.DictField(child=RequirementsMember(), help_text="Por memberId.")
    waitingPeriods = WaitingPeriod(many=True)
    exclusions = ExclusionItem(many=True)


class ClaimsContext(s.Serializer):
    available = s.BooleanField()
    historyMonths = s.IntegerField()
    threeYearsAvailable = s.BooleanField()
    summary = s.JSONField(required=False, help_text="Ver ClaimsSummary (só quando available=true).")
    projections = s.ListField(child=s.DictField())


class IndexationRequest(s.Serializer):
    medicalInflationPct = s.CharField(required=False, allow_null=True, help_text="Por omissão a do plano ou o parâmetro global.")
    roundTo = s.CharField(required=False, allow_null=True, help_text="Arredondar capitais a este múltiplo (por omissão 1).")
    reason = s.CharField(help_text="Motivo (mínimo 10 caracteres).")


class IndexationResult(s.Serializer):
    dryRun = s.BooleanField()
    medicalInflationPct = s.CharField()
    roundTo = s.CharField()
    coverages = s.DictField(child=s.ListField(child=s.DictField()), help_text="Limites indexados por código de cobertura.")
    impact = ImpactSummary()
    quote = QuoteSerializer(required=False, help_text="Cotação atualizada (só quando dryRun=false).")


class ScenarioCompareScenario(s.Serializer):
    id = s.UUIDField()
    name = s.CharField()
    isSelected = s.BooleanField()
    stale = s.BooleanField()
    totalAmount = Money()
    deltaVsFirst = Money()
    deltaPercentVsFirst = s.CharField(allow_null=True)
    participationOption = s.CharField(allow_null=True)
    optionalCoverages = s.ListField(child=s.CharField())
    adjustments = s.ListField(child=s.DictField())
    warnings = s.ListField(child=s.DictField())
    projection = s.JSONField(allow_null=True)


class ScenarioCompareRow(s.Serializer):
    code = s.CharField()
    name = s.CharField(required=False)
    category = s.CharField(required=False, allow_null=True)
    type = s.CharField(required=False, allow_null=True)
    differs = s.BooleanField()
    values = s.DictField(child=s.JSONField(allow_null=True), help_text="Por scenarioId.")


class ScenarioCompare(s.Serializer):
    quoteId = s.UUIDField()
    currencyCode = s.CharField(allow_null=True)
    scenarios = ScenarioCompareScenario(many=True)
    summary = s.DictField(child=s.JSONField(), help_text="lowest, highest, spread.")
    coverages = ScenarioCompareRow(many=True)
    components = ScenarioCompareRow(many=True)


# ----------------------------------------------------------------- policy
class CoverageResult(s.Serializer):
    covered = s.BooleanField()
    reasonCode = s.CharField()
    message = s.CharField()
    waitingPeriodEnds = s.DateField(allow_null=True)


class CoverageMemberResult(CoverageResult):
    memberId = s.UUIDField()


class PolicyCoverage(CoverageResult):
    policyId = s.UUIDField()
    policyNumber = s.CharField(required=False)
    results = CoverageMemberResult(many=True, required=False, help_text="Presente quando memberId é omitido.")
    memberId = s.UUIDField(required=False)


# ----------------------------------------------------------------- claims
class ClaimsImportRequest(s.Serializer):
    file = s.FileField(help_text="CSV ou XLSX; colunas por nome (ver descrição).")
    kind = s.ChoiceField(choices=["CLAIMS", "PREMIUMS"])
    proposerId = s.UUIDField()
    policyId = s.UUIDField(required=False, allow_null=True)
    source = s.ChoiceField(choices=["INTERNAL", "OTHER_INSURER"], required=False, default="INTERNAL")
    dryRun = s.BooleanField(required=False, default=False)


class ClaimsImportRowError(s.Serializer):
    row = s.IntegerField()
    message = s.CharField()


class ClaimsImportResult(s.Serializer):
    dryRun = s.BooleanField()
    kind = s.CharField()
    totalRows = s.IntegerField()
    importedRows = s.IntegerField()
    errorRows = s.IntegerField()
    errors = ClaimsImportRowError(many=True)
    importId = s.UUIDField(required=False)


class ClaimsSummary(s.Serializer):
    proposerId = s.UUIDField()
    currencyCode = s.CharField()
    period = s.DictField(child=s.JSONField())
    historyMonths = s.IntegerField()
    premium = s.DictField(child=s.CharField(allow_null=True), help_text="earned, insuredYears.")
    claims = s.DictField(child=s.JSONField(allow_null=True), help_text="count, paid, provision, total, averageCost, frequencyPerInsuredYear.")
    lossRatioPct = s.CharField(allow_null=True)
    byBenefit = s.ListField(child=s.DictField())
    byMonth = s.ListField(child=s.DictField())
    formulas = s.DictField(child=s.CharField())


class ProfitSharing(s.Serializer):
    proposerId = s.UUIDField()
    currencyCode = s.CharField()
    period = s.DictField(child=s.JSONField())
    earnedPremium = Money()
    claimsTotal = Money()
    lossRatioPct = s.CharField()
    thresholdPct = s.CharField()
    sharePct = s.CharField()
    eligible = s.BooleanField()
    refundAmount = Money()
    formula = s.CharField()
    indicative = s.BooleanField()


# -------------------------------------------------------------- documents
class TemplateSchema(s.Serializer):
    defaultBody = s.DictField(help_text="Corpo por omissão de um modelo de proposta.")
    sections = s.DictField(child=s.CharField(), help_text="Secções permitidas (id → descrição).")
    variables = s.DictField(child=s.CharField(), help_text="Variáveis {{...}} permitidas (nome → descrição).")
    formats = s.ListField(child=s.CharField())


# ---------------------------------------------------------------- portal
class PortalPlanBenefits(s.Serializer):
    policyNumber = s.CharField()
    benefits = s.ListField(child=s.DictField(), help_text="PlanBenefit contratados (snapshot da apólice), com a configuração contratada.")


class PortalQuoteNamed(s.Serializer):
    name = s.CharField()


class PortalQuote(s.Serializer):
    quoteNumber = s.CharField(allow_null=True)
    status = s.CharField(
        help_text="Estado traduzido para o cliente: IN_REVIEW, AWAITING_SIGNATURE, CONTRACTED, REJECTED, EXPIRED "
                  "ou CANCELLED. Rascunhos nunca são devolvidos; uma cotação aprovada cuja validade passou "
                  "aparece como EXPIRED.",
    )
    validUntil = s.DateField(allow_null=True)
    product = PortalQuoteNamed(allow_null=True)
    plan = PortalQuoteNamed()
    totalAmount = s.CharField(allow_null=True, help_text="Só em AWAITING_SIGNATURE, CONTRACTED e EXPIRED.")
    currencyCode = s.CharField(allow_null=True)
    policyNumber = s.CharField(allow_null=True, help_text="Preenchido quando a cotação já gerou apólice.")
    createdAt = s.DateTimeField()


class PortalQuotes(s.Serializer):
    quotes = PortalQuote(many=True)



class PortalDashboard(s.Serializer):
    quotes = s.DictField(help_text="total e byStatus (IN_REVIEW, AWAITING_SIGNATURE, CONTRACTED, REJECTED, EXPIRED, CANCELLED).")
    policies = s.DictField(help_text="total e byPhase (ACTIVE, EXPIRING, RENEWED, EXPIRED, CANCELLED, OTHER).")
    upcoming = s.ListField(child=s.DictField(), help_text="Próximos eventos: prestações e fins de apólice, por data.")
    alerts = s.ListField(child=s.DictField(), help_text="Alertas: prestação em atraso, apólice a vencer, 1.º prémio por pagar, cotação a expirar.")
    financial = s.ListField(child=s.DictField(), help_text="Por moeda: paid, pending e overdue.")


class PortalQuoteTimelineEvent(s.Serializer):
    code = s.CharField()
    label = s.CharField()
    at = s.DateTimeField()


class PortalQuoteDetail(PortalQuote):
    timeline = PortalQuoteTimelineEvent(many=True, help_text="Só eventos que o sistema regista.")
    currentStage = s.CharField()


class PortalPolicySummary(s.Serializer):
    policyNumber = s.CharField(allow_null=True)
    status = s.CharField()
    statusLabel = s.CharField()
    phase = s.CharField(help_text="ACTIVE, EXPIRING (termina em 60 dias), RENEWED, EXPIRED, CANCELLED ou OTHER.")
    product = PortalQuoteNamed(allow_null=True)
    plan = PortalQuoteNamed()
    startDate = s.DateField(allow_null=True)
    endDate = s.DateField(allow_null=True)


class PortalPolicyList(s.Serializer):
    policies = PortalPolicySummary(many=True)


class PortalPolicyDetail(PortalPolicySummary):
    policyType = s.CharField()
    termMonths = s.IntegerField()
    paymentFrequency = s.CharField()
    currencyCode = s.CharField(allow_null=True)
    totalPremium = s.CharField(allow_null=True)
    holder = s.DictField()
    signedAt = s.DateTimeField(allow_null=True)
    members = s.ListField(child=s.DictField())
    installments = s.ListField(child=s.DictField())


class PortalPolicyHistory(s.Serializer):
    policyNumber = s.CharField()
    events = s.ListField(child=s.DictField(), help_text="fromStatus, toStatus e at; sem motivos internos.")


class PortalCard(s.Serializer):
    memberName = s.CharField()
    memberNumber = s.CharField()
    relationship = s.CharField()
    policyNumber = s.CharField(allow_null=True)
    plan = PortalQuoteNamed()
    product = PortalQuoteNamed(allow_null=True)
    validFrom = s.DateField(allow_null=True)
    validUntil = s.DateField(allow_null=True)
    policyStatus = s.CharField()
    memberStatus = s.CharField()


class PortalBeneficiaries(s.Serializer):
    beneficiaries = s.ListField(child=s.DictField())


class PortalPayments(s.Serializer):
    installments = s.ListField(child=s.DictField())
    totals = s.ListField(child=s.DictField(), help_text="Por moeda: paid, pending e overdue.")


class PortalDocuments(s.Serializer):
    documents = s.ListField(child=s.DictField(), help_text="Hoje só propostas geradas.")


class PortalProfile(s.Serializer):
    accountEmail = s.CharField(allow_null=True)
    proposers = s.ListField(child=s.DictField())


# ----------------------------------------- portal: pedidos, mensagens, etc.
class PortalRequestStatus(s.Serializer):
    code = s.CharField()
    label = s.CharField()


class PortalRequestHistoryEvent(s.Serializer):
    status = s.CharField()
    statusLabel = s.CharField()
    note = s.CharField(allow_null=True)
    by = s.CharField()
    at = s.DateTimeField()


class PortalRequestItem(s.Serializer):
    requestNumber = s.CharField()
    type = s.CharField()
    typeLabel = s.CharField()
    subject = s.CharField()
    description = s.CharField()
    status = s.CharField(help_text="OPEN, IN_REVIEW, AWAITING_CUSTOMER, APPROVED, REJECTED ou COMPLETED.")
    statusLabel = s.CharField()
    policyNumber = s.CharField(allow_null=True)
    quoteNumber = s.CharField(allow_null=True)
    resolutionNote = s.CharField(allow_null=True)
    createdAt = s.DateTimeField()
    updatedAt = s.DateTimeField()


class PortalRequestDetail(PortalRequestItem):
    history = PortalRequestHistoryEvent(many=True)


class PortalRequestList(s.Serializer):
    requests = PortalRequestItem(many=True)


class PortalRequestCreate(s.Serializer):
    requestType = s.CharField(help_text="DATA_CHANGE, MEMBER_INCLUSION, MEMBER_EXCLUSION, DOCUMENT_COPY, STATEMENT, "
                                        "CONTACT_CHANGE, COVERAGE_QUESTION, RENEWAL, CANCELLATION, NEW_QUOTE, "
                                        "ACCEPT_QUOTE ou OTHER.")
    subject = s.CharField(required=False, allow_blank=True)
    description = s.CharField(required=False, allow_blank=True)
    policyNumber = s.CharField(required=False, allow_null=True)
    quoteNumber = s.CharField(required=False, allow_null=True)
    payload = s.DictField(required=False, help_text="Dados do pedido; MEMBER_INCLUSION exige firstName, lastName, "
                                                    "dateOfBirth e relationship; MEMBER_EXCLUSION exige memberId.")


class PortalRequestTypes(s.Serializer):
    types = s.ListField(child=s.DictField())
    statuses = PortalRequestStatus(many=True)


class PortalMessageCreate(s.Serializer):
    contextType = s.CharField(help_text="QUOTE, POLICY ou REQUEST.")
    contextRef = s.CharField(help_text="Número da cotação, da apólice ou do pedido.")
    body = s.CharField()


class PortalMessages(s.Serializer):
    messages = s.ListField(child=s.DictField(), help_text="id, from (CUSTOMER|STAFF), fromLabel, body e createdAt.")


class PortalConversations(s.Serializer):
    conversations = s.ListField(child=s.DictField(), help_text="contextType, contextRef, lastMessage, lastFrom, lastAt, unread.")


class PortalNotificationItem(s.Serializer):
    id = s.UUIDField()
    code = s.CharField()
    title = s.CharField()
    body = s.CharField()
    link = s.CharField(allow_null=True)
    createdAt = s.DateTimeField()
    read = s.BooleanField()


class PortalNotifications(s.Serializer):
    unreadCount = s.IntegerField()
    notifications = PortalNotificationItem(many=True)


class PortalMarkRead(s.Serializer):
    ids = s.ListField(child=s.UUIDField(), required=False, allow_null=True, help_text="Omitir marca todas como lidas.")


class PortalMarkReadResult(s.Serializer):
    updated = s.IntegerField()


class PortalRenewal(s.Serializer):
    policyNumber = s.CharField(allow_null=True)
    policyStatus = s.CharField()
    endDate = s.DateField(allow_null=True)
    daysLeft = s.IntegerField(allow_null=True)
    windowDays = s.IntegerField()
    canRequest = s.BooleanField()
    currentTerms = s.DictField()
    request = s.DictField(allow_null=True)
    proposal = PortalQuote(allow_null=True)
    steps = s.ListField(child=s.DictField(), help_text="code, label e state (DONE, CURRENT, PENDING).")


class PortalPlanCompare(s.Serializer):
    policyNumber = s.CharField(allow_null=True)
    product = PortalQuoteNamed(allow_null=True)
    plans = s.ListField(child=s.DictField(), help_text="Planos activos do mesmo produto, com as coberturas e limites; sem preços.")
    benefits = s.ListField(child=s.DictField(), help_text="Coberturas existentes em pelo menos um plano (linhas da tabela).")


class StaffPortalRequestItem(PortalRequestItem):
    customerName = s.CharField(allow_null=True)
    payload = s.DictField()


class StaffPortalRequestDetail(StaffPortalRequestItem):
    history = PortalRequestHistoryEvent(many=True)


class StaffPortalRequestList(s.Serializer):
    requests = StaffPortalRequestItem(many=True)


class StaffPortalTransition(s.Serializer):
    toStatus = s.CharField(help_text="IN_REVIEW, AWAITING_CUSTOMER, APPROVED, REJECTED ou COMPLETED, conforme o estado actual.")
    note = s.CharField(required=False, allow_null=True, allow_blank=True,
                       help_text="Obrigatória para REJECTED e AWAITING_CUSTOMER; o cliente vê-a.")


class StaffPortalConversations(s.Serializer):
    conversations = s.ListField(child=s.DictField(), help_text="Como a do cliente, com customerName e unread = mensagens do cliente por ler.")


class PortalToken(s.Serializer):
    accessToken = s.CharField()
    tokenType = s.CharField(help_text="Bearer.")
    expiresIn = s.IntegerField(help_text="Segundos até o token expirar.")


class PortalMaskedEmail(s.Serializer):
    maskedEmail = s.CharField(help_text="Email para onde foi enviado o código, mascarado (jo***@gmail.com).")


# ------------------------------------------------------- policy emission
class PolicyDraftHolder(s.Serializer):
    id = s.UUIDField()
    name = s.CharField()
    type = s.CharField()
    document = s.CharField(allow_null=True)
    email = s.CharField(allow_null=True)
    phone = s.CharField(allow_null=True)


class PolicyDraftMember(s.Serializer):
    memberId = s.UUIDField()
    name = s.CharField()
    eligibilityDecision = s.CharField(allow_null=True)
    policyStatus = s.CharField(help_text="ACTIVE, PENDING ou EXCLUDED (não entra na apólice).")


class PolicyDraft(s.Serializer):
    """Rascunho de emissão: a apólice pré-preenchida a partir da cotação."""

    quoteId = s.UUIDField()
    quoteNumber = s.CharField(allow_null=True)
    quoteStatus = s.CharField()
    rowVersion = s.IntegerField(help_text="Enviar em `rowVersion` ao emitir.")
    canEmit = s.BooleanField()
    blockingReason = s.CharField(allow_null=True)
    warnings = s.ListField(child=s.CharField(), help_text="Avisos que não impedem a emissão (ex.: cotação já fora de validade).")
    policyId = s.UUIDField(allow_null=True, help_text="Preenchido se a cotação já originou uma apólice.")
    policyNumber = s.CharField(allow_null=True)
    holder = PolicyDraftHolder()
    plan = s.DictField(child=s.CharField(allow_null=True))
    currencyCode = s.CharField()
    quoteCreatedAt = s.DateTimeField(help_text="Data de criação da cotação (a cotação não tem data de efeito).")
    validUntil = s.DateField(allow_null=True)
    premium = s.DictField(child=s.CharField(allow_null=True))
    defaults = s.DictField(help_text="termMonths, paymentFrequency, requestedStartDate, signedAt, signatureMethod, signatory{name,documentType,documentNumber,capacity}.")
    installmentsPreview = s.DictField(help_text="Por fracionamento (ANUAL, SEMESTRAL, TRIMESTRAL, MENSAL): as prestações {installmentNo, amount, currencyCode}.")
    paymentMethods = s.ListField(child=s.DictField())
    members = PolicyDraftMember(many=True)
    terms = s.DictField(allow_null=True, help_text="segment, accessSystem, coverages[], franchise, waiting[], exclusions[], conditions[].")


class EmittedPolicy(s.Serializer):
    id = s.UUIDField()
    policyNumber = s.CharField(allow_null=True)
    sourceQuoteId = s.UUIDField()
    proposerId = s.UUIDField()
    planId = s.UUIDField()
    policyType = s.CharField()
    termMonths = s.IntegerField()
    startDate = s.DateField(allow_null=True)
    endDate = s.DateField(allow_null=True)
    status = s.CharField(help_text="ACTIVE se o pagamento foi registado; senão PENDING_FIRST_PREMIUM.")
    paymentFrequency = s.CharField()
    currencyCode = s.CharField(allow_null=True)
    rowVersion = s.IntegerField()
    documentPath = s.CharField(help_text="GET desta rota devolve a apólice digital.")


# ------------------------------------------------------- cobranças (prestações)
class CollectionInstallment(s.Serializer):
    """Uma prestação na lista de cobranças."""

    id = s.UUIDField()
    installmentNo = s.IntegerField()
    periodFrom = s.DateField()
    periodTo = s.DateField()
    dueDate = s.DateField()
    amount = Money()
    currencyCode = s.CharField()
    status = s.ChoiceField(choices=["DUE", "OVERDUE", "PAID"], help_text="OVERDUE = por pagar com vencimento já passado.")
    paidAt = s.DateTimeField(allow_null=True)
    paymentReference = s.CharField(allow_null=True)
    paymentMethod = s.CharField(allow_null=True)
    policyId = s.UUIDField()
    policyNumber = s.CharField(allow_null=True)
    policyStatus = s.CharField()
    holderName = s.CharField(allow_null=True)
    daysOverdue = s.IntegerField()
    canRegisterPayment = s.BooleanField(help_text="A apólice está ativa e a prestação por pagar.")


class PaymentRegistered(s.Serializer):
    """Resposta do registo de pagamento: a apólice e a prestação paga."""

    id = s.UUIDField()
    policyNumber = s.CharField(allow_null=True)
    status = s.CharField()
    startDate = s.DateField(allow_null=True)
    endDate = s.DateField(allow_null=True)
    rowVersion = s.IntegerField()

    installment = s.DictField(
        help_text="A prestação paga: id, installmentNo, periodFrom, periodTo, dueDate, amount, currencyCode, status, paidAt, paymentReference, paymentMethod."
    )


# ------------------------------------------------- documentos em falta (pessoas seguras)
class MemberDocumentItem(s.Serializer):
    id = s.UUIDField()
    memberId = s.UUIDField()
    evidenceType = s.ChoiceField(choices=["ENROLLMENT_CERTIFICATE", "UNION_HOMOLOGATION", "DEPENDENCY_PROOF", "OTHER"])
    evidenceLabel = s.CharField()
    status = s.ChoiceField(choices=["SUBMITTED", "APPROVED", "REJECTED"])
    statusLabel = s.CharField(help_text="Em análise, Aceite ou Recusado.")
    fileName = s.CharField()
    contentType = s.CharField()
    sizeBytes = s.IntegerField()
    note = s.CharField(allow_null=True)
    submittedBy = s.ChoiceField(choices=["CUSTOMER", "STAFF"])
    submittedAt = s.DateTimeField()
    reviewedAt = s.DateTimeField(allow_null=True)
    reviewNote = s.CharField(allow_null=True)


class MemberDocumentQueueItem(MemberDocumentItem):
    memberName = s.CharField(allow_null=True)
    relationshipCode = s.CharField()


class MemberPendingRequirement(s.Serializer):
    context = s.ChoiceField(choices=["POLICY", "QUOTE"], help_text="Onde a pessoa está pendente.")
    reference = s.CharField(allow_null=True, help_text="Número da apólice ou da cotação.")
    reasonCode = s.CharField(allow_null=True)
    message = s.CharField(allow_null=True, help_text="Texto para o cliente (ex.: «Só falta mais uma coisa: envie…»).")
    needsDocument = s.BooleanField(help_text="false = pendência que um documento não resolve (ex.: junta médica).")
    documentType = s.CharField(allow_null=True)
    documentLabel = s.CharField(allow_null=True)


class MemberDocumentsOverview(s.Serializer):
    memberId = s.UUIDField(required=False)
    documents = MemberDocumentItem(many=True)
    pending = MemberPendingRequirement(many=True, help_text="O que ainda falta enviar para a pessoa ficar coberta.")


class MemberDocumentReviewResult(s.Serializer):
    document = MemberDocumentItem()
    reevaluation = s.DictField(
        allow_null=True,
        help_text="Só ao aprovar: {quoteMembers[], policyMembers[]} com o antes/depois de cada vínculo "
        "(policyMembers[].to = ACTIVE e endorsementNo quando a pessoa ficou coberta).",
    )


class GlobalSearchItem(s.Serializer):
    id = s.CharField()
    title = s.CharField()
    subtitle = s.CharField()
    href = s.CharField(help_text="Rota do back-office (ex.: /clientes/{id}, /cotacoes/{id}/resumo).")


class GlobalSearchGroup(s.Serializer):
    kind = s.ChoiceField(choices=["proposer", "quote", "product", "policy"])
    label = s.CharField()
    items = GlobalSearchItem(many=True)


class GlobalSearchResult(s.Serializer):
    total = s.IntegerField()
    groups = GlobalSearchGroup(many=True, help_text="Só os grupos com resultados.")
