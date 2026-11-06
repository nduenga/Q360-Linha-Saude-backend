"""Reconciliação de extrato bancário com as prestações por pagar.

Duas fases: `preview` lê o ficheiro e classifica cada linha sem gravar nada;
`commit` regista as linhas confirmadas pelas mesmas regras do registo manual,
incluindo a recusa de referências repetidas. Cada linha é independente.
"""
from __future__ import annotations

import csv
import datetime
import io
import re
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.foundation.domain.problem import DomainProblem
from apps.policy.application import issuance_service
from apps.policy.infrastructure.models import Policy, PremiumInstallment

MATCHED = "MATCHED"
MATCHED_MULTIPLE = "MATCHED_MULTIPLE"
ALREADY_REGISTERED = "ALREADY_REGISTERED"
DUPLICATE_IN_FILE = "DUPLICATE_IN_FILE"
NO_POLICY = "NO_POLICY"
AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
BLOCKED = "BLOCKED"
INVALID = "INVALID"
MAX_LINES = 5000
PAYMENT_METHOD = "TRANSFERENCIA"

_HEADERS = {
    "data": "date", "data valor": "date", "data movimento": "date", "date": "date",
    "valor": "amount", "montante": "amount", "crédito": "amount", "credito": "amount", "amount": "amount",
    "referência": "reference", "referencia": "reference", "reference": "reference", "ref": "reference",
    "descrição": "description", "descricao": "description", "descritivo": "description", "description": "description",
}
_TOKEN = re.compile(r"[A-Z0-9][A-Z0-9/_-]*")


class StatementFileError(DomainProblem):
    http_status = 400
    problem_code = "VALIDATION-400"


def _normalise_rows(rows: list[list[Any]]) -> list[dict[str, Any]]:
    if not rows:
        raise StatementFileError("O ficheiro não tem linhas.")
    header = [_HEADERS.get(str(cell or "").strip().casefold()) for cell in rows[0]]
    missing = {"date", "amount", "reference"} - set(header)
    if missing:
        raise StatementFileError("O ficheiro tem de ter as colunas Data, Valor e Referência.")
    parsed = []
    for raw in rows[1:]:
        if all(cell is None or str(cell).strip() == "" for cell in raw):
            continue
        parsed.append({name: cell for name, cell in zip(header, raw) if name})
    if len(parsed) > MAX_LINES:
        raise StatementFileError(f"O ficheiro tem mais de {MAX_LINES} linhas; divida-o em ficheiros mais pequenos.")
    return parsed


def _read_rows(filename: str, content: bytes) -> list[dict[str, Any]]:
    lowered = (filename or "").lower()
    if lowered.endswith(".xlsx"):
        import openpyxl

        try:
            workbook = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
            rows = [list(row) for row in workbook.worksheets[0].iter_rows(values_only=True)]
        except Exception as exc:  # openpyxl levanta vários tipos para um ficheiro corrompido
            raise StatementFileError("Não foi possível ler este ficheiro Excel.") from exc
        return _normalise_rows(rows)
    if lowered.endswith(".csv"):
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = content.decode("latin-1")
        first_line = text.splitlines()[0] if text.splitlines() else ""
        delimiter = ";" if first_line.count(";") >= first_line.count(",") else ","
        return _normalise_rows([list(row) for row in csv.reader(io.StringIO(text), delimiter=delimiter)])
    raise StatementFileError("Carregue um ficheiro .xlsx ou .csv.")


