from pathlib import Path
import hashlib,uuid
from django.conf import settings
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from apps.business_config.domain.catalog import CONFIG_CATALOG
from apps.business_config.domain.form_schemas import get_form_schema
from apps.business_config.infrastructure.models import BusinessConfiguration,BusinessConfigurationDocument
from apps.business_config.application.service import *
from apps.business_config.interfaces.serializers import *
from apps.foundation.application.context import CurrentTenantProvider
from apps.business_config.domain.custom_rules import field_catalog

class CatalogView(APIView):
    @extend_schema(operation_id="getBusinessConfigurationCatalog", summary="Consultar catálogo de configurações", tags=["Configuration"], responses=BusinessConfigurationCatalogSerializer)
    def get(self,request): return Response({"items":[{**x,"formSchema":get_form_schema(x["key"]),"requiresBusinessConfirmation":True} for x in CONFIG_CATALOG]})
class ConfigurationListCreateView(APIView):
    @extend_schema(operation_id="listBusinessConfigurations", summary="Listar configurações de negócio", tags=["Configuration"], responses=BusinessConfigurationListSerializer)
    def get(self,request):
        qs=BusinessConfiguration.objects.all().order_by("config_key","-version_no")
        if request.query_params.get("configKey"):qs=qs.filter(config_key=request.query_params["configKey"])
        if request.query_params.get("status"):qs=qs.filter(status=request.query_params["status"])
        return Response({"items":BusinessConfigurationSerializer(qs,many=True).data})
    @extend_schema(operation_id="createBusinessConfiguration", summary="Criar configuração de negócio", tags=["Configuration"], request=BusinessConfigurationWriteSerializer, responses={201:BusinessConfigurationSerializer})
    def post(self,request):
        s=BusinessConfigurationWriteSerializer(data=request.data);s.is_valid(raise_exception=True)
        c=create_configuration(request, s.validated_data["configKey"],s.validated_data["value"],s.validated_data["effectiveFrom"],s.validated_data.get("effectiveTo"),s.validated_data.get("metadata"))
        return Response(BusinessConfigurationSerializer(c).data,status=201)
class ConfigurationDetailView(APIView):
    @extend_schema(operation_id="getBusinessConfiguration", summary="Consultar configuração de negócio", tags=["Configuration"], responses=BusinessConfigurationSerializer)
    def get(self,request,configuration_id):return Response(BusinessConfigurationSerializer(get_object_or_404(BusinessConfiguration,id=configuration_id)).data)
    @extend_schema(operation_id="updateBusinessConfiguration", summary="Actualizar configuração de negócio em rascunho", tags=["Configuration"], request=BusinessConfigurationUpdateSerializer, responses=BusinessConfigurationSerializer)
    def put(self,request,configuration_id):
        c=get_object_or_404(BusinessConfiguration,id=configuration_id);s=BusinessConfigurationUpdateSerializer(data=request.data);s.is_valid(raise_exception=True)
        c=update_configuration(request,c,s.validated_data["value"],s.validated_data.get("effectiveFrom"),s.validated_data.get("effectiveTo"),s.validated_data.get("metadata"),s.validated_data.get("rowVersion"))
        return Response(BusinessConfigurationSerializer(c).data)
    @extend_schema(operation_id="changeBusinessConfigurationStatus", summary="Submeter ou retirar configuração de negócio", tags=["Configuration"], request=BusinessConfigurationActionSerializer, responses=BusinessConfigurationSerializer)
    def post(self,request,configuration_id):
        c=get_object_or_404(BusinessConfiguration,id=configuration_id);a=request.data.get("action")
        if a=="submit":c=submit_configuration(request,c)
        elif a=="retire":c=retire_configuration(request,c)
        else:return Response({"detail":"Ação inválida."},status=400)
        return Response(BusinessConfigurationSerializer(c).data)
class ConfigurationApproveView(APIView):
    @extend_schema(operation_id="approveBusinessConfiguration", summary="Aprovar configuração de negócio", tags=["Configuration"], request=None, responses=BusinessConfigurationSerializer)
    def post(self,request,configuration_id):return Response(BusinessConfigurationSerializer(approve_configuration(request,get_object_or_404(BusinessConfiguration,id=configuration_id))).data)
class DocumentListView(APIView):
    @extend_schema(operation_id="listBusinessConfigurationDocuments", summary="Listar documentos da configuração", tags=["Configuration"], responses=BusinessConfigurationDocumentListSerializer)
    def get(self,request,configuration_id):
        docs=BusinessConfigurationDocument.objects.filter(configuration_id=configuration_id).order_by("-created_at")
        return Response({"items":BusinessConfigurationDocumentSerializer(docs,many=True).data})
