"""Ficheiros que as lojas leem para validar as ligações universais
(roadmap_mobile.md, Fase 1 — ponto 5). Servidos na raiz do domínio da app
(`/.well-known/...`); se esse domínio for servido por outro servidor (p.ex. o
da web), publique lá os mesmos ficheiros — o conteúdo vem das variáveis
CUSTOMER_PORTAL_APPLE_APP_IDS, CUSTOMER_PORTAL_ANDROID_PACKAGE e
CUSTOMER_PORTAL_ANDROID_SHA256. Sem configuração respondem 404."""
from __future__ import annotations

from django.conf import settings
from django.http import Http404, JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def apple_app_site_association(request):
    app_ids = settings.CUSTOMER_PORTAL_APPLE_APP_IDS
    if not app_ids:
        raise Http404()
    return JsonResponse(
        {
            "applinks": {
                "apps": [],
                "details": [
                    {"appIDs": app_ids, "components": [{"/": "/*"}]},
                ],
            }
        }
    )


@require_GET
def android_asset_links(request):
    package, fingerprints = settings.CUSTOMER_PORTAL_ANDROID_PACKAGE, settings.CUSTOMER_PORTAL_ANDROID_SHA256
    if not package or not fingerprints:
        raise Http404()
    return JsonResponse(
        [
            {
                "relation": ["delegate_permission/common.handle_all_urls"],
                "target": {"namespace": "android_app", "package_name": package, "sha256_cert_fingerprints": fingerprints},
            }
        ],
        safe=False,
    )
