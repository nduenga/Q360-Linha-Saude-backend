"""ORM adapters for the policy module's physical schema
(ROADMAP_APOLICES.md Fase 2). `managed = False` for the same reason as
every other module (DOC-000 s3 P-08): the physical schema is owned
exclusively by `0001_policy_baseline.py`, never by `makemigrations`. All
models inherit `TenantScopedModel` (Q360-S1-04).
"""
from __future__ import annotations

import uuid

from django.db import models

from apps.client.infrastructure.models import InsuredMember, Proposer
from apps.eligibility.infrastructure.models import EligibilityEvaluation
from apps.foundation.infrastructure.models import RuleVersion, Tenant
from apps.foundation.infrastructure.tenant_scoping import TenantScopedModel
from apps.policy.domain.enums import (
    EndorsementType,
    PolicyMemberStatus,
    PolicyStatus,
    PolicyType,
    SignatoryCapacity,
    SignatoryDocumentType,
    SignatureMethod,
)
from apps.product.infrastructure.models import Plan
from apps.quote.infrastructure.models import Quote, QuoteSnapshot


class Policy(TenantScopedModel):
    TYPE_CHOICES = [(t.value, t.value) for t in PolicyType]
    STATUS_CHOICES = [(s.value, s.value) for s in PolicyStatus]
    PAYMENT_FREQUENCY_CHOICES = [
        ("ANUAL", "ANUAL"),
        ("SEMESTRAL", "SEMESTRAL"),
        ("TRIMESTRAL", "TRIMESTRAL"),
        ("MENSAL", "MENSAL"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    policy_number = models.CharField(max_length=100, null=True, blank=True)
    # OneToOne: a Quote produces at most one Policy (PO-APO-1).
    source_quote = models.OneToOneField(Quote, on_delete=models.DO_NOTHING, db_column="source_quote_id")
    contracted_terms_snapshot = models.ForeignKey(
        QuoteSnapshot, on_delete=models.DO_NOTHING, db_column="contracted_terms_snapshot_id"
    )
    proposer = models.ForeignKey(Proposer, on_delete=models.DO_NOTHING, db_column="proposer_id")
    plan = models.ForeignKey(Plan, on_delete=models.DO_NOTHING, db_column="plan_id")
    policy_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    term_months = models.IntegerField()
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    # ROADMAP_APOLICES.md Fase 3 / OD-APO-003 (apps.policy 0002_requested_
    # start_date): the tomador's requested vigência start, validated and
    # used only by issuance_service — never read as the actual start_date.
    requested_start_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=PolicyStatus.PENDING_FIRST_PREMIUM.value)
    payment_frequency = models.CharField(max_length=20, choices=PAYMENT_FREQUENCY_CHOICES)
    currency_code = models.CharField(max_length=3, null=True, blank=True)
    cancellation_reason_code = models.CharField(max_length=100, null=True, blank=True)
    cancellation_effective_date = models.DateField(null=True, blank=True)
    cancelled_by = models.CharField(max_length=200, null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    termination_reason_code = models.CharField(max_length=100, null=True, blank=True)
    terminated_at = models.DateTimeField(null=True, blank=True)
    issued_by = models.CharField(max_length=200)
    issued_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    row_version = models.BigIntegerField(default=0)

    class Meta:
        managed = False
        db_table = "policy"

    def __str__(self) -> str:  # pragma: no cover - debug helper
        return f"Policy({self.policy_number or self.id}, {self.status})"


class PolicySignature(TenantScopedModel):
    DOCUMENT_TYPE_CHOICES = [(t.value, t.value) for t in SignatoryDocumentType]
    CAPACITY_CHOICES = [(c.value, c.value) for c in SignatoryCapacity]
    METHOD_CHOICES = [(m.value, m.value) for m in SignatureMethod]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    policy = models.OneToOneField(Policy, on_delete=models.DO_NOTHING, db_column="policy_id", related_name="signature")
    signatory_name = models.CharField(max_length=250)
    signatory_document_type = models.CharField(max_length=30, choices=DOCUMENT_TYPE_CHOICES)
    signatory_document_number = models.CharField(max_length=100)
    signatory_capacity = models.CharField(max_length=30, choices=CAPACITY_CHOICES)
    signature_method = models.CharField(max_length=20, choices=METHOD_CHOICES, default=SignatureMethod.PRESENCIAL.value)
    signed_at = models.DateTimeField()
    signed_document_ref = models.TextField(null=True, blank=True)
    signed_document_checksum = models.CharField(max_length=128, null=True, blank=True)
    registered_by = models.CharField(max_length=200)
    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "policy_signature"


class PolicyMember(TenantScopedModel):
    STATUS_CHOICES = [(s.value, s.value) for s in PolicyMemberStatus]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    policy = models.ForeignKey(Policy, on_delete=models.DO_NOTHING, db_column="policy_id", related_name="members")
    member = models.ForeignKey(InsuredMember, on_delete=models.DO_NOTHING, db_column="member_id")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PolicyMemberStatus.PENDING.value)
    pending_reason_code = models.CharField(max_length=100, null=True, blank=True)
    inclusion_date = models.DateField(null=True, blank=True)
    exclusion_date = models.DateField(null=True, blank=True)
    eligibility_evaluation = models.ForeignKey(
        EligibilityEvaluation, on_delete=models.DO_NOTHING, db_column="eligibility_evaluation_id", null=True, blank=True
    )
    rule_version = models.ForeignKey(
        RuleVersion, on_delete=models.DO_NOTHING, db_column="rule_version_id", null=True, blank=True
    )
    waiting_period_ends_json = models.JSONField(default=dict)
    loading_percentage = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    row_version = models.BigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = "policy_member"


class PremiumInstallment(TenantScopedModel):
    STATUS_CHOICES = [
        ("DUE", "DUE"),
        ("PAID", "PAID"),
        ("OVERDUE", "OVERDUE"),
        ("VOID", "VOID"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    policy = models.ForeignKey(Policy, on_delete=models.DO_NOTHING, db_column="policy_id", related_name="installments")
    installment_no = models.IntegerField()
    period_from = models.DateField()
    period_to = models.DateField()
    due_date = models.DateField()
    amount = models.DecimalField(max_digits=30, decimal_places=8)
    currency_code = models.CharField(max_length=3)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DUE")
    paid_at = models.DateTimeField(null=True, blank=True)
    payment_reference = models.CharField(max_length=200, null=True, blank=True)
    payment_method = models.CharField(max_length=50, null=True, blank=True)
    registered_by = models.CharField(max_length=200, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = "premium_installment"


class PremiumDefaultNotice(TenantScopedModel):
    OUTCOME_CHOICES = [
        ("PAID", "PAID"),
        ("SUSPENDED", "SUSPENDED"),
        ("TERMINATED", "TERMINATED"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    installment = models.ForeignKey(
        PremiumInstallment, on_delete=models.DO_NOTHING, db_column="installment_id", related_name="default_notices"
    )
    sent_at = models.DateTimeField()
    registered_mail_reference = models.CharField(max_length=200)
    new_deadline = models.DateField()
    suspension_effective_at = models.DateTimeField(null=True, blank=True)
    outcome = models.CharField(max_length=20, choices=OUTCOME_CHOICES, null=True, blank=True)
    registered_by = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "premium_default_notice"


class PolicyEndorsement(TenantScopedModel):
    TYPE_CHOICES = [(t.value, t.value) for t in EndorsementType]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    policy = models.ForeignKey(Policy, on_delete=models.DO_NOTHING, db_column="policy_id", related_name="endorsements")
    endorsement_number = models.IntegerField()
    endorsement_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    effective_date = models.DateField()
    payload_json = models.JSONField(default=dict)
    created_by = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "policy_endorsement"


class PolicyStateHistory(TenantScopedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.DO_NOTHING, db_column="tenant_id")
    policy = models.ForeignKey(Policy, on_delete=models.DO_NOTHING, db_column="policy_id", related_name="state_history")
    from_status = models.CharField(max_length=30, null=True, blank=True)
    to_status = models.CharField(max_length=30)
    reason_code = models.CharField(max_length=100, null=True, blank=True)
    reason_text = models.TextField(null=True, blank=True)
    changed_by = models.CharField(max_length=200)
    changed_at = models.DateTimeField(auto_now_add=True)
    correlation_id = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        managed = False
        db_table = "policy_state_history"
