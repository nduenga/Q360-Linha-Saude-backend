"""Versão mínima da app móvel (roadmap_mobile.md, Fase 4 — «Suporte»).

A app envia `X-App-Version` (e `X-App-Platform`) em todos os pedidos. Quando há
mudanças incompatíveis, define-se `CUSTOMER_PORTAL_MIN_APP_VERSION` e as
versões anteriores recebem 426 com o código `PORTAL-APP-UPDATE-REQUIRED`: a app
mostra o ecrã «atualize a app». Pedidos sem o cabeçalho (a web) nunca são
bloqueados, e `GET /customer-portal/app-config` responde sempre, para a app
poder explicar o que se passa.
"""
from __future__ import annotations

import re

from django.conf import settings
from django.http import JsonResponse

PREFIX = "/api/v1/customer-portal/"
EXEMPT_SUFFIXES = ("/app-config",)


def parse_version(value: str) -> tuple[int, int, int] | None:
    parts = re.findall(r"\d+", value or "")[:3]
    if not parts:
        return None
    numbers = [int(p) for p in parts] + [0] * (3 - len(parts))
    return numbers[0], numbers[1], numbers[2]


def is_below_minimum(version: str, minimum: str) -> bool:
    """Versão ilegível conta como atual: nunca se bloqueia por engano."""
    current, floor = parse_version(version), parse_version(minimum)
    return current is not None and floor is not None and current < floor


class PortalAppVersionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        minimum = settings.CUSTOMER_PORTAL_MIN_APP_VERSION
        version = request.headers.get("X-App-Version", "")
        if (
            minimum and version and request.path.startswith(PREFIX)
            and not request.path.rstrip("/").endswith(EXEMPT_SUFFIXES)
            and is_below_minimum(version, minimum)
        ):
            from apps.foundation.interfaces.middleware import get_correlation_id

            return JsonResponse(
                {
                    "title": "Atualização da app necessária", "status": 426, "code": "PORTAL-APP-UPDATE-REQUIRED",
                    "detail": f"Esta versão da app ({version}) já não é suportada. Atualize para a versão {minimum} ou superior.",
                    "correlationId": get_correlation_id() or "",
                },
                status=426, content_type="application/problem+json",
            )
        return self.get_response(request)
