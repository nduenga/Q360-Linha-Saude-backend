"""`/api/v1/reference-tables` — tabelas de referência do fornecedor vistas
pelo tenant (só leitura): a versão em vigor, com as linhas, para consultar e
para usar nas fórmulas com `tabela("codigo", chave, "coluna")`."""
from __future__ import annotations

from rest_framework.response import Response
from rest_framework.views import APIView

from apps.foundation.application import platform_reference_service as service
from apps.foundation.application.platform_parameter_service import UnknownPlatformParameterError
from apps.foundation.domain.scopes import Scope
from apps.foundation.interfaces.permissions import require_scope


class ReferenceTableListView(APIView):
    """Tabelas com versão em vigor (sem as linhas)."""

    permission_classes = [require_scope(Scope.READ)]

    def get(self, request):
        return Response([
            service.version_payload(v, in_effect_no=v.version_no, with_rows=False)
            for _, v in sorted(service.effective_tables().items())
        ])


class ReferenceTableDetailView(APIView):
    permission_classes = [require_scope(Scope.READ)]

    def get(self, request, code):
        current = service.effective_version(code)
        if current is None:
            raise UnknownPlatformParameterError(f"A tabela de referência '{code}' não existe ou não tem versão em vigor")
        return Response(service.version_payload(current, in_effect_no=current.version_no))
