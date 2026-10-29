from rest_framework import serializers
from apps.business_config.domain.catalog import CATALOG_BY_KEY
from apps.business_config.infrastructure.models import BusinessConfiguration,BusinessConfigurationDocument
class BusinessConfigurationSerializer(serializers.ModelSerializer):
    configKey=serializers.CharField(source="config_key");version=serializers.IntegerField(source="version_no")
    effectiveFrom=serializers.DateField(source="effective_from");effectiveTo=serializers.DateField(source="effective_to",allow_null=True)
    value=serializers.JSONField(source="value_json");metadata=serializers.JSONField(source="metadata_json")
    rowVersion=serializers.IntegerField(source="row_version")
    class Meta:
        model=BusinessConfiguration
        fields=["id","configKey","version","effectiveFrom","effectiveTo","status","value","metadata","checksum","created_by","approved_by","published_by","submitted_at","approved_at","published_at","rowVersion"]
class BusinessConfigurationWriteSerializer(serializers.Serializer):
    configKey=serializers.CharField(max_length=120,help_text="Chave do catálogo (geral) ou `<chave>@<id do produto>` (versão do produto)");value=serializers.JSONField()
    effectiveFrom=serializers.DateField();effectiveTo=serializers.DateField(required=False,allow_null=True)
    metadata=serializers.JSONField(required=False,default=dict)
    def validate_configKey(self,value):
        from apps.business_config.domain.scope import base_key
        if base_key(value) not in CATALOG_BY_KEY:
            raise serializers.ValidationError(f"«{value}» não é uma configuração do catálogo.")
        return value
class BusinessConfigurationUpdateSerializer(serializers.Serializer):
    value=serializers.JSONField();effectiveFrom=serializers.DateField(required=False);effectiveTo=serializers.DateField(required=False,allow_null=True);metadata=serializers.JSONField(required=False);rowVersion=serializers.IntegerField(min_value=0,required=False)
class BusinessConfigurationActionSerializer(serializers.Serializer):
    action=serializers.ChoiceField(choices=("submit","retire"))
class BusinessConfigurationDocumentSerializer(serializers.ModelSerializer):
    documentType=serializers.CharField(source="document_type");originalFilename=serializers.CharField(source="original_filename")
    class Meta:
        model=BusinessConfigurationDocument
        fields=["id","documentType","originalFilename","content_type","checksum","uploaded_by","created_at"]
class BusinessConfigurationListSerializer(serializers.Serializer):
    items=BusinessConfigurationSerializer(many=True)
class BusinessConfigurationDocumentListSerializer(serializers.Serializer):
    items=BusinessConfigurationDocumentSerializer(many=True)
class BusinessConfigurationCatalogEntrySerializer(serializers.Serializer):
    key=serializers.CharField();category=serializers.CharField();label=serializers.CharField()
    priority=serializers.CharField();value_type=serializers.CharField()
    formSchema=serializers.JSONField();requiresBusinessConfirmation=serializers.BooleanField()
class BusinessConfigurationCatalogSerializer(serializers.Serializer):
    items=BusinessConfigurationCatalogEntrySerializer(many=True)
class BusinessConfigurationDocumentUploadSerializer(serializers.Serializer):
    file=serializers.FileField();documentType=serializers.CharField(required=False)

class BusinessConfigurationRejectSerializer(serializers.Serializer):
    reason=serializers.CharField(min_length=5,max_length=1000)
class BusinessConfigurationHistoryEntrySerializer(serializers.Serializer):
    action=serializers.CharField();actorId=serializers.CharField(allow_null=True);occurredAt=serializers.CharField(allow_null=True)
    status=serializers.CharField(allow_null=True);checksum=serializers.CharField(allow_null=True);reason=serializers.CharField(allow_null=True)
class BusinessConfigurationHistorySerializer(serializers.Serializer):
    configurationId=serializers.UUIDField();items=BusinessConfigurationHistoryEntrySerializer(many=True)
class FormulaSubmitSerializer(serializers.Serializer):
    changeReason=serializers.CharField(required=False,allow_blank=True,max_length=1000)
class FormulaTestSerializer(serializers.Serializer):
    expression=serializers.CharField(max_length=500,allow_blank=False)
    variables=serializers.DictField(child=serializers.JSONField(),required=False,default=dict)
class FormulaValidateSerializer(serializers.Serializer):
    value=serializers.JSONField()
class FormulaSimulateSerializer(serializers.Serializer):
    totalAmount=serializers.DecimalField(max_digits=18,decimal_places=2,min_value=0,help_text="Valor de partida: total da cotação (QUOTE) ou prémio da pessoa (PERSON)")
    membersCount=serializers.IntegerField(min_value=0,max_value=100000)
    stage=serializers.ChoiceField(choices=["QUOTE","PERSON"],default="QUOTE")
    age=serializers.IntegerField(min_value=0,max_value=130,required=False,allow_null=True,default=None,help_text="Obrigatória na fase PERSON")
    def validate(self,attrs):
        if attrs["stage"]=="PERSON" and attrs.get("age") is None:
            raise serializers.ValidationError({"age":"Indique a idade para simular fórmulas por pessoa."})
        return attrs