def _parse_amount(value: Any) -> Decimal | None:
    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        return Decimal(str(value))
    text = re.sub(r"[^\d,.\-]", "", str(value or ""))
    if not text:
        return None
    if "," in text and "." in text:
        decimal_mark = "," if text.rfind(",") > text.rfind(".") else "."
        text = text.replace("." if decimal_mark == "," else ",", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    elif text.count(".") > 1:
        text = text.replace(".", "")
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _parse_date(value: Any) -> datetime.date | None:
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    text = str(value or "").strip()[:10]
    for pattern in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    return None


def _open_policies() -> dict[str, Policy]:
    ids = PremiumInstallment.objects.filter(status__in=("DUE", "OVERDUE")).values("policy_id")
    return {p.policy_number: p for p in Policy.objects.filter(id__in=ids).exclude(policy_number__isnull=True)}


def _find_policy_number(texts: list[str], known: dict[str, Any]) -> str | None:
    for text in texts:
        for token in _TOKEN.findall(text.upper()):
            if token in known:
                return token
    return None


def _classify(
    raw: dict[str, Any], *, number: int, open_policies: dict, known_numbers: set, seen: set, claimed: set,
    options_cache: dict, today,
) -> dict[str, Any]:
    reference = " ".join(str(raw.get("reference") or "").split())
    description = str(raw.get("description") or "")
    amount = _parse_amount(raw.get("amount"))
    paid_on = _parse_date(raw.get("date"))
    line: dict[str, Any] = {
        "line": number, "reference": reference or None, "description": description or None,
        "amount": str(issuance_service._round2(amount)) if amount is not None else None,
        "paidOn": paid_on.isoformat() if paid_on else None,
        "policyId": None, "policyNumber": None, "installmentNos": [], "expectedAmount": None, "rowVersion": None,
    }

    def result(status: str, message: str) -> dict[str, Any]:
        return {**line, "status": status, "message": message}

    if not reference or amount is None or amount <= 0 or paid_on is None or paid_on > today:
        return result(INVALID, "Confirme a data, o valor e a referência desta linha.")
    key = issuance_service.payment_reference_key(reference)
    if key in seen:
        return result(DUPLICATE_IN_FILE, "Esta referência já aparece noutra linha do ficheiro.")
    seen.add(key)
    owner = issuance_service.payment_reference_owner(reference)
    if owner is not None:
        return result(
            ALREADY_REGISTERED,
            f"Esta referência já foi registada na prestação {owner.installment_no} da apólice {owner.policy.policy_number}.",
        )
    number_found = _find_policy_number([reference, description], open_policies)
    if number_found is None:
        closed = _find_policy_number([reference, description], dict.fromkeys(known_numbers))
        message = f"A apólice {closed} não tem prestações por pagar." if closed else "Não foi encontrado número de apólice nesta linha."
        return result(NO_POLICY, message)
    policy = open_policies[number_found]
    line.update(policyId=str(policy.id), policyNumber=number_found, rowVersion=policy.row_version)
    if policy.id not in options_cache:
        options_cache[policy.id] = issuance_service.payment_options(policy, today=today)
    options = options_cache[policy.id]
    if options["blockedReason"]:
        return result(BLOCKED, options["blockedReason"])
    line["expectedAmount"] = options["options"][0]["total"]
    received = str(issuance_service._round2(amount))
    match = next((o for o in options["options"] if o["total"] == received), None)
    if match is None:
        return result(AMOUNT_MISMATCH, "O valor recebido não corresponde a prestações completas; trate este recebimento à mão.")
    if policy.id in claimed:
        return result(BLOCKED, "Outra linha do ficheiro já paga prestações desta apólice; registe esta depois de confirmar a primeira.")
    claimed.add(policy.id)
    line["installmentNos"] = match["installmentNos"]
    if match["count"] > 1:
        return result(
            MATCHED_MULTIPLE,
            f"Este valor paga {match['count']} prestações seguidas ({', '.join(map(str, match['installmentNos']))}); confirme se foi essa a intenção do cliente.",
        )
    return result(MATCHED, options.get("effect") or "Pronta a registar.")


def preview(*, filename: str, content: bytes) -> dict[str, Any]:
    rows = _read_rows(filename, content)
    today = timezone.localdate()
    open_policies = _open_policies()
    known = set(Policy.objects.exclude(policy_number__isnull=True).values_list("policy_number", flat=True))
    seen: set[str] = set()
    claimed: set = set()
    options_cache: dict = {}
    lines = [
        _classify(
            raw, number=index, open_policies=open_policies, known_numbers=known, seen=seen, claimed=claimed,
            options_cache=options_cache, today=today,
        )
        for index, raw in enumerate(rows, start=2)
    ]
    counts: dict[str, int] = {}
    for line in lines:
        counts[line["status"]] = counts.get(line["status"], 0) + 1
    return {
        "totalLines": len(lines),
        "matchedLines": counts.get(MATCHED, 0) + counts.get(MATCHED_MULTIPLE, 0),
        "matchedAmount": str(sum((Decimal(l["amount"]) for l in lines if l["status"] in (MATCHED, MATCHED_MULTIPLE)), Decimal("0.00"))),
        "counts": counts,
        "lines": lines,
    }


def commit(*, lines: list[dict[str, Any]], correlation_id: str | None) -> dict[str, Any]:
    """Regista cada linha confirmada; uma recusa não desfaz as outras."""
    registered: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    for line in lines:
        outcome = {"line": line["line"], "reference": line["paymentReference"]}
        policy = Policy.objects.filter(id=line["policyId"]).first()
        if policy is None:
            failed.append({**outcome, "reason": "Esta apólice não existe."})
            continue
        paid_at = timezone.make_aware(datetime.datetime.combine(line["paidOn"], datetime.time(12)))
        try:
            with transaction.atomic():
                issuance_service.allocate_payment(
                    policy=policy, installment_nos=line["installmentNos"], amount=line["amount"], paid_at=paid_at,
                    payment_reference=line["paymentReference"], payment_method=PAYMENT_METHOD,
                    row_version=policy.row_version, correlation_id=correlation_id,
                )
        except DomainProblem as exc:
            failed.append({**outcome, "reason": str(exc)})
            continue
        registered.append({**outcome, "policyNumber": policy.policy_number, "installmentNos": line["installmentNos"]})
    return {"registered": registered, "failed": failed}
