"""DTOs matching ART-006 `Quote`/`QuoteCreateRequest`/`QuoteUpdateRequest`/
`QuoteMemberRequest`/`QuotePriceRequest` verbatim (see
apps/product/interfaces/serializers.py for the general "why plain
Serializer" rationale).
"""
from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers

from apps.pricing.domain.money import round_amount

from apps.quote.domain.enums import (
    DocumentStatus,
    DocumentTemplateStatus,
    DocumentType,
    QuoteDecisionType,
    QuoteStatus,
    ReviewTaskStatus,
)


class QuoteSerializer(serializers.Serializer):
    """DECISIONS_TAKEN.md#S09-POLICY-001 (PO-APO-6): `productVersionId`
    dropped — `planId` alone resolves the product via `Plan.productId`."""

    id = serializers.UUIDField()
    quoteNumber = serializers.CharField(source="quote_number", allow_null=True)
    proposerId = serializers.UUIDField(source="proposer_id")
    sourceChannel = serializers.CharField(source="source_channel", allow_null=True, allow_blank=True)
    planId = serializers.UUIDField(source="plan_id")
    status = serializers.ChoiceField(choices=[s.value for s in QuoteStatus])
    # Sem data de efeito (decisão de 2026-10-15): data de criação e validade.
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)
    submittedAt = serializers.DateTimeField(source="submitted_at", allow_null=True, read_only=True)
    approvedAt = serializers.DateTimeField(source="approved_at", allow_null=True, read_only=True)
    validUntil = serializers.DateField(source="valid_until", allow_null=True)
    currencyCode = serializers.CharField(source="currency_code", allow_null=True)
    latestPricingRunId = serializers.UUIDField(source="latest_pricing_run_id", allow_null=True)
    selection = serializers.JSONField(source="selection_json")
    quoteType = serializers.CharField(source="quote_type")
    sourcePolicyId = serializers.UUIDField(source="source_policy_id", allow_null=True)
    renewal = serializers.JSONField(source="renewal_json")
    rowVersion = serializers.IntegerField(source="row_version")
    # Prémio calculado (último PricingRun associado) — útil para cotações
    # APPROVED/IN_REVIEW/BOUND onde o frontend não pode voltar a correr o
    # priceQuote, mas precisa de mostrar o valor final já calculado.
    premiumAnnualAmount = serializers.SerializerMethodField(method_name="get_premium_annual_amount")
    premiumAnnualCurrency = serializers.SerializerMethodField(method_name="get_premium_annual_currency")
    latestPricingRun = serializers.SerializerMethodField(method_name="get_latest_pricing_run_summary")
    # Pragmatic addition: só para mostrar nomes em vez de ids na UI — não
    # reintroduz productVersionId (planId continua a ser a única forma de
    # o cliente referenciar o produto/plano).
    planName = serializers.SerializerMethodField(method_name="get_plan_name")
    productName = serializers.SerializerMethodField(method_name="get_product_name")
    proposerName = serializers.SerializerMethodField(method_name="get_proposer_name")

    def get_proposer_name(self, obj) -> str | None:
        proposer = getattr(obj, "proposer", None)
        return proposer.display_name if proposer else None

    def get_plan_name(self, obj) -> str | None:
        plan = getattr(obj, "plan", None)
        return plan.name if plan else None

    def get_product_name(self, obj) -> str | None:
        plan = getattr(obj, "plan", None)
        product = getattr(plan, "product", None) if plan else None
        return product.name if product else None

    def get_premium_annual_amount(self, obj) -> str | None:
        pr = getattr(obj, "latest_pricing_run", None)
        if pr is None:
            return None
        return format(pr.total_amount.normalize(), "f")

    def get_premium_annual_currency(self, obj) -> str | None:
        pr = getattr(obj, "latest_pricing_run", None)
        if pr is None:
            return None
        return pr.currency_code

    def get_latest_pricing_run_summary(self, obj) -> dict | None:
        pr = getattr(obj, "latest_pricing_run", None)
        if pr is None:
            return None
        pricing_context = (getattr(pr, "input_snapshot_json", None) or {}).get("context", {})
        experience = pricing_context.get("experienceRating") or {"available": False, "reason": "NOT_RECORDED"}
        factor = Decimal(str(experience["factor"])) if experience.get("available") else None
        return {
            "id": str(pr.id),
            "status": pr.status,
            "currencyCode": pr.currency_code,
            "totalAmount": format(pr.total_amount.normalize(), "f"),
            "calculatedAt": pr.completed_at.isoformat() if getattr(pr, "completed_at", None) else None,
            "experienceRating": {
                "applied": bool(experience.get("available")),
                "factor": str(factor) if factor is not None else None,
                "changedPremium": bool(factor is not None and factor != Decimal("1")),
                "available": bool(experience.get("available")),
                "unavailableReason": experience.get("reason") if not experience.get("available") else None,
            },
        }


