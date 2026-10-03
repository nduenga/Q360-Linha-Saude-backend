from django.apps import AppConfig


class BusinessConfigConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.business_config"
    label = "business_config"

    def ready(self):
        from apps.business_config.application import role_permissions

        role_permissions.register()
