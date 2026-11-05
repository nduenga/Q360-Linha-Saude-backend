from django.apps import AppConfig


class CustomerPortalConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.customer_portal"
    label = "customer_portal"

    def ready(self) -> None:
        from django.core import checks

        from apps.customer_portal.application.email_config import check_email_settings

        checks.register(check_email_settings, "q360")
