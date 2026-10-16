"""`/business-config/approvals/pending` — fila única do que espera pela
aprovação de outra pessoa no tenant (configurações, fórmulas, configuração
de produtos, regras), com as diferenças face à versão publicada."""
from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.business_config.application import approvals_service
from apps.business_config.domain.catalog import AREAS
from apps.foundation.domain.scopes import Scope
from apps.foundation.interfaces.permissions import require_scope


class PendingApprovalsView(APIView):
    """Filtro opcional `?area=` (ORGANIZATION, PRODUCTS, TARIFF, RULES,
    PARAMETERS, DOCUMENTS)."""

    permission_classes = [require_scope(Scope.READ)]

    @extend_schema(operation_id="listPendingApprovals", summary="Fila única de aprovações pendentes",
                   tags=["Configuration"])
    def get(self, request):
        area = request.query_params.get("area")
        if area and area not in AREAS:
            return Response({"detail": f"area inválida (use {list(AREAS)})"}, status=400)
        return Response(approvals_service.pending_queue(area=area))


class PendingApprovalsCountView(APIView):
    permission_classes = [require_scope(Scope.READ)]

    @extend_schema(operation_id="countPendingApprovals", summary="Contagem de aprovações pendentes (para o menu)",
                   tags=["Configuration"])
    def get(self, request):
        return Response(approvals_service.pending_count())
