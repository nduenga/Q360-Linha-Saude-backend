"""API do modelo atuarial (`pricing.actuarial_model`).

O modelo é uma configuração como as outras: edita-se pela rota genérica
`business-config/configurations` (DRAFT -> aprovação -> PUBLISHED). Estas
rotas acrescentam o que o editor do frontend precisa: importar um Excel,
descarregar o modelo de referência e conhecer as opções configuráveis.
"""
from __future__ import annotations

from datetime import date

from django.http import FileResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.business_config.application.actuarial_import import (
    KEPT_FROM_PUBLISHED,
    MAX_WORKBOOK_BYTES,
    build_from_upload,
    import_actuarial_workbook,
    summarize,
)
from apps.business_config.application.resolver import BusinessConfigurationResolver
from apps.business_config.domain.actuarial_model import (
    ADHESION,
    CONFIG_KEY,
    ENTRY_AGE_ON_RENEWAL,
    RECOMMENDED_CALCULATION_SETTINGS,
)
from apps.business_config.interfaces.serializers import BusinessConfigurationSerializer
from apps.business_config.interfaces.views import _ConfigPermissions
from apps.business_config.seed.actuarial_model import WORKBOOK_PATH

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

# Secções do valor do modelo e o que cada uma controla, para o editor.
SECTIONS = [
    {"key": "assumptions", "label": "Premissas gerais",
     "help": "Câmbio, inflação, carregamentos (volatilidade, encargos, comissão, margem), impostos e fracionamento por segmento"},
    {"key": "reference_pure_premiums", "label": "Prémios puros por plano e cobertura",
     "help": "Frequência, custo médio ajustado, tendência e severidade (lognormal) de cada cobertura"},
    {"key": "plan_coverages", "label": "Coberturas e capitais por plano", "help": "Estatuto B/O/— e capital/sublimite"},
    {"key": "age_gender_relativities", "label": "Relatividades idade × sexo", "help": "Factor por cobertura e escalão"},
    {"key": "group_size_factors", "label": "SAG: dimensão do grupo", "help": "Ajuste e volatilidade por número de colaboradores"},
    {"key": "group_participation_factors", "label": "SAG: adesão", "help": "Obrigatória/facultativa e taxa de participação"},
    {"key": "industry_factors", "label": "SAG: sector de atividade", "help": "Factor por sector"},
    {"key": "adjustment_assumptions", "label": "Ajustes",
     "help": "Participação nos custos, pré-existências, idade de adesão, descontos (agregado, venda cruzada, renovação, máximo) e factor regional"},
    {"key": "plan_code_mapping", "label": "Planos do produto → plano atuarial", "help": "Segmento SAU/SAG e plano do Excel"},
    {"key": "coverage_code_mapping", "label": "Coberturas do produto → códigos atuariais", "help": "Cada código só pode estar numa cobertura"},
    {"key": "calculation_settings", "label": "Opções de cálculo",
     "help": "Valores por omissão do perfil atuarial e regra da idade de adesão em renovações"},
]


class ActuarialImportSerializer(serializers.Serializer):
    file = serializers.FileField(help_text=f"Excel .xlsx com a estrutura do modelo (máx. {MAX_WORKBOOK_BYTES // (1024 * 1024)} MB)")
    effectiveFrom = serializers.DateField()
    keepPublishedSettings = serializers.BooleanField(
        default=True,
        help_text=f"Mantém da versão publicada: {', '.join(KEPT_FROM_PUBLISHED)} (não vêm do Excel)",
    )
    dryRun = serializers.BooleanField(default=False, help_text="Só valida e mostra o resumo; não grava nada")


_IMPORT_PREVIEW = inline_serializer("ActuarialImportPreview", fields={
    "valid": serializers.BooleanField(),
    "keptFromPublished": serializers.ListField(child=serializers.CharField()),
    "summary": serializers.JSONField(),
})


class ActuarialAllowedValuesSerializer(serializers.Serializer):
    region = serializers.ListField(child=serializers.CharField())
    industry = serializers.ListField(child=serializers.CharField())
    crossSell = serializers.ListField(child=serializers.CharField())
    costSharing = serializers.JSONField()


