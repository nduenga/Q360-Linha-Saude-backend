"""Restore insurer-approved layout details in the eight prepared DOCX models.

The source model is the visual authority.  This script only restores the
cover's two-line metadata cells, the original guarantees-table headings,
right-aligned running header and a page break before each numbered section.
All other package members remain untouched.
"""
from __future__ import annotations

import copy
import io
import re
import zipfile
from pathlib import Path

from lxml import etree


ROOT = Path(__file__).resolve().parents[1] / "Protteja_Propostas_Saude_v2"
PREPARED = ROOT / "Q360_PREPARADOS_FORMATADOS"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}
QN = lambda name: f"{{{W}}}{name}"


def _text(element) -> str:
    return "".join(node.text or "" for node in element.xpath(".//w:t", namespaces=NS))


def _direct_paragraphs(cell):
    return cell.xpath("./w:p", namespaces=NS)


def _cell_with(cell_text: str, root):
    for cell in root.xpath(".//w:tc", namespaces=NS):
        direct_texts = [_text(paragraph).strip() for paragraph in _direct_paragraphs(cell)]
        if any(text == cell_text or text.startswith(f"{cell_text} ") for text in direct_texts):
            return cell
    raise ValueError(f"Cell not found: {cell_text}")


def _set_paragraph_text(paragraph, value: str) -> None:
    nodes = paragraph.xpath(".//w:t", namespaces=NS)
    if not nodes:
        run = etree.SubElement(paragraph, QN("r"))
        nodes = [etree.SubElement(run, QN("t"))]
    nodes[0].text = value
    for node in nodes[1:]:
        node.text = ""


def _replace_cover_cell(prepared_root, original_root, *, label: str, value: str) -> None:
    target = _cell_with(label, prepared_root)
    source = _cell_with(label, original_root)
    source_paragraphs = _direct_paragraphs(source)
    if len(source_paragraphs) < 2:
        raise ValueError(f"Original cell has no separate value line: {label}")
    for paragraph in _direct_paragraphs(target):
        target.remove(paragraph)
    for paragraph in source_paragraphs[:2]:
        target.append(copy.deepcopy(paragraph))
    _set_paragraph_text(_direct_paragraphs(target)[1], value)


def _restore_guarantee_table(root) -> None:
    for table in root.xpath(".//w:tbl", namespaces=NS):
        rows = table.xpath("./w:tr", namespaces=NS)
        if len(rows) < 2 or "COBERTURA" not in _text(rows[0]):
            continue
        header_cells = rows[0].xpath("./w:tc", namespaces=NS)
        item_cells = rows[1].xpath("./w:tc", namespaces=NS)
        if len(header_cells) != 6 or len(item_cells) != 6:
            continue
        headers = ("", "COBERTURA", "CAPITAL SEGURO", "COMPARTICIPAÇÃO", "CO-PAGAMENTO", "REGIME")
        markers = ("", "{{coverage.name}}", "{{coverage.limits}}", "{{coverage.networkCoinsurancePct}}", "{{coverage.networkCopay}}", "{{coverage.regime}}")
        for cell, value in zip(header_cells, headers):
            _set_paragraph_text(_direct_paragraphs(cell)[0], value)
        for cell, value in zip(item_cells, markers):
            _set_paragraph_text(_direct_paragraphs(cell)[0], value)
        return
    raise ValueError("Guarantee table not found")


def _set_page_breaks(root) -> None:
    for paragraph in root.xpath(".//w:p", namespaces=NS):
        text = _text(paragraph).strip()
        if not re.match(r"^0[2-9]\s+", text):
            continue
        properties = paragraph.find(QN("pPr"))
        if properties is None:
            properties = etree.Element(QN("pPr"))
            paragraph.insert(0, properties)
        if properties.find(QN("pageBreakBefore")) is None:
            properties.append(etree.Element(QN("pageBreakBefore")))


def _right_align_header(xml: bytes) -> bytes:
    root = etree.fromstring(xml)
    for paragraph in root.xpath(".//w:p", namespaces=NS):
        if "{{plan.name}}" not in _text(paragraph):
            continue
        properties = paragraph.find(QN("pPr"))
        if properties is None:
            properties = etree.Element(QN("pPr"))
            paragraph.insert(0, properties)
        alignment = properties.find(QN("jc"))
        if alignment is None:
            alignment = etree.SubElement(properties, QN("jc"))
        alignment.set(QN("val"), "right")
    return etree.tostring(root, encoding="UTF-8", xml_declaration=True, standalone=True)


def _rewrite_docx(source: Path) -> None:
    original = ROOT / source.name
    if not original.is_file():
        raise FileNotFoundError(original)
    output = io.BytesIO()
    with zipfile.ZipFile(original) as approved, zipfile.ZipFile(source) as prepared, zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as target:
        approved_root = etree.fromstring(approved.read("word/document.xml"))
        for entry in prepared.infolist():
            data = prepared.read(entry.filename)
            if entry.filename == "word/document.xml":
                root = etree.fromstring(data)
                _replace_cover_cell(root, approved_root, label="TOMADOR DO SEGURO", value="{{client.name}}")
                _replace_cover_cell(root, approved_root, label="DATA", value="{{quote.date}} - {{quote.validityDays}}")
                _restore_guarantee_table(root)
                _set_page_breaks(root)
                data = etree.tostring(root, encoding="UTF-8", xml_declaration=True, standalone=True)
            elif entry.filename.startswith("word/header") and entry.filename.endswith(".xml"):
                data = _right_align_header(data)
            target.writestr(entry, data)
    source.write_bytes(output.getvalue())


def main() -> None:
    for path in sorted(PREPARED.glob("Protteja_*.docx")):
        _rewrite_docx(path)
        print(f"Updated {path.name}")


if __name__ == "__main__":
    main()
