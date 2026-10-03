from django.db import models
import uuid
from apps.foundation.infrastructure.models import Tenant
from apps.foundation.infrastructure.tenant_scoping import TenantScopedModel
class BusinessConfiguration(TenantScopedModel):
    STATUS_CHOICES=(("DRAFT","DRAFT"),("PENDING_APPROVAL","PENDING_APPROVAL"),("PUBLISHED","PUBLISHED"),("RETIRED","RETIRED"))
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    tenant=models.ForeignKey(Tenant,on_delete=models.DO_NOTHING,db_column="tenant_id")
    config_key=models.CharField(max_length=120); version_no=models.IntegerField()
    effective_from=models.DateField(); effective_to=models.DateField(null=True,blank=True)
    status=models.CharField(max_length=30,choices=STATUS_CHOICES,default="DRAFT")
    value_json=models.JSONField(default=dict); metadata_json=models.JSONField(default=dict)
    checksum=models.CharField(max_length=128,null=True,blank=True)
    created_by=models.CharField(max_length=200); approved_by=models.CharField(max_length=200,null=True,blank=True)
    published_by=models.CharField(max_length=200,null=True,blank=True)
    submitted_at=models.DateTimeField(null=True,blank=True); approved_at=models.DateTimeField(null=True,blank=True); published_at=models.DateTimeField(null=True,blank=True)
    created_at=models.DateTimeField(auto_now_add=True); updated_at=models.DateTimeField(auto_now=True)
    row_version=models.BigIntegerField(default=0)
    class Meta:
        managed=False
        db_table="business_configuration"
class BusinessConfigurationDocument(TenantScopedModel):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    tenant=models.ForeignKey(Tenant,on_delete=models.DO_NOTHING,db_column="tenant_id")
    configuration=models.ForeignKey(BusinessConfiguration,on_delete=models.CASCADE,related_name="documents",db_column="configuration_id")
    document_type=models.CharField(max_length=80); original_filename=models.CharField(max_length=255)
    content_type=models.CharField(max_length=120,null=True,blank=True); storage_key=models.TextField()
    checksum=models.CharField(max_length=128,null=True,blank=True); metadata_json=models.JSONField(default=dict)
    uploaded_by=models.CharField(max_length=200); created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        managed=False
        db_table="business_configuration_document"
