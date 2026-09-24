"""
Inference Worker Tasks — ARQ task functions สำหรับ Inference Jobs

โหลด trained model จาก MLflow Model Registry แล้วรัน inference
ผลลัพธ์ถูกเก็บใน Redis ผ่าน ARQ job result โดยอัตโนมัติ

รัน worker:
    cd backend
    uv run arq app.features.workers.inference_tasks.InferenceWorkerSettings

    หรือผ่าน Docker:
    docker compose up inference-worker
"""

import logging
import os
import time
from typing import Any

from opentelemetry import trace

from core.observability import (
    extract_trace_context,
    record_inference_job,
    setup_observability,
)
from core.redis_client import get_arq_redis_settings

logger = logging.getLogger("inference-worker")


async def run_inference(
    ctx: dict,
    model_name: str,
    model_version: str,
    input_data: dict[str, Any],
    _trace_carrier: dict[str, str] | None = None,
) -> Any:
    """
    โหลดโมเดลจาก MLflow แล้วรัน inference

    Flow:
        1. ดึง OpenTelemetry trace context ข้าม Redis
        2. โหลด model ด้วย mlflow.pyfunc.load_model
        3. เตรียม input data ให้เหมาะกับ model type
        4. รัน model.predict()
        5. Return ผลลัพธ์ (ARQ เก็บใน Redis อัตโนมัติ)
    """
    # ── 1. OpenTelemetry Distributed Trace Context ──
    carrier = _trace_carrier or (
        input_data.get("_trace_carrier") if isinstance(input_data, dict) else None
    )
    parent_ctx = extract_trace_context(carrier) if carrier else None
    tracer = trace.get_tracer("ai-ecosystem.inference-worker")
    start_time = time.time()
    job_id = ctx.get("job_id", "unknown")

    with tracer.start_as_current_span("run_inference", context=parent_ctx) as span:
        span.set_attribute("model.name", model_name)
        span.set_attribute("model.version", model_version)
        span.set_attribute("job.id", str(job_id))

        # ── Compatibility patch for MLflow 2.16 with newer transformers ──
        try:
            import transformers.utils.import_utils as iu
            if not getattr(iu, "_mlflow_patched", False):
                orig_getattr = iu._LazyModule.__getattr__
                def patched_getattr(self, name):
                    if name.endswith("Pipeline") and name != "TokenClassificationPipeline":
                        class DummyPipeline:
                            pass
                        return DummyPipeline
                    return orig_getattr(self, name)
                iu._LazyModule.__getattr__ = patched_getattr
                iu._mlflow_patched = True
        except Exception:
            pass

        import mlflow

        logger.info(f"🔮 [Job {job_id}] เริ่ม inference: model={model_name}, version={model_version}")
        print(f"🔮 [Job {job_id}] เริ่ม inference: model={model_name}, version={model_version}")

        try:
            # ── 1. ตั้ง MLflow tracking URI ──
            mlflow_tracking_uri = os.environ.get(
                "MLFLOW_TRACKING_URI", "http://localhost:5001"
            )
            mlflow.set_tracking_uri(mlflow_tracking_uri)
            logger.info(f"  📡 MLflow tracking URI: {mlflow_tracking_uri}")

            # ── 2. สร้าง model URI ──
            if model_version == "latest":
                # ใช้ MLflow client หา version ล่าสุดของ registered model
                client = mlflow.MlflowClient()
                versions = client.search_model_versions(f"name='{model_name}'")
                if not versions:
                    err_msg = f"ไม่พบโมเดล '{model_name}' ใน MLflow Model Registry"
                    logger.warning(f"  ⚠️ {err_msg}")
                    record_inference_job(model_name, "failed", time.time() - start_time)
                    return {"error": err_msg}
                latest_version = max(versions, key=lambda v: int(v.version))
                model_uri = f"models:/{model_name}/{latest_version.version}"
                logger.info(f"  📦 ใช้ version ล่าสุด: {latest_version.version}")
            else:
                model_uri = f"models:/{model_name}/{model_version}"

            logger.info(f"  📦 Model URI: {model_uri}")

            # ── 3. โหลด model ──
            model = mlflow.pyfunc.load_model(model_uri)
            logger.info("  ✅ โหลดโมเดลสำเร็จ")

            # ── 4. เตรียม input และรัน inference ──
            text = input_data.get("text", "")
            if not text:
                err_msg = "ต้องระบุ 'text' ใน input_data"
                logger.warning(f"  ⚠️ {err_msg}")
                record_inference_job(model_name, "failed", time.time() - start_time)
                return {"error": err_msg}

            prediction = model.predict([text])

            # แปลง prediction เป็น serializable format
            if hasattr(prediction, "tolist"):
                prediction = prediction.tolist()
            elif isinstance(prediction, list):
                result_list = []
                for item in prediction:
                    if isinstance(item, list):
                        result_list.append(
                            [
                                {k: (v.item() if hasattr(v, "item") else v) for k, v in entry.items()}
                                if isinstance(entry, dict)
                                else entry
                                for entry in item
                            ]
                        )
                    elif isinstance(item, dict):
                        result_list.append(
                            {k: (v.item() if hasattr(v, "item") else v) for k, v in item.items()}
                        )
                    else:
                        result_list.append(item)
                prediction = result_list

            duration = time.time() - start_time
            record_inference_job(model_name, "success", duration)
            logger.info(f"  ✅ Inference สำเร็จ (duration: {duration:.3f}s)")
            print(f"  ✅ Inference สำเร็จ")
            return {
                "model_name": model_name,
                "model_version": model_version,
                "predictions": prediction,
            }

        except Exception as e:
            duration = time.time() - start_time
            record_inference_job(model_name, "failed", duration)
            error_msg = f"❌ Inference ล้มเหลว: {e}"
            logger.error(f"  {error_msg}")
            print(f"  {error_msg}")
            span.record_exception(e)
            return {"error": error_msg}


async def startup(ctx: dict):
    """Worker startup hook — initialize OpenTelemetry Observability."""
    setup_observability(service_name="ai-ecosystem-inference-worker")
    logger.info("🚀 Inference Worker started with OpenTelemetry observability")


async def shutdown(ctx: dict):
    """Worker shutdown hook."""
    logger.info("👋 Inference Worker shutting down")


class InferenceWorkerSettings:
    """
    ARQ Worker Settings สำหรับ Inference Worker

    รัน worker ด้วย:
        cd backend
        uv run arq app.features.workers.inference_tasks.InferenceWorkerSettings

        หรือผ่าน Docker:
        docker compose up inference-worker
    """

    functions = [run_inference]
    redis_settings = get_arq_redis_settings()
    queue_name = "arq:inference_queue"
    on_startup = startup
    on_shutdown = shutdown

    # ── Inference ไม่ต้อง timeout นานเท่า training ──
    job_timeout = 300  # 5 นาที
    max_jobs = 4  # รัน inference ได้หลาย job พร้อมกัน

