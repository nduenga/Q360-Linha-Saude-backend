"""Popula a base de dados com dados de configuração (produção) e de teste.

Duas camadas independentes, ambas idempotentes (podem correr-se várias vezes):

  REFERÊNCIA  (--profile reference|all)  segura para produção, sem credenciais
              de demonstração. Cria/actualiza o tenant `--prod-tenant-code`:
              catálogo de relações e de coberturas, produtos/planos de mercado
              (Individual e Grupo), tabela de tarifas, parâmetros, regra de
              elegibilidade Angola, modelo de documento, configuração de
              negócio publicada (tarifas por idade para todos os planos),
              parâmetros do sistema, política de autoridade e, se pedido, o
              primeiro administrador.

  TESTE       (--profile demo|all)  só com DEBUG=True (ou --allow-demo). Corre
              `seed_demo_data` (+ portal) e acrescenta volume: equipa de
              colaboradores, dezenas de clientes (famílias e empresas) com
              cotações em todos os estados, apólices ativas / pendentes /
              com prestações em atraso, sinistralidade e prémios históricos,
              contas, pedidos e mensagens do Portal Cliente e um segundo tenant
              vazio-mas-configurado para testar o isolamento entre tenants.

Exemplos:
    manage.py seed_full_database                       # tudo (ambiente de dev)
    manage.py seed_full_database --profile reference \\
        --admin-email admin@seguradora.ao --admin-password '...'   # produção
    manage.py seed_full_database --profile demo --customers 80 --random-seed 7
"""
from __future__ import annotations

import datetime
import json
import random
import secrets
import uuid
from decimal import Decimal
from types import SimpleNamespace

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.business_config.application.service import approve_configuration, create_configuration, submit_configuration
from apps.business_config.domain.errors import InvalidConfiguration
from apps.business_config.infrastructure.models import BusinessConfiguration
from apps.business_config.seed.reference_rules import CUSTOM_RULES, STATIC_CONFIGS
from apps.claims.application.import_service import import_file, xlsx_from_rows
from apps.policy.application.demo_dates import make_installment_due_soon, make_installment_late
from apps.claims.infrastructure.models import ClaimsImport
from apps.client.application.relationship_service import ensure_relationship_catalog
from apps.client.infrastructure.models import InsuredMember, Proposer
from apps.customer_portal.application import messages_service, requests_service
from apps.customer_portal.infrastructure.models import CustomerAccount, CustomerAccountProposer, PortalRequest
from apps.eligibility.domain.enums import EligibilityDecision
from apps.foundation.application import system_parameter_service
from apps.foundation.application.context import CurrentActorProvider
from apps.foundation.application.rule_service import create_rule_version, publish_rule_version
from apps.foundation.domain.actor import Actor
from apps.foundation.domain.permissions import Role
from apps.foundation.domain.scopes import Scope
from apps.foundation.domain.system_parameters import DEFINITIONS
from apps.foundation.domain.tenant import TenantId
from apps.foundation.infrastructure.models import RuleVersion, Tenant
from apps.foundation.management.commands.seed_default_pricing_config import (
    EARLIEST_EFFECTIVE_FROM,
    ELIGIBILITY_RULE_CODE,
    Command as DefaultPricingCommand,
)
from apps.foundation.management.commands.seed_demo_data import Command as DemoCommand
from apps.policy.application.issuance_service import issue_policy, register_first_premium_payment
from apps.policy.infrastructure.models import Policy, PremiumInstallment
from apps.product.application.benefit_service import ensure_market_catalog
from apps.product.application.market_template_service import apply_market_templates
from apps.product.infrastructure.models import Plan, PlanBenefit, Product
from apps.quote.application.quote_service import decide_quote, price_quote, submit_quote
from apps.quote.domain.enums import QuoteDecisionType, QuoteStatus
from apps.quote.infrastructure.models import AuthorityPolicy, Quote
from apps.staff_accounts.infrastructure.models import StaffAccount, StaffAccountRole

DEFAULT_PROD_TENANT = ("q360-saude", "Q360 Saúde")
DEFAULT_DEMO_TENANT = "demo-saude"
ISOLATION_TENANT = ("demo-isolamento", "Q360 Saúde — Tenant de isolamento (testes)")

STAFF_PASSWORD = "Q360Demo!2026"
CUSTOMER_PASSWORD = "Cliente!Demo2026"

# --- Tarifas anuais de referência (AOA) -------------------------------------
AGE_BANDS = ((0, 17, "150000"), (18, 29, "220000"), (30, 39, "300000"), (40, 49, "420000"),
             (50, 59, "570000"), (60, 69, "760000"), (70, 75, "980000"))
PLAN_MULTIPLIER = {
    "IND-BASE": "1.00", "IND-MEDIO": "1.45", "IND-SUPERIOR": "2.10",
    "GRP-COLABORADORES": "0.80", "GRP-QUADROS": "1.15", "GRP-ADMINISTRACAO": "1.60",
    "FAMILIA-PLUS": "1.00", "EMPRESA-ESSENCIAL": "0.80",
}
AGE_FACTORS = (("0-17", "0.60"), ("18-29", "0.80"), ("30-39", "1.00"), ("40-49", "1.20"),
               ("50-59", "1.50"), ("60-69", "1.90"), ("70+", "2.40"), ("*", "1.00"))

