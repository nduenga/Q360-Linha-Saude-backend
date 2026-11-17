"""Gera os 8 modelos Word de proposta Protteja a partir das propostas originais.

Uso (a partir de backend/):
    ../.venv/bin/python tools/build_protteja_proposal_templates.py \
        ../Protteja_Propostas_Saude_v2 \
        ../Protteja_Propostas_Saude_v2/Q360_PREPARADOS_FINAL_FORMATADOS

Parte de cada proposta original e troca **só os dados da cotação** por marcas
{{variável}}. Tudo o resto fica como a Protteja o desenhou e escreveu: capa,
etiquetas, capital de destaque, âmbito, tabela legal (secção 05), exclusões,
condições comerciais, contactos, cores, fontes e tamanhos. Como cada modelo
serve um só plano, o texto próprio do plano é correto tal como está.

Linhas repetidas pelo sistema (uma linha-modelo por lista, mantendo as faixas
alternadas das duas primeiras): coberturas, pessoas/categorias do prémio e as
linhas «Prémio comercial» e «Desconto», que só aparecem quando há desconto.
As coberturas que o nível não oferece («Não contratada» no original) ficam como
linhas fixas. Depois de gerar, o script valida as marcas e confirma que não
sobra nenhum dado do exemplo.
"""
from __future__ import annotations

import io
import os
import re
import sys
import zipfile
from pathlib import Path

import django

sys.path.insert(0, ".")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
django.setup()

from docx import Document  # noqa: E402

from apps.quote.application import word_template  # noqa: E402

FILES = [
    "Protteja_Saude_Business_Individual.docx", "Protteja_Saude_Business_Grupo.docx",
    "Protteja_Saude_Business_Plus_Individual.docx", "Protteja_Saude_Business_Plus_Grupo.docx",
    "Protteja_Saude_Premium_Individual.docx", "Protteja_Saude_Premium_Grupo.docx",
    "Protteja_Saude_Premium_Plus_Individual.docx", "Protteja_Saude_Premium_Plus_Grupo.docx",
]
REFERENCE = re.compile(r"SIM-SAU-2026-[A-Z]{3}-[IG]\d{3}")
# Dados do exemplo que não podem sobrar num modelo.
SAMPLE_LEFTOVERS = ("João Exemplo", "Maria Exemplo", "Ana Exemplo", "Pedro Exemplo", "Empresa Exemplo",
                    "SIM-SAU-2026", "07.11.2026", "(fictício)", "Documento de exemplo", "valores ilustrativos")


# ------------------------------------------------------------------ texto
def _cells(row):
    seen, out = set(), []
    for cell in row.cells:
        if id(cell._tc) not in seen:
            seen.add(id(cell._tc))
            out.append(cell)
    return out


def _set(paragraph, text: str) -> None:
    """Troca o texto do parágrafo mantendo o formato do primeiro troço com texto."""
    runs = [r for r in paragraph.runs if r.text]
    if not runs:
        paragraph.add_run(text)
        return
    runs[0].text = text
    for run in runs[1:]:
        run.text = ""


def _replace(paragraph, old: str, new: str) -> bool:
    """Substitui dentro do troço que contém o texto (preserva negritos à volta)."""
    for run in paragraph.runs:
        if old in run.text:
            run.text = run.text.replace(old, new)
            return True
    if old in paragraph.text:
        _set(paragraph, paragraph.text.replace(old, new))
        return True
    return False


def _all_paragraphs(document):
    for container in word_template._containers(document):  # noqa: SLF001
        yield from word_template._iter_paragraphs(container)  # noqa: SLF001


def _cell_paragraphs(cell):
    return [p for p in cell.paragraphs if p.text.strip()]


# -------------------------------------------------------------- secções
def _scalars(document, group: bool) -> None:
    for paragraph in _all_paragraphs(document):
        text = paragraph.text.strip()
        if text in ("João Exemplo e Agregado Familiar", "Empresa Exemplo, Lda."):
            _set(paragraph, "{{client.name}}")
        elif REFERENCE.fullmatch(text):
            _set(paragraph, "{{quote.number}}")
        elif text == "07.11.2026 · 30 dias":
            _set(paragraph, "{{quote.date}} · {{quote.validityDays}}")
        elif re.fullmatch(r"[\d.]+ Kz", text) and paragraph._p.getparent() is not None and _is_premium_card(paragraph):
            _set(paragraph, "{{premium.total}}")
        elif re.fullmatch(r"\d+ Pessoas Seguras", text):
            _set(paragraph, "{{insured.count}} Pessoas Seguras")
        elif text.startswith("João Exemplo · NIF") or text.startswith("Empresa Exemplo, Lda. · NIF"):
            _set(paragraph, "{{client.name}} · NIF {{client.nif}}")
        elif text == "Tomador do Seguro, cônjuge e 2 filhos (Agregado Familiar)":
            _set(paragraph, "{{insured.count}} Pessoas Seguras (Agregado Familiar)")
        else:
            _replace(paragraph, "Empresa Exemplo, Lda.", "{{client.name}}")
            if "Simulação de exemplo com valores ilustrativos · " in paragraph.text:
                _replace(paragraph, "Simulação de exemplo com valores ilustrativos · ", "Simulação · ")


