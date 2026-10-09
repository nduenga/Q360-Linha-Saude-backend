"""Agravamentos e descontos comerciais aplicados a uma cotação (R3).

Parsing puro de `context.adjustments` — a lista que o serviço de cotações
constrói a partir das linhas `QuoteAdjustment` ACTIVE (ou de uma simulação
"e se..."). Quatro tipos, como um subscritor fala de preço:

  SURCHARGE_PERCENT  agravamento em %   -> valor * (1 + v/100)
  DISCOUNT_PERCENT   desconto em %      -> valor * (1 - v/100)   (v < 100)
  SURCHARGE_AMOUNT   agravamento fixo   -> valor + v
  DISCOUNT_AMOUNT    desconto fixo      -> valor - v

`scope=MEMBER` aplica-se a uma pessoa segura; `scope=QUOTE` a todas
(percentagens na linha de cada membro, valores fixos uma vez no total).
"""
from __future__ import annotations

import dataclasses
from decimal import Decimal, InvalidOperation
from typing import Any

from apps.pricing.domain.errors import ReferencedEntityNotFoundError

PERCENT_KINDS = ("SURCHARGE_PERCENT", "DISCOUNT_PERCENT")
AMOUNT_KINDS = ("SURCHARGE_AMOUNT", "DISCOUNT_AMOUNT")
KINDS = (*PERCENT_KINDS, *AMOUNT_KINDS)
SCOPES = ("QUOTE", "MEMBER")


@dataclasses.dataclass(frozen=True, slots=True)
class CommercialAdjustment:
    id: str
    kind: str
    value: Decimal
    scope: str
    member_id: str | None
    reason: str | None

    @property
    def is_percent(self) -> bool:
        return self.kind in PERCENT_KINDS

    @property
    def is_surcharge(self) -> bool:
        return self.kind.startswith("SURCHARGE")

    @property
    def code(self) -> str:
        return f"ADJ_{self.kind}_{self.id.replace('-', '')[:8].upper()}"

    def factor(self) -> Decimal:
        pct = self.value / Decimal("100")
        return Decimal("1") + pct if self.is_surcharge else Decimal("1") - pct

    def signed_amount(self) -> Decimal:
        return self.value if self.is_surcharge else -self.value


def parse_commercial_adjustments(raw: Any) -> list[CommercialAdjustment]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ReferencedEntityNotFoundError("context.adjustments tem de ser uma lista")
    parsed: list[CommercialAdjustment] = []
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ReferencedEntityNotFoundError(f"context.adjustments[{idx}] tem de ser um objeto")
        kind = item.get("kind")
        scope = item.get("scope", "QUOTE")
        if kind not in KINDS:
            raise ReferencedEntityNotFoundError(f"context.adjustments[{idx}].kind tem de ser um de {list(KINDS)}")
        if scope not in SCOPES:
            raise ReferencedEntityNotFoundError(f"context.adjustments[{idx}].scope tem de ser um de {list(SCOPES)}")
        try:
            value = Decimal(str(item.get("value")))
        except InvalidOperation as exc:
            raise ReferencedEntityNotFoundError(f"context.adjustments[{idx}].value não é um decimal") from exc
        if not value.is_finite() or value <= 0:
            raise ReferencedEntityNotFoundError(f"context.adjustments[{idx}].value tem de ser maior que zero")
        if kind == "DISCOUNT_PERCENT" and value >= 100:
            raise ReferencedEntityNotFoundError(f"context.adjustments[{idx}]: um desconto percentual tem de ser inferior a 100")
        member_id = item.get("memberId")
        if (scope == "MEMBER") != bool(member_id):
            raise ReferencedEntityNotFoundError(
                f"context.adjustments[{idx}]: memberId é obrigatório exatamente quando o âmbito (scope) é MEMBER"
            )
        parsed.append(
            CommercialAdjustment(
                id=str(item.get("id") or f"adhoc-{idx}"),
                kind=kind,
                value=value,
                scope=scope,
                member_id=str(member_id) if member_id else None,
                reason=item.get("reason"),
            )
        )
    return parsed
