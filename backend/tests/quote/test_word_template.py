from __future__ import annotations

import io
import zipfile

from docx import Document
from docx.shared import Pt, RGBColor

from apps.quote.application.word_template import fill


def _template() -> bytes:
    document = Document()
    document.sections[0].page_width = Pt(595)
    document.sections[0].page_height = Pt(842)

    paragraph = document.add_paragraph()
    paragraph.alignment = 1
    paragraph.add_run("Proposta para ")
    first = paragraph.add_run("{{client.")
    first.font.name = "Arial"
    first.font.size = Pt(18)
    first.font.bold = True
    first.font.color.rgb = RGBColor(20, 60, 120)
    second = paragraph.add_run("name}}")
    second.font.name = "Arial"
    second.font.size = Pt(18)
    second.font.bold = True
    second.font.color.rgb = RGBColor(20, 60, 120)
    paragraph.add_run(" — válida.")

    header = document.sections[0].header.paragraphs[0]
    header.add_run("Documento ")
    header.add_run("{{document.number}}")

    table = document.add_table(rows=2, cols=1)
    cell = table.rows[1].cells[0]
    run = cell.paragraphs[0].add_run("{{insured.name}}")
    run.font.name = "Arial"
    run.font.size = Pt(12)
    run.font.italic = True

    output = io.BytesIO()
    document.save(output)
    return output.getvalue()


def test_fill_preserves_template_format_and_repeats_styled_rows():
    source = _template()
    result = fill(
        source,
        scalars={"client.name": "Maria Exemplo", "document.number": "PROP-001"},
        groups={"insured": [{"name": "Maria"}, {"name": "João"}]},
    )
    document = Document(io.BytesIO(result))

    paragraph = document.paragraphs[0]
    assert paragraph.text == "Proposta para Maria Exemplo — válida."
    assert paragraph.alignment == 1
    variable = next(run for run in paragraph.runs if "Maria Exemplo" in run.text)
    assert variable.font.name == "Arial"
    assert variable.font.size == Pt(18)
    assert variable.bold is True
    assert variable.font.color.rgb == RGBColor(20, 60, 120)

    assert document.sections[0].header.paragraphs[0].text == "Documento PROP-001"
    assert [row.cells[0].text for row in document.tables[0].rows] == ["", "Maria", "João"]
    for row in document.tables[0].rows[1:]:
        run = row.cells[0].paragraphs[0].runs[0]
        assert run.font.name == "Arial"
        assert run.font.size == Pt(12)
        assert run.italic is True

    with zipfile.ZipFile(io.BytesIO(source)) as original, zipfile.ZipFile(io.BytesIO(result)) as generated:
        for name in original.namelist():
            if name not in {"word/document.xml", "word/header1.xml"}:
                assert original.read(name) == generated.read(name), name


def test_fill_uses_a_valid_dash_for_missing_values():
    result = fill(_template(), scalars={}, groups={})
    document = Document(io.BytesIO(result))

    assert "—" in document.paragraphs[0].text
    assert "â€”" not in document.paragraphs[0].text
    assert "{{client.name}}" not in document.paragraphs[0].text
