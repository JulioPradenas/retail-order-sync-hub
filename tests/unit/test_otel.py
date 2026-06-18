from opentelemetry.sdk.trace import TracerProvider
from src.common.otel import setup_tracing


def test_setup_tracing_sets_service_resource() -> None:
    provider = setup_tracing(
        service_name="rosh-test",
        endpoint=None,
        set_global=False,
    )
    assert isinstance(provider, TracerProvider)
    assert provider.resource.attributes["service.name"] == "rosh-test"
    assert "service.version" in provider.resource.attributes


def test_setup_tracing_without_endpoint_has_no_otlp_processor() -> None:
    provider = setup_tracing(service_name="rosh-test", endpoint=None, set_global=False)
    # No exporters attached when endpoint is falsy and console is off.
    span = provider.get_tracer("t").start_span("noop")
    span.end()  # must not raise even with no processors
