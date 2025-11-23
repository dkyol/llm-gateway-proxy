import os
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

def setup_logging():
    if os.getenv("HELICONE_API_KEY"):
        os.environ["HELICONE_API_KEY"] = os.getenv("HELICONE_API_KEY")

    #if os.getenv("ARIZE_PHOENIX_PROJECT_NAME"):
        #os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "https://api.phoenix.arize.com/v1/traces"