def _is_premium_card(paragraph) -> bool:
    """O valor grande do cartão «PRÉMIO TOTAL ANUAL» da capa."""
    cell = paragraph._p.getparent()
    while cell is not None and not cell.tag.endswith("}tc"):
        cell = cell.getparent()
    return cell is not None and "PRÉMIO TOTAL ANUAL" in "".join(t.text or "" for t in cell.iter() if t.tag.endswith("}t"))


def _coverage_table(table) -> None:
    rows = list(table.rows)
    available = [r for r in rows[1:] if "Não contratada" not in r._tr.xpath("string(.)")]
    template_rows = available[:2]
    for row in template_rows:
        cells = _cells(row)
        name_cell = cells[1]
        paragraphs = name_cell.paragraphs
        _set(paragraphs[0], "{{coverage.name}}")
        detail_runs = [r for r in paragraphs[1].runs if r.text.strip()] if len(paragraphs) > 1 else []
        if detail_runs:
            detail_runs[0].text = "{{coverage.category}}  "
            if len(detail_runs) > 1:
                detail_runs[1].text = "{{coverage.details}}"
                for run in detail_runs[2:]:
                    run.text = ""
            else:
                detail_runs[0].text += "{{coverage.details}}"
        for cell, marker in zip(cells[2:6], ("{{coverage.capital}}", "{{coverage.coinsurance}}",
                                               "{{coverage.copay}}", "{{coverage.regime}}")):
            _set(_cell_paragraphs(cell)[0] if _cell_paragraphs(cell) else cell.paragraphs[0], marker)
    for row in rows[1:]:
        if row in template_rows:
            continue
        if row in available:
            row._tr.getparent().remove(row._tr)
    # As linhas «Não contratada» (cobertura que o nível não oferece) ficam fixas.


def _premium_table(table, group: bool) -> None:
    rows = list(table.rows)
    labels = [r._tr.xpath("string(.)") for r in rows]
    total_row = next(r for r, t in zip(rows, labels) if "PRÉMIO TOTAL ANUAL" in t)
    commercial = next(r for r, t in zip(rows, labels) if t.startswith("Prémio comercial"))
    discount = next(r for r, t in zip(rows, labels) if t.startswith("Desconto comercial"))
    data_rows = [r for r in rows[1:] if r not in (total_row, commercial, discount)]
    if group:
        markers = ("{{premiumCategory.relationship}}", "{{premiumCategory.profile}}", "{{premiumCategory.count}}",
                   "{{premiumCategory.perCapita}}", "{{premiumCategory.total}}")
        keep = data_rows[:3]
    else:
        markers = ("{{premiumMember.name}}", "{{premiumMember.relationship}}", "{{premiumMember.age}}",
                   "{{premiumMember.ageBand}}", "{{premiumMember.total}}")
        keep = data_rows[:2]
    for row in keep:
        for cell, marker in zip(_cells(row), markers):
            paragraphs = _cell_paragraphs(cell) or cell.paragraphs
            _set(paragraphs[0], marker)
            for extra in paragraphs[1:]:
                _set(extra, "")
    for row in data_rows[len(keep):]:
        row._tr.getparent().remove(row._tr)
    for row in (commercial, discount):
        cells = _cells(row)
        _set((_cell_paragraphs(cells[0]) or cells[0].paragraphs)[0], "{{premiumBreakdown.label}}")
        _set((_cell_paragraphs(cells[-1]) or cells[-1].paragraphs)[0], "{{premiumBreakdown.amount}}")
    total_cells = _cells(total_row)
    _set((_cell_paragraphs(total_cells[-1]) or total_cells[-1].paragraphs)[0], "{{premium.total}}")


def _monthly_box(table, group: bool) -> None:
    for paragraph in (p for cell in _cells(table.rows[0]) for p in cell.paragraphs):
        text = paragraph.text
        amount = re.search(r"[\d.]+ Kz", text)
        if amount and text.strip().startswith("≈"):
            marker = "{{premium.monthlyPerHolder}}" if group else "{{premium.monthly}}"
            _replace(paragraph, amount.group(0), marker)
        elif re.search(r"para \d+ Pessoas Seguras", text):
            _set(paragraph, re.sub(r"para \d+ Pessoas Seguras", "para {{insured.count}} Pessoas Seguras", text))


