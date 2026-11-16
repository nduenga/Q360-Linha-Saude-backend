"""Converte documentos DOCX para PDF usando a instalação isolada do LibreOffice."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from django.conf import settings

from apps.foundation.domain.problem import DomainProblem

MAX_OUTPUT_BYTES = 50 * 1024 * 1024
CONVERSION_TIMEOUT_SECONDS = 45


class OfficeConversionError(DomainProblem):
    http_status = 503
    problem_code = "DOCUMENT-CONVERSION-UNAVAILABLE"


def _binary() -> str | None:
    # Accept the setting used by Django and both documented environment names.
    # Q360_SOFFICE_PATH is retained for existing deployments and macOS installs.
    configured = (
        getattr(settings, "OFFICE_CONVERTER_BIN", None)
        or os.environ.get("OFFICE_CONVERTER_BIN")
        or os.environ.get("Q360_SOFFICE_PATH")
    )
    if configured:
        return configured if Path(configured).is_file() else None

    on_path = shutil.which("soffice") or shutil.which("libreoffice") or shutil.which("soffice.exe")
    if on_path:
        return on_path

    # macOS desktop installs do not normally add the app's executable to PATH.
    macos_app = Path("/Applications/LibreOffice.app/Contents/MacOS/soffice")
    return str(macos_app) if macos_app.is_file() else None


def docx_to_pdf(docx_bytes: bytes) -> bytes:
    """Converte DOCX sem shell, perfil ou diretório de saída partilhados."""
    binary = _binary()
    if not binary:
        raise OfficeConversionError(
            "A conversão de modelos Word para PDF não está disponível. Instale o LibreOffice Writer no serviço do Q360."
        )

    try:
        with tempfile.TemporaryDirectory(prefix="q360-office-") as temporary:
            root = Path(temporary)
            source_dir = root / "source"
            output_dir = root / "output"
            profile_dir = root / "profile"
            source_dir.mkdir()
            output_dir.mkdir()
            profile_dir.mkdir()
            source = source_dir / "document.docx"
            output = output_dir / "document.pdf"
            source.write_bytes(docx_bytes)

            result = subprocess.run(
                [
                    binary,
                    "--headless",
                    "--nologo",
                    "--nodefault",
                    "--nolockcheck",
                    f"-env:UserInstallation={profile_dir.resolve().as_uri()}",
                    "--convert-to",
                    "pdf:writer_pdf_Export",
                    "--outdir",
                    str(output_dir),
                    str(source),
                ],
                capture_output=True,
                check=False,
                timeout=CONVERSION_TIMEOUT_SECONDS,
            )
            if result.returncode != 0 or not output.is_file():
                raise OfficeConversionError("O LibreOffice não conseguiu converter o modelo Word para PDF.")
            if output.stat().st_size > MAX_OUTPUT_BYTES:
                raise OfficeConversionError("O PDF gerado ultrapassa o tamanho permitido.")
            data = output.read_bytes()
            if not data.startswith(b"%PDF-"):
                raise OfficeConversionError("O LibreOffice não produziu um PDF válido.")
            return data
    except subprocess.TimeoutExpired as exc:
        raise OfficeConversionError("A conversão do documento excedeu o tempo permitido.") from exc
    except OSError as exc:
        raise OfficeConversionError("Não foi possível iniciar o LibreOffice para converter o documento.") from exc
