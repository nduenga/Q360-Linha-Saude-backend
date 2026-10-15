"""Seed a complete, repeatable Q360 Saúde demonstration tenant.

The command intentionally uses the same application services used by the
HTTP API for quotation, eligibility, pricing, approval and policy issuance.
It is local/demo tooling only; it creates no production-like credentials and
does not delete or alter unrelated tenant data.
"""
from __future__ import annotations

import datetime
import json
import uuid
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.client.application.member_service import create_member
from apps.client.application.proposer_service import create_proposer
from apps.client.application.relationship_service import ensure_relationship_catalog
from apps.client.infrastructure.models import InsuredMember, Proposer
from apps.eligibility.application.use_cases import EvaluateEligibilityUseCase
from apps.eligibility.domain.enums import EligibilityDecision
from apps.eligibility.infrastructure.models import EligibilityEvaluation
from apps.foundation.application.context import CurrentActorProvider
from apps.foundation.application.rule_service import create_rule_version, publish_rule_version
from apps.foundation.domain.actor import Actor
from apps.foundation.domain.permissions import Role
from apps.foundation.domain.scopes import Scope
from apps.foundation.domain.tenant import TenantId
from apps.foundation.infrastructure.models import RuleVersion, Tenant
from apps.policy.application.issuance_service import issue_policy, register_first_premium_payment
from apps.policy.infrastructure.models import Policy, PolicyMember
from apps.pricing.application.rating_table_service import create_rating_table, publish_rating_table
from apps.pricing.infrastructure.models import RatingTable
from apps.product.application.benefit_service import add_plan_benefit, ensure_market_catalog
from apps.product.application.pricing_parameter_service import (
    create_pricing_parameter_set,
    publish_pricing_parameter_set,
)
from apps.product.application.product_service import create_plan, create_product
from apps.product.infrastructure.models import Benefit, Plan, PlanBenefit, PricingParameterSet, Product
from apps.quote.application.document_service import create_document_template, publish_document_template
from apps.quote.application.quote_service import (
    create_quote,
    decide_quote,
    price_quote,
    submit_quote,
)
from apps.quote.domain.enums import QuoteDecisionType, QuoteMemberStatus, QuoteStatus
from apps.quote.infrastructure.models import DocumentTemplateVersion, Quote, QuoteMember
from apps.platform_admin.infrastructure.models import PlatformAdmin
from apps.staff_accounts.infrastructure.models import StaffAccount, StaffAccountRole


_PASSWORD = "Q360Demo!2026"
# Super administrador da plataforma (equipa interna; nao pertence a nenhum tenant).
_PLATFORM_ADMIN = ("superadmin.demo@q360.local", "Super Administrador Demo")
_RATING_CODE = "DEMO-RATING-HEALTH"
_PARAMETER_CODE = "DEMO-PARAMS-HEALTH"
_ELIGIBILITY_CODE = "DEMO-ELIGIBILITY-ANGOLA"
_DOCUMENT_TEMPLATE_CODE = "DEMO-QUOTE-PROPOSAL"

_STAFF = (
    ("admin", "admin.demo@q360.local", "Administrador Demo", (Role.ADMIN,)),
    ("manager", "gestor.demo@q360.local", "Gestor de Subscrição Demo", (Role.SUBSCRIPTION_MANAGER,)),
    ("subscriber", "subscritor.demo@q360.local", "Subscritor Demo", (Role.SUBSCRIBER,)),
)


