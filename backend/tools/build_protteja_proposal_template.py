"""Gera o modelo Word da proposta Protteja a partir de uma proposta de exemplo.

Uso (a partir de backend/):
    ../.venv/bin/python tools/build_protteja_proposal_template.py \
        ../Protteja_Propostas_Saude_v2/Protteja_Saude_Business_Individual.docx \
        apps/quote/seed/protteja_proposta_saude.docx

Mantém o grafismo e o texto contratual da Protteja; troca os dados do exemplo
por marcas {{variável}} que o sistema preenche em cada cotação. As linhas das
tabelas de coberturas e de pessoas seguras ficam com uma linha-modelo, que o
sistema repete por cada cobertura e cada pessoa.
"""
from __future__ import annotations

import sys

import django

sys.path.insert(0, ".")
import os  # noqa: E402

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
django.setup()

from docx import Document  # noqa: E402

from apps.quote.application import word_template  # noqa: E402

# Texto exato de um parágrafo -> texto novo ("" apaga o parágrafo).
EXACT = {
    "O essencial, bem feito. Coberturas base de Hospitalização e Ambulatório com acesso à Rede de Prestadores Protteja em todo o país.": "{{plan.product}}",
    "João Exemplo e Agregado Familiar": "{{client.name}}",
    "SIM-SAU-2026-BUS-I013": "{{quote.number}}",
    "07.11.2026 · 30 dias": "{{quote.date}} · válida até {{quote.validUntil}}",
    "CAPITAL SEGURO · HOSPITALIZAÇÃO": "DOCUMENTO",
    "5.000.000 Kz": "{{document.number}}",
    "por Pessoa Segura e por anuidade": "emitido em {{document.date}}",
    "745.500 Kz": "{{premium.total}}",
    "4 Pessoas Seguras": "{{insured.count}} Pessoas Seguras",
    "Angola": "Conforme o plano",
    "Rede de Prestadores nacional": "Ver Condições Particulares",
    "João Exemplo · NIF 000000000LA000 (fictício)": "{{client.name}} · NIF {{client.nif}}",
    "Tomador do Seguro, cônjuge e 2 filhos (Agregado Familiar)": "{{insured.count}} Pessoas Seguras",
    "Seguro Individual, com inclusão de todo o Agregado Familiar": "{{plan.segment}}",
    "Garantias do Business": "Garantias do plano {{plan.name}}",
    "745.500": "Sem encargo",
    "Kz · fracção única": "fracção única",
    "383.933": "+3%",
    "Kz × 2 fracções · +3%": "2 fracções",
    "195.694": "+5%",
    "Kz × 4 fracções · +5%": "4 fracções",
    "66.474": "+7%",
    "Kz × 12 fracções · +7%": "12 fracções",
    "Prémios em Kwanzas para a anuidade simulada. Os prémios de seguros de saúde estão isentos de Imposto do Selo (Código do Imposto do Selo, art. 6.º, n.º 3, al. o)). O início das garantias depende do pagamento prévio do prémio (Art. 25.º).":
        "Prémios em Kwanzas para a anuidade. O encargo de fraccionamento aplica-se sobre o prémio total anual. Os prémios de seguros de saúde estão isentos de Imposto do Selo (Código do Imposto do Selo, art. 6.º, n.º 3, al. o)). O início das garantias depende do pagamento prévio do prémio (Art. 25.º).",
}
PARTIAL = {"Seguro de Saúde Business, em regime de Seguro Individual": "Seguro de Saúde {{plan.name}}, em regime de {{plan.segment}}"}


def _set(paragraph, text: str) -> None:
    runs = paragraph.runs
    if not runs:
        paragraph.add_run(text)
        return
    runs[0].text = text
    for run in runs[1:]:
        run.text = ""


def _unique_cells(row):
    seen = set()
    for cell in row.cells:
        if id(cell._tc) not in seen:
            seen.add(id(cell._tc))
            yield cell


def _cell(cell, text: str) -> None:
    paragraphs = cell.paragraphs
    _set(paragraphs[0], text)
    for extra in paragraphs[1:]:
        extra._p.getparent().remove(extra._p)


def _drop_table(table) -> None:
    table._tbl.getparent().remove(table._tbl)


def build(source: str, target: str) -> None:
    document = Document(source)
    # O nome do plano no cabeçalho; a tabela «Posicionamento na gama» mantém os 4 nomes.
    for paragraph in word_template._iter_paragraphs(document.tables[0]._cells[0]):  # noqa: SLF001
        if paragraph.text.strip() == "Business":
            _set(paragraph, "{{plan.name}}")
    for container in word_template._containers(document):  # noqa: SLF001
        for paragraph in word_template._iter_paragraphs(container):  # noqa: SLF001
            text = paragraph.text.strip()
            if text in EXACT:
                _set(paragraph, EXACT[text])
                continue
            for old, new in PARTIAL.items():
                if old in paragraph.text:
                    _set(paragraph, paragraph.text.replace(old, new))

    tables = document.tables
    coverage, insured, monthly, sample = tables[4], tables[5], tables[6], tables[14]
    header = list(_unique_cells(coverage.rows[0]))
    for cell, label in zip(header[1:], ("COBERTURA", "CAPITAIS E LIMITES", "PARTICIPAÇÃO", "CARÊNCIA", "AUTORIZAÇÃO PRÉVIA")):
        _cell(cell, label)
    template_row = list(_unique_cells(coverage.rows[1]))
    for cell, marker in zip(template_row[1:], ("{{coverage.name}}", "{{coverage.limits}}", "{{coverage.participation}}",
                                                "{{coverage.waiting}}", "{{coverage.priorApproval}}")):
        _cell(cell, marker)
    for row in list(coverage.rows)[2:]:
        row._tr.getparent().remove(row._tr)

    header = list(_unique_cells(insured.rows[0]))
    for cell, label in zip(header, ("PESSOA SEGURA", "QUALIDADE", "IDADE", "ESTADO", "")):
        _cell(cell, label)
    person = list(_unique_cells(insured.rows[1]))
    for cell, marker in zip(person, ("{{insured.name}}", "{{insured.relationship}}", "{{insured.age}}", "{{insured.status}}", "")):
        _cell(cell, marker)
    rows = list(insured.rows)
    total = list(_unique_cells(rows[-1]))
    _cell(total[-1], "{{premium.total}}")
    for row in rows[2:-1]:  # restantes pessoas do exemplo, prémio comercial e desconto
        row._tr.getparent().remove(row._tr)

    _drop_table(monthly)   # «≈ 62.125 Kz por mês»: valor do exemplo
    _drop_table(sample)    # «Documento de exemplo … fictícios»
    document.save(target)


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2])
    with open(sys.argv[2], "rb") as handle:
        report = word_template.validate(handle.read(), "QUOTE_PROPOSAL")
    print(report)
