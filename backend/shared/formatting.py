"""Formatação única de valores e datas em texto para pessoas (mensagens do
portal, notificações, documentos). A mesma regra do frontend
(`src/shared/format.ts`): «Kz 15.375,00» — milhares com «.», decimais com
«,», prefixo «Kz» para AOA — e datas dd/mm/aaaa."""
from __future__ import annotations

import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any


def number(value: Any, digits: int = 2) -> str:
    try:
        amount = Decimal(str(value)).quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return str(value)
    text = f"{abs(amount):,.{digits}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"-{text}" if amount < 0 else text


def money(value: Any, currency: str | None = "AOA") -> str:
    if value is None or value == "":
        return "—"
    code = (currency or "AOA").upper()
    text = number(value)
    if text.startswith("-"):
        return f"-{'Kz' if code == 'AOA' else code} {text[1:]}"
    return f"{'Kz' if code == 'AOA' else code} {text}"


def date(value: Any) -> str:
    if value in (None, ""):
        return "—"
    if isinstance(value, datetime.datetime):
        value = value.date()
    if isinstance(value, str):
        try:
            value = datetime.date.fromisoformat(value[:10])
        except ValueError:
            return value
    return value.strftime("%d/%m/%Y")
