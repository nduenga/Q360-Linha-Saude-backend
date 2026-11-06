import re

from django.db.models import Q, Case, When, Value, IntegerField
from django.db.models.functions import Replace

from shared.status_labels import status_label


def _rank(field: str, q: str) -> Case:
    """Ranking: exato (0) > começa com (1) > contém (2) > resto (3)."""
    return Case(
        When(**{f'{field}__iexact': q}, then=Value(0)),
        When(**{f'{field}__istartswith': q}, then=Value(1)),
        When(**{f'{field}__icontains': q}, then=Value(2)),
        default=Value(3),
        output_field=IntegerField(),
    )


def mask_identifier(value: str | None) -> str | None:
    """Mostra só o fim do NIF: chega para distinguir homónimos sem o expor."""
    if not value:
        return None
    visible = value[-5:]
    return '•••••' + visible if len(value) > 5 else value


def _proposer_subtitle(proposer, masked: str | None, city: str | None) -> str:
    kind = 'Organização' if proposer.proposer_type == 'ORGANISATION' else 'Individual'
    parts = [kind, f'NIF {masked}' if masked else None, city]
    return ' · '.join(part for part in parts if part)


def search_proposers(q: str, limit: int = 5) -> list[dict]:
    from apps.client.infrastructure.models import Proposer
    from apps.policy.infrastructure.models import Policy

    digits = re.sub(r'\D', '', q)
    phone_match = Q(phone__icontains=q)
    if len(digits) >= 4:
        phone_match |= Q(phone_digits__icontains=digits)
    qs = (
        Proposer.objects
        .annotate(phone_digits=Replace(Replace(Replace('phone', Value(' '), Value('')), Value('-'), Value('')), Value('+'), Value('')))
        .filter(
            Q(display_name__icontains=q)
            | Q(nif__icontains=q)
            | Q(registration_number__icontains=q)
            | Q(email__icontains=q)
            | phone_match
        )
        .annotate(rank=_rank('display_name', q))
        .order_by('rank', 'display_name')[:limit]
    )
    results = []
    for p in qs:
        masked = mask_identifier(p.nif or p.registration_number)
        city = p.municipality or p.province
        open_policy = Policy.objects.filter(proposer_id=p.id, status='ACTIVE').order_by('-created_at').first()
        actions = [{'code': 'NEW_QUOTE', 'label': f'Nova cotação para {p.display_name}', 'href': f'/cotacoes/nova?proposerId={p.id}'}]
        if open_policy is not None:
            actions.append({
                'code': 'REGISTER_PAYMENT',
                'label': f'Registar pagamento — {open_policy.policy_number}',
                'href': f'/cobrancas?policyNumber={open_policy.policy_number}',
            })
        results.append({
            'id': str(p.id),
            'title': p.display_name,
            'subtitle': _proposer_subtitle(p, masked, city),
            'href': f'/clientes/{p.id}',
            'maskedNif': masked,
            'city': city,
            'actions': actions,
        })
    return results


def search_quotes(q: str, limit: int = 5) -> list[dict]:
    from apps.quote.infrastructure.models import Quote
    qs = (
        Quote.objects
        .select_related('proposer')
        .filter(Q(quote_number__icontains=q) | Q(proposer__display_name__icontains=q))
        .annotate(rank=_rank('quote_number', q))
        .order_by('rank', '-created_at')[:limit]
    )
    return [
        {
            'id': str(qt.id),
            'title': qt.quote_number or str(qt.id)[:8],
            'subtitle': ' · '.join(filter(None, [qt.proposer.display_name, status_label('quote', qt.status)])),
            'href': f'/cotacoes/{qt.id}/resumo',
            'status': qt.status,
            'statusLabel': status_label('quote', qt.status),
        }
        for qt in qs
    ]


def search_products(q: str, limit: int = 5) -> list[dict]:
    from apps.product.infrastructure.models import Product
    qs = (
        Product.objects
        .filter(Q(name__icontains=q) | Q(code__icontains=q))
        .annotate(rank=_rank('name', q))
        .order_by('rank', 'name')[:limit]
    )
    return [
        {
            'id': str(p.id),
            'title': p.name,
            'subtitle': p.code or '',
            'href': f'/produtos/{p.id}',
        }
        for p in qs
    ]


def search_policies(q: str, limit: int = 5) -> list[dict]:
    from apps.policy.infrastructure.models import Policy
    qs = (
        Policy.objects
        .select_related('proposer')
        .filter(Q(policy_number__icontains=q) | Q(proposer__display_name__icontains=q))
        .annotate(rank=_rank('policy_number', q))
        .order_by('rank', '-created_at')[:limit]
    )
    return [
        {
            'id': str(p.id),
            'title': p.policy_number or str(p.id)[:8],
            'subtitle': ' · '.join(filter(None, [p.proposer.display_name, status_label('policy', p.status)])),
            'href': f'/apolices/{p.id}',
            'status': p.status,
            'statusLabel': status_label('policy', p.status),
        }
        for p in qs
    ]


def search_requests(q: str, limit: int = 5) -> list[dict]:
    from apps.client.infrastructure.models import Proposer
    from apps.customer_portal.infrastructure.models import PortalRequest

    rows = list(
        PortalRequest.objects
        .filter(Q(request_number__icontains=q) | Q(subject__icontains=q))
        .annotate(rank=_rank('request_number', q))
        .order_by('rank', '-created_at')[:limit]
    )
    holders = dict(Proposer.objects.filter(id__in={r.proposer_id for r in rows}).values_list('id', 'display_name'))
    return [
        {
            'id': str(r.id),
            'title': r.request_number,
            'subtitle': ' · '.join(filter(None, [holders.get(r.proposer_id), r.subject])),
            'href': f'/atendimento/pedidos/{r.request_number}',
            'status': r.status,
            'statusLabel': status_label('portalRequest', r.status),
        }
        for r in rows
    ]