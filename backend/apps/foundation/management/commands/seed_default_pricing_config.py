"""Dev/demo convenience: seed a sensible, out-of-the-box configuration —
a RatingTable, a PricingParameterSet, an ELIGIBILITY RuleVersion and a
document template — all created DRAFT then published immediately, so a
freshly-created Product/Plan can be priced, checked for eligibility and
have a proposal generated without first hand-configuring all 4 of these
through Administration.

Idempotent: skips whatever already has a PUBLISHED row for its code,
rather than piling up a new version every time this is re-run.

Not an ART-006 endpoint, not a Product Owner-approved configuration
catalogue — purely local/demo tooling, same posture as
`seed_dev_tenant`/`issue_dev_token`/`create_staff_account`.
"""
from __future__ import annotations

import datetime
from types import SimpleNamespace

from django.core.management.base import BaseCommand, CommandError

from apps.business_config.application.service import approve_configuration, create_configuration, submit_configuration
from apps.business_config.infrastructure.models import BusinessConfiguration
from apps.business_config.seed.actuarial_model import build_actuarial_model
from apps.foundation.application.context import CurrentActorProvider
from apps.foundation.application.rule_service import create_rule_version, publish_rule_version
from apps.foundation.domain.actor import Actor
from apps.foundation.domain.tenant import TenantId
from apps.foundation.infrastructure.models import RuleVersion, Tenant
from apps.pricing.application.rating_table_service import create_rating_table, publish_rating_table
from apps.pricing.infrastructure.models import RatingTable
from apps.product.application.pricing_parameter_service import (
    create_pricing_parameter_set,
    publish_pricing_parameter_set,
)
from apps.product.infrastructure.models import PricingParameterSet
from apps.quote.application.document_service import create_document_template, publish_document_template
from apps.quote.infrastructure.models import DocumentTemplateVersion

RATING_TABLE_CODE = "RATING-DEFAULT"
PARAMETER_SET_CODE = "PARAMS-DEFAULT"
ELIGIBILITY_RULE_CODE = "ELIGIBILITY-DEFAULT"
DOCUMENT_TEMPLATE_CODE = "QUOTE_PROPOSAL_DEFAULT"  # fixed convention, document_service.DEFAULT_TEMPLATE_CODE

# All 4 resolvers (resolve_rating_table / resolve_pricing_parameter_set /
# resolve_eligibility_rule_version / _resolve_published_template) require
# `effective_from <= <the quote's own effective_date>` - using today's date
# here would make a "default" break for any quote whose effective_date is
# earlier than the day this command happens to be run (a very likely case
# for pre-existing test quotes). A safely-past anchor date instead covers
# any realistic past/current/near-future quote.
EARLIEST_EFFECTIVE_FROM = datetime.date(2020, 1, 1)


