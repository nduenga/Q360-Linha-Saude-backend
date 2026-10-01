"""drf-spectacular `AutoSchema` that documents every Q360 endpoint from the
code: request/response serializers recovered by static analysis
(`analysis.py`), the endpoints built from plain dicts described in
`registry.py` + `doc_serializers.py`, paging, query parameters, the
Idempotency-Key header, OAuth2 scopes/permissions, and the standard
`application/problem+json` error responses."""
from __future__ import annotations

import re
from typing import Any

from drf_spectacular.openapi import AutoSchema
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse
from rest_framework import serializers

from apps.foundation.domain.permissions import Permission
from apps.foundation.domain.scopes import Scope
from config.openapi.analysis import analyse
from config.openapi.registry import REGISTRY

_TAGS = [
    ("/api/v1/customer-portal", "Customer Portal"),
    ("/api/v1/admin", "Administration"),
    ("/api/v1/auth", "Identity"),
    ("/api/v1/me", "Identity"),
    ("/api/v1/health", "Health"),
    ("/api/v1/schema", "Health"),
    ("/api/v1/benefits", "Benefits"),
    ("/api/v1/product-templates", "Products"),
    ("/api/v1/products", "Products"),
    ("/api/v1/plans", "Plans"),
    ("/api/v1/configuration", "Configuration"),
    ("/api/v1/pricing-parameter-sets", "Configuration"),
    ("/api/v1/rating-tables", "Configuration"),
    ("/api/v1/rule-versions", "Configuration"),
    ("/api/v1/system-parameters", "Configuration"),
    ("/api/v1/pricing", "Pricing"),
    ("/api/v1/scenarios", "Scenarios"),
    ("/api/v1/quotes/{quote_id}/scenarios", "Scenarios"),
    ("/api/v1/quotes/{quote_id}/proposal", "Documents"),
    ("/api/v1/document-templates", "Documents"),
    ("/api/v1/documents", "Documents"),
    ("/api/v1/reviews", "Underwriting"),
    ("/api/v1/quotes/{quote_id}/review", "Underwriting"),
    ("/api/v1/quotes/{quote_id}/decision", "Underwriting"),
    ("/api/v1/quotes", "Quotes"),
    ("/api/v1/policies", "Policies"),
    ("/api/v1/coverage", "Policies"),
    ("/api/v1/claims", "Claims"),
    ("/api/v1/audit-events", "Audit"),
    ("/api/v1/dashboard", "Audit"),
    ("/api/v1/eligibility", "Eligibility"),
    ("/api/v1/proposers", "Clients"),
    ("/api/v1/members", "Population"),
    ("/api/v1/member-imports", "Population"),
    ("/api/v1/relationship-codes", "Population"),
]

