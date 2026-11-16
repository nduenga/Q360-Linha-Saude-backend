"""Install the prepared Protteja quotation DOCX templates for one tenant.

The source files are deliberately installed as drafts.  They must be
previewed by the insurer before being published: the preparation guide calls
out fixed legal/commercial text that needs that approval.
"""
from __future__ import annotations

import datetime
import hashlib
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.foundation.application.context import CurrentActorProvider
from apps.foundation.domain.actor import Actor
from apps.foundation.domain.tenant import TenantId
from apps.quote.application import document_service, template_files, word_template
from apps.quote.domain.proposal_template import default_body
from apps.quote.infrastructure.models import DocumentTemplateVersion


TEMPLATES = {
    "Protteja_Saude_Business_Individual.docx": "PROTTEJA_BUSINESS_INDIVIDUAL",
    "Protteja_Saude_Business_Grupo.docx": "PROTTEJA_BUSINESS_GRUPO",
    "Protteja_Saude_Business_Plus_Individual.docx": "PROTTEJA_BUSINESS_PLUS_INDIVIDUAL",
    "Protteja_Saude_Business_Plus_Grupo.docx": "PROTTEJA_BUSINESS_PLUS_GRUPO",
    "Protteja_Saude_Premium_Individual.docx": "PROTTEJA_PREMIUM_INDIVIDUAL",
    "Protteja_Saude_Premium_Grupo.docx": "PROTTEJA_PREMIUM_GRUPO",
    "Protteja_Saude_Premium_Plus_Individual.docx": "PROTTEJA_PREMIUM_PLUS_INDIVIDUAL",
    "Protteja_Saude_Premium_Plus_Grupo.docx": "PROTTEJA_PREMIUM_PLUS_GRUPO",
}


def _default_source_dir() -> Path:
    root = Path(__file__).resolve().parents[5]
    base = root / "Protteja_Propostas_Saude_v2"
    # The requested FINAL_FORMATADOS name is accepted when supplied later;
    # the checked-in prepared files currently live in FORMATADOS.
    for name in ("Q360_PREPARADOS_FINAL_FORMATADOS", "Q360_PREPARADOS_FORMATADOS"):
        candidate = base / name
        if candidate.is_dir():
            return candidate
    return base / "Q360_PREPARADOS_FINAL_FORMATADOS"


class Command(BaseCommand):
    help = "Instala os oito modelos DOCX Protteja como rascunhos de proposta para um tenant."

    def add_arguments(self, parser):
        parser.add_argument("--tenant-id", required=True, help="UUID do tenant que receberá os modelos.")
        parser.add_argument(
            "--source-dir",
            default=str(_default_source_dir()),
            help="Pasta com os oito DOCX preparados (por omissão, Q360_PREPARADOS_FORMATADOS).",
        )
        parser.add_argument("--effective-from", default=str(datetime.date.today()), help="Data inicial YYYY-MM-DD.")
        parser.add_argument("--publish", action="store_true", help="Publica os modelos após a instalação e a validação.")

    def handle(self, *args, **options):
        try:
            tenant_id = TenantId.parse(options["tenant_id"])
            effective_from = datetime.date.fromisoformat(options["effective_from"])
        except ValueError as exc:
            raise CommandError("tenant-id ou effective-from inválido") from exc

        source_dir = Path(options["source_dir"]).resolve()
        if not source_dir.is_dir():
            raise CommandError(f"A pasta de modelos não existe: {source_dir}")

        files = {name: source_dir / name for name in TEMPLATES}
        missing = [str(path) for path in files.values() if not path.is_file()]
        if missing:
            raise CommandError("Faltam modelos Protteja: " + ", ".join(missing))

        actor_token = CurrentActorProvider.bind(
            Actor(actor_id="system:install-protteja-templates", tenant_id=tenant_id, roles=frozenset(), actor_type="SYSTEM")
        )
        try:
            for file_name, template_code in TEMPLATES.items():
                data = files[file_name].read_bytes()
                word_template.validate(data, "QUOTE_PROPOSAL")
                digest = hashlib.sha256(data).hexdigest()
                existing = (
                    DocumentTemplateVersion.objects.filter(template_code=template_code)
                    .order_by("-version_no")
                    .first()
                )
                existing_digest = ((existing.settings_json or {}).get("word") or {}).get("checksum") if existing else None
                if existing_digest == digest:
                    if options["publish"] and existing.status == "DRAFT":
                        document_service.publish_document_template(existing)
                        self.stdout.write(self.style.SUCCESS(f"Publicado: {template_code}"))
                        continue
                    self.stdout.write(f"Ignorado (já instalado): {template_code}")
                    continue

                # A prior interrupted install may have made the DRAFT record
                # but not reached the file upload. Complete that safe draft
                # instead of creating a needless extra version.
                if existing is not None and existing.status == "DRAFT" and not existing.word_key:
                    template = existing
                else:
                    template = document_service.create_document_template(
                        template_code=template_code,
                        storage_ref=default_body(),
                        effective_from=effective_from,
                        document_type="QUOTE_PROPOSAL",
                    )
                upload = SimpleUploadedFile(
                    file_name,
                    data,
                    content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
                template_files.save_word(template, upload)
                if options["publish"]:
                    document_service.publish_document_template(template)
                    status = "publicado"
                else:
                    status = "rascunho"
                self.stdout.write(self.style.SUCCESS(f"Instalado ({status}): {template_code}"))
        finally:
            CurrentActorProvider.reset(actor_token)