class _TitularMemberInputSerializer(serializers.Serializer):
    """Campos opcionais usados para criar o membro titular automaticamente
    no mesmo request que a cotação (quando não há ainda membro criado)."""

    relationshipCode = serializers.CharField(min_length=2, max_length=30, required=False, default="TITULAR")
    firstName = serializers.CharField(max_length=120, allow_null=True, required=False, default=None, allow_blank=True)
    lastName = serializers.CharField(max_length=120, allow_null=True, required=False, default=None, allow_blank=True)
    # Se vier vazia usa-se a data de nascimento do proponente individual
    # (o titular é o próprio proponente). Pelo menos uma das duas é obrigatória.
    dateOfBirth = serializers.DateField(allow_null=True, required=False, default=None)
    sexCode = serializers.CharField(max_length=5, allow_null=True, required=False, default=None, allow_blank=True)
    externalReference = serializers.CharField(max_length=120, allow_null=True, required=False, default=None, allow_blank=True)
    attributes = serializers.JSONField(required=False, default=None, allow_null=True)


class _ProposerInputSerializer(serializers.Serializer):
    """Campos necessários para criar um Proposer no mesmo request que a
    criação da cotação. Rejeita caso exista outro proposer com o mesmo NIF."""

    proposerType = serializers.CharField(max_length=30, required=False, default="INDIVIDUAL")
    displayName = serializers.CharField(min_length=1, max_length=200)
    externalReference = serializers.CharField(max_length=120, allow_null=True, required=False, default=None, allow_blank=True)
    nif = serializers.CharField(min_length=1, max_length=60)
    registrationNumber = serializers.CharField(min_length=1, max_length=60)
    # Obrigatória para proponente INDIVIDUAL (validado em `QuoteCreateRequestSerializer`).
    dateOfBirth = serializers.DateField(required=False, allow_null=True, default=None)
    email = serializers.CharField(max_length=200, required=False, default="", allow_null=True, allow_blank=True)
    phone = serializers.CharField(max_length=60, required=False, default="", allow_null=True, allow_blank=True)
    address = serializers.CharField(max_length=500, required=False, default=None, allow_null=True, allow_blank=True)
    province = serializers.CharField(max_length=100, required=False, default=None, allow_null=True, allow_blank=True)
    municipality = serializers.CharField(max_length=100, required=False, default=None, allow_null=True, allow_blank=True)
    attributes = serializers.JSONField(required=False, default=None, allow_null=True)


class QuoteCreateRequestSerializer(serializers.Serializer):
    """Aceita dois caminhos:
    - Modo "referência": `proposerId` (UUID) + `planId`.
    - Modo "inline":    `proposerInput` (e opcionalmente `titularMemberInput`)
                         + `planId`. Cria tudo no mesmo request.

    A cotação não tem data de efeito: fica com a data de criação e a validade
    (`quote.validity_days`); o início da vigência escolhe-se na emissão.
    """

    proposerId = serializers.UUIDField(required=False, default=None, allow_null=True)
    proposerInput = _ProposerInputSerializer(required=False, default=None, allow_null=True)
    titularMemberInput = _TitularMemberInputSerializer(required=False, default=None, allow_null=True)
    planId = serializers.UUIDField()
    sourceChannel = serializers.CharField(max_length=60, required=False, allow_null=True, allow_blank=True, default=None)

    def validate(self, attrs: dict) -> dict:
        if attrs.get("sourceChannel") is not None:
            attrs["sourceChannel"] = " ".join(attrs["sourceChannel"].split()).upper() or None
        if attrs.get("proposerId") is None and attrs.get("proposerInput") is None:
            raise serializers.ValidationError(
                "proposerId ou proposerInput deve ser fornecido (não ambos são nulos)."
            )
        if attrs.get("proposerId") is not None and attrs.get("proposerInput") is not None:
            raise serializers.ValidationError(
                "Forneça apenas um: proposerId OU proposerInput (não ambos)."
            )
        if attrs.get("titularMemberInput") is not None and attrs.get("proposerInput") is None:
            raise serializers.ValidationError(
                "titularMemberInput só é aceite se também fornecer proposerInput."
            )

        proposer_input = attrs.get("proposerInput")
        if proposer_input is not None:
            from apps.client.domain.nif import NifFormatError, validate_agt_nif

            proposer_type = proposer_input.get("proposerType") or "INDIVIDUAL"
            if proposer_type not in ("INDIVIDUAL", "ORGANISATION"):
                raise serializers.ValidationError({"proposerInput": {"proposerType": "Tipo inválido."}})
            # NIF por tipo: individual = 14 caracteres; empresa = 10 dígitos.
            for field in ("nif", "registrationNumber"):
                try:
                    validate_agt_nif(proposer_input[field], proposer_type)
                except NifFormatError as exc:
                    raise serializers.ValidationError({"proposerInput": {field: str(exc)}}) from exc
            if proposer_type == "INDIVIDUAL":
                titular = attrs.get("titularMemberInput") or {}
                if proposer_input.get("dateOfBirth") is None and titular.get("dateOfBirth") is None:
                    raise serializers.ValidationError(
                        {"proposerInput": {"dateOfBirth": "A data de nascimento é obrigatória para proponentes individuais."}}
                    )
        return attrs


