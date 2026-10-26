"""Nome legível do registo de cada evento de auditoria («COT-47», «APO-1»,
«Ana Paula Silva», «Hospitalização · Família Plus»…), para o trilho mostrar
nomes em vez de identificadores técnicos. Resolve uma página de eventos de
uma vez (uma consulta por tipo de registo), dentro do tenant atual."""
from __future__ import annotations

from collections import defaultdict
from typing import Callable, Iterable
from uuid import UUID


def _member_name(m) -> str:
    return " ".join(part for part in (m.first_name, m.last_name) if part) or "Pessoa segura sem nome"


def _resolvers() -> dict[str, tuple[Callable[[list[UUID]], Iterable], Callable]]:
    from apps.business_config.infrastructure.models import BusinessConfiguration
    from apps.client.infrastructure.models import InsuredMember, Proposer
    from apps.customer_portal.infrastructure.models import CustomerAccount, PortalRequest
    from apps.eligibility.infrastructure.models import EligibilityEvaluation
    from apps.foundation.infrastructure.models import RuleVersion, SystemParameter
    from apps.policy.infrastructure.models import Policy
    from apps.pricing.infrastructure.models import PricingRun, RatingTable
    from apps.product.infrastructure.models import Plan, PlanBenefit, PricingParameterSet, Product
    from apps.quote.infrastructure.models import DocumentTemplateVersion, Quote
    from apps.staff_accounts.infrastructure.models import StaffAccount

    def run_label(run) -> str:
        quote = Quote.objects.filter(latest_pricing_run_id=run.id).values_list("quote_number", flat=True).first()
        return f"Cálculo da cotação {quote}" if quote else f"Cálculo de prémio · {run.plan.name}"

    def config_label(cfg) -> str:
        from apps.business_config.domain.catalog import CATALOG_BY_KEY

        entry = CATALOG_BY_KEY.get(cfg.config_key) or {}
        return f"{entry.get('label') or cfg.config_key} · v{cfg.version_no}"

    return {
        "Quote": (lambda ids: Quote.objects.filter(id__in=ids), lambda q: q.quote_number or "Cotação"),
        "Policy": (lambda ids: Policy.objects.filter(id__in=ids), lambda p: p.policy_number or "Apólice"),
        "Proposer": (lambda ids: Proposer.objects.filter(id__in=ids), lambda p: p.display_name),
        "InsuredMember": (lambda ids: InsuredMember.objects.filter(id__in=ids), _member_name),
        "StaffAccount": (lambda ids: StaffAccount.objects.filter(id__in=ids), lambda a: a.name),
        "Plan": (lambda ids: Plan.objects.filter(id__in=ids), lambda p: p.name),
        "Product": (lambda ids: Product.objects.filter(id__in=ids), lambda p: p.name),
        "PlanBenefit": (lambda ids: PlanBenefit.objects.select_related("benefit", "plan").filter(id__in=ids),
                        lambda pb: f"{pb.benefit.name} · {pb.plan.name}"),
        "EligibilityEvaluation": (lambda ids: EligibilityEvaluation.objects.select_related("member").filter(id__in=ids),
                                  lambda e: f"Elegibilidade de {_member_name(e.member)}" if e.member_id else "Elegibilidade"),
        "PricingRun": (lambda ids: PricingRun.objects.select_related("plan").filter(id__in=ids), run_label),
        "PortalRequest": (lambda ids: PortalRequest.objects.filter(id__in=ids), lambda r: r.request_number),
        "CustomerAccount": (lambda ids: CustomerAccount.objects.filter(id__in=ids), lambda a: f"Conta do portal · {a.email}"),
        "RatingTable": (lambda ids: RatingTable.objects.filter(id__in=ids), lambda t: t.name or t.code),
        "PricingParameterSet": (lambda ids: PricingParameterSet.objects.filter(id__in=ids), lambda p: p.code),
        "DocumentTemplateVersion": (lambda ids: DocumentTemplateVersion.objects.filter(id__in=ids), lambda d: d.template_code),
        "RuleVersion": (lambda ids: RuleVersion.objects.select_related("rule_set").filter(id__in=ids),
                        lambda r: f"{r.rule_set.code} · v{r.version_no}" if getattr(r, "version_no", None) else r.rule_set.code),
        "SystemParameter": (lambda ids: SystemParameter.objects.filter(id__in=ids), lambda p: p.code),
        "BUSINESS_CONFIGURATION": (lambda ids: BusinessConfiguration.objects.filter(id__in=ids), config_label),
        "BusinessConfiguration": (lambda ids: BusinessConfiguration.objects.filter(id__in=ids), config_label),
    }


def entity_labels(events: Iterable) -> dict[tuple[str, str], str]:
    wanted: dict[str, set[UUID]] = defaultdict(set)
    for event in events:
        try:
            wanted[event.entity_type].add(UUID(str(event.entity_id)))
        except (TypeError, ValueError, AttributeError):
            continue
    resolvers = _resolvers()
    out: dict[tuple[str, str], str] = {}
    for entity_type, ids in wanted.items():
        resolver = resolvers.get(entity_type)
        if resolver is None:
            continue
        fetch, label = resolver
        try:
            for obj in fetch(list(ids)):
                out[(entity_type, str(obj.id))] = label(obj)
        except Exception:  # noqa: BLE001 - um nome em falta nunca pode partir a auditoria
            continue
    return out
