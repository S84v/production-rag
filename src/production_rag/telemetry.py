from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
)

SERVICE_NAME = "production-rag"


def configure_telemetry(app) -> None:
    resource = Resource.create({"service.name": SERVICE_NAME})

    provider = TracerProvider(resource=resource)

    provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app)


def get_tracer():
    return trace.get_tracer(SERVICE_NAME)
