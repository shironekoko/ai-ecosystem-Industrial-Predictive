"""
Workers Tasks — ARQ task functions สำหรับ background jobs

เพิ่ม task functions ที่ต้องการรันเป็น background job ไว้ที่นี่
แล้ว register ใน WorkerSettings.functions

รัน worker:
    cd backend
    uv run arq app.features.workers.tasks.WorkerSettings

    หรือผ่าน Docker:
    docker compose up trainer-worker

MLflow Integration:
    - log params, metrics, model artifact เข้า MLflow Tracking Server
    - register model เข้า Model Registry
"""

import os
import tempfile
import time
from datetime import datetime
from pathlib import Path

from core.redis_client import get_arq_redis_settings
from core.config import settings
from core.minio_client import (
    download_file,
    ensure_bucket,
    list_objects,
    upload_file,
)


async def train_model(ctx: dict, dataset_name: str, model_name: str) -> str:
    """
    Fine-tune โมเดล Token Classification ด้วย Hugging Face Transformers

    Flow:
        1. โหลด dataset (parquet) จาก MinIO bucket 'datasets/{dataset_name}/'
        2. Tokenize + align labels
        3. Fine-tune ด้วย AutoModelForTokenClassification + HF Trainer
        4. เขียน training log (loss/epoch/step) ลงไฟล์
        5. Upload โมเดล + log ขึ้น MinIO bucket 'models/{model_name}/v{timestamp}/'
        6. Return summary string

    Args:
        ctx: ARQ context dict
        dataset_name: ชื่อ dataset ใน MinIO (เช่น "conll2003")
        model_name: ชื่อโมเดลที่จะ save (เช่น "bert-base-ner")

    Returns:
        Summary string ของผลการเทรน
    """
    # ── Lazy imports (เฉพาะเมื่อ worker หยิบงาน — ไม่ต้อง import ตอน API boot) ──
    import torch
    import numpy as np
    from datasets import load_dataset as hf_load_dataset, Dataset
    from transformers import (
        AutoTokenizer,
        AutoModelForTokenClassification,
        TrainingArguments,
        Trainer,
        DataCollatorForTokenClassification,
        TrainerCallback,
    )
    import evaluate

    start_time = time.time()
    job_id = ctx.get("job_id", "unknown")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    version_path = f"{model_name}/v{timestamp}"

    print(f"🚀 [Job {job_id}] เริ่มเทรน: dataset={dataset_name}, model={model_name}")

    # ── 1. Download dataset จาก MinIO ──
    datasets_bucket = settings.minio_datasets_bucket
    models_bucket = settings.minio_models_bucket

    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = os.path.join(tmpdir, "data")
        model_dir = os.path.join(tmpdir, "model")
        log_dir = os.path.join(tmpdir, "logs")
        os.makedirs(data_dir, exist_ok=True)
        os.makedirs(model_dir, exist_ok=True)
        os.makedirs(log_dir, exist_ok=True)

        log_file = os.path.join(log_dir, "train.log")

        def write_log(message: str):
            """เขียน log ลงไฟล์พร้อม timestamp"""
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            line = f"[{ts}] {message}\n"
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(line)
            print(f"  📝 {message}")

        write_log(f"Job ID: {job_id}")
        write_log(f"Dataset: {dataset_name}")
        write_log(f"Model Name: {model_name}")
        write_log(f"Version: v{timestamp}")
        write_log("--- Downloading dataset from MinIO ---")

        # ดาวน์โหลดไฟล์ parquet ทั้งหมดจาก MinIO
        objects = list_objects(datasets_bucket, prefix=f"{dataset_name}/")
        downloaded_files = []
        for obj in objects:
            obj_name = obj["name"] if isinstance(obj, dict) else obj.object_name
            local_file = os.path.join(data_dir, os.path.basename(obj_name))
            download_file(datasets_bucket, obj_name, local_file)
            downloaded_files.append(local_file)
            write_log(f"Downloaded: {obj_name}")

        if not downloaded_files:
            error_msg = f"❌ ไม่พบไฟล์ dataset '{dataset_name}' ใน MinIO bucket '{datasets_bucket}'"
            write_log(error_msg)
            return error_msg

        # ── 2. Load dataset จาก parquet ──
        write_log("--- Loading dataset ---")

        # หา split files
        split_datasets = {}
        for fpath in downloaded_files:
            split_name = Path(fpath).stem  # e.g., "train", "validation", "test"
            split_datasets[split_name] = Dataset.from_parquet(fpath)
            write_log(f"Loaded split '{split_name}': {len(split_datasets[split_name])} rows")

        if "train" not in split_datasets:
            error_msg = "❌ ไม่พบ split 'train' ใน dataset"
            write_log(error_msg)
            return error_msg

        train_ds = split_datasets["train"]
        eval_ds = split_datasets.get("validation", split_datasets.get("test", None))

        # ── 3. สร้าง label mapping จาก dataset ──
        write_log("--- Preparing label mapping ---")

        # conll2003 dataset มี ner_tags เป็น ClassLabel
        # ลองอ่าน label names จาก features
        ner_column = None
        token_column = None
        for col in train_ds.column_names:
            if "ner" in col.lower() or "label" in col.lower() or "tag" in col.lower():
                ner_column = col
            if "token" in col.lower() or "word" in col.lower():
                token_column = col

        if ner_column is None:
            ner_column = "ner_tags"
        if token_column is None:
            token_column = "tokens"

        write_log(f"Token column: {token_column}")
        write_log(f"NER column: {ner_column}")

        # ดึง label names
        if hasattr(train_ds.features.get(ner_column, None), "feature"):
            ner_feature = train_ds.features[ner_column].feature
            if hasattr(ner_feature, "names"):
                label_names = ner_feature.names
            else:
                # fallback: สร้าง label list จากค่า unique ใน dataset
                all_labels = set()
                for row in train_ds:
                    all_labels.update(row[ner_column])
                label_names = [f"LABEL_{i}" for i in sorted(all_labels)]
        else:
            all_labels = set()
            for row in train_ds:
                if isinstance(row[ner_column], list):
                    all_labels.update(row[ner_column])
                else:
                    all_labels.add(row[ner_column])
            label_names = sorted([str(l) for l in all_labels])

        label2id = {label: i for i, label in enumerate(label_names)}
        id2label = {i: label for i, label in enumerate(label_names)}
        num_labels = len(label_names)

        write_log(f"Labels ({num_labels}): {label_names}")

        # ── 4. Load tokenizer + model ──
        write_log("--- Loading pretrained model & tokenizer ---")

        pretrained_model = "bert-base-cased"
        tokenizer = AutoTokenizer.from_pretrained(pretrained_model)
        model = AutoModelForTokenClassification.from_pretrained(
            pretrained_model,
            num_labels=num_labels,
            id2label=id2label,
            label2id=label2id,
        )

        write_log(f"Base model: {pretrained_model}")
        write_log(f"Num labels: {num_labels}")

        # ── 5. Tokenize + align labels ──
        write_log("--- Tokenizing dataset ---")

        def tokenize_and_align_labels(examples):
            tokenized_inputs = tokenizer(
                examples[token_column],
                truncation=True,
                is_split_into_words=True,
                max_length=128,
            )
            labels = []
            for i, label_ids in enumerate(examples[ner_column]):
                word_ids = tokenized_inputs.word_ids(batch_index=i)
                previous_word_idx = None
                label_list = []
                for word_idx in word_ids:
                    if word_idx is None:
                        label_list.append(-100)
                    elif word_idx != previous_word_idx:
                        label_list.append(label_ids[word_idx])
                    else:
                        # สำหรับ sub-word tokens: ใช้ -100 (ignore ตอน compute loss)
                        label_list.append(-100)
                    previous_word_idx = word_idx
                labels.append(label_list)
            tokenized_inputs["labels"] = labels
            return tokenized_inputs

        tokenized_train = train_ds.map(
            tokenize_and_align_labels, batched=True, remove_columns=train_ds.column_names
        )
        write_log(f"Tokenized train: {len(tokenized_train)} examples")

        tokenized_eval = None
        if eval_ds is not None:
            tokenized_eval = eval_ds.map(
                tokenize_and_align_labels, batched=True, remove_columns=eval_ds.column_names
            )
            write_log(f"Tokenized eval: {len(tokenized_eval)} examples")

        # ── 6. Metrics ──
        seqeval = evaluate.load("seqeval")

        def compute_metrics(p):
            predictions, labels = p
            predictions = np.argmax(predictions, axis=2)

            true_predictions = [
                [label_names[pred] for (pred, lab) in zip(prediction, label) if lab != -100]
                for prediction, label in zip(predictions, labels)
            ]
            true_labels = [
                [label_names[lab] for (pred, lab) in zip(prediction, label) if lab != -100]
                for prediction, label in zip(predictions, labels)
            ]

            results = seqeval.compute(predictions=true_predictions, references=true_labels)
            return {
                "precision": results["overall_precision"],
                "recall": results["overall_recall"],
                "f1": results["overall_f1"],
                "accuracy": results["overall_accuracy"],
            }

        # ── 7. Training callback สำหรับเขียน log ──
        class TrainingLogCallback(TrainerCallback):
            def on_log(self, args, state, control, logs=None, **kwargs):
                if logs:
                    step = state.global_step
                    epoch = state.epoch
                    loss = logs.get("loss", logs.get("eval_loss", "N/A"))
                    write_log(f"Step {step} | Epoch {epoch:.2f} | Loss: {loss}")

        # ── 8. Training ──
        write_log("--- Starting training ---")

        data_collator = DataCollatorForTokenClassification(tokenizer=tokenizer)

        training_output_dir = os.path.join(tmpdir, "training_output")
        training_args = TrainingArguments(
            output_dir=training_output_dir,
            eval_strategy="epoch" if tokenized_eval is not None else "no",
            save_strategy="epoch",
            learning_rate=2e-5,
            per_device_train_batch_size=16,
            per_device_eval_batch_size=16,
            num_train_epochs=3,
            weight_decay=0.01,
            logging_steps=50,
            save_total_limit=1,
            load_best_model_at_end=True if tokenized_eval is not None else False,
            metric_for_best_model="f1" if tokenized_eval is not None else None,
            report_to="none",  # ไม่ส่ง log ไป wandb/tensorboard
        )

        trainer = Trainer(
            model=model,
            args=training_args,
            train_dataset=tokenized_train,
            eval_dataset=tokenized_eval,
            processing_class=tokenizer,
            data_collator=data_collator,
            compute_metrics=compute_metrics if tokenized_eval is not None else None,
            callbacks=[TrainingLogCallback()],
        )

        train_result = trainer.train()

        write_log(f"Training loss: {train_result.training_loss:.4f}")
        write_log(f"Training runtime: {train_result.metrics.get('train_runtime', 0):.1f}s")

        # ── 9. Evaluate ──
        eval_f1 = None
        if tokenized_eval is not None:
            write_log("--- Evaluating ---")
            eval_metrics = trainer.evaluate()
            eval_f1 = eval_metrics.get("eval_f1", None)
            write_log(f"Eval Precision: {eval_metrics.get('eval_precision', 'N/A')}")
            write_log(f"Eval Recall: {eval_metrics.get('eval_recall', 'N/A')}")
            write_log(f"Eval F1: {eval_f1}")
            write_log(f"Eval Accuracy: {eval_metrics.get('eval_accuracy', 'N/A')}")

        # ── 10. MLflow Tracking — log params, metrics, model ──
        write_log("--- Logging to MLflow ---")
        import mlflow
        import mlflow.transformers

        mlflow_tracking_uri = os.environ.get(
            "MLFLOW_TRACKING_URI", "http://localhost:5001"
        )
        mlflow.set_tracking_uri(mlflow_tracking_uri)
        experiment_name = f"training-{dataset_name}"
        mlflow.set_experiment(experiment_name)
        write_log(f"MLflow tracking URI: {mlflow_tracking_uri}")
        write_log(f"MLflow experiment: {experiment_name}")

        with mlflow.start_run(run_name=f"{model_name}-v{timestamp}") as run:
            # Log parameters
            mlflow.log_param("dataset_name", dataset_name)
            mlflow.log_param("model_name", model_name)
            mlflow.log_param("base_model", pretrained_model)
            mlflow.log_param("num_labels", num_labels)
            mlflow.log_param("num_train_epochs", int(training_args.num_train_epochs))
            mlflow.log_param("learning_rate", training_args.learning_rate)
            mlflow.log_param("batch_size", training_args.per_device_train_batch_size)
            mlflow.log_param("version", f"v{timestamp}")

            # Log metrics
            mlflow.log_metric("training_loss", train_result.training_loss)
            mlflow.log_metric(
                "training_runtime",
                train_result.metrics.get("train_runtime", 0),
            )
            if eval_f1 is not None:
                mlflow.log_metric("eval_f1", eval_f1)
                mlflow.log_metric(
                    "eval_precision",
                    eval_metrics.get("eval_precision", 0),
                )
                mlflow.log_metric(
                    "eval_recall", eval_metrics.get("eval_recall", 0)
                )
                mlflow.log_metric(
                    "eval_accuracy",
                    eval_metrics.get("eval_accuracy", 0),
                )

            # Log model artifact (transformers pipeline)
            components = {"model": model, "tokenizer": tokenizer}
            mlflow.transformers.log_model(
                transformers_model=components,
                artifact_path="model",
                registered_model_name=model_name,
                task="token-classification",
                pip_requirements=["torch", "transformers", "accelerate"],
            )

            # Log training log file
            mlflow.log_artifact(log_file, artifact_path="logs")

            write_log(f"MLflow run ID: {run.info.run_id}")
            write_log(f"Model registered as: {model_name}")

        # ── 11. Save model + tokenizer (local) ──
        write_log("--- Saving model ---")
        trainer.save_model(model_dir)
        tokenizer.save_pretrained(model_dir)
        write_log(f"Model saved to: {model_dir}")

        # ── 12. Upload ทั้งโฟลเดอร์ขึ้น MinIO ──
        write_log("--- Uploading to MinIO ---")
        ensure_bucket(models_bucket)

        # Upload model files
        for root, dirs, files in os.walk(model_dir):
            for fname in files:
                local_path = os.path.join(root, fname)
                rel_path = os.path.relpath(local_path, model_dir)
                object_name = f"{version_path}/{rel_path}".replace("\\", "/")
                upload_file(models_bucket, object_name, local_path)
                write_log(f"Uploaded: {object_name}")

        # Upload training log
        log_object_name = f"{version_path}/train.log"
        upload_file(models_bucket, log_object_name, log_file)
        write_log(f"Uploaded log: {log_object_name}")

        # ── 13. Summary ──
        elapsed = time.time() - start_time
        f1_str = f"{eval_f1:.4f}" if eval_f1 is not None else "N/A"
        epochs = int(training_args.num_train_epochs)
        summary = (
            f"✅ เทรนเสร็จ: {version_path} — "
            f"eval_f1={f1_str} ({epochs} epochs, {elapsed:.1f}s)"
        )
        write_log(summary)
        write_log("=== Training Complete ===")

        # คัดลอก log ไปที่ /logs (volume mount) ด้วยถ้ามี
        host_log_dir = "/logs"
        if os.path.isdir(host_log_dir):
            import shutil
            host_log_file = os.path.join(host_log_dir, f"train_{model_name}_{timestamp}.log")
            shutil.copy2(log_file, host_log_file)

