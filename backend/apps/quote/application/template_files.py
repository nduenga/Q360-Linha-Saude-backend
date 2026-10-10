"""Ficheiros dos modelos de documento: papel timbrado (PDF) e modelo Word.

Só um modelo em rascunho (DRAFT) aceita ficheiros novos ou removê-los: uma vez
publicado, o modelo e os seus ficheiros ficam imutáveis (um documento já
gerado tem de continuar a poder ser reproduzido).
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from django.conf import settings

from apps.quote.application import letterhead, word_template
from apps.quote.application.document_service import TemplateImmutableError
from apps.quote.domain.enums import DocumentTemplateStatus
from apps.quote.domain.proposal_template import InvalidTemplateError
from apps.quote.infrastructure.models import DocumentTemplateVersion

MAX_FILE_BYTES = 10 * 1024 * 1024
_PDF_TYPES = {"application/pdf", "application/x-pdf"}
_DOCX_TYPES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/octet-stream",  # alguns browsers não enviam o tipo correto
}


def _require_draft(template: DocumentTemplateVersion) -> None:
    if template.status != DocumentTemplateStatus.DRAFT.value:
        raise TemplateImmutableError(
            f"O modelo de documento {template.id} não está em rascunho (DRAFT); só um rascunho aceita ficheiros"
        )


def _read_upload(uploaded_file: Any, *, kind_label: str) -> bytes:
    size = int(getattr(uploaded_file, "size", 0) or 0)
    if size <= 0:
        raise InvalidTemplateError("O ficheiro está vazio")
    if size > MAX_FILE_BYTES:
        raise InvalidTemplateError(f"O ficheiro excede o tamanho máximo de {MAX_FILE_BYTES // (1024 * 1024)} MB")
    data = b"".join(uploaded_file.chunks())
    if not data:
        raise InvalidTemplateError(f"O ficheiro {kind_label} está vazio")
    return data


def _path(template: DocumentTemplateVersion, filename: str) -> tuple[str, Path]:
    key = f"document-templates/{template.tenant_id}/{template.id}/{filename}"
    return key, Path(settings.MEDIA_ROOT) / key


def _write(template: DocumentTemplateVersion, filename: str, data: bytes) -> str:
    key, path = _path(template, filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return key


def _read(template: DocumentTemplateVersion, key: str | None, checksum: str | None) -> bytes | None:
    if not key:
        return None
    path = Path(settings.MEDIA_ROOT) / key
    if not path.exists():
        raise InvalidTemplateError("O ficheiro do modelo já não está disponível: carregue-o de novo")
    data = path.read_bytes()
    if checksum and hashlib.sha256(data).hexdigest() != checksum:
        raise InvalidTemplateError("O ficheiro do modelo falhou a verificação de integridade: carregue-o de novo")
    return data


# --------------------------------------------------------- papel timbrado
def save_letterhead(template: DocumentTemplateVersion, uploaded_file: Any, margins_form: dict[str, Any]) -> DocumentTemplateVersion:
    _require_draft(template)
    content_type = (getattr(uploaded_file, "content_type", "") or "").split(";")[0].strip().lower()
    if content_type not in _PDF_TYPES and not str(getattr(uploaded_file, "name", "")).lower().endswith(".pdf"):
        raise InvalidTemplateError("O papel timbrado tem de ser um ficheiro PDF")
    data = _read_upload(uploaded_file, kind_label="PDF")
    info = letterhead.inspect(data)
    margins = letterhead.margins_from_form(margins_form)
    key = _write(template, "letterhead.pdf", data)
    new_settings = {
        **(template.settings_json or {}),
        "letterhead": {**info, "marginsCm": margins, "checksum": hashlib.sha256(data).hexdigest()},
    }
    DocumentTemplateVersion.objects.filter(id=template.id).update(
        letterhead_key=key, letterhead_name=(getattr(uploaded_file, "name", None) or "papel-timbrado.pdf")[:255], settings_json=new_settings
    )
    template.refresh_from_db()
    return template


def delete_letterhead(template: DocumentTemplateVersion) -> DocumentTemplateVersion:
    _require_draft(template)
    new_settings = {k: v for k, v in (template.settings_json or {}).items() if k != "letterhead"}
    DocumentTemplateVersion.objects.filter(id=template.id).update(letterhead_key=None, letterhead_name=None, settings_json=new_settings)
    template.refresh_from_db()
    return template


def read_letterhead(template: DocumentTemplateVersion) -> bytes | None:
    meta = (template.settings_json or {}).get("letterhead") or {}
    return _read(template, template.letterhead_key, meta.get("checksum"))


def layout_for(template: DocumentTemplateVersion) -> dict[str, Any] | None:
    """Tamanho de página e margens do documento, para o texto cair dentro da
    área livre do papel timbrado. `None` = layout por omissão (A4)."""
    meta = (template.settings_json or {}).get("letterhead")
    if not template.letterhead_key or not meta:
        return None
    return letterhead.layout_for(meta, meta["marginsCm"])


# ------------------------------------------------------------ modelo Word
def save_word(template: DocumentTemplateVersion, uploaded_file: Any) -> tuple[DocumentTemplateVersion, dict[str, Any]]:
    _require_draft(template)
    name = str(getattr(uploaded_file, "name", "") or "")
    content_type = (getattr(uploaded_file, "content_type", "") or "").split(";")[0].strip().lower()
    if not name.lower().endswith(".docx") or content_type not in _DOCX_TYPES:
        raise InvalidTemplateError("O modelo Word tem de ser um ficheiro .docx (Word 2007 ou posterior)")
    data = _read_upload(uploaded_file, kind_label="Word")
    report = word_template.validate(data, template.document_type)
    key = _write(template, "template.docx", data)
    new_settings = {**(template.settings_json or {}), "word": {**report, "checksum": hashlib.sha256(data).hexdigest()}}
    DocumentTemplateVersion.objects.filter(id=template.id).update(word_key=key, word_name=name[:255], settings_json=new_settings)
    template.refresh_from_db()
    return template, report


def delete_word(template: DocumentTemplateVersion) -> DocumentTemplateVersion:
    _require_draft(template)
    new_settings = {k: v for k, v in (template.settings_json or {}).items() if k != "word"}
    DocumentTemplateVersion.objects.filter(id=template.id).update(word_key=None, word_name=None, settings_json=new_settings)
    template.refresh_from_db()
    return template


def read_word(template: DocumentTemplateVersion) -> bytes | None:
    meta = (template.settings_json or {}).get("word") or {}
    return _read(template, template.word_key, meta.get("checksum"))
