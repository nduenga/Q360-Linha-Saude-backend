"""Carrega da base de dados os valores do fornecedor que as fórmulas usam
(constantes e tabelas de referência em vigor) — ver
`apps.foundation.domain.platform_inputs`."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from apps.foundation.application import platform_parameter_service, platform_reference_service
from apps.foundation.domain.platform_inputs import PlatformInputs
from apps.foundation.domain.system_parameters import PLATFORM_CONSTANTS


def load() -> PlatformInputs:
    constants: dict[str, Decimal] = {}
    for name, code in PLATFORM_CONSTANTS.items():
        raw = platform_parameter_service.platform_value(code)
        try:
            constants[name] = Decimal(str(raw))
        except (InvalidOperation, TypeError, ValueError):
            continue  # sem valor em vigor: a fórmula que a use falha com mensagem clara
    tables = {
        code: platform_reference_service.as_reference_table(version)
        for code, version in platform_reference_service.effective_tables().items()
    }
    return PlatformInputs(constants=constants, tables=tables)


def versions() -> dict[str, dict[str, int]]:
    """Versões em vigor (parâmetros e tabelas) — para o rasto do cálculo."""
    return {"parameters": platform_parameter_service.snapshot(), "tables": platform_reference_service.snapshot()}
