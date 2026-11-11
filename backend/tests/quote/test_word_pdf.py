"""O PDF de uma proposta com modelo Word sai do próprio Word (convertido pelo
LibreOffice); sem LibreOffice, mantém-se o layout da plataforma."""
from __future__ import annotations

import pytest

from apps.quote.application import docx_to_pdf, proposal_service
from apps.quote.domain.proposal_template import DEFAULT_TEMPLATE

FAKE_PDF = b"%PDF-1.7 convertido do Word"


class _Template:
    """Modelo com Word, só com o que o `_render` lê."""

    def __init__(self, word: bytes):
        import json

        self.storage_ref = json.dumps(DEFAULT_TEMPLATE)
        self.word_key = "template.docx"
        self.settings_json = {}
        self._word = word


@pytest.fixture
def word_template(monkeypatch):
    from pathlib import Path

    from apps.quote.application import template_files

    data = (Path(__file__).resolve().parents[2] / "apps/quote/seed/protteja_proposta_saude.docx").read_bytes()
    monkeypatch.setattr(template_files, "read_word", lambda template: template._word)
    monkeypatch.setattr(template_files, "layout_for", lambda template: None)
    monkeypatch.setattr(template_files, "read_letterhead", lambda template: None)
    return _Template(data)


def test_pdf_comes_from_the_word_template_when_libreoffice_exists(monkeypatch, word_template):
    received = {}

    def convert(data):
        received["docx"] = data
        return FAKE_PDF

    monkeypatch.setattr(docx_to_pdf, "convert", convert)
    data, content_type = proposal_service._render(  # noqa: SLF001
        proposal_service.sample_content(), word_template, "PDF", document_number="DOC-1"
    )
    assert (data, content_type) == (FAKE_PDF, "application/pdf")
    assert received["docx"][:2] == b"PK", "o que se converte é o Word preenchido"


def test_pdf_falls_back_to_the_platform_layout_without_libreoffice(monkeypatch, word_template):
    monkeypatch.setattr(docx_to_pdf, "convert", lambda data: None)
    data, content_type = proposal_service._render(  # noqa: SLF001
        proposal_service.sample_content(), word_template, "PDF", document_number="DOC-1"
    )
    assert content_type == "application/pdf" and data.startswith(b"%PDF") and data != FAKE_PDF


def test_missing_libreoffice_is_reported_not_raised(monkeypatch):
    monkeypatch.setattr(docx_to_pdf, "soffice_path", lambda: None)
    assert docx_to_pdf.convert(b"PK qualquer coisa") is None


@pytest.mark.skipif(not docx_to_pdf.is_available(), reason="LibreOffice não instalado nesta máquina")
def test_real_conversion_of_the_protteja_template():
    from pathlib import Path

    data = (Path(__file__).resolve().parents[2] / "apps/quote/seed/protteja_proposta_saude.docx").read_bytes()
    pdf = docx_to_pdf.convert(data)
    assert pdf is not None and pdf.startswith(b"%PDF")
