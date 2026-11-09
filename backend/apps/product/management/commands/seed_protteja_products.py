"""Carrega a gama Seguro de Saúde Protteja (4 níveis × Individual e Grupo) numa
seguradora: produtos, planos, coberturas e a tarifa do produto.

Os valores vêm de `apps/product/seed/protteja_saude.py` (tirados das propostas
de exemplo; substitua-os pelos oficiais antes de produção).

Seguro para produção e idempotente:
  - um produto ou plano que já existe nunca é alterado (pode ter sido editado);
  - os planos novos ficam INATIVOS até a tarifa estar publicada;
  - a tarifa entra como configuração do produto **a aguardar aprovação**: um
    administrador aprova em Administração › Aprovações (regra dos quatro olhos).

Passos em produção:
    manage.py seed_protteja_products --tenant-code <código>      # cria e submete
    (um administrador aprova as configurações no ecrã de Aprovações)
    manage.py seed_protteja_products --tenant-code <código> --activate

Em staging ou testes, `--approve-as <email>` aprova logo com essa conta (tem
de ser outra pessoa que não o autor, que é o utilizador técnico do seed).
"""
from __future__ import annotations

import datetime
from types import SimpleNamespace
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.business_config.application.service import approve_configuration, create_configuration, submit_configuration
from apps.business_config.domain.scope import product_key
from apps.business_config.infrastructure.models import BusinessConfiguration
from apps.foundation.application.context import CurrentActorProvider
from apps.foundation.domain.actor import Actor
from apps.foundation.domain.permissions import Role
from apps.foundation.domain.scopes import Scope
from apps.foundation.domain.tenant import TenantId
from apps.foundation.infrastructure.models import RuleVersion, Tenant
from apps.product.application import product_service
from apps.product.application.benefit_service import ensure_market_catalog
from apps.product.application.plan_configuration_service import configure_plan_benefit, validate_plan
from apps.product.infrastructure.models import Benefit, Plan, Product
from apps.product.seed import protteja_saude as data

CREATOR_SUBJECT = "system:seed-protteja"
PROPOSAL_TEMPLATE_CODE = "PROTTEJA-PROPOSTA-SAUDE"
PROPOSAL_TEMPLATE_FILE = str(
    __import__("pathlib").Path(__file__).resolve().parents[3] / "quote" / "seed" / "protteja_proposta_saude.docx"
)
_STAMP_DUTY_EXEMPT = {"charges": [{
    "code": "STAMP-DUTY", "category": "TAX", "type": "PERCENTAGE", "value": "0", "included_in_premium": False,
    "description": "Imposto do Selo: seguros de saúde isentos (Código do Imposto do Selo, art. 6.º, n.º 3, al. o)).",
}]}