class DocumentUploadView(APIView):
    parser_classes=[MultiPartParser]
    @extend_schema(operation_id="uploadBusinessConfigurationDocument", summary="Anexar documento à configuração", tags=["Configuration"], request=BusinessConfigurationDocumentUploadSerializer, responses={201:BusinessConfigurationDocumentSerializer})
    def post(self,request,configuration_id):
        c=get_object_or_404(BusinessConfiguration,id=configuration_id)
        if c.status!="DRAFT":return Response({"detail":"Só DRAFT aceita documentos."},status=409)
        f=request.FILES.get("file")
        if not f:return Response({"detail":"file é obrigatório."},status=400)
        tid=str(CurrentTenantProvider.require().value);did=uuid.uuid4();rel=Path("business-config")/tid/str(c.id)/str(did);path=Path(settings.MEDIA_ROOT)/rel;path.parent.mkdir(parents=True,exist_ok=True);sha=hashlib.sha256()
        with path.open("wb") as out:
            for chunk in f.chunks():sha.update(chunk);out.write(chunk)
        d=BusinessConfigurationDocument.all_tenants.create(id=did,tenant_id=tid,configuration_id=c.id,document_type=request.data.get("documentType","BUSINESS_DOCUMENT"),original_filename=f.name[:255],content_type=f.content_type,storage_key=str(rel),checksum=sha.hexdigest(),metadata_json={},uploaded_by=str(getattr(request.user,"username","system")))
        return Response(BusinessConfigurationDocumentSerializer(d).data,status=201)
class DocumentDownloadView(APIView):
    @extend_schema(operation_id="downloadBusinessConfigurationDocument", summary="Descarregar documento da configuração", tags=["Configuration"], responses={(200, "application/octet-stream"): OpenApiTypes.BINARY})
    def get(self,request,document_id):
        d=get_object_or_404(BusinessConfigurationDocument,id=document_id);p=Path(settings.MEDIA_ROOT)/d.storage_key
        if not p.exists():return Response({"detail":"Documento não encontrado."},status=404)
        return FileResponse(p.open("rb"),as_attachment=True,filename=d.original_filename,content_type=d.content_type or "application/octet-stream")

class CustomRulesCatalogView(APIView):
    @extend_schema(
        operation_id="getCustomRulesCatalog",
        summary="Consultar catálogo do construtor de regras personalizadas",
        tags=["Configuration"],
    )
    def get(self, request):
        return Response(field_catalog())
    
class CustomRulesListCreateView(APIView):
    @extend_schema(
        operation_id="listCustomRules",
        summary="Consultar regras personalizadas",
        tags=["Configuration"],
        responses=BusinessConfigurationSerializer,
    )
    def get(self, request):
        qs = (
            BusinessConfiguration.objects
            .filter(config_key="rules.custom")
            .order_by("-version_no")
        )

        status = request.query_params.get("status")
        if status:
            qs = qs.filter(status=status)

        return Response({
            "items": BusinessConfigurationSerializer(qs, many=True).data
        })

    @extend_schema(
        operation_id="createCustomRules",
        summary="Criar nova versão de regras personalizadas",
        tags=["Configuration"],
        request=BusinessConfigurationWriteSerializer,
        responses={201: BusinessConfigurationSerializer},
    )
    def post(self, request):
        serializer = BusinessConfigurationWriteSerializer(
            data={
                **request.data,
                "configKey": "rules.custom",
            }
        )
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        configuration = create_configuration(
            request,
            "rules.custom",
            data["value"],
            data["effectiveFrom"],
            data.get("effectiveTo"),
            data.get("metadata"),
        )

        return Response(
            BusinessConfigurationSerializer(configuration).data,
            status=201,
        )

class CustomRulesDetailView(APIView):
    @extend_schema(
        operation_id="updateCustomRules",
        summary="Actualizar regras personalizadas em DRAFT",
        tags=["Configuration"],
        request=BusinessConfigurationUpdateSerializer,
        responses=BusinessConfigurationSerializer,
    )
    def put(self, request, configuration_id):
        configuration = get_object_or_404(
            BusinessConfiguration,
            id=configuration_id,
            config_key="rules.custom",
        )

        serializer = BusinessConfigurationUpdateSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        configuration = update_configuration(
            request,
            configuration,
            data["value"],
            data.get("effectiveFrom"),
            data.get("effectiveTo"),
            data.get("metadata"),
            data.get("rowVersion"),
        )

        return Response(
            BusinessConfigurationSerializer(configuration).data
        )
        
class CustomRulesSubmitView(APIView):
    @extend_schema(
        operation_id="submitCustomRules",
        summary="Submeter regras personalizadas para aprovação",
        tags=["Configuration"],
        request=BusinessConfigurationActionSerializer,
        responses=BusinessConfigurationSerializer,
    )
    def post(self, request, configuration_id):
        configuration = get_object_or_404(
            BusinessConfiguration,
            id=configuration_id,
            config_key="rules.custom",
        )

        configuration = submit_configuration(
            request,
            configuration,
        )

        return Response(
            BusinessConfigurationSerializer(configuration).data
        )


class CustomRulesApproveView(APIView):
    @extend_schema(
        operation_id="approveCustomRules",
        summary="Publicar nova versão das regras personalizadas",
        tags=["Configuration"],
        responses=BusinessConfigurationSerializer,
    )
    def post(self, request, configuration_id):
        configuration = get_object_or_404(
            BusinessConfiguration,
            id=configuration_id,
            config_key="rules.custom",
        )

        configuration = approve_configuration(
            request,
            configuration,
        )

        return Response(
            BusinessConfigurationSerializer(configuration).data
        )