_QUERY_TYPES = {
    "page": ("integer", False, "Página (começa em 0)."),
    "size": ("integer", False, "Itens por página (máx. 200)."),
}
_MEDIA = {"xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}


def _first_sentence(text: str) -> str:
    flat = re.sub(r"\s+", " ", text).strip()
    return re.split(r"(?<=[.!?])\s", flat, maxsplit=1)[0].strip()[:200]


class Problem(serializers.Serializer):
    """ART-006 ProblemDetail (application/problem+json)."""

    type = serializers.CharField(required=False)
    title = serializers.CharField()
    status = serializers.IntegerField()
    code = serializers.CharField(help_text="Código do catálogo de erros (VALIDATION-400, CONFLICT, QUOTE-STATE, ...).")
    detail = serializers.CharField(required=False)
    instance = serializers.CharField(required=False)
    correlationId = serializers.CharField()
    fieldErrors = serializers.ListField(child=serializers.DictField(child=serializers.CharField()), required=False)


Problem.__name__ = "ProblemDetail"


class PageMeta(serializers.Serializer):
    page = serializers.IntegerField()
    size = serializers.IntegerField()
    totalElements = serializers.IntegerField()
    totalPages = serializers.IntegerField()


_PAGE_CACHE: dict[type, type] = {}


def paginated(serializer: type) -> type:
    if serializer not in _PAGE_CACHE:
        annotation = getattr(serializer, "_spectacular_annotation", {}) or {}
        name = annotation.get("component_name") or serializer.__name__.removesuffix("Serializer")
        name += "Page"
        _PAGE_CACHE[serializer] = type(
            name, (serializers.Serializer,), {"items": serializer(many=True), "page": PageMeta(), "__doc__": f"Página de {serializer.__name__}."}
        )
    return _PAGE_CACHE[serializer]


class Q360AutoSchema(AutoSchema):
    # ---------------------------------------------------------------- helpers
    def _key(self) -> str:
        return f"{self.view.__class__.__name__}.{self.method.lower()}"

    def _info(self):
        return analyse(self.view.__class__, self.method.lower())

    def _reg(self) -> dict[str, Any]:
        return REGISTRY.get(self._key(), {})

    def _permissions(self) -> tuple[list[str], list[str], bool]:
        scopes: list[str] = []
        permissions: list[str] = []
        public = False
        try:
            classes = self.view.get_permissions()
        except Exception:  # noqa: BLE001 - view needs a request to decide
            classes = []
        for permission in classes:
            name = type(permission).__name__
            if name == "AllowAny":
                public = True
            elif name.startswith("RequiresScope_"):
                scopes.append(Scope[name.split("_", 1)[1]].value)
            elif name.startswith("Requires_"):
                permissions.append(Permission[name.split("_", 1)[1]].value)
        return scopes, permissions, public

    # --------------------------------------------------------------- metadata
    def get_operation_id(self) -> str:
        view = self.view.__class__.__name__.removesuffix("View")
        return self.method.lower() + view

    def get_tags(self) -> list[str]:
        path = self.path
        for prefix, tag in _TAGS:
            if path.startswith(prefix):
                return [tag]
        return ["Other"]

    def get_summary(self) -> str | None:
        method_doc = (getattr(self.view, self.method.lower(), None).__doc__ or "").strip()
        if method_doc:
            return _first_sentence(method_doc)
        verbs = {"get": "Obter", "post": "Criar", "put": "Substituir", "patch": "Alterar", "delete": "Remover"}
        name = re.sub(r"(?<!^)(?=[A-Z])", " ", self.view.__class__.__name__.removesuffix("View")).lower()
        verb = verbs[self.method.lower()]
        if self.method.lower() == "get" and "{" not in self.path.rsplit("/", 1)[-1] and (self._info().paginated or "list" in name):
            verb = "Listar"
        return f"{verb} {name}"

    def get_description(self) -> str:
        method_doc = (getattr(self.view, self.method.lower(), None).__doc__ or "").strip()
        class_doc = (self.view.__class__.__doc__ or "").strip()
        parts = [re.sub(r"[ \t]+", " ", p).strip() for p in (class_doc, method_doc) if p]
        extra = self._reg().get("notes")
        scopes, permissions, _ = self._permissions()
        if scopes or permissions:
            parts.append(
                "Requer: " + ", ".join([*(f"scope {s}" for s in scopes), *(f"permissão {p}" for p in permissions)]) + "."
            )
        if extra:
            parts.append(extra)
        return "\n\n".join(parts)

    def get_auth(self) -> list[dict[str, list[str]]]:
        scopes, _, public = self._permissions()
        authenticators = [a.__name__ for a in getattr(self.view, "authentication_classes", [])]
        if public or (not authenticators and not scopes):
            return []
        if "CustomerPortalJwtAuthentication" in authenticators:
            return [{"customerPortalBearer": []}]
        return [{"oauth2": scopes or ["q360.read"]}]

    # -------------------------------------------------------------- parameters
    def get_override_parameters(self) -> list[OpenApiParameter]:
        params: list[OpenApiParameter] = []
        info = self._info()
        reg = self._reg()
        declared = dict(reg.get("queries", {}))
        names = list(declared)
        for name in info.queries:
            if name not in names:
                names.append(name)
        if info.paginated:
            for name in ("page", "size"):
                if name not in names:
                    names.append(name)
        for name in names:
            kind, required, description = declared.get(name) or _QUERY_TYPES.get(name) or ("string", False, "Filtro.")
            params.append(
                OpenApiParameter(
                    name=name,
                    location=OpenApiParameter.QUERY,
                    required=required,
                    description=description,
                    type={"integer": OpenApiTypes.INT, "boolean": OpenApiTypes.BOOL}.get(kind, OpenApiTypes.STR),
                )
            )
        if self.method.upper() in ("POST", "PUT", "PATCH", "DELETE") and getattr(self.view.__class__, "_q360_requires_idempotency", False):
            params.append(
                OpenApiParameter(
                    name="Idempotency-Key", location=OpenApiParameter.HEADER, required=False, type=OpenApiTypes.STR,
                    description="Chave de idempotência: o mesmo pedido repetido devolve a resposta gravada; payload diferente devolve IDEMP-REPLAY.",
                )
            )
        return params

    # ---------------------------------------------------------------- request
    def get_request_serializer(self):
        reg = self._reg()
        if "request" in reg:
            return reg["request"]
        return self._info().request

    # --------------------------------------------------------------- response
    def get_response_serializers(self):
        info = self._info()
        reg = self._reg()
        method = self.method.upper()
        responses: dict[Any, Any] = {}

        success = reg.get("response")
        if success is None and info.responses:
            serializer, many = info.responses[0]
            success = paginated(serializer) if info.paginated else (serializer(many=True) if many else serializer)
        elif isinstance(success, type) and reg.get("many"):
            success = success(many=True)
        status = reg.get("status") or info.status or (201 if method == "POST" and info.request is not None and "create" in self.view.__class__.__name__.lower() else 200)

        descriptions = {200: "Sucesso.", 201: "Criado.", 202: "Aceite.", 204: "Sem conteúdo."}
        if isinstance(success, dict):
            for code, ser in success.items():
                responses[code] = OpenApiResponse(ser if ser is not None else OpenApiTypes.OBJECT, description=descriptions.get(code, "Resposta."))
        elif reg.get("media") or info.file_response:
            responses[200] = OpenApiResponse(OpenApiTypes.BINARY, description="Ficheiro.")
        elif success is not None:
            responses[status] = OpenApiResponse(success, description=descriptions.get(status, "Resposta."))
        elif method == "DELETE" or info.status == 204:
            responses[204] = OpenApiResponse(description="Sem conteúdo.")
        elif method == "POST" and not info.responses:
            responses[status if info.status else 200] = OpenApiResponse(description="Sucesso.")
        else:
            responses[200] = OpenApiResponse(description="Sucesso.")

        scopes, permissions, public = self._permissions()
        has_path_params = "{" in self.path
        problem = Problem
        if method in ("POST", "PUT", "PATCH") or info.queries:
            responses.setdefault(400, OpenApiResponse(problem, description="Pedido inválido (VALIDATION-400)."))
        if not public:
            responses.setdefault(401, OpenApiResponse(problem, description="Não autenticado (AUTH-401)."))
            responses.setdefault(403, OpenApiResponse(problem, description="Sem autorização (AUTH-403 / SEC-403)."))
        if has_path_params:
            responses.setdefault(404, OpenApiResponse(problem, description="Recurso não encontrado (NOT-FOUND)."))
        if method in ("POST", "PUT", "PATCH", "DELETE"):
            responses.setdefault(409, OpenApiResponse(problem, description="Conflito, versão ou estado inválido (CONFLICT, VERSION-CONFLICT, QUOTE-STATE)."))
        if "pricing" in self.path or "preview" in self.path or "adjustments" in self.path:
            responses.setdefault(422, OpenApiResponse(problem, description="Configuração/cálculo impossível (PRICING-CONFIG, PRICING-FAILED)."))
        return responses

    def get_response_media_types(self):
        media = self._reg().get("media")
        if media:
            return [media]
        info = self._info()
        if info.file_response:
            return ["application/octet-stream"]
        return super().get_response_media_types()