class Command(BaseCommand):
    help = "Carrega a gama Seguro de Saúde Protteja (produtos, planos, coberturas e tarifa) numa seguradora."

    def add_arguments(self, parser):
        parser.add_argument("--tenant-code", required=True)
        parser.add_argument("--effective-from", type=datetime.date.fromisoformat, default=None,
                            help="Início de vigência da tarifa (AAAA-MM-DD); por omissão, hoje.")
        parser.add_argument("--approve-as", help="Email de uma conta da seguradora que aprova já (staging/testes).")
        parser.add_argument("--activate", action="store_true",
                            help="Ativa os planos Protteja cuja tarifa já está publicada.")

    def handle(self, *args, **opts):
        tenant = Tenant.objects.filter(code=opts["tenant_code"]).first()
        if tenant is None:
            raise CommandError(f"Não existe nenhuma seguradora com o código '{opts['tenant_code']}'.")
        self.tenant = tenant
        self.notes: list[str] = []
        token = CurrentActorProvider.bind(self._actor(CREATOR_SUBJECT))
        try:
            if opts["activate"]:
                self._activate()
            else:
                with transaction.atomic():
                    products = self._products_and_plans()
                    approver_id = self._approver_id(opts["approve_as"]) if opts["approve_as"] else None
                    self._configurations(products, opts["effective_from"] or timezone.localdate(), approver_id)
                    self._tenant_checks(approver_id)
                    self._proposal_template(publish=bool(approver_id))
                if opts["approve_as"]:
                    self._activate()
        finally:
            CurrentActorProvider.reset(token)
        self.stdout.write(self.style.SUCCESS("=== seed_protteja_products concluído ==="))
        for line in self.notes:
            self.stdout.write(f" • {line}")

    # ------------------------------------------------------------- apoio
    def _actor(self, actor_id: str) -> Actor:
        return Actor(actor_id=actor_id, tenant_id=TenantId.parse(self.tenant.id),
                     roles=frozenset({Role.ADMIN}), scopes=frozenset(Scope))

    def _approver_id(self, email: str) -> str:
        from apps.staff_accounts.infrastructure.models import StaffAccount

        account = StaffAccount.all_tenants.filter(tenant_id=self.tenant.id, email__iexact=email, status="ACTIVE").first()
        if account is None:
            raise CommandError(f"Não existe nenhuma conta ativa '{email}' nesta seguradora.")
        return str(account.id)

    # ------------------------------------------------------------- produtos
    def _products_and_plans(self) -> dict[str, Product]:
        ensure_market_catalog(self.tenant.id)
        benefits = {b.code: b for b in Benefit.objects.all()}
        products: dict[str, Product] = {}
        for spec in (data.INDIVIDUAL_PRODUCT, data.GROUP_PRODUCT):
            product = Product.objects.filter(code=spec["code"]).first()
            if product is None:
                product = product_service.create_product(code=spec["code"], name=spec["name"], description=spec["description"])
                self.notes.append(f"Produto criado: {product.code}")
            products[spec["code"]] = product

        created, kept = [], []
        for plan_spec in data.plans():
            product = products[plan_spec["product"]]
            if Plan.objects.filter(product=product, code=plan_spec["code"]).exists():
                kept.append(plan_spec["code"])
                continue
            complementary = [
                benefits[c["code"]].id for c in plan_spec["coverages"] if benefits[c["code"]].benefit_type == "COMPLEMENTARY"
            ]
            plan = product_service.create_plan(
                product=product, code=plan_spec["code"], name=plan_spec["name"], description=plan_spec["description"],
                complementary_benefit_ids=complementary, settings=plan_spec["settings"],
            )
            for coverage in plan_spec["coverages"]:
                configure_plan_benefit(plan=plan, benefit=benefits[coverage["code"]], configuration=coverage["config"])
            Plan.objects.filter(id=plan.id).update(status="INACTIVE")  # só depois de a tarifa estar publicada
            report = validate_plan(plan=plan)
            if not report["valid"]:
                raise CommandError(f"O plano {plan.code} não é válido: {report['errors']}")
            created.append(plan.code)
        if created:
            self.notes.append(f"Planos criados (inativos até a tarifa ser publicada): {', '.join(created)}")
        if kept:
            self.notes.append(f"Planos que já existiam e não foram alterados: {', '.join(kept)}")
        return products

    # ------------------------------------------------------- configurações
    def _configurations(self, products: dict[str, Product], effective_from: datetime.date, approver_id: str | None) -> None:
        pending, published, unchanged = [], [], []
        for product_code, group in ((data.INDIVIDUAL_PRODUCT["code"], False), (data.GROUP_PRODUCT["code"], True)):
            product = products[product_code]
            for base, value in data.product_configurations(group).items():
                key = product_key(base, product.id)
                current = (
                    BusinessConfiguration.objects.filter(config_key=key, status__in=("PUBLISHED", "PENDING_APPROVAL"))
                    .order_by("-version_no").first()
                )
                if current is not None and current.value_json == value:
                    unchanged.append(f"{base} ({product_code})")
                    if current.status == "PENDING_APPROVAL" and approver_id:
                        self._approve(current, approver_id)
                        published.append(f"{base} ({product_code})")
                    continue
                config = create_configuration(
                    SimpleNamespace(), config_key=key, value=value, effective_from=effective_from,
                    metadata={"source": data.SOURCE, "seed": "seed_protteja_products"},
                )
                submit_configuration(SimpleNamespace(), config, change_reason="Gama Seguro de Saúde Protteja")
                if approver_id:
                    self._approve(config, approver_id)
                    published.append(f"{base} ({product_code})")
                else:
                    pending.append(f"{base} ({product_code})")
        if pending:
            self.notes.append(
                "A aguardar aprovação em Administração › Aprovações: " + ", ".join(pending)
                + ". Depois de aprovadas, corra de novo com --activate."
            )
        if published:
            self.notes.append("Publicadas: " + ", ".join(published))
        if unchanged:
            self.notes.append("Já existiam com os mesmos valores: " + ", ".join(unchanged))

    def _approve(self, config: BusinessConfiguration, approver_id: str) -> None:
        token = CurrentActorProvider.bind(self._actor(approver_id))
        try:
            approve_configuration(SimpleNamespace(), config)
        finally:
            CurrentActorProvider.reset(token)

    def _tenant_checks(self, approver_id: str | None) -> None:
        """O que a tarifa Protteja precisa da seguradora e o seed não altera sozinho."""
        taxes = BusinessConfiguration.objects.filter(config_key="pricing.taxes_fees", status="PUBLISHED").order_by("-version_no").first()
        pending_taxes = BusinessConfiguration.objects.filter(config_key="pricing.taxes_fees", status="PENDING_APPROVAL").first()
        if taxes is None and pending_taxes is not None and approver_id and pending_taxes.value_json == _STAMP_DUTY_EXEMPT:
            self._approve(pending_taxes, approver_id)
            self.notes.append("Impostos e encargos publicados: seguros de saúde isentos de Imposto do Selo.")
            return self._eligibility_note()
        if taxes is None:
            if pending_taxes is None:
                config = create_configuration(
                    SimpleNamespace(), config_key="pricing.taxes_fees", value=_STAMP_DUTY_EXEMPT,
                    effective_from=timezone.localdate(), metadata={"seed": "seed_protteja_products"},
                )
                submit_configuration(SimpleNamespace(), config, change_reason="Seguros de saúde isentos de Imposto do Selo")
                if approver_id:
                    self._approve(config, approver_id)
                    self.notes.append("Impostos e encargos publicados: seguros de saúde isentos de Imposto do Selo.")
                    return self._eligibility_note()
            self.notes.append("A seguradora não tinha impostos e encargos publicados: ficou uma proposta (isento) a aguardar aprovação.")
        else:
            charged = [c for c in (taxes.value_json or {}).get("charges", [])
                       if str(c.get("value", "0")) not in ("0", "0.0", "0.00") and not c.get("included_in_premium")]
            if charged:
                self.notes.append(
                    "ATENÇÃO: os impostos e encargos publicados acrescentam "
                    + ", ".join(f"{c.get('code')} {c.get('value')}%" for c in charged)
                    + " ao prémio; as propostas Protteja não têm acréscimos (saúde isenta de Imposto do Selo)."
                )
        self._eligibility_note()

    def _eligibility_note(self) -> None:
        if not RuleVersion.objects.filter(rule_set__rule_domain="ELIGIBILITY", status="PUBLISHED").exists():
            self.notes.append("ATENÇÃO: a seguradora não tem regra de elegibilidade publicada; as cotações não avançam sem ela.")
        self.notes.append(
            "Valores de exemplo (propostas Protteja v2): confirmar com a Tabela de Benefícios e a tarifa oficiais. "
            "Sem tarifa para 51–65 anos no Individual: essas idades ficam sem cálculo até haver valores."
        )

    # ------------------------------------------------- modelo de proposta
    def _proposal_template(self, *, publish: bool) -> None:
        """Modelo Word da proposta Protteja (gerado por
        `tools/build_protteja_proposal_template.py`), como rascunho."""
        import json
        from pathlib import Path

        from django.core.files.uploadedfile import SimpleUploadedFile

        from apps.quote.application import document_service, template_files
        from apps.quote.application.word_template import DOCX_CONTENT_TYPE
        from apps.quote.domain.proposal_template import DEFAULT_TEMPLATE
        from apps.quote.infrastructure.models import DocumentTemplateVersion

        if DocumentTemplateVersion.objects.filter(template_code=PROPOSAL_TEMPLATE_CODE).exists():
            self.notes.append(f"Modelo de proposta {PROPOSAL_TEMPLATE_CODE} já existia: não foi alterado.")
            return
        body = {**DEFAULT_TEMPLATE, "title": "Proposta Comercial de Seguro de Saúde Protteja {{quote.number}}"}
        template = document_service.create_document_template(
            template_code=PROPOSAL_TEMPLATE_CODE, storage_ref=json.dumps(body, ensure_ascii=False),
            effective_from=timezone.localdate(),
        )
        data = Path(PROPOSAL_TEMPLATE_FILE).read_bytes()
        template, _report = template_files.save_word(
            template, SimpleUploadedFile("protteja_proposta_saude.docx", data, content_type=DOCX_CONTENT_TYPE)
        )
        if publish:
            document_service.publish_document_template(template)
            self.notes.append(f"Modelo de proposta {PROPOSAL_TEMPLATE_CODE} publicado.")
        else:
            self.notes.append(
                f"Modelo de proposta {PROPOSAL_TEMPLATE_CODE} criado em rascunho: confira-o e publique-o em "
                "Administração › Documentos."
            )

    # ---------------------------------------------------------- ativação
    def _activate(self) -> None:
        keys = [
            product_key(base, product.id)
            for product in Product.objects.filter(code__in=(data.INDIVIDUAL_PRODUCT["code"], data.GROUP_PRODUCT["code"]))
            for base in data.product_configurations(False)
        ]
        missing = [k for k in keys if not BusinessConfiguration.objects.filter(config_key=k, status="PUBLISHED").exists()]
        if missing or len(keys) < 10:
            self.notes.append(f"Planos não ativados: faltam publicar {len(missing) or 'as'} configurações da tarifa.")
            return
        codes = [p["code"] for p in data.plans()]
        activated = Plan.objects.filter(code__in=codes, status="INACTIVE").update(status="ACTIVE")
        self.notes.append(f"Planos ativados: {activated} (os restantes já estavam ativos).")