class QuoteMemberRequestSerializer(serializers.Serializer):
    memberId = serializers.UUIDField()


class QuoteSelectionRequestSerializer(serializers.Serializer):
    """Coberturas opcionais escolhidas, opção A–E e "e se..." de capitais —
    ver apps.pricing.application.plan_dimensions."""

    selection = serializers.JSONField()
    rowVersion = serializers.IntegerField(min_value=0)


class QuotePreviewRequestSerializer(serializers.Serializer):
    selection = serializers.JSONField(required=False, default=None, allow_null=True)
    adjustments = serializers.ListField(child=serializers.JSONField(), required=False, default=list)


class AdjustmentRequestSerializer(serializers.Serializer):
    kind = serializers.CharField()
    value = serializers.JSONField()
    scope = serializers.CharField(required=False, default="QUOTE")
    memberId = serializers.UUIDField(required=False, allow_null=True, default=None)
    reason = serializers.CharField(required=False, allow_null=True, allow_blank=True, default=None)


class AdjustmentRemoveRequestSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_null=True, allow_blank=True, default=None)


class QuoteAdjustmentSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    quoteId = serializers.UUIDField(source="quote_id")
    quoteRowVersion = serializers.IntegerField(source="quote.row_version")
    kind = serializers.CharField()
    value = serializers.SerializerMethodField()
    scope = serializers.CharField()
    memberId = serializers.UUIDField(source="member_id", allow_null=True)
    reason = serializers.CharField()
    status = serializers.CharField()
    impact = serializers.JSONField(source="impact_json")
    appliedBy = serializers.CharField(source="applied_by")
    appliedByName = serializers.SerializerMethodField()
    appliedAt = serializers.DateTimeField(source="applied_at")
    removedBy = serializers.CharField(source="removed_by", allow_null=True)
    removedByName = serializers.SerializerMethodField()
    removedAt = serializers.DateTimeField(source="removed_at", allow_null=True)
    removedReason = serializers.CharField(source="removed_reason", allow_null=True)

    def get_value(self, obj) -> str:
        return format(obj.value.normalize(), "f")

    def get_appliedByName(self, obj) -> str | None:
        return self.context.get("responsible_names", {}).get(str(obj.applied_by))

    def get_removedByName(self, obj) -> str | None:
        return self.context.get("responsible_names", {}).get(str(obj.removed_by))


class QuoteDiscountApprovalSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    quoteId = serializers.UUIDField(source="quote_id")
    quoteNumber = serializers.CharField(source="quote.quote_number", allow_null=True)
    proposerName = serializers.CharField(source="quote.proposer.display_name")
    spec = serializers.JSONField(source="spec_json")
    reason = serializers.CharField()
    status = serializers.CharField()
    requestedBy = serializers.CharField(source="requested_by")
    requestedAt = serializers.DateTimeField(source="requested_at")
    decidedBy = serializers.CharField(source="decided_by", allow_null=True)
    decidedAt = serializers.DateTimeField(source="decided_at", allow_null=True)
    decisionNote = serializers.CharField(source="decision_note", allow_null=True)
    adjustmentId = serializers.UUIDField(source="adjustment_id", allow_null=True)
    impact = serializers.JSONField(source="impact_json")


class QuoteDiscountApprovalDecisionSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=("APPROVE", "REJECT"))
    note = serializers.CharField(min_length=10, max_length=1000)


class PreExistingDecisionRequestSerializer(serializers.Serializer):
    decision = serializers.JSONField()
    reason = serializers.CharField(required=False, allow_null=True, allow_blank=True, default=None)


class QuotePriceRequestSerializer(serializers.Serializer):
    recalculate = serializers.BooleanField(required=False, default=False)


class QuoteMemberSerializer(serializers.Serializer):
    """Pragmatic V1 addition (`GET /quotes/{quoteId}/members`, not in
    ART-006 — see OPEN_DECISIONS.md#S04-LISTING-GAPS-001/DECISIONS_TAKEN.md):
    `Quote` itself has no population field, so the frontend needs a real
    way to see who is on the quote."""

    id = serializers.UUIDField()
    memberId = serializers.UUIDField(source="member_id")
    status = serializers.CharField()
    eligibilityEvaluationId = serializers.UUIDField(source="eligibility_evaluation_id", allow_null=True)
    preExisting = serializers.JSONField(source="pre_existing_json")


class QuoteSubmitRequestSerializer(serializers.Serializer):
    rowVersion = serializers.IntegerField(min_value=0)


class DecisionRequestSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=[d.value for d in QuoteDecisionType])
    reasonCode = serializers.CharField(min_length=1, max_length=100, source="reason_code")
    reasonText = serializers.CharField(source="reason_text", allow_null=True, required=False, default=None)
    rowVersion = serializers.IntegerField(min_value=0)


class ReviewTaskSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    quoteId = serializers.UUIDField(source="quote_id")
    quoteName = serializers.SerializerMethodField(method_name="get_quote_name")
    quoteNumber = serializers.CharField(source="quote.quote_number", allow_null=True)
    proposerName = serializers.CharField(source="quote.proposer.display_name")
    planName = serializers.CharField(source="quote.plan.name")
    productName = serializers.CharField(source="quote.plan.product.name")
    status = serializers.ChoiceField(choices=[s.value for s in ReviewTaskStatus])
    assignedTo = serializers.CharField(source="assigned_to", allow_null=True)
    createdAt = serializers.DateTimeField(source="created_at")

    def get_quote_name(self, obj) -> str:
        """Quote has no standalone name; compose a readable queue label."""
        proposer_name = obj.quote.proposer.display_name
        plan_name = obj.quote.plan.name
        if proposer_name and plan_name:
            return f"{proposer_name} · {plan_name}"
        return proposer_name or plan_name or obj.quote.quote_number or f"Cotação {str(obj.quote_id)[:8]}"


class StateHistoryItemSerializer(serializers.Serializer):
    fromStatus = serializers.CharField(source="from_status", allow_null=True)
    toStatus = serializers.CharField(source="to_status")
    reasonCode = serializers.CharField(source="reason_code", allow_null=True)
    reasonText = serializers.CharField(source="reason_text", allow_null=True)

    changedBy = serializers.CharField(source="changed_by")
    changedByName = serializers.SerializerMethodField()

    changedAt = serializers.DateTimeField(source="changed_at")

    def get_changedByName(self, obj) -> str | None:
        return self.context.get("responsible_names", {}).get(
            str(obj.changed_by)
        )

class CancelQuoteRequestSerializer(serializers.Serializer):
    reasonCode = serializers.CharField(min_length=1, max_length=100, source="reason_code")
    reasonText = serializers.CharField(source="reason_text", allow_null=True, required=False, default=None)
    rowVersion = serializers.IntegerField(min_value=0)


class DocumentSerializer(serializers.Serializer):
    """DTO matching ART-006 `Document` verbatim."""

    id = serializers.UUIDField()
    quoteId = serializers.UUIDField(source="quote_id")
    documentType = serializers.ChoiceField(source="document_type", choices=[t.value for t in DocumentType])
    documentNumber = serializers.CharField(source="document_number", allow_null=True)
    status = serializers.ChoiceField(choices=[s.value for s in DocumentStatus])
    generatedAt = serializers.DateTimeField(source="generated_at", allow_null=True)


