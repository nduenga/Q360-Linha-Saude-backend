"""Generic `{"items": [...], "page": PageMeta}` envelope shared by every
paginated list endpoint in ART-006 (`ProductPage`, `PlanPage`,
`ProposerPage`, `MemberPage`, `QuotePage`, `ReviewTaskPage`,
`AuditEventPage` — all identical in shape). Lives in `shared/` rather than
inside any one module because DOC-004 s3.1 assigns it to no single bounded
context (see shared/README.md).

ART-006 `parameters.Page`/`parameters.Size`: `page` is 0-indexed, default 0;
`size` defaults to 20, max 200 — deliberately not DRF's default 1-indexed
`PageNumberPagination`.
"""
from __future__ import annotations

from rest_framework.pagination import BasePagination
from rest_framework.response import Response

_DEFAULT_SIZE = 20
_MAX_SIZE = 200


class Q360PageNumberPagination(BasePagination):
    def paginate_queryset(self, queryset, request, view=None):
        self.page = self._parse_int(request.query_params.get("page"), default=0, minimum=0)
        self.size = self._parse_int(
            request.query_params.get("size"), default=_DEFAULT_SIZE, minimum=1, maximum=_MAX_SIZE
        )
        self.total_elements = queryset.count()
        start = self.page * self.size
        return list(queryset[start : start + self.size])

    def get_paginated_response(self, data) -> Response:
        total_pages = (self.total_elements + self.size - 1) // self.size if self.size else 0
        return Response(
            {
                "items": data,
                "page": {
                    "page": self.page,
                    "size": self.size,
                    "totalElements": self.total_elements,
                    "totalPages": total_pages,
                },
            }
        )

    @staticmethod
    def _parse_int(raw: str | None, *, default: int, minimum: int, maximum: int | None = None) -> int:
        if raw is None:
            return default
        try:
            value = int(raw)
        except ValueError:
            return default
        value = max(value, minimum)
        if maximum is not None:
            value = min(value, maximum)
        return value
