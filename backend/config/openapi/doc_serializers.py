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