class DocumentTemplateCreateRequestSerializer(serializers.Serializer):
    """Pragmatic V1 addition, not in ART-006 (see
    apps/quote/application/document_service.py module docstring)."""

    documentType = serializers.ChoiceField(
        source="document_type", choices=["QUOTE_PROPOSAL", "POLICY"], default="QUOTE_PROPOSAL",
        help_text="Para que documento serve: a proposta (cotação) ou a apólice.",
    )
    templateCode = serializers.CharField(
        source="template_code", required=False, default=None, allow_null=True,
        help_text="Omitir: usa QUOTE_PROPOSAL_DEFAULT (proposta) ou POLICY_DEFAULT (apólice).",
    )
    storageRef = serializers.CharField(
        source="storage_ref", required=False, default=None, allow_null=True,
        help_text="Corpo JSON opcional (títulos e secções). Omitir usa o corpo por omissão; o aspeto vem do papel timbrado e/ou do Word carregados.",
    )
    effectiveFrom = serializers.DateField(source="effective_from")
    effectiveTo = serializers.DateField(source="effective_to", allow_null=True, required=False, default=None)


class DocumentTemplateUpdateRequestSerializer(serializers.Serializer):
    """ROADMAP_ANGOLA_CUSTOMIZATION.md Épico 6 — only DRAFT is editable;
    `templateCode`/`effectiveFrom`/`effectiveTo` are not editable fields."""

    storageRef = serializers.CharField(source="storage_ref")


class DocumentTemplateHeaderSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    templateCode = serializers.CharField(source="template_code")
    versionNo = serializers.IntegerField(source="version_no")
    status = serializers.ChoiceField(choices=[s.value for s in DocumentTemplateStatus])
    effectiveFrom = serializers.DateField(source="effective_from")
    effectiveTo = serializers.DateField(source="effective_to", allow_null=True)
    checksum = serializers.CharField(allow_null=True)
    documentType = serializers.CharField(source="document_type")
    hasLetterhead = serializers.SerializerMethodField()
    letterhead = serializers.SerializerMethodField()
    hasWordTemplate = serializers.SerializerMethodField()
    word = serializers.SerializerMethodField()

    def get_hasLetterhead(self, obj) -> bool:
        return bool(obj.letterhead_key)

    def get_letterhead(self, obj) -> dict | None:
        meta = (obj.settings_json or {}).get("letterhead")
        if not obj.letterhead_key or not meta:
            return None
        return {"fileName": obj.letterhead_name, "pages": meta.get("pages"), "marginsCm": meta.get("marginsCm")}

    def get_hasWordTemplate(self, obj) -> bool:
        return bool(obj.word_key)

    def get_word(self, obj) -> dict | None:
        meta = (obj.settings_json or {}).get("word")
        if not obj.word_key or not meta:
            return None
        return {"fileName": obj.word_name, "placeholders": meta.get("placeholders", [])}


class TemplateLetterheadUploadSerializer(serializers.Serializer):
    file = serializers.FileField(help_text="PDF com o aspeto da seguradora (logótipo, cabeçalho, rodapé, fundo). Até 10 MB.")
    left = serializers.FloatField(required=False, help_text="Margem esquerda em cm (por omissão 2).")
    right = serializers.FloatField(required=False, help_text="Margem direita em cm (por omissão 2).")
    top = serializers.FloatField(required=False, help_text="Margem de topo em cm, para não escrever sobre o cabeçalho (por omissão 3,5).")
    bottom = serializers.FloatField(required=False, help_text="Margem de base em cm, para não escrever sobre o rodapé (por omissão 3).")


class TemplateWordUploadSerializer(serializers.Serializer):
    file = serializers.FileField(help_text="Modelo .docx com marcas {{variável}}. Até 10 MB.")


class ScenarioSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    quoteId = serializers.UUIDField(source="quote_id")
    name = serializers.CharField()
    description = serializers.CharField(allow_null=True)
    parameters = serializers.JSONField(source="parameters_json")
    result = serializers.JSONField(source="result_json")
    isSelected = serializers.BooleanField(source="is_selected")
    baseScenarioId = serializers.UUIDField(source="base_scenario_id", allow_null=True)
    stale = serializers.SerializerMethodField()
    createdBy = serializers.CharField(source="created_by")
    createdAt = serializers.DateTimeField(source="created_at")
    updatedAt = serializers.DateTimeField(source="updated_at")
    rowVersion = serializers.IntegerField(source="row_version")

    def get_stale(self, obj) -> bool:
        from apps.quote.application import scenario_service

        return scenario_service.is_stale(obj)


