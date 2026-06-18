"""OpenTelemetry tracing setup.

Phase 1 wires a ``TracerProvider`` that exports spans over OTLP/gRPC to the
collector (which, for now, just logs them to stdout). A console exporter can be
enabled for local debugging. Metrics and auto-instrumentation arrive in Phase 6.
"""

from __future__ import annotations

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
)

from src import __version__


def setup_tracing(
    *,
    service_name: str,
    endpoint: str | None,
    console: bool = False,
    set_global: bool = True,
) -> TracerProvider:
    """Build and (optionally) install a global ``TracerProvider``.

    Args:
        service_name: value for the ``service.name`` resource attribute.
        endpoint: OTLP/gRPC collector endpoint (e.g. ``http://localhost:4317``).
            When falsy, no OTLP exporter is attached (useful for tests/CI).
        console: also export spans to stdout (local debugging).
        set_global: register the provider as the global tracer provider.
    """
    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": __version__,
        }
    )
    provider = TracerProvider(resource=resource)

    if console:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    if endpoint:
        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True))
        )

    if set_global:
        trace.set_tracer_provider(provider)

    return provider


def get_tracer(name: str) -> trace.Tracer:
    """Return a tracer from the globally configured provider."""
    return trace.get_tracer(name)
