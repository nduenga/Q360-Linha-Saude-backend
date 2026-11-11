"""Converte um documento Word (.docx) em PDF com o LibreOffice sem interface.

É o que faz o PDF de um modelo Word sair igual ao próprio Word (por exemplo o
modelo de proposta da Protteja). Precisa do LibreOffice e das fontes do modelo
instalados no servidor; sem eles devolve None e quem chama mantém o PDF com o
layout da plataforma.

O caminho do executável pode ser fixado em `Q360_SOFFICE_PATH`; senão procura-se
`soffice`/`libreoffice` no PATH e a instalação habitual em macOS.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 90
_MACOS_PATH = "/Applications/LibreOffice.app/Contents/MacOS/soffice"


def soffice_path() -> str | None:
    configured = os.environ.get("Q360_SOFFICE_PATH")
    if configured:
        return configured if Path(configured).exists() else None
    for name in ("soffice", "libreoffice"):
        found = shutil.which(name)
        if found:
            return found
    return _MACOS_PATH if Path(_MACOS_PATH).exists() else None


def is_available() -> bool:
    return soffice_path() is not None


def convert(data: bytes) -> bytes | None:
    """PDF do Word, ou None se o LibreOffice não existir ou a conversão falhar."""
    binary = soffice_path()
    if binary is None:
        logger.warning("LibreOffice não encontrado: o PDF usa o layout da plataforma em vez do modelo Word.")
        return None
    with tempfile.TemporaryDirectory(prefix="q360-docx-") as workdir:
        source = Path(workdir) / "documento.docx"
        source.write_bytes(data)
        # Perfil próprio por conversão: duas conversões em paralelo não disputam o mesmo perfil.
        profile = Path(workdir) / "perfil"
        command = [
            binary, "--headless", "--norestore", "--nologo",
            f"-env:UserInstallation={profile.as_uri()}",
            "--convert-to", "pdf", "--outdir", workdir, str(source),
        ]
        try:
            subprocess.run(command, check=True, capture_output=True, timeout=TIMEOUT_SECONDS)
        except (subprocess.SubprocessError, OSError) as exc:
            logger.warning("A conversão do Word para PDF falhou (%s); usa-se o layout da plataforma.", exc)
            return None
        target = source.with_suffix(".pdf")
        if not target.exists() or target.stat().st_size == 0:
            logger.warning("O LibreOffice não produziu o PDF; usa-se o layout da plataforma.")
            return None
        return target.read_bytes()
