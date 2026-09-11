from django.conf import settings


def test_drf_is_configured():
    assert "rest_framework" in settings.INSTALLED_APPS
    assert settings.REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] == [
        "rest_framework.renderers.JSONRenderer"
    ]
