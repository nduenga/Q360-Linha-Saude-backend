from django.apps import AppConfig


class FoundationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.foundation"
    label = "foundation"

    def ready(self) -> None:
        from apps.foundation.observability import configure

        configure()

        # As fórmulas usam constantes e tabelas do fornecedor; fora de um
        # cálculo (que as carrega uma vez), são lidas a pedido.
        from apps.foundation.application import platform_inputs_loader
        from apps.foundation.domain import platform_inputs

        platform_inputs.set_provider(platform_inputs_loader.load)
