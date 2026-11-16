"""Proposal PDF uses Chromium; DOCX remains an independent Word output."""
from __future__ import annotations

from pathlib import Path

from apps.quote.application import chromium_converter, docx_to_pdf, office_converter, proposal_layout, proposal_service, protteja_html
from apps.quote.domain.proposal_template import DEFAULT_TEMPLATE

FAKE_PDF = b"%PDF-1.7 chromium proposal"


class _Template:
    def __init__(self, word: bytes):
        import json

        self.storage_ref = json.dumps(DEFAULT_TEMPLATE)
        self.word_key = "template.docx"
        self.document_type = "QUOTE_PROPOSAL"
        self.settings_json = {}
        self._word = word


def word_template(monkeypatch):
    from apps.quote.application import template_files

    data = (Path(__file__).resolve().parents[2] / "apps/quote/seed/protteja_proposta_saude.docx").read_bytes()
    monkeypatch.setattr(template_files, "read_word", lambda template: template._word)
    return _Template(data)


def test_quote_pdf_uses_protteja_html_and_chromium(monkeypatch):
    captured = {}

    def convert(data):
        captured["html"] = data
        return FAKE_PDF

    monkeypatch.setattr(chromium_converter, "html_to_pdf", convert)
    monkeypatch.setattr(office_converter, "docx_to_pdf", lambda _data: (_ for _ in ()).throw(AssertionError("LibreOffice não deve converter propostas")))
    data, content_type = proposal_service._render(  # noqa: SLF001
        proposal_service.sample_content(), word_template(monkeypatch), "PDF", document_number="DOC-1"
    )

    assert (data, content_type) == (FAKE_PDF, "application/pdf")
    html = captured["html"].decode("utf-8")
    assert "brand-banner" in html and "protteja-header.png" not in html
    assert "data:image/png;base64," in html
    assert "Pessoas seguras" in html


def test_quote_docx_still_uses_the_uploaded_word_template(monkeypatch):
    template = word_template(monkeypatch)
    data, content_type = proposal_service._render(  # noqa: SLF001
        proposal_service.sample_content(), template, "DOCX", document_number="DOC-1"
    )
    assert content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    assert data.startswith(b"PK")


def test_html_handles_long_households_and_escapes_customer_text():
    content = proposal_service.sample_content()
    marker = "Cliente " + ("Agregado familiar extenso " * 8) + "<script>alert(1)</script>"
    member = dict(content["population"][0])
    content["population"] = [dict(member, name=f"Pessoa segura {index}: {marker}") for index in range(30)]
    content["client"]["name"] = marker
    variables = proposal_layout.variables_for(
        content, document_number="DOC-1", generated_on=content["meta"]["generatedOn"]
    )
    blocks = proposal_layout.build_blocks(content, DEFAULT_TEMPLATE, variables)
    rendered = protteja_html.render(blocks, title="Proposta DOC-1").decode("utf-8")

    assert marker.replace("<script>", "&lt;script&gt;").replace("</script>", "&lt;/script&gt;") in rendered
    assert "<script>" not in rendered
    assert rendered.count("Pessoa segura ") >= 30
    assert "break-inside: avoid" in rendered and "@page { size: A4" in rendered
    assert rendered.count("data:image/png;base64,") == 3


def test_missing_libreoffice_is_reported_not_raised(monkeypatch):
    monkeypatch.setattr(docx_to_pdf, "soffice_path", lambda: None)
    assert docx_to_pdf.convert(b"PK qualquer coisa") is None
