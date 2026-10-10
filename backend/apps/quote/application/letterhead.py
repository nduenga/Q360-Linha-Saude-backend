"""Papel timbrado em PDF (opção A): o GTE carrega um PDF com o aspeto da
seguradora (logótipo, cabeçalho, rodapé, fundo) e o sistema escreve o
conteúdo do documento por cima.

A página 1 do papel serve de fundo à 1.ª página do documento; a página 2 (se
existir) serve de fundo às seguintes, senão repete-se a página 1.
"""
from __future__ import annotations

import io

from apps.quote.domain.proposal_template import InvalidTemplateError

DEFAULT_MARGINS_CM = {"left": 2.0, "right": 2.0, "top": 3.5, "bottom": 3.0}
_MIN_CM, _MAX_CM = 0.5, 10.0


def inspect(pdf_bytes: bytes) -> dict:
    """Valida o PDF e devolve o tamanho da página e o número de páginas."""
    from pypdf import PdfReader
    from pypdf.errors import PyPdfError

    if not pdf_bytes.startswith(b"%PDF"):
        raise InvalidTemplateError("O ficheiro não é um PDF válido")
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        if reader.is_encrypted:
            raise InvalidTemplateError("O PDF está protegido por palavra-passe: carregue uma versão sem proteção")
        pages = len(reader.pages)
        if pages < 1:
            raise InvalidTemplateError("O PDF não tem páginas")
        box = reader.pages[0].mediabox
        return {"pages": pages, "pageWidthPt": float(box.width), "pageHeightPt": float(box.height)}
    except InvalidTemplateError:
        raise
    except (PyPdfError, ValueError, OSError) as exc:
        raise InvalidTemplateError("Não foi possível ler o PDF; confirme que o ficheiro não está danificado") from exc


def margins_from_form(raw: dict) -> dict:
    """Margens em cm vindas do formulário (as omitidas ficam por omissão)."""
    margins = dict(DEFAULT_MARGINS_CM)
    for key in margins:
        value = raw.get(key)
        if value in (None, ""):
            continue
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise InvalidTemplateError(f"A margem '{key}' tem de ser um número em centímetros") from exc
        if not (_MIN_CM <= number <= _MAX_CM):
            raise InvalidTemplateError(f"A margem '{key}' tem de estar entre {_MIN_CM} e {_MAX_CM} cm")
        margins[key] = number
    return margins


def layout_for(info: dict, margins_cm: dict) -> dict:
    from reportlab.lib.units import cm

    return {
        "pageSize": (info["pageWidthPt"], info["pageHeightPt"]),
        "margins": (margins_cm["left"] * cm, margins_cm["right"] * cm, margins_cm["top"] * cm, margins_cm["bottom"] * cm),
    }


def apply(content_pdf: bytes, letterhead_pdf: bytes) -> bytes:
    """Escreve as páginas de `content_pdf` por cima do papel timbrado."""
    from pypdf import PdfReader, PdfWriter

    content = PdfReader(io.BytesIO(content_pdf))
    writer = PdfWriter()
    for index, page in enumerate(content.pages):
        background = PdfReader(io.BytesIO(letterhead_pdf))  # leitor novo: merge_page altera a página
        use = 1 if index > 0 and len(background.pages) > 1 else 0
        base = background.pages[use]
        base.merge_page(page)
        writer.add_page(base)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()