async def train_yolo_model(
    ctx: dict,
    dataset_name: str = "chip",
    model_name: str = "yolov8_chip_wear",
    epochs: int = 10,
    batch_size: int = 16,
) -> str:
    """
    ARQ Task สำหรับ Fine-tune / Retrain โมเดล YOLOv8 Classification (Non-Time Series Vision)

    Flow:
        1. ค้นหาโฟลเดอร์ dataset (data_yolo_chip หรือ data_yolo_tool)
        2. รัน Fine-tune YOLOv8-cls (เริ่มจาก best.pt เดิม หรือ yolov8n-cls.pt)
        3. บันทึกผลลัพธ์ลง MLflow และเก็บไฟล์ weights/best.pt
        4. Upload โมเดลและผลลัพธ์ขึ้น MinIO (ถ้าพร้อมใช้งาน)
        5. Return สรุปผลการ Retrain
    """
    import asyncio
    from ultralytics import YOLO

    start_time = time.time()
    job_id = ctx.get("job_id", "unknown")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    version_path = f"{model_name}/v{timestamp}"

    print(f"🚀 [Job {job_id}] เริ่ม Retrain YOLOv8: dataset={dataset_name}, model={model_name}, epochs={epochs}")

    # หา root path ของ backend
    backend_dir = Path(__file__).resolve().parent.parent.parent.parent
    data_dir = backend_dir / f"data_yolo_{dataset_name}"

    if not data_dir.exists() or not (data_dir / "train").exists():
        raw_dataset_dir = (
            backend_dir.parent
            / "dataset"
            / "Nonastreda Multimodal Dataset for Identifying Tool Wear Condition"
            / "Nonastreda Multimodal Dataset for Identifying Tool Wear Condition"
        )
        if raw_dataset_dir.exists():
            from scripts.train_yolov8_chip import prepare_chip_dataset
            prepare_chip_dataset(str(raw_dataset_dir), str(data_dir))
        else:
            raise FileNotFoundError(f"ไม่พบชุดข้อมูลสำหรับเทรนที่: {data_dir}")

    # เลือกว่าจะ fine-tune ต่อจาก best.pt เดิม หรือเริ่มจาก base pretrained
    existing_best = backend_dir / "models" / model_name / "weights" / "best.pt"
    base_weights = str(existing_best) if existing_best.exists() else "yolov8n-cls.pt"

    project_dir = str(backend_dir / "models")

    # รัน YOLO training บน thread executor เพื่อไม่ให้บล็อก async event loop
    loop = asyncio.get_event_loop()

    def _do_train():
        model = YOLO(base_weights)
        train_results = model.train(
            data=str(data_dir),
            epochs=epochs,
            imgsz=224,
            batch=batch_size,
            project=project_dir,
            name=model_name,
            exist_ok=True,
            workers=2,
            verbose=True,
        )
        return train_results

    results = await loop.run_in_executor(None, _do_train)

    elapsed = time.time() - start_time
    top1 = getattr(results, "top1", None)
    top1_str = f"{top1 * 100:.2f}%" if top1 is not None else "N/A"

    best_pt_path = backend_dir / "models" / model_name / "weights" / "best.pt"

    # อัปโหลดขึ้น MinIO ถ้าเปิดใช้งาน
    models_bucket = settings.minio_models_bucket
    try:
        if best_pt_path.exists():
            ensure_bucket(models_bucket)
            upload_file(models_bucket, f"{version_path}/best.pt", str(best_pt_path))
    except Exception as e:
        print(f"⚠️ MinIO upload warning: {e}")

    summary = (
        f"✅ Retrain YOLOv8 สำเร็จ: {model_name} (version: v{timestamp}) — "
        f"Top-1 Accuracy={top1_str} ({epochs} epochs, {elapsed:.1f}s)"
    )
    print(f"🎉 {summary}")
    return summary


async def startup(ctx: dict):
    from core.observability import setup_observability
    setup_observability(service_name="ai-ecosystem-trainer-worker")
    import logging
    logging.getLogger("trainer-worker").info("🚀 Trainer Worker started with OpenTelemetry observability")


async def shutdown(ctx: dict):
    import logging
    logging.getLogger("trainer-worker").info("👋 Trainer Worker shutting down")


class WorkerSettings:
    """
    ARQ Worker Settings

    รัน worker ด้วย:
        cd backend
        uv run arq app.features.workers.tasks.WorkerSettings

        หรือผ่าน Docker:
        docker compose up trainer-worker
    """

    functions = [train_model, train_yolo_model]
    redis_settings = get_arq_redis_settings()
    on_startup = startup
    on_shutdown = shutdown

    # ── ตั้ง timeout นานขึ้นสำหรับงานเทรน (default 300s อาจไม่พอ) ──
    job_timeout = 7200  # 2 ชั่วโมง
    max_jobs = 1  # รันทีละ 1 job (GPU มีจำกัด)

