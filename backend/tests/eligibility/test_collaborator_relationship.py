"""O COLABORADOR de uma empresa é o titular do seu agregado: as regras de
elegibilidade publicadas antes desta relação existir (que só listam TITULAR)
não o podem recusar."""
from apps.eligibility.domain.evaluation import _relationship_allowed


def test_collaborator_counts_as_titular_in_existing_rules():
    legacy = frozenset({"TITULAR", "CONJUGE", "FILHO"})
    assert _relationship_allowed("COLABORADOR", legacy)
    assert _relationship_allowed("CONJUGE", legacy)
    assert not _relationship_allowed("ASCENDENTE", legacy)
    assert not _relationship_allowed("COLABORADOR", frozenset({"CONJUGE", "FILHO"}))
    assert _relationship_allowed("COLABORADOR", frozenset({"COLABORADOR"}))
