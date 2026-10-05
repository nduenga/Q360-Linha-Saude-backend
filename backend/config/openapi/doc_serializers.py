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
    category = s.ChoiceField(choices=["OPERATIONAL", "STRUCTURAL"], help_text="OPERATIONAL: o GTE altera; STRUCTURAL: só por evolução do sistema.")
    value = s.JSONField(allow_null=True)
    default = s.JSONField(allow_null=True)
    isDefault = s.BooleanField()
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


class RequirementsMember(s.Serializer):
    ageAtEffectiveDate = s.IntegerField(allow_null=True)
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
    effectiveDate = s.DateField()
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
