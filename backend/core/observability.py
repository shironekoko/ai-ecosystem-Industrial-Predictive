"""
Observability — OpenTelemetry (trace + metric + log) → OTel Collector → Tempo / Prometheus / Loki → Grafana

เปิดใช้เมื่อมี OTEL_EXPORTER_OTLP_ENDPOINT (ตั้งใน compose.observability.yml) — ถ้าไม่ตั้ง ทุกฟังก์ชันในไฟล์นี้เป็น no-op
ระบบหลักจึงรันได้เหมือนเดิมโดยไม่ต้องมีชุด observability

สิ่งที่ส่งออก
- trace: ทุก HTTP request (FastAPI) + SQLAlchemy + Redis + span ของงานหลัก (ถอดดอก → ถ่ายภาพ/วัด VB, retrain ข้าม ARQ)
- log: logger ของ Python ตั้งแต่ระดับ INFO พร้อม trace_id (ดูใน Loki แล้วกดไป trace ได้)
- metric: ของ HTTP (FastAPI instrumentation) + ของระบบนี้ตาม METRICS ด้านล่าง + gauge ที่ลงทะเบียนด้วย register_gauge()
  ชื่อใน Prometheus = "ai_ecosystem_" + ชื่อ (จุด → _) + หน่วย (เช่น _seconds) + _total สำหรับตัวนับ
"""

from __future__ import annotations

import contextlib
import itertools
import logging
import os
import time
from typing import Any, Callable, Iterable

try:
    from opentelemetry import _logs, metrics, trace
    from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.logging import LoggingInstrumentor
    from opentelemetry.instrumentation.redis import RedisInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    from opentelemetry.instrumentation.utils import suppress_instrumentation
    from opentelemetry.metrics import CallbackOptions, Observation
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

log = logging.getLogger("observability")

# ── metric ของระบบนี้: ชื่อ → (ชนิด, หน่วย, คำอธิบาย, ขอบ bucket ของ histogram / ค่า label ที่ตั้งตัวนับเป็น 0 ไว้ก่อน) ──
# ตัวนับของเหตุการณ์ที่เกิดไม่บ่อย (ถอดดอก, ตรวจใบมีด, retrain) ต้องมี series ค่า 0 ตั้งแต่เริ่ม
# ไม่เช่นนั้น increase() ของ Prometheus จะไม่นับครั้งแรก (series เริ่มที่ 1)
_SEC = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]
_M = ["M1", "M2", "M3"]
METRICS: dict[str, tuple[str, str, str, Any]] = {
    # Time series — RUL ดอกกัด (GRU)
    "tool_rul.inference.duration": ("histogram", "s", "เวลาพยากรณ์ RUL ต่อ 1 รัน (สร้างหน้าต่างอินพุต + GRU)", _SEC),
    "tool_rul.predictions": ("counter", "", "จำนวนการพยากรณ์ RUL แยกตามคำแนะนำ",
                             dict(machine=_M, recommendation=["OK", "WATCH", "PLAN_REPLACEMENT", "REPLACE_NOW"])),
    "tool_rul.tool_removals": ("counter", "", "จำนวนดอกที่ถูกถอด (ผู้ควบคุมถอด / ข้อมูลหมด)",
                               dict(machine=_M, reason=["REPLACED_BY_OPERATOR", "DATASET_END"])),
    # Vision — วัด VB จากภาพใบมีด
    "tool_vision.inference.duration": ("histogram", "s", "เวลาวัด VB จากภาพ 4 ใบมีดของ 1 ดอก (CPU)", _SEC),
    "tool_vision.inspections": ("counter", "", "จำนวนงานตรวจใบมีด แยกตามผล AI ระดับดอก",
                                dict(machine=_M, verdict=["OK", "MONITOR", "REPLACE"])),
    "tool_vision.blade_reviews": ("counter", "", "จำนวนใบมีดที่ผู้ตรวจยืนยัน แยกตามที่มา (AI / MANUAL)",
                                  dict(source=["AI", "MANUAL"])),
    "tool_vision.ai_abs_error": ("histogram", "um", "|VB ที่ AI วัด − VB ที่วัดจริง| ของใบที่วัดจริง",
                                 [5, 10, 15, 20, 30, 40, 60, 80, 120, 200]),
    "tool_vision.model.changes": ("counter", "", "การเปลี่ยนแบบจำลองวัด VB (promote / reject / activate)",
                                  dict(action=["promote", "reject", "activate"])),
    "tool_vision.retrain.jobs": ("counter", "", "งาน retrain ที่ worker ทำเสร็จ แยกตามผล gate",
                                 dict(outcome=["gate_passed", "gate_failed", "error"])),
    "tool_vision.retrain.duration": ("histogram", "s", "เวลาที่ใช้ retrain 1 งาน (GPU)",
                                     [30, 60, 120, 300, 600, 1200, 1800, 3600, 7200]),
}

_initialized = False
_meter = None
_tracer = None
_instruments: dict[str, Any] = {}


def enabled() -> bool:
    return _initialized


