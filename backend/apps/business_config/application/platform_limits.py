"""Tetos que o fornecedor impõe à configuração de negócio dos tenants
(parâmetros `LIMIT`/`LEGAL` da camada geral).

São verificados ao submeter e ao aprovar uma configuração: assim um teto
baixado pelo fornecedor entre a submissão e a aprovação também é respeitado.
Uma versão já publicada continua a calcular; a próxima versão terá de cumprir
o teto em vigor."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from apps.business_config.domain.errors import InvalidConfiguration
from apps.foundation.application import system_parameter_service

COMMISSION_LIMIT = "limits.max_acquisition_commission_pct"


def _decimal(raw: Any) -> Decimal | None:
    try:
        return Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _check_actuarial_model(value: dict[str, Any]) -> None:
    cap_pct = _decimal(system_parameter_service.get_value(COMMISSION_LIMIT))
    if cap_pct is None or cap_pct >= 100:
        return
    loadings = ((value.get("assumptions") or {}).get("loadings") or {})
    for segment, row in sorted(loadings.items()):
        commission = _decimal((row or {}).get("acquisition_commission"))
        if commission is not None and commission * 100 > cap_pct:
            raise InvalidConfiguration(
                f"Comissão de mediação de {format(commission * 100, 'f')} % no segmento {segment} acima do máximo "
                f"de {format(cap_pct, 'f')} % definido pelo fornecedor ({COMMISSION_LIMIT})."
            )


_CHECKS = {"pricing.actuarial_model": _check_actuarial_model}


def check_platform_limits(config_key: str, value: Any) -> None:
    check = _CHECKS.get(config_key)
    if check is not None and isinstance(value, dict):
        check(value)
