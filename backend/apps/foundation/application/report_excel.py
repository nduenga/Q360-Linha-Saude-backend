"""Excel (.xlsx) dos relatórios de análise, com os dados do relatório em ecrã.

As quantidades ficam como números, para se poderem somar e filtrar no Excel.
"""
from __future__ import annotations

import datetime
import io
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from apps.foundation.application.report_pdf import (
    COVERAGE_TYPE,
    REPORTS,
    STATUS_LABEL,
    generated_label,
    insurer_name,
    period_label,
)

XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_HEADER_FILL = PatternFill("solid", fgColor="EEEEEE")
_MIN_WIDTH = 14
_MAX_WIDTH = 60


def _status_label(status: str) -> str:
    return STATUS_LABEL.get(status, status)


def _top_products_table(rows: list[dict[str, Any]]) -> tuple[list[str], list[list[Any]]]:
    return (
        ["Produto", "Cotações", "Emitidas"],
        [[row["productName"], row["quoteCount"], row["issuedCount"]] for row in rows],
    )


def _top_coverages_table(rows: list[dict[str, Any]]) -> tuple[list[str], list[list[Any]]]:
    return (
        ["Cobertura", "Tipo", "Planos cotados"],
        [[row["benefitName"], COVERAGE_TYPE.get(row["category"], row["category"]), row["planCount"]] for row in rows],
    )


def _issuance_table(data: dict[str, Any]) -> tuple[list[str], list[list[Any]]]:
    return (
        ["Tipo", "Estado", "Quantidade"],
        [
            *[["Cotação", _status_label(row["status"]), row["count"]] for row in data["quotesByStatus"]],
            *[["Apólice", _status_label(row["status"]), row["count"]] for row in data["policiesByStatus"]],
        ],
    )


_TABLES = {
    "top-products": _top_products_table,
    "top-coverages": _top_coverages_table,
    "issuance": _issuance_table,
}


def _write_row(sheet, row_number: int, values: list[Any]) -> list[Any]:
    cells = []
    for column, value in enumerate(values, start=1):
        cell = sheet.cell(row=row_number, column=column, value=value)
        if isinstance(value, str):
            # Um nome que comece por «=» fica como texto, nunca como fórmula do Excel.
            cell.data_type = "s"
        cells.append(cell)
    return cells


def render_report_excel(slug: str, data: Any, *, tenant_id: Any, date_from: datetime.date | None,
                        date_to: datetime.date | None) -> tuple[bytes, str]:
    title, filename, period_note, _ = REPORTS[slug]
    header, rows = _TABLES[slug](data)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Relatório"

    _write_row(sheet, 1, [title])[0].font = Font(bold=True, size=14)
    _write_row(sheet, 2, ["Seguradora", insurer_name(tenant_id)])
    _write_row(sheet, 3, ["Período", period_label(date_from, date_to)])
    _write_row(sheet, 4, ["Gerado em", generated_label()])
    _write_row(sheet, 5, [period_note])

    header_row = 7
    for cell in _write_row(sheet, header_row, header):
        cell.font = Font(bold=True)
        cell.fill = _HEADER_FILL
    for offset, row in enumerate(rows, start=1):
        _write_row(sheet, header_row + offset, row)
    if rows:
        sheet.auto_filter.ref = f"A{header_row}:{chr(64 + len(header))}{header_row + len(rows)}"
    else:
        _write_row(sheet, header_row + 1, ["Sem dados neste período."])
    sheet.freeze_panes = f"A{header_row + 1}"

    table = [header, *rows]
    for index in range(len(header)):
        width = max(len(str(row[index])) for row in table) + 2
        sheet.column_dimensions[chr(65 + index)].width = min(max(width, _MIN_WIDTH), _MAX_WIDTH)

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue(), f"{filename}.xlsx"
