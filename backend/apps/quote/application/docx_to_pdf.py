"""Converte um documento Word (.docx) em PDF com o LibreOffice sem interface.

É o que faz o PDF de um modelo Word sair igual ao próprio Word (por exemplo o
modelo de proposta da Protteja). Precisa do LibreOffice e das fontes do modelo
instalados no servidor; sem eles devolve None e quem chama mantém o PDF com o
layout da plataforma.

O caminho do executável pode ser fixado em `Q360_SOFFICE_PATH`; senão procura-se
`soffice`/`libreoffice` no PATH e a instalação habitual em macOS.

Fontes: o LibreOffice sem interface nem sempre vê as fontes instaladas para o
utilizador (no macOS ignora `~/Library/Fonts`) e troca-as por outras, mudando o
aspeto do PDF. Por isso, as fontes das pastas indicadas em `Q360_PDF_FONT_DIRS`
(separadas por `:`) e das pastas habituais são ligadas à pasta de fontes do
perfil de cada conversão, que o LibreOffice lê sempre.
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
_FONT_SUFFIXES = (".ttf", ".otf", ".ttc")
_DEFAULT_FONT_DIRS = ("~/Library/Fonts", "/usr/local/share/fonts", "~/.local/share/fonts", "~/.fonts")


def font_dirs() -> list[Path]:
    configured = [d for d in os.environ.get("Q360_PDF_FONT_DIRS", "").split(os.pathsep) if d.strip()]
    dirs = []
    for raw in (*configured, *_DEFAULT_FONT_DIRS):
        path = Path(raw).expanduser()
        if path.is_dir() and path not in dirs:
            dirs.append(path)
    return dirs


def _link_fonts(profile: Path) -> int:
    """Liga as fontes à pasta `user/fonts` do perfil; devolve quantas ligou."""
    target = profile / "user" / "fonts"
    target.mkdir(parents=True, exist_ok=True)
    linked = 0
    for directory in font_dirs():
        for font in directory.rglob("*"):
            if font.suffix.lower() not in _FONT_SUFFIXES or not font.is_file():
                continue
            destination = target / font.name
            if destination.exists():
                continue
            try:
                destination.symlink_to(font)
            except OSError:
                shutil.copyfile(font, destination)
            linked += 1
    return linked


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
        _link_fonts(profile)
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
