"""ART-006 `/api/v1/rating-tables`: `createRatingTable` (POST), security ->
oauth2: [q360.admin]. Gated additionally by DOC-001 s18
`pricing-config:manage` — rating tables are unambiguously pricing
configuration (unlike the shared rule-version endpoint, which spans
domains and is scope-only, see apps/product/interfaces/views.py
ConfigurationPublishView).
"""
from __future__ import annotations

from rest_framework.response import Response
from rest_framework.views import APIView

from apps.foundation.domain.permissions import Permission
from apps.foundation.domain.scopes import Scope
from apps.foundation.interfaces.permissions import require_permission, require_scope
from apps.pricing.application.rating_table_service import create_rating_table
from apps.pricing.interfaces.serializers import RatingTableRequestSerializer, VersionedConfigHeaderSerializer


class RatingTableCreateView(APIView):
    permission_classes = [require_scope(Scope.ADMIN), require_permission(Permission.PRICING_CONFIG_MANAGE)]

    def post(self, request):
        body = RatingTableRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        rating_table = create_rating_table(
            code=data["code"],
            name=data["name"],
            effective_from=data["effectiveFrom"],
            effective_to=data["effectiveTo"],
            currency_code=data["currencyCode"],
            factor_rows=data["factors"],
        )
        return Response(VersionedConfigHeaderSerializer(rating_table).data, status=201)