class Command(BaseCommand):
    help = "Seed an idempotent demo tenant with staff, policies, coverages and portal-client scenarios."

    def add_arguments(self, parser):
        parser.add_argument("--tenant-code", default="demo-saude")
        parser.add_argument("--tenant-name", default="Q360 Saúde — Demonstração")
        parser.add_argument(
            "--no-portal", action="store_true",
            help="Não criar os dados do Portal Cliente (seed_portal_demo), só a plataforma.",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                "seed_demo_data só pode ser executado em ambientes DEBUG. Em produção, use prepare_portal_test_accounts com um ID de tenant explícito."
            )
        tenant, _ = Tenant.objects.get_or_create(
            code=options["tenant_code"], defaults={"name": options["tenant_name"]}
        )
        self._ensure_platform_admin()
        original_actor = CurrentActorProvider.bind(None)
        try:
            staff = self._ensure_staff(tenant)
            self._bind(tenant, staff["admin"], Role.ADMIN)
            ensure_relationship_catalog(tenant.id)
            self._ensure_configuration(tenant)
            plans = self._ensure_products_and_plans(tenant)

            ana_policy = self._ensure_ana_family_policy(tenant, staff, plans["family"])
            carlos_policy = self._ensure_carlos_pending_policy(tenant, staff, plans["family"])
            company_policy = self._ensure_company_policy(tenant, staff, plans["corporate"])
            self._ensure_backoffice_quote_states(tenant, staff, plans["family"])
        finally:
            CurrentActorProvider.reset(original_actor)

        self._print_summary(
            tenant=tenant,
            staff=staff,
            policies={"Ana Silva": ana_policy, "Carlos Mendes": carlos_policy, "Empresa Kilamba": company_policy},
        )
        if not options["no_portal"]:
            self.stdout.write("")
            call_command("seed_portal_demo", tenant_code=tenant.code, stdout=self.stdout)

    @staticmethod
    def _ensure_platform_admin() -> None:
        """Idempotente: cria o super admin demo ou repoe a palavra-passe e o
        estado documentados, tal como acontece com o staff demo."""
        email, name = _PLATFORM_ADMIN
        admin = PlatformAdmin.objects.filter(email__iexact=email).first()
        if admin is None:
            PlatformAdmin.objects.create(email=email, name=name, password_hash=make_password(_PASSWORD))
        else:
            PlatformAdmin.objects.filter(id=admin.id).update(
                password_hash=make_password(_PASSWORD), status=PlatformAdmin.ACTIVE, failed_login_attempts=0, locked_until=None
            )

    @staticmethod
    def _bind(tenant: Tenant, account: StaffAccount, role: Role) -> None:
        CurrentActorProvider.bind(
            Actor(
                actor_id=str(account.id),
                tenant_id=TenantId.parse(tenant.id),
                roles=frozenset({role}),
                scopes=frozenset(Scope),
            )
        )

    def _ensure_staff(self, tenant: Tenant) -> dict[str, StaffAccount]:
        accounts: dict[str, StaffAccount] = {}
        for key, email, name, roles in _STAFF:
            account = StaffAccount.all_tenants.filter(tenant_id=tenant.id, email__iexact=email).first()
            if account is None:
                account = StaffAccount.all_tenants.create(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    email=email,
                    name=name,
                    password_hash=make_password(_PASSWORD),
                    status=StaffAccount.ACTIVE,
                )
            else:
                # The command owns these clearly named demo accounts, so a
                # rerun restores the documented login credentials.
                StaffAccount.all_tenants.filter(id=account.id).update(
                    name=name,
                    password_hash=make_password(_PASSWORD),
                    status=StaffAccount.ACTIVE,
                    failed_login_attempts=0,
                    locked_until=None,
                )
                account.refresh_from_db()

            StaffAccountRole.all_tenants.filter(staff_account_id=account.id).delete()
            StaffAccountRole.all_tenants.bulk_create(
                [
                    StaffAccountRole(
                        id=uuid.uuid4(), tenant_id=tenant.id, staff_account_id=account.id, role=role.value
                    )
                    for role in roles
                ]
            )
            accounts[key] = account
        return accounts

    def _ensure_configuration(self, tenant: Tenant) -> None:
        effective_from = datetime.date(2020, 1, 1)

        rating = RatingTable.objects.filter(code=_RATING_CODE).order_by("-version_no").first()
        if rating is None:
            rating = create_rating_table(
                code=_RATING_CODE,
                name="Tabela de tarifas demo por faixa etária",
                effective_from=effective_from,
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
                    {"factorCode": "AGE_FACTOR", "dimensions": {}, "factorValue": "1.00", "priority": -1},
                ],
            )
        if rating.status == "DRAFT":
            publish_rating_table(rating)

        parameter_set = PricingParameterSet.objects.filter(code=_PARAMETER_CODE).order_by("-version_no").first()
        if parameter_set is None:
            parameter_set = create_pricing_parameter_set(
                code=_PARAMETER_CODE,
                effective_from=effective_from,
                effective_to=None,
                parameter_rows=[
                    {"parameter_code": "BASE_PREMIUM", "value_type": "DECIMAL", "decimal_value": "15000.00"},
                ],
            )
        if parameter_set.status == "DRAFT":
            publish_pricing_parameter_set(parameter_set)

        rule = RuleVersion.objects.filter(rule_set__code=_ELIGIBILITY_CODE).order_by("-version_no").first()
        if rule is None:
            rule = create_rule_version(
                code=_ELIGIBILITY_CODE,
                name="Elegibilidade demo Angola — família e pré-existências",
                rule_domain="ELIGIBILITY",
                effective_from=effective_from,
                effective_to=None,
                artifact_type="JSON",
                artifact_ref=json.dumps(
                    {
                        "minEntryAge": 0,
                        "maxEntryAge": 75,
                        "allowedRelationshipCodes": ["TITULAR", "CONJUGE", "FILHO", "ASCENDENTE"],
                        "categoryRules": {
                            "CHILD": {"maxAgeWithoutProof": 18, "maxAgeWithProof": 25},
                            "SPOUSE": {"requiresUnionProofFor": ["UNIAO_DE_FACTO"]},
                            "ASCENDANT": {"requiresCohabitationOrFinancialDependency": True},
                        },
                        "waitingPeriod": {
                            "defaultDays": 30,
                            "defaultDaysByBenefitCategory": {"PHARMACY": 15, "DENTAL": 90, "MATERNITY": 365},
                            "waivedOnVerifiedPortability": True,
                        },
                        "preExistingConditionPolicy": {"mode": "LOADING", "loadingPercentage": "15.00"},
                    }
                ),
                artifact_checksum=None,
            )
        if rule.status == "DRAFT":
            publish_rule_version(rule)

        template = DocumentTemplateVersion.objects.filter(template_code=_DOCUMENT_TEMPLATE_CODE).order_by("-version_no").first()
        if template is None:
            template = create_document_template(
                template_code=_DOCUMENT_TEMPLATE_CODE,
                storage_ref="templates/demo-quote-proposal.json",
                effective_from=effective_from,
                effective_to=None,
            )
        if template.status == "DRAFT":
            publish_document_template(template)

        self._assert_unambiguous_pricing_configuration()

    @staticmethod
    def _assert_unambiguous_pricing_configuration() -> None:
        today = timezone.localdate()
        active_tables = set(
            RatingTable.objects.filter(status="PUBLISHED", effective_from__lte=today)
            .filter(effective_to__isnull=True)
            .values_list("code", flat=True)
        )
        active_parameter_sets = set(
            PricingParameterSet.objects.filter(status="PUBLISHED", effective_from__lte=today)
            .filter(effective_to__isnull=True)
            .values_list("code", flat=True)
        )
        if len(active_tables) != 1 or len(active_parameter_sets) != 1:
            raise CommandError(
                "O tenant de demonstração tem configuração de preços publicada ambígua. Use um tenant novo (por omissão demo-saude) ou retire os códigos de configuração publicados em excesso."
            )

    def _ensure_products_and_plans(self, tenant: Tenant) -> dict[str, Plan]:
        ensure_market_catalog(tenant.id)
        benefits = {benefit.code: benefit for benefit in Benefit.objects.all()}

        family_product = self._ensure_product("DEMO-SAUDE-FAMILIA", "Seguro Saúde Família Demo")
        family_plan = self._ensure_plan(
            family_product,
            "FAMILIA-PLUS",
            "Família Plus",
            ["PHARMACY", "MATERNITY", "DENTAL", "OPTICAL", "PHYSIOTHERAPY", "TRAVEL_ASSISTANCE"],
            benefits,
        )

        company_product = self._ensure_product("DEMO-SAUDE-EMPRESA", "Seguro Saúde Empresa Demo")
        corporate_plan = self._ensure_plan(
            company_product,
            "EMPRESA-ESSENCIAL",
            "Empresa Essencial",
            ["PHARMACY", "DENTAL"],
            benefits,
        )
        return {"family": family_plan, "corporate": corporate_plan}

    @staticmethod
    def _ensure_product(code: str, name: str) -> Product:
        return Product.objects.filter(code=code).first() or create_product(code=code, name=name, description="Dados de demonstração")

    @staticmethod
    def _ensure_plan(product: Product, code: str, name: str, benefit_codes: list[str], benefits: dict[str, Benefit]) -> Plan:
        plan = Plan.objects.filter(product=product, code=code).first()
        if plan is None:
            plan = create_plan(
                product=product,
                code=code,
                name=name,
                description="Plano de demonstração para testes funcionais",
                complementary_benefit_ids=[benefits[code].id for code in benefit_codes],
            )
        else:
            for benefit_code in benefit_codes:
                add_plan_benefit(plan=plan, benefit=benefits[benefit_code])
        return plan

    def _ensure_ana_family_policy(self, tenant: Tenant, staff: dict[str, StaffAccount], plan: Plan) -> Policy:
        proposer = self._ensure_proposer(
            tenant,
            external_reference="DEMO-ANA-SILVA",
            proposer_type="INDIVIDUAL",
            display_name="Ana Paula Silva",
            registration_number="000000001LA001",
            email="fabiongila@gmail.com",
            phone="+244 900 000 001",
        )
        members = {
            "holder": self._ensure_member(proposer, "DEMO-ANA-TITULAR", "TITULAR", "Ana Paula", "Silva", "1990-05-14"),
            "spouse": self._ensure_member(proposer, "DEMO-ANA-CONJUGE", "CONJUGE", "Miguel", "Silva", "1988-03-02"),
            "child": self._ensure_member(proposer, "DEMO-ANA-FILHO", "FILHO", "Inês", "Silva", "2006-08-20"),
            "senior": self._ensure_member(proposer, "DEMO-ANA-ASCENDENTE", "ASCENDENTE", "Rosa", "Silva", "1961-01-10"),
            "over-age": self._ensure_member(proposer, "DEMO-ANA-IDADE-LIMITE", "ASCENDENTE", "António", "Silva", "1940-01-10"),
        }
        existing = Policy.objects.filter(proposer=proposer, status="ACTIVE", plan=plan).order_by("created_at").first()
        if existing:
            self._ensure_loading_scenario(
                proposer=proposer, member=members["senior"], plan=plan, policy=existing
            )
            return existing

        today = timezone.localdate()
        effective_date = today - datetime.timedelta(days=7)
        quote = self._create_quote_with_evaluations(
            proposer=proposer,
            plan=plan,
            members=[
                (members["holder"], {"angola": {"previousPolicyNumber": "APO-ANTERIOR-001", "previousPolicyContinuous": True}}),
                (members["spouse"], {"angola": {"unionBondType": "UNIAO_DE_FACTO"}}),
                (members["child"], {"angola": {}}),
                (
                    members["senior"],
                    {
                        "angola": {
                            "hasCohabitationOrFinancialDependencyProof": True,
                            "hasPreExistingCondition": True,
                        }
                    },
                ),
            ],
        )
        # Persist a hard-stop evaluation as a visible back-office scenario,
        # without inserting that person in the quote/policy population.
        EvaluateEligibilityUseCase().execute(
            proposer_id=proposer.id,
            member_id=members["over-age"].id,
            plan_id=plan.id,
            effective_date=effective_date,
            context={"angola": {}},
            correlation_id="demo-ana-hard-stop",
        )
        policy = self._approve_issue_and_activate(
            tenant=tenant,
            staff=staff,
            quote=quote,
            signatory_name="Ana Paula Silva",
            document_number=proposer.registration_number,
            payment_frequency="TRIMESTRAL",
        )
        self._ensure_loading_scenario(proposer=proposer, member=members["senior"], plan=plan, policy=policy)
        return policy

    @staticmethod
    def _ensure_loading_scenario(*, proposer: Proposer, member: InsuredMember, plan: Plan, policy: Policy) -> None:
        """Ensure the demo's pre-existing-condition outcome is visible.

        Older executions of this command created the ascendant without the
        dependency evidence.  That correctly yielded PENDING_DOCUMENT, but
        hid the distinct ELIGIBLE_WITH_LOADING route.  Evaluations are
        immutable, so the corrective path creates one proper evaluation and
        points only the seed-owned PolicyMember at it.
        """
        evaluation = (
            EligibilityEvaluation.objects.filter(
                proposer=proposer,
                member=member,
                plan=plan,
                decision=EligibilityDecision.ELIGIBLE_WITH_LOADING.value,
            )
            .order_by("-evaluated_at")
            .first()
        )
        if evaluation is None:
            evaluation = EvaluateEligibilityUseCase().execute(
                proposer_id=proposer.id,
                member_id=member.id,
                plan_id=plan.id,
                effective_date=policy.start_date or timezone.localdate(),
                context={
                    "angola": {
                        "hasCohabitationOrFinancialDependencyProof": True,
                        "hasPreExistingCondition": True,
                    }
                },
                correlation_id="demo-ana-loading",
            )
        policy_member = PolicyMember.objects.filter(policy=policy, member=member).first()
        if policy_member is None:
            return

        # For a new policy, issuance has already calculated this from the
        # rule.  It is repeated here only to repair an older demo execution
        # which had initially classified this member as pending.
        inclusion_date = policy.start_date
        waiting_period_ends = {}
        if inclusion_date is not None:
            days_by_benefit = {"PHARMACY": 15, "DENTAL": 90, "MATERNITY": 365}
            for plan_benefit in PlanBenefit.objects.filter(plan=plan).select_related("benefit"):
                days = days_by_benefit.get(plan_benefit.benefit.code, 30)
                if days:
                    waiting_period_ends[plan_benefit.benefit.code] = (
                        inclusion_date + datetime.timedelta(days=days)
                    ).isoformat()

        desired = {
            "status": "ACTIVE",
            "pending_reason_code": None,
            "eligibility_evaluation": evaluation,
            "rule_version": evaluation.rule_version,
            "loading_percentage": Decimal("15.00"),
            "inclusion_date": inclusion_date,
            "waiting_period_ends_json": waiting_period_ends,
        }
        if any(getattr(policy_member, field) != value for field, value in desired.items()):
            PolicyMember.objects.filter(id=policy_member.id).update(
                **desired, row_version=policy_member.row_version + 1
            )

    def _ensure_carlos_pending_policy(self, tenant: Tenant, staff: dict[str, StaffAccount], plan: Plan) -> Policy:
        proposer = self._ensure_proposer(
            tenant,
            external_reference="DEMO-CARLOS-MENDES",
            proposer_type="INDIVIDUAL",
            display_name="Carlos Mendes",
            registration_number="000000002LA002",
            email="sethlussueki@gmail.com",
            phone="+244 900 000 002",
        )
        holder = self._ensure_member(proposer, "DEMO-CARLOS-TITULAR", "TITULAR", "Carlos", "Mendes", "1985-10-18")
        existing = Policy.objects.filter(proposer=proposer, status="PENDING_FIRST_PREMIUM", plan=plan).first()
        if existing:
            return existing

        quote = self._create_quote_with_evaluations(
            proposer=proposer,
            plan=plan,
            members=[(holder, {"angola": {}})],
        )
        return self._approve_and_issue_pending(
            tenant=tenant,
            staff=staff,
            quote=quote,
            signatory_name="Carlos Mendes",
            document_number=proposer.registration_number,
        )

    def _ensure_company_policy(self, tenant: Tenant, staff: dict[str, StaffAccount], plan: Plan) -> Policy:
        proposer = self._ensure_proposer(
            tenant,
            external_reference="DEMO-EMPRESA-KILAMBA",
            proposer_type="ORGANISATION",
            display_name="Empresa Kilamba, Lda.",
            registration_number="5410000030",
            email="empresa.kilamba@demo.q360.local",
            phone="+244 900 000 003",
        )
        holder = self._ensure_member(proposer, "DEMO-EMPRESA-TITULAR", "TITULAR", "João", "Domingos", "1993-06-08")
        spouse = self._ensure_member(proposer, "DEMO-EMPRESA-CONJUGE", "CONJUGE", "Teresa", "Domingos", "1995-07-11")
        existing = Policy.objects.filter(proposer=proposer, status="ACTIVE", plan=plan).order_by("created_at").first()
        if existing:
            return existing

        quote = self._create_quote_with_evaluations(
            proposer=proposer,
            plan=plan,
            members=[
                (holder, {"angola": {"previousPolicyNumber": "APO-GRUPO-ANTERIOR", "previousPolicyContinuous": True}}),
                (spouse, {"angola": {}}),
            ],
        )
        return self._approve_issue_and_activate(
            tenant=tenant,
            staff=staff,
            quote=quote,
            signatory_name="Empresa Kilamba, Lda.",
            document_number=proposer.registration_number,
            payment_frequency="SEMESTRAL",
        )

    def _ensure_backoffice_quote_states(self, tenant: Tenant, staff: dict[str, StaffAccount], plan: Plan) -> None:
        """Create a small work queue in addition to the issued policies.

        Portal journeys need active contracts, but the staff application also
        needs realistic work at the quotation stages.  These scenarios are
        deliberately kept separate from the customer portal data so they do
        not change what a customer can see after signing in.
        """
        proposer = self._ensure_proposer(
            tenant,
            external_reference="DEMO-DIANA-LOPES",
            proposer_type="INDIVIDUAL",
            display_name="Diana Lopes",
            registration_number="000000004LA004",
            email="diana.lopes@demo.q360.local",
            phone="+244 900 000 004",
        )
        member = self._ensure_member(
            proposer, "DEMO-DIANA-TITULAR", "TITULAR", "Diana", "Lopes", "1992-02-22"
        )
        if not Quote.objects.filter(proposer=proposer, status="DRAFT").exists():
            self._bind(tenant, staff["subscriber"], Role.SUBSCRIBER)
            self._create_quote_with_evaluations(
                proposer=proposer,
                plan=plan,
                members=[(member, {"angola": {}})],
            )

        if not Quote.objects.filter(proposer=proposer, status="IN_REVIEW").exists():
            self._bind(tenant, staff["subscriber"], Role.SUBSCRIBER)
            quote = self._create_quote_with_evaluations(
                proposer=proposer,
                plan=plan,
                members=[(member, {"angola": {}})],
            )
            quote = self._price_and_submit(quote, "review")

        if not Quote.objects.filter(proposer=proposer, status="REJECTED").exists():
            self._bind(tenant, staff["subscriber"], Role.SUBSCRIBER)
            quote = self._create_quote_with_evaluations(
                proposer=proposer,
                plan=plan,
                members=[(member, {"angola": {}})],
            )
            quote = self._price_and_submit(quote, "reject")
            self._bind(tenant, staff["manager"], Role.SUBSCRIPTION_MANAGER)
            decide_quote(
                quote=quote,
                decision=QuoteDecisionType.REJECT.value,
                reason_code="DEMO_UNDERWRITING_REJECTED",
                reason_text="Cenário de rejeição para testes do back-office.",
                row_version=quote.row_version,
                correlation_id="demo-reject-decision",
            )

    @staticmethod
    def _price_and_submit(quote: Quote, tag: str) -> Quote:
        """Price the quote and leave it in review. Pricing already sends it to
        review by itself when a member needs manual validation, so only a quote
        that came out READY still has to be submitted."""
        price_quote(quote=quote, recalculate=True, correlation_id=f"demo-{tag}-price")
        quote.refresh_from_db()
        if quote.status == QuoteStatus.READY.value:
            submit_quote(quote=quote, row_version=quote.row_version, correlation_id=f"demo-{tag}-submit")
            quote.refresh_from_db()
        return quote

    def _ensure_proposer(self, tenant: Tenant, **data) -> Proposer:
        proposer = Proposer.objects.filter(external_reference=data["external_reference"]).first()
        if proposer is not None:
            # Seed-owned portal users keep the documented e-mail address on
            # every run, so changing a demo credential is immediately
            # reflected in the existing local database.
            if proposer.email != data["email"]:
                Proposer.objects.filter(id=proposer.id).update(email=data["email"])
                proposer.refresh_from_db()
            return proposer
        # The canonical `nif` field was introduced after the legacy
        # `registration_number` field.  Demo data deliberately writes both
        # with the same valid AGT value so portal login and newer API clients
        # exercise the same identity.
        data["nif"] = data["registration_number"]
        return create_proposer(attributes={"seed": "demo"}, **data)

    @staticmethod
    def _ensure_member(
        proposer: Proposer,
        external_reference: str,
        relationship_code: str,
        first_name: str,
        last_name: str,
        birth_date: str,
    ) -> InsuredMember:
        member = InsuredMember.objects.filter(proposer=proposer, external_reference=external_reference).first()
        if member is not None:
            return member
        return create_member(
            proposer=proposer,
            relationship_code=relationship_code,
            first_name=first_name,
            last_name=last_name,
            date_of_birth=datetime.date.fromisoformat(birth_date),
            sex_code=None,
            external_reference=external_reference,
            attributes={"seed": "demo"},
        )

    def _create_quote_with_evaluations(self, *, proposer: Proposer, plan: Plan, members):
        quote = create_quote(proposer_id=proposer.id, plan_id=plan.id)
        for member, context in members:
            evaluation = EvaluateEligibilityUseCase().execute(
                proposer_id=proposer.id,
                member_id=member.id,
                plan_id=plan.id,
                effective_date=quote.reference_date,
                context=context,
                correlation_id=f"demo-eligibility-{member.external_reference}",
            )
            QuoteMember.objects.create(
                tenant_id=quote.tenant_id,
                quote=quote,
                member=member,
                status=self._quote_member_status(evaluation.decision),
                eligibility_evaluation=evaluation,
            )
        return quote

    @staticmethod
    def _quote_member_status(decision: str) -> str:
        if decision in (EligibilityDecision.ELIGIBLE.value, EligibilityDecision.WARNING.value, EligibilityDecision.ELIGIBLE_WITH_LOADING.value):
            return QuoteMemberStatus.INCLUDED.value
        if decision in (EligibilityDecision.REFERRAL.value, EligibilityDecision.PENDING_DOCUMENT.value, EligibilityDecision.PENDING_MEDICAL_BOARD.value):
            return QuoteMemberStatus.REFERRAL.value
        return QuoteMemberStatus.EXCLUDED.value

    def _approve_and_issue_pending(
        self,
        *,
        tenant: Tenant,
        staff: dict[str, StaffAccount],
        quote: Quote,
        signatory_name: str,
        document_number: str,
        payment_frequency: str = "ANUAL",
    ) -> Policy:
        self._bind(tenant, staff["subscriber"], Role.SUBSCRIBER)
        quote = self._price_and_submit(quote, "approve")

        self._bind(tenant, staff["manager"], Role.SUBSCRIPTION_MANAGER)
        decide_quote(
            quote=quote,
            decision=QuoteDecisionType.APPROVE.value,
            reason_code="DEMO_APPROVED",
            reason_text="Aprovação de dados de demonstração",
            row_version=quote.row_version,
            correlation_id="demo-approve",
        )
        quote.refresh_from_db()
        return issue_policy(
            quote=quote,
            signatory_name=signatory_name,
            signatory_document_type="BI",
            signatory_document_number=document_number,
            signatory_capacity="TOMADOR",
            signature_method="DIGITAL",
            signed_at=timezone.now() - datetime.timedelta(days=1),
            term_months=12,
            payment_frequency=payment_frequency,
            requested_start_date=None,
            row_version=quote.row_version,
            correlation_id="demo-policy-issued",
        )

    def _approve_issue_and_activate(
        self,
        *,
        tenant: Tenant,
        staff: dict[str, StaffAccount],
        quote: Quote,
        signatory_name: str,
        document_number: str,
        payment_frequency: str,
    ) -> Policy:
        policy = self._approve_and_issue_pending(
            tenant=tenant,
            staff=staff,
            quote=quote,
            signatory_name=signatory_name,
            document_number=document_number,
            payment_frequency=payment_frequency,
        )
        return self._activate_policy(policy=policy)

    @staticmethod
    def _activate_policy(*, policy: Policy) -> Policy:
        return register_first_premium_payment(
            policy=policy,
            paid_at=timezone.now() - datetime.timedelta(days=1),
            payment_reference=f"DEMO-PAY-{policy.id.hex[:8].upper()}",
            payment_method="TRANSFERENCIA",
            row_version=policy.row_version,
            correlation_id="demo-policy-payment",
        )

    def _print_summary(self, *, tenant: Tenant, staff: dict[str, StaffAccount], policies: dict[str, Policy]) -> None:
        self.stdout.write(self.style.SUCCESS("Dados de demonstração Q360 Saúde prontos."))
        self.stdout.write(f"Tenant: {tenant.code} ({tenant.id})")
        self.stdout.write(f"\nSuper administrador da plataforma (POST /api/v1/platform/auth/login): {_PLATFORM_ADMIN[0]} / {_PASSWORD}")
        self.stdout.write("\nColaboradores (todos usam a palavra-passe Q360Demo!2026):")
        for key, email, _name, roles in _STAFF:
            self.stdout.write(f"  - {email} — {', '.join(role.value for role in roles)}")
        self.stdout.write("\nClientes e apólices demo (o Portal Cliente é preparado por seed_portal_demo):")
        for name, policy in policies.items():
            self.stdout.write(f"  - {name}: apólice {policy.policy_number} ({policy.status})")
        self.stdout.write("\nBack-office: existem ainda cotações demo nos estados DRAFT, IN_REVIEW e REJECTED.")
