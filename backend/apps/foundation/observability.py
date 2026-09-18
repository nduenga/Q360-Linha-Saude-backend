"""Safe OpenTelemetry façade used by the HTTP and application layers.

The façade deliberately has a no-op implementation when telemetry is not
enabled. This keeps the business modules independent from a vendor SDK while
still producing real OpenTelemetry spans once the optional dependencies and
OTLP endpoint are configured.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

from django.conf import settings

_configured = False


def configure() -> None:
    """Install one OTLP tracer provider when observability is enabled.

    Kept idempotent because Django's autoreloader can import app configs more
    than once. Configuration failures intentionally degrade to no-op logging
    rather than preventing the underwriting API from starting.
    """
    global _configured
    if _configured or not settings.Q360_OTEL_ENABLED:
        return
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        return

    provider = TracerProvider(
        resource=Resource.create({"service.name": settings.Q360_OTEL_SERVICE_NAME})
    )
    kwargs = {}
    if settings.Q360_OTEL_EXPORTER_OTLP_ENDPOINT:
        kwargs["endpoint"] = settings.Q360_OTEL_EXPORTER_OTLP_ENDPOINT
        kwargs["insecure"] = not settings.Q360_OTEL_EXPORTER_OTLP_ENDPOINT.startswith("https://")
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(**kwargs)))
    trace.set_tracer_provider(provider)
    _configured = True


@dataclass
class _NoopSpan:
    def set_status_code(self, _status_code: int) -> None:
        return None


def _tracer():
    if not settings.Q360_OTEL_ENABLED:
        return None
    try:
        from opentelemetry import trace
    except ImportError:
        return None
    return trace.get_tracer(settings.Q360_OTEL_SERVICE_NAME)


@contextmanager
def request_span(method: str, path: str) -> Iterator[_NoopSpan | object]:
    tracer = _tracer()
    if tracer is None:
        yield _NoopSpan()
        return

    # Do not use raw URL/query string as an attribute: path_info excludes the
    # query but may still contain ids. Keep a generic route marker only.
    with tracer.start_as_current_span("http.request") as span:
        span.set_attribute("http.request.method", method)
        span.set_attribute("url.path", _normalise_path(path))

        class _OtelSpan:
            def set_status_code(self, status_code: int) -> None:
                span.set_attribute("http.response.status_code", status_code)

        yield _OtelSpan()


def _normalise_path(path: str) -> str:
    """Avoid emitting resource UUIDs into telemetry."""
    import re

    return re.sub(
        r"[0-9a-fA-F]{8}-[0-9a-fA-F-]{27,}",
        "{id}",
        path,
    )
