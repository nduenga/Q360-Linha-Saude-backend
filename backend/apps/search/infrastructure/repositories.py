from django.db.models import Q, Case, When, Value, IntegerField


def _rank(field: str, q: str) -> Case:
    """Ranking: exato (0) > começa com (1) > contém (2) > resto (3)."""
    return Case(
        When(**{f'{field}__iexact': q}, then=Value(0)),
        When(**{f'{field}__istartswith': q}, then=Value(1)),
        When(**{f'{field}__icontains': q}, then=Value(2)),
        default=Value(3),
        output_field=IntegerField(),
    )


def search_proposers(q: str, limit: int = 5) -> list[dict]:
    from apps.client.infrastructure.models import Proposer
    qs = (
        Proposer.objects
        .filter(
            Q(display_name__icontains=q)
            | Q(nif__icontains=q)
            | Q(registration_number__icontains=q)
            | Q(email__icontains=q)
            | Q(phone__icontains=q)
        )
        .annotate(rank=_rank('display_name', q))
        .order_by('rank', 'display_name')[:limit]
    )
    return [
        {
            'id': str(p.id),
            'title': p.display_name,
            'subtitle': p.nif or p.registration_number or p.email or '',
            'href': f'/clientes/{p.id}',
        }
        for p in qs
    ]


def search_quotes(q: str, limit: int = 5) -> list[dict]:
    from apps.quote.infrastructure.models import Quote
    qs = (
        Quote.objects
        .filter(Q(quote_number__icontains=q))
        .annotate(rank=_rank('quote_number', q))
        .order_by('rank', '-created_at')[:limit]
    )
    return [
        {
            'id': str(qt.id),
            'title': qt.quote_number or str(qt.id)[:8],
            'subtitle': qt.status or '',
            'href': f'/cotacoes/{qt.id}/resumo',
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
        .filter(Q(policy_number__icontains=q))
        .annotate(rank=_rank('policy_number', q))
        .order_by('rank', '-created_at')[:limit]
    )
    return [
        {
            'id': str(p.id),
            'title': p.policy_number or str(p.id)[:8],
            'subtitle': p.status or '',
            'href': f'/apolices/{p.id}',
        }
        for p in qs
    ]