ELIGIBILITY_ARTIFACT = {
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

# Valores operacionais explícitos (os restantes ficam no valor por omissão).
SYSTEM_PARAMETERS = {
    "quote.validity_days": 30,
    "documents.signed_url_ttl_seconds": 900,
    "renewal.default_medical_inflation_pct": "14.90",
}

# --- Gerador de pessoas angolanas -------------------------------------------
FIRST_M = ["João", "António", "Manuel", "Paulo", "Pedro", "Carlos", "José", "Domingos", "Joaquim", "Miguel",
           "Bento", "Fernando", "Eduardo", "Armando", "Sebastião", "Adilson", "Délcio", "Hélder", "Nelson", "Tomás"]
FIRST_F = ["Maria", "Ana", "Teresa", "Isabel", "Luísa", "Joana", "Helena", "Rosa", "Beatriz", "Catarina",
           "Mariana", "Sofia", "Inês", "Domingas", "Esperança", "Natália", "Vanda", "Cláudia", "Nsimba", "Lúcia"]
LAST = ["Silva", "Santos", "Ferreira", "Costa", "Pereira", "Gomes", "Fernandes", "Mendes", "Domingos", "Neto",
        "Kiala", "Lussueki", "Ngola", "Cardoso", "Baptista", "Van-Dúnem", "Sebastião", "Tavares", "Matias", "Zau"]
COMPANY_A = ["Kilamba", "Luanda", "Atlântico", "Mussulo", "Benguela", "Huambo", "Cabinda", "Namibe", "Lobito", "Zango"]
COMPANY_B = ["Construções", "Logística", "Petróleos", "Comércio Geral", "Tecnologias", "Agro-Indústria",
             "Serviços Financeiros", "Telecomunicações", "Hotelaria", "Distribuição"]
LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ"
CLAIM_BENEFITS = ["OUTPATIENT", "HOSPITALIZATION", "PHARMACY", "DENTAL", "OPTICAL", "EMERGENCY",
                  "PHYSIOTHERAPY", "AMBULATORY_SURGERY"]


class _ReferencePricing(DefaultPricingCommand):
    """`seed_default_pricing_config` com conteúdo de produção: regra de
    elegibilidade Angola completa e tarifas para todos os planos de mercado."""

    plan_codes: tuple[str, ...] = ()

    def _seed_eligibility_rule(self) -> None:
        if RuleVersion.objects.filter(rule_set__code=ELIGIBILITY_RULE_CODE, status="PUBLISHED").exists():
            return
        rule = create_rule_version(
            code=ELIGIBILITY_RULE_CODE,
            name="Elegibilidade Angola — família, pré-existências e carências",
            rule_domain="ELIGIBILITY",
            effective_from=EARLIEST_EFFECTIVE_FROM,
            effective_to=None,
            artifact_type="JSON",
            artifact_ref=json.dumps(ELIGIBILITY_ARTIFACT),
            artifact_checksum=None,
        )
        publish_rule_version(rule)
        self.stdout.write(self.style.SUCCESS(f"Regra de elegibilidade '{ELIGIBILITY_RULE_CODE}' publicada"))

    publish_actuarial = True

    def _publish(self, key: str, value: dict) -> None:
        tenant_id = CurrentActorProvider.get().tenant_id.value
        if BusinessConfiguration.objects.filter(tenant_id=tenant_id, config_key=key, status="PUBLISHED").exists():
            return
        req = SimpleNamespace()
        try:
            config = create_configuration(
                req, config_key=key, value=value, effective_from=EARLIEST_EFFECTIVE_FROM, effective_to=None,
                metadata={"source": "seed_full_database", "scope": "default"},
            )
        except InvalidConfiguration as exc:  # chave fora do catálogo suportado pela aplicação
            self.stdout.write(self.style.WARNING(f"Configuração '{key}' ignorada: {exc}"))
            return
        submit_configuration(req, config)
        token = self._as_approver()  # four-eyes: quem cria não aprova
        try:
            approve_configuration(SimpleNamespace(), config)
        finally:
            CurrentActorProvider.reset(token)
        self.stdout.write(self.style.SUCCESS(f"Configuração '{key}' publicada"))

    @staticmethod
    def _mirror_plan_rows() -> tuple[list[dict], list[dict]]:
        """Capitais anuais e carências tal como estão nos planos (PDF de mercado), para a
        interface de configuração mostrar os valores reais sem os poder contradizer."""
        capitals, waiting = [], {}
        kinds = ("ANNUAL_PER_PERSON", "HOUSEHOLD_SHARED", "BIENNIAL", "FIXED_AMOUNT")
        for pb in PlanBenefit.objects.select_related("plan", "benefit").order_by("plan__code", "benefit__code"):
            cfg = pb.configuration_json or {}
            if cfg.get("inclusion") == "UNAVAILABLE":
                continue
            primary = next((x for x in cfg.get("limits") or [] if x.get("kind") in kinds and x.get("amount")), None)
            if primary:
                capitals.append({"plan": pb.plan.code, "coverage": pb.benefit.code, "annual_capital": str(primary["amount"])})
            days = cfg.get("waitingDays")
            if days and pb.benefit.code not in waiting:
                row = {"coverage": pb.benefit.code}
                if days.get("individual") is not None:
                    row["individual_days"] = int(days["individual"])
                if days.get("group") is not None:
                    row["group_days"] = int(days["group"])
                if days.get("accidentWaived") is not None:
                    row["accident_exempt"] = bool(days["accidentWaived"])
                waiting[pb.benefit.code] = row
        return capitals, list(waiting.values())

    def _seed_business_config(self) -> None:
        premiums = [
            {"plan": code, "age_from": lo, "age_to": hi,
             "annual_premium": str((Decimal(base) * Decimal(PLAN_MULTIPLIER[code])).quantize(Decimal("1")))}
            for code in self.plan_codes for lo, hi, base in AGE_BANDS
        ]
        self._publish("pricing.reference_premiums", {"currency_code": "AOA", "premiums": premiums})
        self._publish("pricing.factors", {"factors": [
            {"code": "AGE_FACTOR", "dimension": "ageBand", "condition": c, "factor": f} for c, f in AGE_FACTORS
        ]})
        self._publish("pricing.adjustments", {"rules": []})  # condicionais vivem em rules.custom
        for key, value in STATIC_CONFIGS.items():
            self._publish(key, value)
        capitals, waiting = self._mirror_plan_rows()
        if capitals:
            self._publish("product.capitals_sublimits", {"items": capitals})
        if waiting:
            self._publish("product.waiting_periods", {"items": waiting})
        self._publish("rules.custom", CUSTOM_RULES)
        if self.publish_actuarial:
            self._publish_actuarial_model()
        else:
            self._seed_actuarial_model_draft()

    def _publish_actuarial_model(self) -> None:
        """Valida as 94 células da planilha e publica o modelo (vigência desde 2020-01-01)."""
        tenant_id = CurrentActorProvider.get().tenant_id.value
        if BusinessConfiguration.objects.filter(
            tenant_id=tenant_id, config_key="pricing.actuarial_model", status="PUBLISHED"
        ).exists():
            return
        try:
            call_command("publish_actuarial_model", tenant_code=self._tenant.code,
                         effective_from=EARLIEST_EFFECTIVE_FROM.isoformat(), stdout=self.stdout)
        except SystemExit as exc:
            raise CommandError(f"Publicação do modelo atuarial falhou (código {exc.code}).") from exc


class Command(BaseCommand):
    help = "Seed completo: configuração pronta para produção + dados de teste em volume (idempotente)."

    def add_arguments(self, parser):
        parser.add_argument("--profile", choices=("all", "reference", "demo"), default="all")
        parser.add_argument("--prod-tenant-code", default=DEFAULT_PROD_TENANT[0])
        parser.add_argument("--prod-tenant-name", default=DEFAULT_PROD_TENANT[1])
        parser.add_argument("--admin-email", help="Cria/garante o 1.º ADMIN do tenant de referência.")
        parser.add_argument("--admin-name", default="Administrador")
        parser.add_argument("--admin-password", help="Omitir para gerar uma palavra-passe aleatória (é impressa).")
        parser.add_argument("--demo-tenant-code", default=DEFAULT_DEMO_TENANT)
        parser.add_argument("--customers", type=int, default=40, help="Nº de clientes em massa (por omissão 40).")
        parser.add_argument("--random-seed", type=int, default=2026, help="Semente do gerador (dados reproduzíveis).")
        parser.add_argument("--allow-demo", action="store_true", help="Permite a camada de teste com DEBUG=False.")
        parser.add_argument("--no-isolation-tenant", action="store_true")
        parser.add_argument("--no-actuarial", action="store_true",
                            help="Não publica o modelo atuarial (fica em rascunho para aprovação do actuário).")

    # ------------------------------------------------------------------ main
    def handle(self, *args, **opts):
        profile = opts["profile"]
        if profile in ("all", "demo") and not (settings.DEBUG or opts["allow_demo"]):
            raise CommandError(
                "A camada de teste cria contas com palavras-passe conhecidas e só corre com DEBUG=True. "
                "Em produção use --profile reference (ou --allow-demo se for mesmo um ambiente de testes)."
            )
        if opts["customers"] < 0:
            raise CommandError("--customers não pode ser negativo")
        self.rng = random.Random(opts["random_seed"])
        _ReferencePricing.publish_actuarial = not opts["no_actuarial"]
        self.report: list[str] = []
        self.demo_ran = False
        if profile in ("all", "reference"):
            self._reference_layer(opts)
        if profile in ("all", "demo"):
            self._demo_layer(opts)
        self._print_report()

    # ------------------------------------------------------------ referência
    def _reference_layer(self, opts) -> None:
        code, name = opts["prod_tenant_code"], opts["prod_tenant_name"]
        tenant, created = Tenant.objects.get_or_create(code=code, defaults={"name": name})
        self.stdout.write(self.style.MIGRATE_HEADING(f"[REFERÊNCIA] tenant {code} ({tenant.id})"))
        plan_codes = self._seed_tenant_reference(tenant, with_market_plans=True)
        _ReferencePricing.plan_codes = tuple(plan_codes)
        self._seed_pricing_config(tenant)
        self._seed_system_parameters(tenant)
        self._seed_authority_policy(tenant)
        self.report.append(f"Tenant de referência: {code} ({tenant.id}) — planos: {', '.join(plan_codes)}")
        if opts["admin_email"]:
            self._ensure_admin(tenant, opts)
        else:
            self.report.append("Nenhum ADMIN criado no tenant de referência (use --admin-email/--admin-password).")
        self._smoke_test_pricing(tenant)

    def _actor(self, tenant: Tenant, subject: str = "system-seed", roles=frozenset()) -> Actor:
        return Actor(actor_id=subject, tenant_id=TenantId.parse(tenant.id), roles=frozenset(roles),
                     scopes=frozenset(Scope))

    def _seed_tenant_reference(self, tenant: Tenant, *, with_market_plans: bool) -> list[str]:
        token = CurrentActorProvider.bind(self._actor(tenant, roles={Role.ADMIN}))
        try:
            ensure_relationship_catalog(tenant.id)
            ensure_market_catalog(tenant.id)
            if with_market_plans:
                result = apply_market_templates()
                self.stdout.write(
                    f"  produtos novos: {result['createdProducts']} · planos novos: {result['createdPlans']} · "
                    f"já existiam: {len(result['skippedPlans'])}"
                )
            return sorted(
                Plan.objects.filter(product__code__in=("SAUDE-INDIVIDUAL", "SAUDE-GRUPO")).values_list("code", flat=True)
            )
        finally:
            CurrentActorProvider.reset(token)

    def _seed_pricing_config(self, tenant: Tenant) -> None:
        cmd = _ReferencePricing(stdout=self.stdout, stderr=self.stderr)
        cmd.handle(tenant_code=tenant.code)

    def _seed_system_parameters(self, tenant: Tenant) -> None:
        token = CurrentActorProvider.bind(self._actor(tenant, roles={Role.ADMIN}))
        try:
            for code, value in SYSTEM_PARAMETERS.items():
                if code not in DEFINITIONS:
                    continue
                stored = system_parameter_service.get_stored_value(code)
                if stored is not None:
                    continue
                system_parameter_service.set_value(
                    code=code, value=value, reason="Valor inicial (seed_full_database)", row_version=0
                )
        finally:
            CurrentActorProvider.reset(token)

    def _seed_authority_policy(self, tenant: Tenant) -> None:
        if AuthorityPolicy.all_tenants.filter(tenant_id=tenant.id, code="AUTHORITY-DEFAULT").exists():
            return
        AuthorityPolicy.all_tenants.create(
            tenant_id=tenant.id, code="AUTHORITY-DEFAULT", version_no=1, effective_from=EARLIEST_EFFECTIVE_FROM,
            status="PUBLISHED", policy_json={"maxApprovalAmount": "2000000000", "currency": "AOA"},
            published_at=timezone.now(), published_by="system-seed", approved_by="system-seed-approver",
        )

    def _ensure_admin(self, tenant: Tenant, opts) -> None:
        email, password = opts["admin_email"].strip().lower(), opts["admin_password"]
        if password is not None and len(password) < 12:
            raise CommandError("--admin-password deve ter pelo menos 12 caracteres")
        generated = password is None
        password = password or secrets.token_urlsafe(14)
        account = StaffAccount.all_tenants.filter(tenant_id=tenant.id, email__iexact=email).first()
        if account is None:
            account = StaffAccount.all_tenants.create(
                id=uuid.uuid4(), tenant_id=tenant.id, email=email, name=opts["admin_name"],
                password_hash=make_password(password), status=StaffAccount.ACTIVE,
            )
            StaffAccountRole.all_tenants.create(
                id=uuid.uuid4(), tenant_id=tenant.id, staff_account_id=account.id, role=Role.ADMIN.value
            )
            msg = f"ADMIN criado: {email}" + (f" · palavra-passe gerada: {password}" if generated else "")
        else:
            msg = f"ADMIN {email} já existia (palavra-passe inalterada)."
        self.report.append(msg)

    def _smoke_test_pricing(self, tenant: Tenant) -> None:
        """Garante que a configuração publicada calcula mesmo um prémio, sem
        deixar nada gravado (a transacção é desfeita no fim)."""
        from apps.client.application.member_service import create_member
        from apps.client.application.proposer_service import create_proposer
        from apps.eligibility.application.use_cases import EvaluateEligibilityUseCase
        from apps.quote.application.quote_service import create_quote
        from apps.quote.infrastructure.models import QuoteMember

        class _Rollback(Exception):
            pass

        token = CurrentActorProvider.bind(self._actor(tenant, "smoke-test", {Role.ADMIN}))
        try:
            plan = Plan.objects.filter(code="IND-BASE").first()
            if plan is None:
                return
            from apps.pricing.application.plan_dimensions import resolve_plan_pricing_context
            problems = []
            for p in Plan.objects.filter(product__code__in=("SAUDE-INDIVIDUAL", "SAUDE-GRUPO")):
                ctx = resolve_plan_pricing_context(plan=p, selection={}, effective_date=timezone.localdate())
                problems += [f"{p.code}: {w['message']}" for w in ctx.warnings if "OVERLAY" in w.get("code", "")]
            self.report.append("Configuração de negócio vs. planos: " + (
                "sem conflitos." if not problems else f"{len(problems)} conflito(s): " + "; ".join(problems[:5])))
            try:
                with transaction.atomic():
                    prop = create_proposer(
                        proposer_type="INDIVIDUAL", display_name="Smoke Test", external_reference=None,
                        nif="000000000ZZ000", registration_number="000000000ZZ000", email="smoke@q360.local",
                        phone="+244900000000", attributes={},
                    )
                    member = create_member(
                        proposer=prop, relationship_code="TITULAR", first_name="Smoke", last_name="Test",
                        date_of_birth=datetime.date(1990, 1, 1), sex_code="M", external_reference=None, attributes={},
                    )
                    quote = create_quote(proposer_id=prop.id, plan_id=plan.id)
                    ev = EvaluateEligibilityUseCase().execute(
                        proposer_id=prop.id, member_id=member.id, plan_id=plan.id, effective_date=quote.reference_date,
                        context={"angola": {}}, correlation_id="smoke",
                    )
                    QuoteMember.objects.create(tenant_id=quote.tenant_id, quote=quote, member=member,
                                               status="INCLUDED", eligibility_evaluation=ev)
                    price_quote(quote=quote, recalculate=True, correlation_id="smoke-price")
                    quote.refresh_from_db()
                    total = quote.latest_pricing_run.total_amount if quote.latest_pricing_run else None
                    self.report.append(f"Teste de fumo do pricing (IND-BASE, 36 anos): OK, prémio {total} AOA (revertido).")
                    raise _Rollback
            except _Rollback:
                pass
            except Exception as exc:  # noqa: BLE001 - diagnóstico, não deve impedir o resto do seed
                self.report.append(f"AVISO: teste de fumo do pricing falhou: {type(exc).__name__}: {exc}")
        finally:
            CurrentActorProvider.reset(token)

    # ---------------------------------------------------------------- teste
    def _demo_layer(self, opts) -> None:
        code = opts["demo_tenant_code"]
        self.demo_ran = True
        self.stdout.write(self.style.MIGRATE_HEADING(f"[TESTE] tenant {code}"))
        # seed_demo_data exige DEBUG; --allow-demo contorna-o só para esta chamada.
        was_debug = settings.DEBUG
        settings.DEBUG = True
        try:
            call_command("seed_demo_data", tenant_code=code, stdout=self.stdout)
        finally:
            settings.DEBUG = was_debug
        tenant = Tenant.objects.get(code=code)
        self.demo = DemoCommand()
        self.tenant = tenant
        original = CurrentActorProvider.bind(None)
        try:
            self.staff = self._extra_staff(tenant)
            self.demo._bind(tenant, self.staff["admin"], Role.ADMIN)  # noqa: SLF001
            plans = {p.code: p for p in Plan.objects.filter(code__in=("FAMILIA-PLUS", "EMPRESA-ESSENCIAL"))}
            stats = self._bulk_customers(opts["customers"], plans)
            self.demo._bind(tenant, self.staff["admin"], Role.ADMIN)  # noqa: SLF001
            stats["historico"] = self._claims_history()
            self.report.append(
                f"Tenant de teste: {code} ({tenant.id}) — clientes em massa: {stats['customers']}, "
                f"apólices ativas: {stats['active']}, a aguardar 1.º pagamento: {stats['pending']}, "
                f"cotações em curso/recusadas: {stats['quotes']}, contas de portal: {stats['accounts']}, "
                f"pedidos: {stats['requests']}, importações de sinistralidade: {stats['historico']}, falhas: {stats['failed']}"
            )
        finally:
            CurrentActorProvider.reset(original)
        if not opts["no_isolation_tenant"]:
            self._isolation_tenant()
        self.report.append(f"Colaboradores de teste (palavra-passe {STAFF_PASSWORD}): " + ", ".join(
            f"{a.email} [{'/'.join(r.role for r in StaffAccountRole.all_tenants.filter(staff_account_id=a.id))}]"
            for a in StaffAccount.all_tenants.filter(tenant_id=tenant.id).order_by("email")
        ))
        self.report.append(f"Clientes de portal em massa (palavra-passe {CUSTOMER_PASSWORD}): "
                           f"emails bulk.NNN@clientes.q360.local")

    def _extra_staff(self, tenant: Tenant) -> dict[str, StaffAccount]:
        """Equipa maior que a do seed_demo_data, para testar listagens, filtros e
        a regra dos quatro olhos (quem submete não decide)."""
        def get(email: str) -> StaffAccount:
            return StaffAccount.all_tenants.get(tenant_id=tenant.id, email__iexact=email)

        staff = {"admin": get("admin.demo@q360.local"), "manager": get("gestor.demo@q360.local"),
                 "subscriber": get("subscritor.demo@q360.local")}
        extras = (
            ("manager2", "gestor2.demo@q360.local", "Gestora de Subscrição 2", Role.SUBSCRIPTION_MANAGER),
            ("subscriber2", "subscritor2.demo@q360.local", "Subscritora 2", Role.SUBSCRIBER),
            ("subscriber3", "subscritor3.demo@q360.local", "Subscritor 3", Role.SUBSCRIBER),
            ("admin2", "admin2.demo@q360.local", "Administradora 2", Role.ADMIN),
        )
        for key, email, name, role in extras:
            account = StaffAccount.all_tenants.filter(tenant_id=tenant.id, email__iexact=email).first()
            if account is None:
                account = StaffAccount.all_tenants.create(
                    id=uuid.uuid4(), tenant_id=tenant.id, email=email, name=name,
                    password_hash=make_password(STAFF_PASSWORD), status=StaffAccount.ACTIVE,
                )
                StaffAccountRole.all_tenants.create(
                    id=uuid.uuid4(), tenant_id=tenant.id, staff_account_id=account.id, role=role.value
                )
            staff[key] = account
        # Conta bloqueada, para testar a mensagem de login.
        locked = StaffAccount.all_tenants.filter(tenant_id=tenant.id, email__iexact="bloqueado.demo@q360.local").first()
        if locked is None:
            locked = StaffAccount.all_tenants.create(
                id=uuid.uuid4(), tenant_id=tenant.id, email="bloqueado.demo@q360.local", name="Conta Bloqueada",
                password_hash=make_password(STAFF_PASSWORD), status=StaffAccount.ACTIVE,
                failed_login_attempts=5, locked_until=timezone.now() + datetime.timedelta(days=3650),
            )
            StaffAccountRole.all_tenants.create(
                id=uuid.uuid4(), tenant_id=tenant.id, staff_account_id=locked.id, role=Role.SUBSCRIBER.value
            )
        return staff

    # -- clientes em massa --------------------------------------------------
    def _nif_person(self, i: int) -> str:
        return f"{500000000 + i * 7919 % 99999999:09d}{self.rng.choice(LETTERS)}{self.rng.choice(LETTERS)}{self.rng.randint(0, 999):03d}"

    @staticmethod
    def _nif_company(i: int) -> str:
        return f"{5400000000 + i * 104729 % 99999999:010d}"

    def _person(self, last: str | None = None, female: bool | None = None) -> tuple[str, str]:
        female = self.rng.random() < 0.5 if female is None else female
        return self.rng.choice(FIRST_F if female else FIRST_M), last or self.rng.choice(LAST)

    def _dob(self, lo: int, hi: int) -> datetime.date:
        age_days = self.rng.randint(lo * 365 + 5, hi * 365 - 5)
        return timezone.localdate() - datetime.timedelta(days=age_days)

    def _bulk_customers(self, count: int, plans: dict[str, Plan]) -> dict[str, int]:
        stats = dict(customers=0, active=0, pending=0, quotes=0, accounts=0, requests=0, failed=0)
        # Distribuição do destino de cada cliente (soma 100).
        outcomes = (["ACTIVE"] * 46 + ["PENDING"] * 14 + ["IN_REVIEW"] * 12 + ["APPROVED"] * 9 + ["REJECTED"] * 7
                    + ["DRAFT"] * 8 + ["EXPIRING"] * 4)
        for i in range(1, count + 1):
            outcome = outcomes[(i * 37 + self.rng.randint(0, 99)) % 100]
            corporate = i % 4 == 0
            try:
                with transaction.atomic():
                    self._one_customer(i, outcome, corporate, plans, stats)
                stats["customers"] += 1
            except Exception as exc:  # noqa: BLE001 - um cliente falhado não deve parar o lote
                stats["failed"] += 1
                self.stderr.write(self.style.WARNING(f"  cliente bulk-{i:03d} ({outcome}) falhou: {type(exc).__name__}: {exc}"))
            finally:
                self.demo._bind(self.tenant, self.staff["admin"], Role.ADMIN)  # noqa: SLF001
        return stats

    def _one_customer(self, i: int, outcome: str, corporate: bool, plans: dict[str, Plan], stats: dict[str, int]) -> None:
        ref = f"BULK-{i:03d}"
        email = f"bulk.{i:03d}@clientes.q360.local"
        if Proposer.objects.filter(external_reference=ref).exists():
            proposer = Proposer.objects.get(external_reference=ref)
            self._portal_account(proposer, stats)
            return

        if corporate:
            name = f"{self.rng.choice(COMPANY_A)} {self.rng.choice(COMPANY_B)}, Lda."
            nif, ptype, plan = self._nif_company(i), "ORGANISATION", plans["EMPRESA-ESSENCIAL"]
        else:
            first, last = self._person()
            name, nif, ptype, plan = f"{first} {last}", self._nif_person(i), "INDIVIDUAL", plans["FAMILIA-PLUS"]
        proposer = self.demo._ensure_proposer(  # noqa: SLF001
            self.tenant, external_reference=ref, proposer_type=ptype, display_name=name, registration_number=nif,
            email=email, phone=f"+244 9{self.rng.randint(10, 99)} {self.rng.randint(100, 999)} {self.rng.randint(100, 999)}",
            address=f"Rua {self.rng.randint(1, 300)}, {self.rng.choice(['Talatona', 'Maianga', 'Viana', 'Kilamba', 'Benfica', 'Ingombota'])}, Luanda",
        )
        members = self._members(proposer, ref, corporate, name)

        subscriber_key = self.rng.choice(["subscriber", "subscriber2", "subscriber3"])
        manager_key = self.rng.choice(["manager", "manager2"])
        self.demo._bind(self.tenant, self.staff[subscriber_key], Role.SUBSCRIBER)  # noqa: SLF001
        quote = self.demo._create_quote_with_evaluations(  # noqa: SLF001
            proposer=proposer, plan=plan, members=members
        )

        if outcome == "DRAFT":
            stats["quotes"] += 1
        elif outcome == "IN_REVIEW":
            self.demo._price_and_submit(quote, f"bulk{i}")  # noqa: SLF001
            stats["quotes"] += 1
        elif outcome == "REJECTED":
            quote = self.demo._price_and_submit(quote, f"bulk{i}")  # noqa: SLF001
            self.demo._bind(self.tenant, self.staff[manager_key], Role.SUBSCRIPTION_MANAGER)  # noqa: SLF001
            decide_quote(quote=quote, decision=QuoteDecisionType.REJECT.value,
                         reason_code=self.rng.choice(["RISK_TOO_HIGH", "INCOMPLETE_DOCUMENTATION", "OUT_OF_APPETITE"]),
                         reason_text="Cotação recusada (dados de teste).", row_version=quote.row_version,
                         correlation_id=f"bulk-{i}-reject")
            stats["quotes"] += 1
        else:
            quote = self.demo._price_and_submit(quote, f"bulk{i}")  # noqa: SLF001
            self.demo._bind(self.tenant, self.staff[manager_key], Role.SUBSCRIPTION_MANAGER)  # noqa: SLF001
            decide_quote(quote=quote, decision=QuoteDecisionType.APPROVE.value, reason_code="BULK_APPROVED",
                         reason_text="Aprovada (dados de teste).", row_version=quote.row_version,
                         correlation_id=f"bulk-{i}-approve")
            quote.refresh_from_db()
            if outcome == "APPROVED":
                stats["quotes"] += 1
            else:
                self.demo._bind(self.tenant, self.staff["admin"], Role.ADMIN)  # noqa: SLF001
                policy = issue_policy(
                    quote=quote, signatory_name=name, signatory_document_type="BI",
                    signatory_document_number=nif, signatory_capacity="TOMADOR", signature_method="DIGITAL",
                    signed_at=timezone.now() - datetime.timedelta(hours=self.rng.randint(1, 48)),
                    term_months=12, payment_frequency=self.rng.choice(["ANUAL", "SEMESTRAL", "TRIMESTRAL", "MENSAL"]),
                    requested_start_date=None, row_version=quote.row_version, correlation_id=f"bulk-{i}-issue",
                )
                if outcome == "PENDING":
                    stats["pending"] += 1
                else:
                    policy = register_first_premium_payment(
                        policy=policy, paid_at=timezone.now() - datetime.timedelta(hours=self.rng.randint(1, 24)),
                        payment_reference=f"BULK-PAY-{policy.id.hex[:8].upper()}",
                        payment_method=self.rng.choice(["TRANSFERENCIA", "MULTICAIXA", "NUMERARIO"]),
                        row_version=policy.row_version, correlation_id=f"bulk-{i}-pay",
                    )
                    stats["active"] += 1
                    self._shape_installments(policy)
                    if outcome == "EXPIRING":
                        Policy.all_tenants.filter(id=policy.id).update(
                            end_date=timezone.localdate() + datetime.timedelta(days=self.rng.randint(10, 55)))

        self.demo._bind(self.tenant, self.staff["admin"], Role.ADMIN)  # noqa: SLF001
        if i % 2 == 0 and outcome in ("ACTIVE", "EXPIRING", "IN_REVIEW", "APPROVED", "PENDING"):
            account = self._portal_account(proposer, stats)
            if outcome in ("ACTIVE", "EXPIRING") and i % 4 in (0, 2) and account is not None:
                self._portal_activity(account, proposer, stats)

    def _members(self, proposer: Proposer, ref: str, corporate: bool, name: str):
        """Lista de (beneficiário, contexto de elegibilidade). Mistura casos
        simples com casos que exigem prova/carregamento, como no mundo real."""
        r, out = self.rng, []
        if corporate:
            for n in range(1, r.randint(3, 9) + 1):
                first, last = self._person()
                m = self.demo._ensure_member(proposer, f"{ref}-COL{n}", "TITULAR", first, last,  # noqa: SLF001
                                             self._dob(21, 58).isoformat())
                ctx = {"angola": {"previousPolicyNumber": f"APO-PREV-{r.randint(1000, 9999)}",
                                  "previousPolicyContinuous": True}} if n == 1 else {"angola": {}}
                out.append((m, ctx))
            return out
        first, last = self._person()
        out.append((self.demo._ensure_member(proposer, f"{ref}-TIT", "TITULAR", first, last,  # noqa: SLF001
                                             self._dob(24, 60).isoformat()), {"angola": {}}))
        if r.random() < 0.7:
            sf, _ = self._person(female=r.random() < 0.5)
            union = r.random() < 0.3
            ctx = {"angola": {"unionBondType": "UNIAO_DE_FACTO"}} if union else {"angola": {}}
            out.append((self.demo._ensure_member(proposer, f"{ref}-CONJ", "CONJUGE", sf, last,  # noqa: SLF001
                                                 self._dob(24, 58).isoformat()), ctx))
        for n in range(1, r.choice([0, 1, 1, 2, 2, 3]) + 1):
            cf, _ = self._person()
            out.append((self.demo._ensure_member(proposer, f"{ref}-FIL{n}", "FILHO", cf, last,  # noqa: SLF001
                                                 self._dob(0, 17).isoformat()), {"angola": {}}))
        if r.random() < 0.18:
            af, _ = self._person()
            ctx = {"angola": {"hasCohabitationOrFinancialDependencyProof": True,
                              "hasPreExistingCondition": r.random() < 0.5}}
            out.append((self.demo._ensure_member(proposer, f"{ref}-ASC", "ASCENDENTE", af, last,  # noqa: SLF001
                                                 self._dob(61, 72).isoformat()), ctx))
        return out

    def _shape_installments(self, policy: Policy) -> None:
        """Parte das apólices fracionadas fica com prestações em atraso / a vencer."""
        r = self.rng
        rows = list(PremiumInstallment.all_tenants.filter(policy_id=policy.id).order_by("installment_no"))
        if len(rows) < 2 or r.random() > 0.35:
            return
        # A apólice inteira recua no tempo, para que o período da prestação em
        # atraso / a vencer já tenha (ou esteja quase a) começar.
        late = rows[1]
        if r.random() < 0.5:
            make_installment_late(policy, late.installment_no, days_late=r.randint(3, 40))
        else:
            make_installment_due_soon(policy, late.installment_no, in_days=r.randint(1, 14))

    # -- portal -------------------------------------------------------------
    def _portal_account(self, proposer: Proposer, stats: dict[str, int]):
        email = proposer.email.strip().lower()
        if not email:
            return None
        fields = dict(password_hash=make_password(CUSTOMER_PASSWORD), password_set_at=timezone.now(),
                      email_verified=True, failed_otp_attempts=0, locked_until=None)
        account = CustomerAccount.all_tenants.filter(tenant_id=self.tenant.id, email__iexact=email).first()
        if account is None:
            account = CustomerAccount.all_tenants.create(tenant_id=self.tenant.id, email=email, **fields)
            stats["accounts"] += 1
        CustomerAccountProposer.all_tenants.get_or_create(
            tenant_id=self.tenant.id, customer_account=account, proposer=proposer)
        return account

    def _portal_activity(self, account, proposer: Proposer, stats: dict[str, int]) -> None:
        if PortalRequest.objects.filter(proposer_id=proposer.id).exists():
            return
        policy = Policy.objects.filter(proposer=proposer, status="ACTIVE").first()
        if policy is None:
            return
        customer = Actor(
            actor_id=str(account.id), tenant_id=TenantId.parse(self.tenant.id), roles=frozenset(), scopes=frozenset(),
            actor_type="CUSTOMER", customer_proposer_ids=frozenset({str(proposer.id)}),
        )
        CurrentActorProvider.bind(customer)
        catalogue = (
            ("DATA_CHANGE", "Actualizar contactos", "Mudei de número de telefone.", False),
            ("DOCUMENT_COPY", "Segunda via do cartão", "Perdi o cartão de beneficiário.", False),
            ("STATEMENT", "Declaração de cobertura", "Preciso de uma declaração para o empregador.", True),
            ("COVERAGE_QUESTION", "Cobertura de estomatologia", "Qual é o limite anual e a carência?", False),
        )
        kind, subject, description, needs_policy = self.rng.choice(catalogue)
        req = requests_service.create_request(
            account_id=account.id, request_type=kind, subject=subject, description=description,
            policy_number=policy.policy_number if needs_policy else None, quote_number=None, payload={})
        stats["requests"] += 1
        messages_service.customer_send(
            account_id=account.id, context_type="POLICY", context_ref=policy.policy_number,
            body="Bom dia, podem ajudar-me com o meu pedido?")
        self.demo._bind(self.tenant, self.staff["admin"], Role.ADMIN)  # noqa: SLF001
        step = self.rng.choice([None, "IN_REVIEW", "AWAITING_CUSTOMER"])
        if step:
            requests_service.staff_transition(request_number=req.request_number, to_status="IN_REVIEW",
                                              note=None, actor_ref=str(self.staff["admin"].id))
        if step == "AWAITING_CUSTOMER":
            requests_service.staff_transition(request_number=req.request_number, to_status="AWAITING_CUSTOMER",
                                              note="Envie-nos um comprovativo.", actor_ref=str(self.staff["admin"].id))

    # -- sinistralidade -----------------------------------------------------
    def _claims_history(self) -> int:
        """24 meses de prémios e sinistros (outra seguradora) por proponente com
        apólice ativa, para os ecrãs de sinistralidade e projeção."""
        created = 0
        today = timezone.localdate()
        proposers = list(Proposer.objects.filter(external_reference__startswith="BULK-",
                                                 id__in=Policy.objects.filter(status="ACTIVE").values("proposer_id"))[:25])
        proposers += list(Proposer.objects.filter(external_reference__in=["DEMO-ANA-SILVA", "DEMO-EMPRESA-KILAMBA"]))
        for proposer in proposers:
            if ClaimsImport.objects.filter(proposer=proposer, source="OTHER_INSURER").exists():
                continue
            corporate = proposer.proposer_type == "ORGANISATION"
            insured = max(1, InsuredMember.objects.filter(proposer=proposer).count())
            prem = [["period_start", "period_end", "premium_amount", "insured_count", "currency"]]
            claims = [["occurrence_date", "benefit_code", "paid_amount", "member_reference", "provision_amount",
                       "currency", "status"]]
            base = Decimal(260000 if not corporate else 200000) * insured
            for k in range(24, 0, -1):
                start = (today.replace(day=1) - datetime.timedelta(days=30 * k)).replace(day=1)
                end = (start + datetime.timedelta(days=32)).replace(day=1) - datetime.timedelta(days=1)
                prem.append([start, end, f"{(base / 12).quantize(Decimal('0.01'))}", insured, "AOA"])
                for _ in range(self.rng.randint(0, 2 + insured // 2)):
                    day = start + datetime.timedelta(days=self.rng.randint(0, (end - start).days))
                    amount = Decimal(self.rng.randint(8, 400)) * 1000
                    claims.append([day, self.rng.choice(CLAIM_BENEFITS), f"{amount:.2f}",
                                   f"{proposer.external_reference}-M{self.rng.randint(1, insured)}",
                                   "0" if day < today - datetime.timedelta(days=90) else f"{amount / 4:.2f}",
                                   "AOA", self.rng.choice(["PAID"] * 8 + ["OPEN", "REJECTED"])])
            for kind, rows, name in (("PREMIUMS", prem, "premios"), ("CLAIMS", claims, "sinistros")):
                import_file(kind=kind, proposer_id=proposer.id, policy_id=None, source="OTHER_INSURER",
                            filename=f"{proposer.external_reference}-{name}.xlsx",
                            content=xlsx_from_rows(rows), dry_run=False)
                created += 1
        return created

    # -- segundo tenant -----------------------------------------------------
    def _isolation_tenant(self) -> None:
        code, name = ISOLATION_TENANT
        tenant, _ = Tenant.objects.get_or_create(code=code, defaults={"name": name})
        self.stdout.write(self.style.MIGRATE_HEADING(f"[TESTE] tenant de isolamento {code}"))
        plan_codes = self._seed_tenant_reference(tenant, with_market_plans=True)
        _ReferencePricing.plan_codes = tuple(plan_codes)
        self._seed_pricing_config(tenant)
        account = StaffAccount.all_tenants.filter(tenant_id=tenant.id, email__iexact="admin@isolamento.q360.local").first()
        if account is None:
            account = StaffAccount.all_tenants.create(
                id=uuid.uuid4(), tenant_id=tenant.id, email="admin@isolamento.q360.local",
                name="Admin Isolamento", password_hash=make_password(STAFF_PASSWORD), status=StaffAccount.ACTIVE)
            StaffAccountRole.all_tenants.create(
                id=uuid.uuid4(), tenant_id=tenant.id, staff_account_id=account.id, role=Role.ADMIN.value)
        token = CurrentActorProvider.bind(self._actor(tenant, str(account.id), {Role.ADMIN}))
        try:
            if not Proposer.objects.exists():
                self.demo.tenant = tenant
                self.demo._ensure_proposer(  # noqa: SLF001
                    tenant, external_reference="ISO-CLIENTE-1", proposer_type="INDIVIDUAL",
                    display_name="Cliente Exclusivo do Outro Tenant", registration_number="900000001LA001",
                    email="cliente@isolamento.q360.local", phone="+244 900 900 001")
        finally:
            CurrentActorProvider.reset(token)
        self.report.append(
            f"Tenant de isolamento: {code} ({tenant.id}) — admin@isolamento.q360.local / {STAFF_PASSWORD}; "
            "nenhum dado deste tenant pode aparecer ao autenticar no demo-saude.")

    # --------------------------------------------------------------- resumo
    def _print_report(self) -> None:
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=== seed_full_database concluído ==="))
        for line in self.report:
            self.stdout.write(f" • {line}")
        if self.demo_ran:
            self.stdout.write(
                "\nPlataforma: superadmin.demo@q360.local · Portal: ver `seed_portal_demo` para os cenários "
                "nomeados (Ana, Diana, Carlos, Empresa Kilamba, Mariana)."
            )
