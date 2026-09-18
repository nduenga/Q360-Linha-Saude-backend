from django.apps import AppConfig


class FoundationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.foundation"
    label = "foundation"

    def ready(self) -> None:
        from apps.foundation.observability import configure

        configure()
