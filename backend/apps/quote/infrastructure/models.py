"""ORM adapters for the quote module's physical schema (Q360-S6-01..04).

Source of truth: Q360-MVP-ART-005 ("QUOTATION"), ported verbatim by
Q360-MVP-ART-012 V019-V021 — see `infrastructure/migrations/0001_quote_baseline.py`.
`managed = False` for the same reason as every other module (DOC-000 s3
P-08). Inherits `TenantScopedModel` (Q360-S1-04).

References `Proposer`/`InsuredMember` (apps.client), `ProductVersion`/`Plan`
(apps.product), `PricingRun` (apps.pricing) and `EligibilityEvaluation`
(apps.eligibility) directly — same pre-existing cross-module read pattern
as apps.eligibility/apps.pricing, see OPEN_DECISIONS.md#S04-CROSS-MODULE-001.
"""
from __future__ import annotations

import datetime
import uuid

from django.db import models
from django.utils import timezone

from apps.client.infrastructure.models import InsuredMember, Proposer
from apps.eligibility.infrastructure.models import EligibilityEvaluation
from apps.foundation.infrastructure.models import Tenant
from apps.foundation.infrastructure.tenant_scoping import TenantScopedModel
from apps.pricing.infrastructure.models import PricingRun
from apps.product.infrastructure.models import Plan, ProductVersion
from apps.quote.domain.enums import (
    DocumentStatus,
    DocumentTemplateStatus,
    DocumentType,
    QuoteDecisionType,
    QuoteMemberStatus,
    QuoteSnapshotType,
    QuoteStatus,
    ReviewTaskStatus,
)


def pricing_today() -> datetime.date:
    """Dia do cálculo de uma cotação aberta. Função à parte para os casos de
    referência do Excel poderem fixar o dia sem mexer no relógio do sistema."""
    return timezone.localdate()


