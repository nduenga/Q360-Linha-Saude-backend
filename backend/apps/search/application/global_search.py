from apps.search.domain.result import SearchGroup, SearchItem
from apps.search.infrastructure import repositories as repo


def global_search(q: str) -> dict:
    q = q.strip()
    if len(q) < 2:
        return {'total': 0, 'groups': []}

    groups: list[SearchGroup] = []

    proposers = repo.search_proposers(q)
    if proposers:
        groups.append(SearchGroup(
            kind='proposer',
            label='Clientes',
            items=[SearchItem(**p) for p in proposers],
        ))

    quotes = repo.search_quotes(q)
    if quotes:
        groups.append(SearchGroup(
            kind='quote',
            label='Cotações',
            items=[SearchItem(**qt) for qt in quotes],
        ))

    products = repo.search_products(q)
    if products:
        groups.append(SearchGroup(
            kind='product',
            label='Produtos',
            items=[SearchItem(**p) for p in products],
        ))

    policies = repo.search_policies(q)
    if policies:
        groups.append(SearchGroup(
            kind='policy',
            label='Apólices',
            items=[SearchItem(**p) for p in policies],
        ))

    total = sum(len(g.items) for g in groups)

    return {
        'total': total,
        'groups': [g.to_dict() for g in groups],
    }