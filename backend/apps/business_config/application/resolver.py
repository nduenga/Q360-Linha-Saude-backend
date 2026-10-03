from django.db import models
from django.utils import timezone
from apps.foundation.application.context import CurrentTenantProvider
from apps.business_config.infrastructure.models import BusinessConfiguration
class BusinessConfigurationResolver:
    @staticmethod
    def get(config_key,effective_date=None):
        d=effective_date or timezone.localdate()
        tenant=CurrentTenantProvider.require().value
        return BusinessConfiguration.objects.filter(config_key=config_key,tenant_id=tenant,status="PUBLISHED",effective_from__lte=d).filter(models.Q(effective_to__isnull=True)|models.Q(effective_to__gte=d)).order_by("-version_no").first()
