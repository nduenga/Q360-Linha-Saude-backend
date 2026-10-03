"""Configuração de negócio (tarifas, regras, textos) gerida pela interface.

Leitura: q360.read. Escrita/envio/retirada: q360.write + pricing-config:manage.
Aprovação (publicação): q360.approve + pricing-config:manage e actor diferente
do criador."""
import hashlib
import uuid
from pathlib import Path

from django.conf import settings
from django.http import FileResponse
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.business_config.application import service
from apps.business_config.domain.catalog import CONFIG_CATALOG
from apps.business_config.domain.errors import ConfigurationStateError, InvalidConfiguration
from apps.business_config.domain.form_schemas import get_form_schema
from apps.business_config.infrastructure.models import BusinessConfiguration, BusinessConfigurationDocument
from apps.business_config.interfaces.serializers import (
    BusinessConfigurationActionSerializer,
    BusinessConfigurationDocumentSerializer,
    BusinessConfigurationSerializer,
    BusinessConfigurationUpdateSerializer,
    BusinessConfigurationWriteSerializer,
)
from apps.foundation.application.context import CurrentTenantProvider
from apps.foundation.domain.permissions import Permission
from apps.foundation.domain.problem import DomainProblem
from apps.foundation.domain.scopes import Scope
from apps.foundation.interfaces.middleware import requires_idempotency
from apps.foundation.interfaces.permissions import require_permission, require_scope


class ConfigurationNotFound(DomainProblem):
    http_status = 404
    problem_code = "NOT-FOUND"


def _get(model, **kw):
    obj = model.objects.filter(**kw).first()
    if obj is None:
        raise ConfigurationNotFound("Configuração ou documento não encontrado.")
    return obj


def _read():
    return [require_scope(Scope.READ)()]


def _write():
    return [require_scope(Scope.WRITE)(), require_permission(Permission.PRICING_CONFIG_MANAGE)()]


class BCCatalogView(APIView):
    def get_permissions(self):
        return _read()

    def get(self, request):
        return Response({"items": [
            {**x, "formSchema": get_form_schema(x["key"]), "requiresBusinessConfirmation": True}
            for x in CONFIG_CATALOG]})


@requires_idempotency
class BCConfigurationListCreateView(APIView):
    def get_permissions(self):
        return _write() if self.request.method == "POST" else _read()

    def get(self, request):
        qs = BusinessConfiguration.objects.all().order_by("config_key", "-version_no")
        if request.query_params.get("configKey"):
            qs = qs.filter(config_key=request.query_params["configKey"])
        if request.query_params.get("status"):
            qs = qs.filter(status=request.query_params["status"])
        return Response({"items": BusinessConfigurationSerializer(qs, many=True).data})

    def post(self, request):
        s = BusinessConfigurationWriteSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        v = s.validated_data
        c = service.create_configuration(request, v["configKey"], v["value"], v["effectiveFrom"],
                                         v.get("effectiveTo"), v.get("metadata"))
        return Response(BusinessConfigurationSerializer(c).data, status=201)


@requires_idempotency
class BCConfigurationDetailView(APIView):
    def get_permissions(self):
        return _read() if self.request.method == "GET" else _write()

    def get(self, request, configuration_id):
        return Response(BusinessConfigurationSerializer(_get(BusinessConfiguration, id=configuration_id)).data)

    def put(self, request, configuration_id):
        c = _get(BusinessConfiguration, id=configuration_id)
        s = BusinessConfigurationUpdateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        v = s.validated_data
        c = service.update_configuration(request, c, v["value"], v.get("effectiveFrom"), v.get("effectiveTo"),
                                         v.get("metadata"), v.get("rowVersion"))
        return Response(BusinessConfigurationSerializer(c).data)

    def post(self, request, configuration_id):
        c = _get(BusinessConfiguration, id=configuration_id)
        s = BusinessConfigurationActionSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        action = s.validated_data["action"]
        c = service.submit_configuration(request, c) if action == "submit" else service.retire_configuration(request, c)
        return Response(BusinessConfigurationSerializer(c).data)


@requires_idempotency
class BCConfigurationApproveView(APIView):
    def get_permissions(self):
        return [require_scope(Scope.APPROVE)(), require_permission(Permission.PRICING_CONFIG_MANAGE)()]

    def post(self, request, configuration_id):
        c = service.approve_configuration(request, _get(BusinessConfiguration, id=configuration_id))
        return Response(BusinessConfigurationSerializer(c).data)


class BCDocumentListView(APIView):
    def get_permissions(self):
        return _read()

    def get(self, request, configuration_id):
        _get(BusinessConfiguration, id=configuration_id)
        docs = BusinessConfigurationDocument.objects.filter(configuration_id=configuration_id).order_by("-created_at")
        return Response({"items": BusinessConfigurationDocumentSerializer(docs, many=True).data})


@requires_idempotency
class BCDocumentUploadView(APIView):
    parser_classes = [MultiPartParser]

    def get_permissions(self):
        return _write()

    def post(self, request, configuration_id):
        c = _get(BusinessConfiguration, id=configuration_id)
        if c.status != "DRAFT":
            raise ConfigurationStateError("Só uma versão DRAFT aceita documentos.")
        f = request.FILES.get("file")
        if not f:
            raise InvalidConfiguration("file é obrigatório.")
        tenant = str(CurrentTenantProvider.require().value)
        did = uuid.uuid4()
        rel = Path("business-config") / tenant / str(c.id) / str(did)
        path = Path(settings.MEDIA_ROOT) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        sha = hashlib.sha256()
        with path.open("wb") as out:
            for chunk in f.chunks():
                sha.update(chunk)
                out.write(chunk)
        d = BusinessConfigurationDocument.all_tenants.create(
            id=did, tenant_id=tenant, configuration_id=c.id,
            document_type=str(request.data.get("documentType") or "BUSINESS_DOCUMENT")[:80],
            original_filename=f.name[:255], content_type=f.content_type, storage_key=str(rel),
            checksum=sha.hexdigest(), metadata_json={}, uploaded_by=service.actor_id())
        return Response(BusinessConfigurationDocumentSerializer(d).data, status=201)


class BCDocumentDownloadView(APIView):
    def get_permissions(self):
        return _read()

    def get(self, request, document_id):
        d = _get(BusinessConfigurationDocument, id=document_id)
        p = Path(settings.MEDIA_ROOT) / d.storage_key
        if not p.exists():
            raise ConfigurationNotFound("Ficheiro do documento não encontrado.")
        return FileResponse(p.open("rb"), as_attachment=True, filename=d.original_filename,
                            content_type=d.content_type or "application/octet-stream")
