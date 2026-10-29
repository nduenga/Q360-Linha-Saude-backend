"""As importações (membros, coberturas, sinistros) só aceitam o modelo Excel
.xlsx. Os testes continuam a escrever os dados como texto CSV, que é mais
legível; `csv_to_xlsx` converte-o num livro Excel com uma folha."""
from __future__ import annotations

import csv
import io

import openpyxl


def csv_to_xlsx(text: str) -> bytes:
    delimiter = ";" if text.splitlines() and text.splitlines()[0].count(";") > text.splitlines()[0].count(",") else ","
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    for row in csv.reader(io.StringIO(text), delimiter=delimiter):
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
