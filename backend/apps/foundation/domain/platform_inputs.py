"""Valores da camada geral do fornecedor que as fórmulas dos tenants podem
usar: constantes (`cambio_usd_aoa`, `taxa_arseg_pct`…) e tabelas de
referência (`tabela("codigo", chave, "coluna")`).

O motor carrega-os uma vez por cálculo e abre um contexto com `use(...)`; o
avaliador de fórmulas lê-os daí. Fora de um contexto, usa o fornecedor
registado pela aplicação (`set_provider`), que os carrega da base de dados.
Este módulo não acede à base de dados."""
from __future__ import annotations

import contextlib
import dataclasses
from collections.abc import Callable, Iterator, Mapping
from contextvars import ContextVar
from decimal import Decimal, InvalidOperation
from typing import Any


def normalise_key(raw: Any) -> str:
    """Chaves comparáveis: números pelo valor (5 = 5.0), texto sem maiúsculas."""
    if isinstance(raw, bool):
        return str(raw).casefold()
    try:
        number = Decimal(str(raw).strip())
        if number.is_finite():
            return format(number.normalize(), "f")
    except (InvalidOperation, ValueError):
        pass
    return str(raw).strip().casefold()


@dataclasses.dataclass(frozen=True)
class ReferenceTable:
    code: str
    version_no: int
    key_column: str
    columns: tuple[str, ...]
    rows: Mapping[str, Mapping[str, Any]]  # chave normalizada -> linha

    def lookup(self, key: Any, column: str) -> Any:
        if column not in self.columns:
            raise KeyError(f"a tabela '{self.code}' não tem a coluna '{column}' (colunas: {list(self.columns)})")
        row = self.rows.get(normalise_key(key))
        if row is None:
            raise KeyError(f"a tabela '{self.code}' não tem a chave '{key}'")
        return row.get(column)


@dataclasses.dataclass(frozen=True)
class PlatformInputs:
    constants: Mapping[str, Decimal] = dataclasses.field(default_factory=dict)
    tables: Mapping[str, ReferenceTable] = dataclasses.field(default_factory=dict)


_current: ContextVar[PlatformInputs | None] = ContextVar("q360_platform_inputs", default=None)
_provider: Callable[[], PlatformInputs] | None = None


def set_provider(provider: Callable[[], PlatformInputs]) -> None:
    global _provider
    _provider = provider


def current() -> PlatformInputs:
    inputs = _current.get()
    if inputs is not None:
        return inputs
    return _provider() if _provider is not None else PlatformInputs()


@contextlib.contextmanager
def use(inputs: PlatformInputs) -> Iterator[PlatformInputs]:
    token = _current.set(inputs)
    try:
        yield inputs
    finally:
        _current.reset(token)