class ScenarioCreateRequestSerializer(serializers.Serializer):
    name = serializers.CharField(min_length=1, max_length=200)
    description = serializers.CharField(allow_null=True, required=False, default=None)
    # Omitted/null = start from the current state of the quote.
    parameters = serializers.JSONField(required=False, default=None, allow_null=True)


class ScenarioUpdateRequestSerializer(serializers.Serializer):
    name = serializers.CharField(min_length=1, max_length=200)
    description = serializers.CharField(allow_null=True, required=False, default=None)
    parameters = serializers.JSONField(required=False, default=None, allow_null=True)
    rowVersion = serializers.IntegerField(min_value=0)


class ScenarioCloneRequestSerializer(serializers.Serializer):
    name = serializers.CharField(min_length=1, max_length=200, required=False, allow_null=True, default=None)


class ScenarioApplyRequestSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_null=True, allow_blank=True, default=None)


class QuoteRenewalRequestSerializer(serializers.Serializer):
    sourcePolicyId = serializers.UUIDField()
    planId = serializers.UUIDField(required=False, allow_null=True, default=None)


class QuoteCloneRequestSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_null=True, allow_blank=True, default=None)


class QuoteReopenRequestSerializer(serializers.Serializer):
    """Reabrir uma cotação REJEITADA (volta a DRAFT). `reason` obrigatório."""

    reason = serializers.CharField(min_length=1)
    rowVersion = serializers.IntegerField(min_value=0)


class QuoteVersionSerializer(serializers.Serializer):
    versionNo = serializers.IntegerField(source="version_no")
    source = serializers.CharField()
    reason = serializers.CharField(allow_null=True)
    totalAmount = serializers.SerializerMethodField()
    currencyCode = serializers.CharField(source="currency_code", allow_null=True)
    createdBy = serializers.CharField(source="created_by")
    createdByName = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source="created_at")

    def get_totalAmount(self, obj) -> str | None:
        return None if obj.total_amount is None else str(round_amount(obj.total_amount))

    def get_createdByName(self, obj) -> str | None:
        return self.context.get("responsible_names", {}).get(str(obj.created_by))


class QuoteVersionDetailSerializer(QuoteVersionSerializer):
    snapshot = serializers.JSONField(source="snapshot_json")
    checksum = serializers.CharField()


class QuoteVersionSaveRequestSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_null=True, allow_blank=True, default=None)


class QuoteIndexationRequestSerializer(serializers.Serializer):
    medicalInflationPct = serializers.JSONField(required=False, allow_null=True, default=None)
    roundTo = serializers.JSONField(required=False, allow_null=True, default=None)
    reason = serializers.CharField(required=False, allow_null=True, allow_blank=True, default=None)


class ProposalRequestSerializer(serializers.Serializer):
    templateCode = serializers.CharField(required=False, allow_null=True, default=None)
    scenarioId = serializers.UUIDField(required=False, allow_null=True, default=None)
    format = serializers.CharField(required=False, default="PDF")


class ProposalDocumentSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    quoteId = serializers.UUIDField(source="quote_id")
    documentNumber = serializers.CharField(source="document_number", allow_null=True)
    proposalNo = serializers.IntegerField(source="proposal_no", allow_null=True)
    format = serializers.CharField()
    status = serializers.CharField()
    scenarioId = serializers.UUIDField(source="scenario_id", allow_null=True)
    templateCode = serializers.CharField(source="template_version.template_code")
    templateVersion = serializers.IntegerField(source="template_version.version_no")
    fileName = serializers.CharField(source="file_name", allow_null=True)
    contentType = serializers.CharField(source="content_type", allow_null=True)
    checksum = serializers.CharField(allow_null=True)
    failure = serializers.CharField(source="failure_code", allow_null=True)
    requestedBy = serializers.CharField(source="requested_by")
    requestedAt = serializers.DateTimeField(source="requested_at")
    generatedAt = serializers.DateTimeField(source="generated_at", allow_null=True)
    downloadUrl = serializers.SerializerMethodField()

    def get_downloadUrl(self, obj) -> str | None:
        return f"/api/v1/documents/{obj.id}/download" if obj.status == "GENERATED" else None
