"""Dados de demonstração do Portal Cliente, por cima do tenant que
`seed_demo_data` cria (plataforma + colaboradores + apólices).

Idempotente e só de desenvolvimento/demonstração: repõe as palavras-passe e o
estado dos clientes demo sempre que corre, tal como `seed_demo_data` faz com o
staff. Cada cliente existe para provar uma parte do portal:

  Ana Silva        entra com email + palavra-passe; apólice activa, prestação em
                   atraso e outra a vencer, cotação aprovada à espera de aceitação,
                   pedidos (um a aguardar o cliente) e mensagens.
  Diana Lopes      entra com email + palavra-passe; só tem cotações (em análise e
                   recusada); o rascunho não aparece.
  Carlos Mendes    SEM conta: serve para o primeiro acesso (apólice a aguardar o
                   1.º pagamento).
  Empresa Kilamba  SEM conta: primeiro acesso, e a apólice termina daqui a 45 dias
                   (janela de renovação aberta).
  Mariana Costa    SEM conta e SEM email no registo: o primeiro acesso responde que
                   falta o email (PORTAL-NO-EMAIL).
"""
from __future__ import annotations

import datetime

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.client.infrastructure.models import InsuredMember, Proposer
from apps.customer_portal.application import messages_service, requests_service
from apps.customer_portal.infrastructure.models import CustomerAccount, CustomerAccountProposer, PortalRequest
from apps.foundation.application.context import CurrentActorProvider
from apps.foundation.domain.actor import Actor
from apps.foundation.domain.permissions import Role
from apps.foundation.domain.tenant import TenantId
from apps.foundation.infrastructure.models import Tenant
from apps.foundation.management.commands.seed_demo_data import _STAFF, Command as DemoCommand
from apps.policy.infrastructure.models import Policy, PremiumInstallment
from apps.quote.application.quote_service import decide_quote
from apps.quote.domain.enums import QuoteDecisionType
from apps.quote.infrastructure.models import Quote
from apps.staff_accounts.infrastructure.models import StaffAccount

PORTAL_PASSWORD = "Cliente!Demo2026"
_MARIANA = "DEMO-MARIANA-SEM-EMAIL"