class Command(BaseCommand):
    help = "Seed + publish a default RatingTable, PricingParameterSet, ELIGIBILITY RuleVersion and document template."

    def add_arguments(self, parser):
        parser.add_argument("--tenant-code", default="dev-tenant")

    def handle(self, *args, **options):
        try:
            tenant = Tenant.objects.get(code=options["tenant_code"])
        except Tenant.DoesNotExist as exc:
            raise CommandError(
                f"No tenant with code '{options['tenant_code']}'. Run "
                f"`manage.py seed_dev_tenant --code {options['tenant_code']}` first."
            ) from exc

        # No HTTP request here to authenticate a real actor from, so this
        # binds one directly - same pattern as apps.customer_portal's
        # pre-auth views binding an anonymous actor before a tenant is
        # otherwise resolvable (see interfaces/views.py in that app).
        CurrentActorProvider.bind(
            Actor(actor_id="system-seed", tenant_id=TenantId.parse(tenant.id), roles=frozenset(), scopes=frozenset())
        )

        self._seed_rating_table()
        self._seed_parameter_set()
        self._seed_eligibility_rule()
        self._seed_document_template()
        self._seed_business_config()

    def _seed_rating_table(self) -> None:
        if RatingTable.objects.filter(code=RATING_TABLE_CODE, status="PUBLISHED").exists():
            self.stdout.write(f"RatingTable '{RATING_TABLE_CODE}' already published — skipping.")
            return
        rating_table = create_rating_table(
            code=RATING_TABLE_CODE,
            name="Tabela de fatores por idade (padrão)",
            effective_from=EARLIEST_EFFECTIVE_FROM,
            effective_to=None,
            currency_code="AOA",
            factor_rows=[
                {"factorCode": "AGE_FACTOR", "dimensions": {"ageBand": "0-17"}, "factorValue": "0.60"},
                {"factorCode": "AGE_FACTOR", "dimensions": {"ageBand": "18-29"}, "factorValue": "0.80"},
                {"factorCode": "AGE_FACTOR", "dimensions": {"ageBand": "30-39"}, "factorValue": "1.00"},
                {"factorCode": "AGE_FACTOR", "dimensions": {"ageBand": "40-49"}, "factorValue": "1.20"},
                {"factorCode": "AGE_FACTOR", "dimensions": {"ageBand": "50-59"}, "factorValue": "1.50"},
                {"factorCode": "AGE_FACTOR", "dimensions": {"ageBand": "60-69"}, "factorValue": "1.90"},
                {"factorCode": "AGE_FACTOR", "dimensions": {"ageBand": "70+"}, "factorValue": "2.40"},
                # Catch-all (empty dimensions, lowest priority): never leaves
                # a member with no matching factor if ageBand is missing/
                # unrecognised from the pricing call's context.
                {"factorCode": "AGE_FACTOR", "dimensions": {}, "factorValue": "1.00", "priority": -1},
            ],
        )
        publish_rating_table(rating_table)
        self.stdout.write(self.style.SUCCESS(f"Created + published RatingTable '{RATING_TABLE_CODE}'"))

    def _seed_parameter_set(self) -> None:
        if PricingParameterSet.objects.filter(code=PARAMETER_SET_CODE, status="PUBLISHED").exists():
            self.stdout.write(f"PricingParameterSet '{PARAMETER_SET_CODE}' already published — skipping.")
            return
        parameter_set = create_pricing_parameter_set(
            code=PARAMETER_SET_CODE,
            effective_from=EARLIEST_EFFECTIVE_FROM,
            effective_to=None,
            parameter_rows=[
                {"parameter_code": "BASE_PREMIUM", "value_type": "DECIMAL", "decimal_value": "15000.00"},
            ],
        )
        publish_pricing_parameter_set(parameter_set)
        self.stdout.write(self.style.SUCCESS(f"Created + published PricingParameterSet '{PARAMETER_SET_CODE}'"))

    def _seed_eligibility_rule(self) -> None:
        if RuleVersion.objects.filter(rule_set__code=ELIGIBILITY_RULE_CODE, status="PUBLISHED").exists():
            self.stdout.write(f"ELIGIBILITY RuleVersion '{ELIGIBILITY_RULE_CODE}' already published — skipping.")
            return
        # Deliberately permissive (0-75, no relationship/waiting-period
        # restrictions): a usable-by-default rule, not a real underwriting
        # policy — Administration > Configuração de Pricing is where a
        # tenant tightens this for their actual market rules.
        rule_version = create_rule_version(
            code=ELIGIBILITY_RULE_CODE,
            name="Elegibilidade padrão (0-75 anos, sem restrições)",
            rule_domain="ELIGIBILITY",
            effective_from=EARLIEST_EFFECTIVE_FROM,
            effective_to=None,
            artifact_type="JSON",
            artifact_ref='{"minEntryAge": 0, "maxEntryAge": 75}',
            artifact_checksum=None,
        )
        publish_rule_version(rule_version)
        self.stdout.write(self.style.SUCCESS(f"Created + published ELIGIBILITY RuleVersion '{ELIGIBILITY_RULE_CODE}'"))

    def _seed_document_template(self) -> None:
        if DocumentTemplateVersion.objects.filter(template_code=DOCUMENT_TEMPLATE_CODE, status="PUBLISHED").exists():
            self.stdout.write(f"Document template '{DOCUMENT_TEMPLATE_CODE}' already published — skipping.")
            return
        template = create_document_template(
            template_code=DOCUMENT_TEMPLATE_CODE,
            storage_ref="templates/quote-proposal-default.json",
            effective_from=EARLIEST_EFFECTIVE_FROM,
            effective_to=None,
        )
        publish_document_template(template)
        self.stdout.write(self.style.SUCCESS(f"Created + published document template '{DOCUMENT_TEMPLATE_CODE}'"))

    def _seed_business_config(self) -> None:
        default_configs = {
            "pricing.reference_premiums": {
                "currency_code": "AOA",
                "premiums": [
                    {"plan": "FAMILIA-PLUS", "age_from": 0, "age_to": 17, "annual_premium": "150000"},
                    {"plan": "FAMILIA-PLUS", "age_from": 18, "age_to": 29, "annual_premium": "220000"},
                    {"plan": "FAMILIA-PLUS", "age_from": 30, "age_to": 39, "annual_premium": "300000"},
                    {"plan": "FAMILIA-PLUS", "age_from": 40, "age_to": 49, "annual_premium": "420000"},
                    {"plan": "FAMILIA-PLUS", "age_from": 50, "age_to": 59, "annual_premium": "570000"},
                    {"plan": "FAMILIA-PLUS", "age_from": 60, "age_to": 69, "annual_premium": "760000"},
                    {"plan": "FAMILIA-PLUS", "age_from": 70, "age_to": 75, "annual_premium": "980000"},
                    {"plan": "EMPRESA-ESSENCIAL", "age_from": 0, "age_to": 17, "annual_premium": "120000"},
                    {"plan": "EMPRESA-ESSENCIAL", "age_from": 18, "age_to": 29, "annual_premium": "180000"},
                    {"plan": "EMPRESA-ESSENCIAL", "age_from": 30, "age_to": 39, "annual_premium": "240000"},
                    {"plan": "EMPRESA-ESSENCIAL", "age_from": 40, "age_to": 49, "annual_premium": "340000"},
                    {"plan": "EMPRESA-ESSENCIAL", "age_from": 50, "age_to": 59, "annual_premium": "470000"},
                    {"plan": "EMPRESA-ESSENCIAL", "age_from": 60, "age_to": 69, "annual_premium": "620000"},
                    {"plan": "EMPRESA-ESSENCIAL", "age_from": 70, "age_to": 75, "annual_premium": "820000"},
                ],
            },
            "pricing.factors": {
                "factors": [
                    {"code": "AGE_FACTOR", "dimension": "ageBand", "condition": "0-17", "factor": "0.60"},
                    {"code": "AGE_FACTOR", "dimension": "ageBand", "condition": "18-29", "factor": "0.80"},
                    {"code": "AGE_FACTOR", "dimension": "ageBand", "condition": "30-39", "factor": "1.00"},
                    {"code": "AGE_FACTOR", "dimension": "ageBand", "condition": "40-49", "factor": "1.20"},
                    {"code": "AGE_FACTOR", "dimension": "ageBand", "condition": "50-59", "factor": "1.50"},
                    {"code": "AGE_FACTOR", "dimension": "ageBand", "condition": "60-69", "factor": "1.90"},
                    {"code": "AGE_FACTOR", "dimension": "ageBand", "condition": "70+", "factor": "2.40"},
                    {"code": "AGE_FACTOR", "dimension": "ageBand", "condition": "*", "factor": "1.00"},
                ]
            },
            "pricing.adjustments": {"rules": []},
            "pricing.taxes_fees": {"charges": []},
        }

        create_request = SimpleNamespace(actor=SimpleNamespace(subject="system-seed"))
        approval_request = SimpleNamespace(actor=SimpleNamespace(subject="system-approver"))
        for config_key, value in default_configs.items():
            if BusinessConfiguration.objects.filter(
                tenant_id=CurrentActorProvider.get().tenant_id.value,
                config_key=config_key,
                status="PUBLISHED",
            ).exists():
                self.stdout.write(f"Business configuration '{config_key}' already published — skipping.")
                continue

            config = create_configuration(
                create_request,
                config_key=config_key,
                value=value,
                effective_from=EARLIEST_EFFECTIVE_FROM,
                effective_to=None,
                metadata={"source": "seed_default_pricing_config", "scope": "default"},
            )
            submit_configuration(create_request, config)
            approve_configuration(approval_request, config)
            self.stdout.write(
                self.style.SUCCESS(f"Created + published BusinessConfiguration '{config_key}'")
            )

        self._seed_actuarial_model_draft()

    def _seed_actuarial_model_draft(self) -> None:
        config_key = "pricing.actuarial_model"
        tenant_id = CurrentActorProvider.get().tenant_id.value
        if BusinessConfiguration.objects.filter(tenant_id=tenant_id, config_key=config_key).exists():
            self.stdout.write(f"Business configuration '{config_key}' already exists — skipping.")
            return

        request = SimpleNamespace(actor=SimpleNamespace(subject="system-seed"))
        create_configuration(
            request,
            config_key=config_key,
            value=build_actuarial_model(),
            effective_from=EARLIEST_EFFECTIVE_FROM,
            effective_to=None,
            metadata={
                "source": "Modelo_Actuarial_Saude_SAU_SAG_Angola.xlsx",
                "scope": "actuarial-model-draft",
                "requiresActuarialApproval": True,
            },
        )
        self.stdout.write(self.style.SUCCESS("Created DRAFT BusinessConfiguration 'pricing.actuarial_model'"))