ActuarialModelCatalogSerializer = inline_serializer("ActuarialModelCatalog", fields={
    "configKey": serializers.CharField(),
    "sections": serializers.ListField(child=serializers.JSONField()),
    "calculationSettings": serializers.JSONField(),
    "publishedVersion": serializers.JSONField(allow_null=True),
    "allowedValues": ActuarialAllowedValuesSerializer(),
    "import": serializers.JSONField(),
})


class ActuarialModelImportView(_ConfigPermissions, APIView):
    parser_classes = [MultiPartParser]

    @extend_schema(operation_id="importActuarialModelWorkbook", tags=["Configuration"],
                   summary="Importar o modelo atuarial de um Excel (cria uma versão DRAFT para aprovação)",
                   request={"multipart/form-data": ActuarialImportSerializer},
                   responses={200: _IMPORT_PREVIEW, 201: BusinessConfigurationSerializer})
    def post(self, request):
        s = ActuarialImportSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data
        upload = data["file"]
        if upload.size > MAX_WORKBOOK_BYTES:
            return Response({"detail": f"O ficheiro excede {MAX_WORKBOOK_BYTES // (1024 * 1024)} MB."}, status=400)
        content = upload.read()
        if data["dryRun"]:
            model, kept = build_from_upload(content=content, filename=upload.name, effective_from=data["effectiveFrom"],
                                            keep_published_settings=data["keepPublishedSettings"])
            return Response({"valid": True, "keptFromPublished": kept, "summary": summarize(model)})
        configuration, kept = import_actuarial_workbook(
            request, content=content, filename=upload.name, effective_from=data["effectiveFrom"],
            keep_published_settings=data["keepPublishedSettings"],
        )
        return Response({**BusinessConfigurationSerializer(configuration).data, "keptFromPublished": kept,
                         "summary": summarize(configuration.value_json)}, status=201)


class ActuarialModelTemplateView(_ConfigPermissions, APIView):
    @extend_schema(operation_id="downloadActuarialModelTemplate", tags=["Configuration"],
                   summary="Descarregar o Excel de referência do modelo atuarial (modelo para importação)",
                   responses={(200, XLSX): OpenApiTypes.BINARY})
    def get(self, request):
        return FileResponse(WORKBOOK_PATH.open("rb"), as_attachment=True, filename=WORKBOOK_PATH.name, content_type=XLSX)


class ActuarialModelCatalogView(_ConfigPermissions, APIView):
    @extend_schema(operation_id="getActuarialModelCatalog", tags=["Configuration"],
                   summary="Secções editáveis e opções de cálculo do modelo atuarial",
                   responses=ActuarialModelCatalogSerializer)
    def get(self, request):
        published = BusinessConfigurationResolver.get(CONFIG_KEY, effective_date=date.today())
        model = published.value_json if published is not None and isinstance(published.value_json, dict) else {}
        adjustments = model.get("adjustment_assumptions") or {}
        cost_sharing = adjustments.get("cost_sharing") or {}
        return Response({
            "configKey": CONFIG_KEY,
            "sections": SECTIONS,
            "calculationSettings": {
                "entryAgeOnRenewal": [{"value": k, "label": v} for k, v in ENTRY_AGE_ON_RENEWAL.items()],
                "profileFields": ["region", "industry", "adhesion", "participationRate", "crossSell",
                                  "noClaimsRenewal", "costSharing"],
                "adhesion": list(ADHESION),
                "recommended": RECOMMENDED_CALCULATION_SETTINGS,
            },
            # Valores válidos no modelo publicado em vigor (vazios se não houver).
            "publishedVersion": {"id": str(published.id), "version": published.version_no} if published else None,
            "allowedValues": {
                "region": [r.get("region") for r in adjustments.get("regional_factors") or []],
                "industry": [r.get("industry") for r in model.get("industry_factors") or []],
                "crossSell": [r.get("product") for r in adjustments.get("cross_sell_discounts") or []],
                "costSharing": {table: [r.get("value") for r in rows] for table, rows in cost_sharing.items()},
            },
            "import": {"maxBytes": MAX_WORKBOOK_BYTES, "keptFromPublished": list(KEPT_FROM_PUBLISHED),
                       "template": "/api/v1/business-config/actuarial-model/template"},
        })