def setup_observability(service_name: str | None = None, otlp_endpoint: str | None = None) -> None:
    """เริ่ม TracerProvider / MeterProvider / LoggerProvider และ instrument Redis + SQLAlchemy + logging

    ไม่ทำอะไรถ้าไม่มี endpoint (OTEL_EXPORTER_OTLP_ENDPOINT) หรือไม่ได้ติดตั้งแพ็กเกจ OpenTelemetry
    """
    global _initialized, _meter, _tracer
    endpoint = otlp_endpoint or os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not _HAS_OTEL or _initialized or not endpoint:
        return
    name = os.environ.get("OTEL_SERVICE_NAME") or service_name or "ai-ecosystem-backend"
    resource = Resource.create({
        "service.name": name,
        "service.version": "1.0.0",
        "deployment.environment": os.environ.get("ENVIRONMENT", "development"),
    })

    # trace → Tempo
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True)))
    trace.set_tracer_provider(tracer_provider)
    _tracer = trace.get_tracer("ai_ecosystem")

    # metric → Prometheus (collector เปิด :8889 ให้ Prometheus ดึง)
    reader = PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=endpoint, insecure=True), export_interval_millis=10_000)
    metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[reader]))
    _meter = metrics.get_meter("ai_ecosystem", "1.0.0")
    for key, (kind, unit, desc, extra) in METRICS.items():
        if kind == "counter":
            _instruments[key] = c = _meter.create_counter(key, unit=unit, description=desc)
            for combo in itertools.product(*extra.values()):
                c.add(0, dict(zip(extra.keys(), combo)))
        else:
            _instruments[key] = _meter.create_histogram(key, unit=unit, description=desc,
                                                        explicit_bucket_boundaries_advisory=extra)

    # log → Loki: ใส่ trace_id/span_id ใน record แล้วส่งทาง OTLP (ไม่เพิ่ม handler บน console จึงไม่ซ้ำกับ log เดิม)
    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter(endpoint=endpoint, insecure=True)))
    _logs.set_logger_provider(logger_provider)
    LoggingInstrumentor().instrument(set_logging_format=False)
    root = logging.getLogger()
    root.addHandler(LoggingHandler(level=logging.INFO, logger_provider=logger_provider))
    if root.level > logging.INFO or root.level == logging.NOTSET:
        root.setLevel(logging.INFO)

    try:
        RedisInstrumentor().instrument()
    except Exception as e:
        log.warning("Redis instrumentation skipped: %s", e)
    try:
        from core.database import engine
        SQLAlchemyInstrumentor().instrument(engine=engine)
    except Exception as e:
        log.warning("SQLAlchemy instrumentation skipped: %s", e)

    _initialized = True
    log.info("observability on: service=%s → OTLP %s", name, endpoint)


def instrument_fastapi(app: Any) -> None:
    """HTTP trace + metric ของทุก endpoint (ไม่นับ health check และสตรีม SSE ที่เปิดค้างไว้)"""
    if not _initialized:
        return
    try:
        FastAPIInstrumentor.instrument_app(app, excluded_urls="health,/stream")
    except Exception as e:
        log.warning("FastAPI instrumentation failed: %s", e)


# ── metric ──
def inc(name: str, value: float = 1, **attrs) -> None:
    """เพิ่มตัวนับใน METRICS (no-op ถ้าไม่ได้เปิด)"""
    inst = _instruments.get(name)
    if inst is not None:
        inst.add(value, {k: str(v) for k, v in attrs.items()})


def observe(name: str, value: float, **attrs) -> None:
    """บันทึกค่าลง histogram ใน METRICS (no-op ถ้าไม่ได้เปิด)"""
    inst = _instruments.get(name)
    if inst is not None:
        inst.record(float(value), {k: str(v) for k, v in attrs.items()})


@contextlib.contextmanager
def timed(name: str, **attrs):
    """จับเวลาบล็อกโค้ดลง histogram ชื่อ name (วินาที)"""
    t0 = time.perf_counter()
    try:
        yield
    finally:
        observe(name, time.perf_counter() - t0, **attrs)


def register_gauge(name: str, description: str, unit: str,
                   read: Callable[[], Iterable[tuple[float, dict]]]) -> None:
    """gauge ที่อ่านค่าปัจจุบันทุกครั้งที่ส่งออก — read() คืน [(ค่า, {label: ค่า}), ...]"""
    if _meter is None:
        return

    def callback(_: CallbackOptions):
        try:
            with suppress_instrumentation():        # query ที่อ่านค่า gauge ทุก 10 วินาทีไม่ต้องเป็น trace
                return [Observation(float(v), {k: str(x) for k, x in a.items()}) for v, a in read() if v is not None]
        except Exception as e:                      # อ่านค่าไม่ได้ (เช่น DB หลุด) → ข้ามรอบนี้ ไม่ให้ exporter ล้ม
            log.debug("gauge %s skipped: %s", name, e)
            return []

    _meter.create_observable_gauge(name, callbacks=[callback], unit=unit, description=description)


# ── trace ──
@contextlib.contextmanager
def span(name: str, parent: dict | None = None, **attrs):
    """span ของงานหลัก — parent = carrier จาก inject_trace_context() (เช่น ส่งข้ามคิว ARQ)"""
    if _tracer is None:
        yield None
        return
    ctx = TraceContextTextMapPropagator().extract(parent) if parent else None
    with _tracer.start_as_current_span(name, context=ctx, attributes={k: str(v) for k, v in attrs.items()}) as s:
        yield s


def inject_trace_context() -> dict:
    """trace context ปัจจุบัน (W3C traceparent) สำหรับส่งไปกับงานในคิว — {} ถ้าไม่ได้เปิด"""
    carrier: dict = {}
    if _initialized:
        TraceContextTextMapPropagator().inject(carrier)
    return carrier
