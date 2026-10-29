from django.db import models
from django.utils import timezone
from apps.foundation.application.context import CurrentTenantProvider
from apps.business_config.domain.scope import is_scopable, product_key
from apps.business_config.infrastructure.models import BusinessConfiguration
class BusinessConfigurationResolver:
    @staticmethod
    def get(config_key,effective_date=None,product_id=None):
        """Versão PUBLISHED vigente. Com `product_id`, a do produto
        (`<chave>@<id>`) prevalece sobre a geral (ver `domain/scope.py`)."""
        if product_id is not None and is_scopable(config_key):
            scoped=BusinessConfigurationResolver._published(product_key(config_key,product_id),effective_date)
            if scoped is not None:
                return scoped
        return BusinessConfigurationResolver._published(config_key,effective_date)
    @staticmethod
    def _published(config_key,effective_date=None):
        d=effective_date or timezone.localdate()
        tenant=CurrentTenantProvider.require().value
        return BusinessConfiguration.objects.filter(config_key=config_key,tenant_id=tenant,status="PUBLISHED",effective_from__lte=d).filter(models.Q(effective_to__isnull=True)|models.Q(effective_to__gte=d)).order_by("-version_no").first()
