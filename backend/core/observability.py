"""
Observability Module — OpenTelemetry Tracing, Metrics, and Logging Setup

Central configuration for exporting telemetry to OpenTelemetry Collector,
which routes:
- Distributed Traces -> Tempo
- Metrics -> Prometheus
- Logs -> Loki
- Visualized in Grafana
"""

import logging
import os
import time
from typing import Any, Optional

try:
    from opentelemetry import _logs, metrics, trace
    from opentelemetry.exporter.otlp.proto.grpc._log_exporter import (
        OTLPLogExporter as GRPCLogExporter,
    )
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
        OTLPMetricExporter as GRPCMetricExporter,
    )
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
        OTLPSpanExporter as GRPCSpanExporter,
    )
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.logging import LoggingInstrumentor
    from opentelemetry.instrumentation.redis import RedisInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
    _HAS_OTEL = True
except ImportError:
    _HAS_OTEL = False

_initialized = False
_http_requests_counter = None
_inference_jobs_counter = None
_inference_duration_histogram = None


def setup_observability(
    service_name: str | None = None,
    otlp_endpoint: str | None = None,
) -> None:
    """
    Initialize OpenTelemetry SDK (TracerProvider, MeterProvider, LoggerProvider)
    and instrument standard libraries (Redis, SQLAlchemy, Logging).

    Args:
        service_name: Unique name for this component (e.g., ai-ecosystem-backend)
        otlp_endpoint: OTLP gRPC endpoint (e.g., http://otel-collector:4317)
    """
    global _initialized, _http_requests_counter, _inference_jobs_counter, _inference_duration_histogram
    if not _HAS_OTEL or _initialized:
        return

    # Determine service name & endpoint
    name = (
        service_name
        or os.environ.get("OTEL_SERVICE_NAME")
        or "ai-ecosystem-backend"
    )
    endpoint = (
        otlp_endpoint
        or os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        or "http://localhost:4317"
    )

    resource = Resource.create(
        {
            "service.name": name,
            "service.version": "1.0.0",
            "deployment.environment": os.environ.get("ENVIRONMENT", "development"),
        }
    )

    # ── 1. Distributed Tracing (Tempo) ──
    span_exporter = GRPCSpanExporter(endpoint=endpoint, insecure=True)
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
    trace.set_tracer_provider(tracer_provider)

    # ── 2. Metrics (Prometheus via OTel Collector) ──
    metric_exporter = GRPCMetricExporter(endpoint=endpoint, insecure=True)
    metric_reader = PeriodicExportingMetricReader(
        metric_exporter,
        export_interval_millis=5000,
    )
    meter_provider = MeterProvider(
        resource=resource,
        metric_readers=[metric_reader],
    )
    metrics.set_meter_provider(meter_provider)

    meter = metrics.get_meter("ai_ecosystem_meter", "1.0.0")
    _http_requests_counter = meter.create_counter(
        name="ai_ecosystem_http_requests_total",
        description="Total number of HTTP requests processed",
        unit="1",
    )
    _inference_jobs_counter = meter.create_counter(
        name="ai_ecosystem_inference_jobs_total",
        description="Total number of inference jobs executed",
        unit="1",
    )
    _inference_duration_histogram = meter.create_histogram(
        name="ai_ecosystem_inference_duration_seconds",
        description="Duration of inference jobs in seconds",
        unit="s",
    )

    # ── 3. Logs (Loki via OTel Collector) & Log Correlation ──
    log_exporter = GRPCLogExporter(endpoint=endpoint, insecure=True)
    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))
    _logs.set_logger_provider(logger_provider)

    # Attach OTLP logging handler to root logger
    otel_log_handler = LoggingHandler(
        level=logging.INFO,
        logger_provider=logger_provider,
    )
    root_logger = logging.getLogger()
    root_logger.addHandler(otel_log_handler)

    # Instrument python logging so formatted logs contain trace_id and span_id
    LoggingInstrumentor().instrument(set_logging_format=True)

    # ── 4. Auto-instrument Redis and SQLAlchemy ──
    try:
        RedisInstrumentor().instrument()
    except Exception as e:
        logging.warning(f"Redis auto-instrumentation skipped/failed: {e}")

    try:
        from core.database import engine
        SQLAlchemyInstrumentor().instrument(engine=engine)
    except Exception as e:
        logging.warning(f"SQLAlchemy auto-instrumentation skipped/failed: {e}")

    _initialized = True
    logging.info(
        f"🔭 Observability initialized for '{name}' -> OTLP: {endpoint}"
    )


def instrument_fastapi(app: Any) -> None:
    """Instrument a FastAPI application instance."""
    if not _HAS_OTEL:
        return
    try:
        FastAPIInstrumentor.instrument_app(app)
        logging.info("✅ FastAPI application instrumented with OpenTelemetry")
    except Exception as e:
        logging.warning(f"⚠️ FastAPI instrumentation failed: {e}")


def inject_trace_context(carrier: dict | None = None) -> dict:
    """
    Inject current active trace context into a dict carrier for W3C trace propagation.
    Useful for propagating trace context across ARQ / Redis queues.
    """
    if carrier is None:
        carrier = {}
    TraceContextTextMapPropagator().inject(carrier)
    return carrier


def extract_trace_context(carrier: dict | None):
    """
    Extract trace context from a dict carrier (W3C traceparent/tracestate).
    Returns an OpenTelemetry Context that can be used as parent context.
    """
    if not carrier:
        return None
    return TraceContextTextMapPropagator().extract(carrier)


def record_inference_job(model_name: str, status: str, duration: float) -> None:
    """Record metrics for an executed inference job."""
    global _inference_jobs_counter, _inference_duration_histogram
    if _inference_jobs_counter:
        _inference_jobs_counter.add(
            1,
            {"model_name": model_name, "status": status},
        )
    if _inference_duration_histogram:
        _inference_duration_histogram.record(
            duration,
            {"model_name": model_name, "status": status},
        )
