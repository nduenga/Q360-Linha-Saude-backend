"""HTML to PDF conversion through the bundled, headless Chromium browser."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from apps.foundation.domain.problem import DomainProblem

MAX_HTML_BYTES = 20 * 1024 * 1024
MAX_PDF_BYTES = 50 * 1024 * 1024
CONVERSION_TIMEOUT_MS = 45_000


class ChromiumConversionError(DomainProblem):
    http_status = 503
    problem_code = "DOCUMENT-CONVERSION-UNAVAILABLE"


def html_to_pdf(html_data: bytes) -> bytes:
    """Render a self-contained proposal HTML document to an A4 PDF."""
    if len(html_data) > MAX_HTML_BYTES:
        raise ChromiumConversionError("O HTML da proposta ultrapassa o tamanho permitido.")

    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise ChromiumConversionError(
            "O Playwright não está instalado no ambiente Python do Q360. Instale as dependências do backend e reinicie o serviço."
        ) from exc

    try:
        with sync_playwright() as playwright:
            launch_options = {"headless": True, "args": ["--no-sandbox"]}
            executable = _system_chromium()
            if executable:
                # Local developer machines may already have Chrome installed
                # even when Playwright's separately managed browser is absent.
                launch_options["executable_path"] = executable
            browser = playwright.chromium.launch(**launch_options)
            try:
                page = browser.new_page()
                page.set_default_timeout(CONVERSION_TIMEOUT_MS)
                page.set_default_navigation_timeout(CONVERSION_TIMEOUT_MS)
                page.set_content(html_data.decode("utf-8"), wait_until="load", timeout=CONVERSION_TIMEOUT_MS)
                data = page.pdf(
                    format="A4",
                    print_background=True,
                    prefer_css_page_size=True,
                    display_header_footer=False,
                )
            finally:
                browser.close()
    except PlaywrightTimeoutError as exc:
        raise ChromiumConversionError("A geração do PDF da proposta excedeu o tempo permitido.") from exc
    except PlaywrightError as exc:
        raise ChromiumConversionError("O Chromium não conseguiu renderizar o PDF da proposta.") from exc

    if len(data) > MAX_PDF_BYTES:
        raise ChromiumConversionError("O PDF gerado ultrapassa o tamanho permitido.")
    if not data.startswith(b"%PDF-"):
        raise ChromiumConversionError("O Chromium não produziu um PDF válido.")
    return data


def _system_chromium() -> str | None:
    """Use an explicitly configured/system Chrome when available.

    In deployed containers Playwright's bundled Chromium remains the default.
    """
    configured = os.environ.get("Q360_CHROMIUM_EXECUTABLE")
    if configured and Path(configured).is_file():
        return configured
    if sys.platform == "darwin":
        mac_chrome = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
        return str(mac_chrome) if mac_chrome.is_file() else None
    for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable"):
        executable = shutil.which(name)
        if executable:
            return executable
    return None