class Quote(TenantScopedModel):
    STATUS_CHOICES = [(s.value, s.value) for s in QuoteStatus]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    quote_number = models.CharField(max_length=100, null=True, blank=True)
    source_channel = models.CharField(max_length=60, null=True, blank=True)
    proposer = models.ForeignKey(Proposer, on_delete=models.DO_NOTHING, db_column="proposer_id")
    # DECISIONS_TAKEN.md#S09-POLICY-001 (PO-APO-6): no more ProductVersion —
    # `plan.product_id` already resolves the product. Kept nullable only
    # for pre-existing rows (apps.quote 0004_product_version_optional);
    # never written by new code.
    product_version = models.ForeignKey(
        ProductVersion, on_delete=models.DO_NOTHING, db_column="product_version_id", null=True, blank=True
    )
    plan = models.ForeignKey(Plan, on_delete=models.DO_NOTHING, db_column="plan_id")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=QuoteStatus.DRAFT.value)
    # Decisão de 2026-10-15: a cotação não tem data de efeito (ainda não se
    # sabe se vai ser apólice; o início da vigência decide-se na emissão).
    # Tem data de criação e validade (`quote.validity_days`, configurável).
    valid_until = models.DateField(null=True, blank=True)
    currency_code = models.CharField(max_length=3, null=True, blank=True)
    latest_pricing_run = models.ForeignKey(
        PricingRun, on_delete=models.DO_NOTHING, db_column="latest_pricing_run_id", null=True, blank=True
    )
    submitted_by = models.CharField(max_length=200, null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.CharField(max_length=200, null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_by = models.CharField(max_length=200, null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(null=True, blank=True)
    created_by = models.CharField(max_length=200)
    # Simulador GTE (0006): escolhas do cliente, tipo de cotação e renovação.
    selection_json = models.JSONField(default=dict)
    quote_type = models.CharField(max_length=20, default="NEW")
    source_policy_id = models.UUIDField(null=True, blank=True)
    renewal_json = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    row_version = models.BigIntegerField(default=0)

    source_quote = models.ForeignKey(
    "self",
    null=True,
    blank=True,
    on_delete=models.PROTECT,
    related_name="cloned_quotes",
    db_column="source_quote_id",
    )

    clone_reason = models.TextField(
        blank=True,
        default="",
    )

    class Meta:
        managed = False
        db_table = "quote"

    @property
    def reference_date(self) -> datetime.date:
        """Data de referência do cálculo: idades, configurações, tarifas e
        regras em vigor, disponibilidade do plano.

        Cotação aberta (DRAFT/READY, ou ainda sem cálculo): o dia de hoje — o
        que for publicado na interface passa a valer no próximo cálculo.
        Depois de submetida o prémio fica congelado: vale o dia do último
        cálculo, para documentos, emissão e reavaliações baterem com ele.
        (A cotação não tem data de efeito; a validade conta da criação.)"""
        if self.status in ("DRAFT", "READY") or self.latest_pricing_run_id is None:
            return pricing_today()
        return self.latest_pricing_run.effective_date

    def __str__(self) -> str:  # pragma: no cover - debug helper
        return f"Quote({self.id}, {self.status})"


class QuoteMember(TenantScopedModel):
    STATUS_CHOICES = [(s.value, s.value) for s in QuoteMemberStatus]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    quote = models.ForeignKey(Quote, on_delete=models.CASCADE, db_column="quote_id", related_name="members")
    member = models.ForeignKey(InsuredMember, on_delete=models.DO_NOTHING, db_column="member_id")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=QuoteMemberStatus.INCLUDED.value)
    eligibility_evaluation = models.ForeignKey(
        EligibilityEvaluation,
        on_delete=models.DO_NOTHING,
        db_column="eligibility_evaluation_id",
        null=True,
        blank=True,
    )
    pre_existing_json = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = "quote_member"
    
    


class QuoteAdjustment(TenantScopedModel):
    """Agravamento/desconto aplicado a uma cotação (R3). Nunca se apaga:
    remover marca `REMOVED` com autor e motivo (auditoria)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    quote = models.ForeignKey(Quote, on_delete=models.CASCADE, db_column="quote_id", related_name="adjustments")
    kind = models.CharField(max_length=30)
    value = models.DecimalField(max_digits=30, decimal_places=8)
    scope = models.CharField(max_length=20)
    member = models.ForeignKey(
        InsuredMember, on_delete=models.DO_NOTHING, db_column="member_id", null=True, blank=True
    )
    reason = models.TextField()
    status = models.CharField(max_length=20, default="ACTIVE")
    impact_json = models.JSONField(default=dict)
    applied_by = models.CharField(max_length=200)
    applied_at = models.DateTimeField(auto_now_add=True)
    removed_by = models.CharField(max_length=200, null=True, blank=True)
    removed_at = models.DateTimeField(null=True, blank=True)
    removed_reason = models.TextField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "quote_adjustment"


class QuoteDiscountApproval(TenantScopedModel):
    STATUS_CHOICES = (("PENDING", "PENDING"), ("APPROVED", "APPROVED"), ("REJECTED", "REJECTED"))

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    quote = models.ForeignKey(Quote, on_delete=models.CASCADE, db_column="quote_id", related_name="discount_approvals")
    quote_row_version = models.BigIntegerField()
    spec_json = models.JSONField(default=dict)
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    requested_by = models.CharField(max_length=200)
    requested_at = models.DateTimeField(auto_now_add=True)
    decided_by = models.CharField(max_length=200, null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(null=True, blank=True)
    adjustment = models.ForeignKey(QuoteAdjustment, on_delete=models.DO_NOTHING, db_column="adjustment_id", null=True, blank=True)
    impact_json = models.JSONField(default=dict)

    class Meta:
        managed = False
        db_table = "quote_discount_approval"


class QuoteSnapshot(TenantScopedModel):
    TYPE_CHOICES = [(t.value, t.value) for t in QuoteSnapshotType]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    quote = models.ForeignKey(Quote, on_delete=models.DO_NOTHING, db_column="quote_id", related_name="snapshots")
    snapshot_no = models.IntegerField()
    snapshot_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    pricing_run = models.ForeignKey(
        PricingRun, on_delete=models.DO_NOTHING, db_column="pricing_run_id", null=True, blank=True
    )
    # DECISIONS_TAKEN.md#S09-POLICY-001 (PO-APO-6): see Quote.product_version
    # above — nullable, legacy-only, never written by new code.
    product_version = models.ForeignKey(
        ProductVersion, on_delete=models.DO_NOTHING, db_column="product_version_id", null=True, blank=True
    )
    plan = models.ForeignKey(Plan, on_delete=models.DO_NOTHING, db_column="plan_id")
    snapshot_json = models.JSONField()
    checksum = models.CharField(max_length=128)
    created_by = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "quote_snapshot"


class QuoteStateHistory(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    quote = models.ForeignKey(Quote, on_delete=models.DO_NOTHING, db_column="quote_id", related_name="state_history")
    from_status = models.CharField(max_length=20, null=True, blank=True)
    to_status = models.CharField(max_length=20)
    reason_code = models.CharField(max_length=100, null=True, blank=True)
    reason_text = models.TextField(null=True, blank=True)
    changed_by = models.CharField(max_length=200)
    changed_at = models.DateTimeField(auto_now_add=True)
    correlation_id = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        managed = False
        db_table = "quote_state_history"


class AuthorityPolicy(TenantScopedModel):
    """OD-005 ("matriz de autoridade de aprovação") container — genuinely
    open, see DECISIONS_TAKEN.md#S07-REVIEW-001. No CRUD/publish endpoint
    is exposed in V1 (ART-006 has none for this resource, unlike
    RatingTable/PricingParameterSet/RuleVersion) — the model exists only so
    `quote_decision.authority_policy_id` (ART-012 V023) has something to
    reference once OD-005 is resolved and a Change Request adds the
    endpoint. Absence of a PUBLISHED policy is treated as "no configured
    limit" (any actor with q360.approve + quote:approve may decide), not a
    fail-closed block — see DECISIONS_TAKEN.md."""

    STATUS_CHOICES = (("DRAFT", "DRAFT"), ("PUBLISHED", "PUBLISHED"), ("RETIRED", "RETIRED"))

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    code = models.CharField(max_length=80)
    version_no = models.IntegerField()
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DRAFT")
    policy_json = models.JSONField()
    checksum = models.CharField(max_length=128, null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.CharField(max_length=200, null=True, blank=True)
    approved_by = models.CharField(max_length=200, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "authority_policy"


class ReviewTask(TenantScopedModel):
    STATUS_CHOICES = [(s.value, s.value) for s in ReviewTaskStatus]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    quote = models.ForeignKey(Quote, on_delete=models.DO_NOTHING, db_column="quote_id", related_name="review_tasks")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=ReviewTaskStatus.OPEN.value)
    assigned_to = models.CharField(max_length=200, null=True, blank=True)
    created_by = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    row_version = models.BigIntegerField(default=0)

    class Meta:
        managed = False
        db_table = "review_task"


class ReviewNote(TenantScopedModel):
    """ART-012 V023. No endpoint exposes this in ART-006 V1 (same posture
    as apps.product's Benefit/PlanBenefit, see
    OPEN_DECISIONS.md#S02-CONTRACT-001) — the table exists for schema
    completeness only."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    review_task = models.ForeignKey(ReviewTask, on_delete=models.CASCADE, db_column="review_task_id", related_name="notes")
    note_text = models.TextField()
    created_by = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "review_note"


class QuoteDecision(TenantScopedModel):
    DECISION_CHOICES = [(d.value, d.value) for d in QuoteDecisionType]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    quote = models.ForeignKey(Quote, on_delete=models.DO_NOTHING, db_column="quote_id", related_name="decisions")
    review_task = models.ForeignKey(
        ReviewTask, on_delete=models.DO_NOTHING, db_column="review_task_id", null=True, blank=True
    )
    authority_policy = models.ForeignKey(
        AuthorityPolicy, on_delete=models.DO_NOTHING, db_column="authority_policy_id", null=True, blank=True
    )
    decision = models.CharField(max_length=20, choices=DECISION_CHOICES)
    reason_code = models.CharField(max_length=100)
    reason_text = models.TextField(null=True, blank=True)
    decided_by = models.CharField(max_length=200)
    submitted_by = models.CharField(max_length=200, null=True, blank=True)
    decided_at = models.DateTimeField(auto_now_add=True)
    snapshot = models.ForeignKey(
        QuoteSnapshot, on_delete=models.DO_NOTHING, db_column="snapshot_id", null=True, blank=True
    )

    class Meta:
        managed = False
        db_table = "quote_decision"


class DocumentTemplateVersion(TenantScopedModel):
    """OD-006 ("template oficial da proposta") container — genuinely open,
    see DECISIONS_TAKEN.md#S08-DOCUMENT-001. `storage_ref` is a pointer
    (like `RuleVersion.artifact_ref`), never real legal/branded document
    content."""

    STATUS_CHOICES = [(s.value, s.value) for s in DocumentTemplateStatus]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    template_code = models.CharField(max_length=80)
    version_no = models.IntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=DocumentTemplateStatus.DRAFT.value)
    storage_ref = models.TextField()
    checksum = models.CharField(max_length=128)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.CharField(max_length=200, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # A proposta ou a apólice; e os ficheiros opcionais carregados pelo GTE:
    # papel timbrado (PDF) e modelo Word com marcas {{variável}}.
    document_type = models.CharField(max_length=20, default="QUOTE_PROPOSAL")
    letterhead_key = models.TextField(null=True, blank=True)
    letterhead_name = models.CharField(max_length=255, null=True, blank=True)
    word_key = models.TextField(null=True, blank=True)
    word_name = models.CharField(max_length=255, null=True, blank=True)
    settings_json = models.JSONField(default=dict)

    class Meta:
        managed = False
        db_table = "document_template_version"


class NumberingSequence(TenantScopedModel):
    """OD-007/OD-008 ("política de numeração") — genuinely open, see
    DECISIONS_TAKEN.md#S08-DOCUMENT-001. The atomic counter mechanism is
    real; the prefix/suffix format is a placeholder until a real numbering
    policy is approved."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    sequence_code = models.CharField(max_length=80)
    period_key = models.CharField(max_length=40)
    current_value = models.BigIntegerField(default=0)
    prefix = models.CharField(max_length=50, null=True, blank=True)
    suffix = models.CharField(max_length=50, null=True, blank=True)
    row_version = models.BigIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = "numbering_sequence"


class Document(TenantScopedModel):
    TYPE_CHOICES = [(t.value, t.value) for t in DocumentType]
    STATUS_CHOICES = [(s.value, s.value) for s in DocumentStatus]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    quote = models.ForeignKey(Quote, on_delete=models.DO_NOTHING, db_column="quote_id", related_name="documents")
    snapshot = models.ForeignKey(QuoteSnapshot, on_delete=models.DO_NOTHING, db_column="snapshot_id")
    template_version = models.ForeignKey(
        DocumentTemplateVersion, on_delete=models.DO_NOTHING, db_column="template_version_id"
    )
    document_type = models.CharField(max_length=30, choices=TYPE_CHOICES, default=DocumentType.QUOTE_PROPOSAL.value)
    document_number = models.CharField(max_length=100, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=DocumentStatus.REQUESTED.value)
    storage_ref = models.TextField(null=True, blank=True)
    checksum = models.CharField(max_length=128, null=True, blank=True)
    failure_code = models.CharField(max_length=100, null=True, blank=True)
    requested_by = models.CharField(max_length=200)
    requested_at = models.DateTimeField(auto_now_add=True)
    generated_at = models.DateTimeField(null=True, blank=True)
    format = models.CharField(max_length=10, default="JSON")
    scenario_id = models.UUIDField(null=True, blank=True)
    content_type = models.CharField(max_length=100, null=True, blank=True)
    file_name = models.CharField(max_length=200, null=True, blank=True)
    proposal_no = models.IntegerField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "document"


class QuoteScenario(TenantScopedModel):
    """Cenário de cotação (R5). `parameters_json` = {selection, adjustments};
    `result_json` = último cálculo (pré-visualização, nada persistido no
    motor); `inputs_hash` deteta quando o resultado ficou desatualizado
    (plano, tarifas, membros ou parâmetros mudaram)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    quote = models.ForeignKey(Quote, on_delete=models.CASCADE, db_column="quote_id", related_name="scenarios")
    name = models.CharField(max_length=200)
    description = models.TextField(null=True, blank=True)
    parameters_json = models.JSONField(default=dict)
    result_json = models.JSONField(default=dict)
    inputs_hash = models.CharField(max_length=64, null=True, blank=True)
    base_scenario = models.ForeignKey(
        "self", on_delete=models.SET_NULL, db_column="base_scenario_id", null=True, blank=True, related_name="clones"
    )
    is_selected = models.BooleanField(default=False)
    created_by = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    row_version = models.BigIntegerField(default=0)

    class Meta:
        managed = False
        db_table = "quote_scenario"


class QuoteVersion(TenantScopedModel):
    """Ponto de gravação imutável do estado editável de uma cotação."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    quote = models.ForeignKey(Quote, on_delete=models.CASCADE, db_column="quote_id", related_name="versions")
    version_no = models.IntegerField()
    source = models.CharField(max_length=30)
    reason = models.TextField(null=True, blank=True)
    snapshot_json = models.JSONField()
    checksum = models.CharField(max_length=64)
    total_amount = models.DecimalField(max_digits=30, decimal_places=8, null=True, blank=True)
    currency_code = models.CharField(max_length=3, null=True, blank=True)
    created_by = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "quote_version"