class Command(BaseCommand):
    help = "Seed customer-portal demo data on top of the demo tenant created by seed_demo_data."

    def add_arguments(self, parser):
        parser.add_argument("--tenant-code", default="demo-saude")
        parser.add_argument("--password", default=PORTAL_PASSWORD, help="Palavra-passe dos clientes demo com conta.")

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                "seed_portal_demo is restricted to DEBUG environments. "
                "For production, use prepare_portal_test_accounts with an explicit tenant ID."
            )
        try:
            tenant = Tenant.objects.get(code=options["tenant_code"])
        except Tenant.DoesNotExist as exc:
            raise CommandError(
                f"No tenant '{options['tenant_code']}'. Run `manage.py seed_demo_data` first."
            ) from exc

        demo = DemoCommand()
        original_actor = CurrentActorProvider.bind(None)
        try:
            staff = {
                key: StaffAccount.all_tenants.filter(tenant_id=tenant.id, email__iexact=email).first()
                for key, email, _name, _roles in _STAFF
            }
            if not all(staff.values()):
                raise CommandError("Demo staff accounts are missing. Run `manage.py seed_demo_data` first.")
            demo._bind(tenant, staff["admin"], Role.ADMIN)  # noqa: SLF001

            proposers = {
                key: Proposer.objects.filter(external_reference=ref).first()
                for key, ref in (
                    ("ana", "DEMO-ANA-SILVA"), ("carlos", "DEMO-CARLOS-MENDES"),
                    ("empresa", "DEMO-EMPRESA-KILAMBA"), ("diana", "DEMO-DIANA-LOPES"),
                )
            }
            if not all(proposers.values()):
                raise CommandError("Demo customers are missing. Run `manage.py seed_demo_data` first.")
            ana_policy = Policy.objects.filter(proposer=proposers["ana"], status="ACTIVE").order_by("created_at").first()
            empresa_policy = Policy.objects.filter(proposer=proposers["empresa"], status="ACTIVE").first()
            if ana_policy is None or empresa_policy is None:
                raise CommandError("Demo policies are missing. Run `manage.py seed_demo_data` first.")

            accounts = {
                "ana": self._account(tenant, proposers["ana"], options["password"]),
                "diana": self._account(tenant, proposers["diana"], options["password"]),
            }
            self._reset_accountless(tenant, proposers["carlos"], proposers["empresa"])
            self._ana_payments(ana_policy)
            self._ana_approved_quote(demo, tenant, staff, proposers["ana"], ana_policy)
            self._empresa_renewal_window(empresa_policy)
            mariana = self._mariana(demo, tenant, staff, ana_policy)
            self._ana_requests_and_messages(demo, tenant, staff, accounts["ana"], proposers["ana"], ana_policy)
            demo._bind(tenant, staff["admin"], Role.ADMIN)  # noqa: SLF001 (the summary reads tenant data)
            self._print_summary(tenant, proposers, mariana, options["password"])
        finally:
            CurrentActorProvider.reset(original_actor)

    # ------------------------------------------------------------ contas
    @staticmethod
    def _account(tenant: Tenant, proposer: Proposer, password: str) -> CustomerAccount:
        email = proposer.email.strip().lower()
        now = timezone.now()
        fields = dict(
            password_hash=make_password(password), password_set_at=now, email_verified=True,
            failed_otp_attempts=0, locked_until=None,
        )
        account = CustomerAccount.all_tenants.filter(tenant_id=tenant.id, email__iexact=email).first()
        if account is None:
            account = CustomerAccount.all_tenants.create(tenant_id=tenant.id, email=email, **fields)
        else:
            CustomerAccount.all_tenants.filter(id=account.id).update(**fields)
            account.refresh_from_db()
        CustomerAccountProposer.all_tenants.get_or_create(
            tenant_id=tenant.id, customer_account=account, proposer=proposer
        )
        return account

    @staticmethod
    def _reset_accountless(tenant: Tenant, *proposers: Proposer) -> None:
        """Carlos and Empresa Kilamba must be able to do the first access again:
        drop any account/password a previous test run created for their email."""
        for proposer in proposers:
            email = (proposer.email or "").strip().lower()
            CustomerAccount.all_tenants.filter(tenant_id=tenant.id, email__iexact=email).update(
                password_hash=None, password_set_at=None, failed_otp_attempts=0, locked_until=None
            )

    # ----------------------------------------------------- cenários da Ana
    @staticmethod
    def _ana_payments(policy: Policy) -> None:
        """One instalment overdue and one due soon, for the payments page, the
        dashboard alerts and the notifications."""
        today = datetime.date.today()
        installments = list(PremiumInstallment.all_tenants.filter(policy_id=policy.id).order_by("installment_no"))
        if len(installments) < 3:
            return
        PremiumInstallment.all_tenants.filter(id=installments[1].id).update(
            status="OVERDUE", due_date=today - datetime.timedelta(days=10), paid_at=None
        )
        PremiumInstallment.all_tenants.filter(id=installments[2].id).update(
            status="DUE", due_date=today + datetime.timedelta(days=5), paid_at=None
        )

    @staticmethod
    def _ana_approved_quote(demo, tenant, staff, proposer: Proposer, policy: Policy) -> None:
        """An approved quote waiting for the customer's acceptance."""
        if Quote.objects.filter(proposer=proposer, status="APPROVED").exists():
            return
        holder = InsuredMember.objects.get(proposer=proposer, external_reference="DEMO-ANA-TITULAR")
        demo._bind(tenant, staff["subscriber"], Role.SUBSCRIBER)  # noqa: SLF001
        quote = demo._create_quote_with_evaluations(  # noqa: SLF001
            proposer=proposer, plan=policy.plan, effective_date=datetime.date.today() + datetime.timedelta(days=10),
            members=[(holder, {"angola": {}})],
        )
        quote = demo._price_and_submit(quote, "portal-approved")  # noqa: SLF001
        demo._bind(tenant, staff["manager"], Role.SUBSCRIPTION_MANAGER)  # noqa: SLF001
        decide_quote(
            quote=quote, decision=QuoteDecisionType.APPROVE.value, reason_code="DEMO_APPROVED",
            reason_text="Cotação aprovada para testar a aceitação no portal.", row_version=quote.row_version,
            correlation_id="demo-portal-approved-decision",
        )
        demo._bind(tenant, staff["admin"], Role.ADMIN)  # noqa: SLF001

    @staticmethod
    def _empresa_renewal_window(policy: Policy) -> None:
        Policy.all_tenants.filter(id=policy.id).update(end_date=datetime.date.today() + datetime.timedelta(days=45))

    @staticmethod
    def _mariana(demo, tenant, staff, ana_policy: Policy) -> dict:
        """A customer with a visible quote but no email on file."""
        proposer = demo._ensure_proposer(  # noqa: SLF001
            tenant, external_reference=_MARIANA, proposer_type="INDIVIDUAL", display_name="Mariana Costa",
            registration_number="000000005LA005", email="", phone="+244 900 000 005",
        )
        member = demo._ensure_member(  # noqa: SLF001
            proposer, "DEMO-MARIANA-TITULAR", "TITULAR", "Mariana", "Costa", "1994-04-04"
        )
        quote = Quote.objects.filter(proposer=proposer).order_by("created_at").first()
        if quote is None:
            demo._bind(tenant, staff["subscriber"], Role.SUBSCRIBER)  # noqa: SLF001
            quote = demo._create_quote_with_evaluations(  # noqa: SLF001
                proposer=proposer, plan=ana_policy.plan,
                effective_date=datetime.date.today() + datetime.timedelta(days=12), members=[(member, {"angola": {}})],
            )
            demo._price_and_submit(quote, "mariana")  # noqa: SLF001
            demo._bind(tenant, staff["admin"], Role.ADMIN)  # noqa: SLF001
        return {"proposer": proposer, "quote_number": quote.quote_number}

    @staticmethod
    def _ana_requests_and_messages(demo, tenant, staff, account, proposer: Proposer, policy: Policy) -> None:
        if PortalRequest.objects.filter(proposer_id=proposer.id).exists():
            return
        customer = Actor(
            actor_id=str(account.id), tenant_id=TenantId.parse(tenant.id), roles=frozenset(), scopes=frozenset(),
            actor_type="CUSTOMER", customer_proposer_ids=frozenset({str(proposer.id)}),
        )
        CurrentActorProvider.bind(customer)
        waiting = requests_service.create_request(
            account_id=account.id, request_type="DATA_CHANGE", subject="Actualizar a morada",
            description="Mudei de casa e quero actualizar a morada da apólice.", policy_number=policy.policy_number,
            quote_number=None, payload={},
        )
        requests_service.create_request(
            account_id=account.id, request_type="COVERAGE_QUESTION", subject="A farmácia cobre medicamentos de uso crónico?",
            description="Quero saber o limite e a carência.", policy_number=policy.policy_number, quote_number=None, payload={},
        )
        messages_service.customer_send(
            account_id=account.id, context_type="POLICY", context_ref=policy.policy_number,
            body="Bom dia, gostava de saber como funciona o cartão digital.",
        )

        demo._bind(tenant, staff["admin"], Role.ADMIN)  # noqa: SLF001
        actor_ref = str(staff["admin"].id)
        requests_service.staff_transition(request_number=waiting.request_number, to_status="IN_REVIEW", note=None, actor_ref=actor_ref)
        requests_service.staff_transition(
            request_number=waiting.request_number, to_status="AWAITING_CUSTOMER",
            note="Envie-nos um comprovativo da nova morada.", actor_ref=actor_ref,
        )
        messages_service.staff_send(
            context_type="POLICY", context_ref=policy.policy_number,
            body="Bom dia! O cartão digital está em «Beneficiários». Pode mostrá-lo no telemóvel.", actor_ref=actor_ref,
        )

    # ----------------------------------------------------------- resumo
    def _print_summary(self, tenant: Tenant, proposers: dict, mariana: dict, password: str) -> None:
        ana_policy = Policy.objects.filter(proposer=proposers["ana"], status="ACTIVE").order_by("created_at").first()
        carlos_policy = Policy.objects.filter(proposer=proposers["carlos"]).order_by("created_at").first()
        empresa_policy = Policy.objects.filter(proposer=proposers["empresa"], status="ACTIVE").first()
        diana_quote = Quote.objects.filter(proposer=proposers["diana"], status="IN_REVIEW").first()
        w = self.stdout.write
        w(self.style.SUCCESS("Portal do Cliente: dados de demonstração prontos."))
        w(f"Tenant: {tenant.code} ({tenant.id})  <- NEXT_PUBLIC_CUSTOMER_PORTAL_TENANT_ID do portal")
        w(f"\nCLIENTES COM CONTA (entrar com email + palavra-passe: {password})")
        w(f"  Ana Silva   {proposers['ana'].email}  — apólice {ana_policy.policy_number}")
        w(f"  Diana Lopes {proposers['diana'].email}  — só cotações")
        w("\nCLIENTES SEM CONTA (testar «Criar a minha palavra-passe»: referência + documento)")
        w(f"  Carlos Mendes   referência {carlos_policy.policy_number}  documento {proposers['carlos'].registration_number}  email {proposers['carlos'].email}")
        w(f"  Empresa Kilamba referência {empresa_policy.policy_number}  documento {proposers['empresa'].registration_number}  email {proposers['empresa'].email}")
        w(f"  Mariana Costa   referência {mariana['quote_number']} (cotação)  documento {mariana['proposer'].registration_number}  — SEM email (deve dar erro)")
        if diana_quote:
            w(f"\nTambém funciona com número de cotação, p.ex. {diana_quote.quote_number} + documento {proposers['diana'].registration_number}.")