def _fractionation(table) -> None:
    for cell in _cells(table.rows[0]):
        paragraphs = _cell_paragraphs(cell)
        for paragraph, marker in zip(paragraphs, ("{{paymentOption.frequency}}", "{{paymentOption.amount}}",
                                                  "{{paymentOption.paymentSummary}}")):
            _set(paragraph, marker)


def _closing_note(table) -> None:
    paragraphs = _cell_paragraphs(table.rows[0].cells[0])
    _set(paragraphs[0], "Proposta comercial")
    _set(paragraphs[1], "Esta proposta é uma simulação e não constitui contrato. A emissão da Apólice depende da "
                        "aceitação da Seguradora e rege-se pelas Condições Gerais, Especiais e Particulares.")
    for extra in paragraphs[2:]:
        _set(extra, "")


def _find(document, needle: str):
    return next(t for t in document.tables if needle in t._tbl.xpath("string(.)"))


# Cores por valor na tabela de coberturas, como no original: «100%» e «Isento» a
# verde-azulado, valores parciais a escuro, coberturas não contratadas a cinzento.
VALUE_COLORS = {"coverage": [
    {"field": "coinsurance", "equals": ["100%"], "color": "0F8A8C", "otherwise": "14272A"},
    {"field": "copay", "equals": ["Isento"], "color": "0F8A8C", "otherwise": "14272A"},
    {"field": "capital", "equals": ["Não contratada"], "color": "9AAFB1", "fields": ["name", "capital"]},
]}


def _add_value_colors(custom_xml: bytes) -> bytes:
    """Acrescenta a propriedade `q360.valueColors` às propriedades personalizadas."""
    import json

    from lxml import etree

    ns = "http://schemas.openxmlformats.org/officeDocument/2006/custom-properties"
    vt = "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"
    root = etree.fromstring(custom_xml)
    for prop in list(root):
        if prop.get("name") == word_template.VALUE_COLORS_PROPERTY:
            root.remove(prop)
    pid = max([int(p.get("pid", "1")) for p in root] + [1]) + 1
    prop = etree.SubElement(root, f"{{{ns}}}property", fmtid="{D5CDD505-2E9C-101B-9397-08002B2CF9AE}",
                            pid=str(pid), name=word_template.VALUE_COLORS_PROPERTY)
    etree.SubElement(prop, f"{{{vt}}}lpwstr").text = json.dumps(VALUE_COLORS, ensure_ascii=False)
    return etree.tostring(root, encoding="UTF-8", xml_declaration=True, standalone=True)


def _headers_and_footers(data: bytes) -> bytes:
    """Referência da cotação no cabeçalho de cada página (fora do corpo) e regras
    de cor por valor nas propriedades do documento."""
    source = zipfile.ZipFile(io.BytesIO(data))
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as target:
        for item in source.infolist():
            content = source.read(item.filename)
            if re.fullmatch(r"word/(header|footer)\d*\.xml", item.filename):
                content = REFERENCE.sub("{{quote.number}}", content.decode("utf-8")).encode("utf-8")
            elif item.filename == "docProps/custom.xml":
                content = _add_value_colors(content)
            target.writestr(item, content)
    return output.getvalue()


def build(source: Path, target: Path) -> None:
    group = "_Grupo" in source.name
    document = Document(str(source))
    _scalars(document, group)
    _coverage_table(_find(document, "COBERTURACAPITAL SEGURO"))
    _premium_table(_find(document, "Prémio comercial"), group)
    _monthly_box(_find(document, "≈"), group)
    _fractionation(_find(document, "fracção única"))
    _closing_note(_find(document, "Documento de exemplo"))
    buffer = io.BytesIO()
    document.save(buffer)
    data = _headers_and_footers(buffer.getvalue())

    report = word_template.validate(data, "QUOTE_PROPOSAL")
    text = "".join(
        zipfile.ZipFile(io.BytesIO(data)).read(name).decode("utf-8")
        for name in zipfile.ZipFile(io.BytesIO(data)).namelist() if name.startswith("word/") and name.endswith(".xml")
    )
    leftovers = [sample for sample in SAMPLE_LEFTOVERS if sample in text]
    if leftovers:
        raise SystemExit(f"{source.name}: sobraram dados do exemplo: {leftovers}")
    target.write_bytes(data)
    print(f"{target.name}: {len(report['placeholders'])} marcas")


if __name__ == "__main__":
    source_dir, target_dir = Path(sys.argv[1]), Path(sys.argv[2])
    target_dir.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        build(source_dir / name, target_dir / name)
