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
    configKey=serializers.ChoiceField(choices=list(CATALOG_BY_KEY));value=serializers.JSONField()
    effectiveFrom=serializers.DateField();effectiveTo=serializers.DateField(required=False,allow_null=True)
    metadata=serializers.JSONField(required=False,default=dict)
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
