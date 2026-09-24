"""
Load Hugging Face Dataset to MinIO — สคริปต์โหลด dataset จาก HF Hub ลง MinIO

ใช้งาน:
    cd backend
    uv run python scripts/load_hf_dataset_to_minio.py --dataset eriktks/conll2003

Flow:
    1. โหลด dataset จาก Hugging Face Hub ด้วย datasets library
       (ลองใช้ revision "refs/convert/parquet" ก่อน เพื่อเลี่ยงปัญหา
        "Dataset scripts are no longer supported" ใน datasets v4+
        ถ้าไม่มี branch นี้ ค่อย fallback ไปโหลดแบบปกติ)
    2. Save แต่ละ split เป็น parquet ลง disk (/tmp)
    3. Upload ไฟล์ parquet ทั้งหมดเข้า MinIO bucket "datasets"
       ที่ path: datasets/{dataset_name}/{split}.parquet

ข้อกำหนด:
    - ต้องรัน MinIO ก่อน (docker compose up minio)
    - ต้องติดตั้ง datasets library (อยู่ใน pyproject.toml แล้ว)

หมายเหตุเรื่องชื่อ dataset:
    - ใช้ "eriktks/conll2003" แทน "conll2003" เฉย ๆ เพราะ dataset ID แบบไม่มี
      namespace (canonical/legacy) ทำให้ datasets library อ่าน
      revision="refs/convert/parquet" ไม่ได้ (ต้องเป็นรูปแบบ namespace/name เสมอ)
      eriktks/conll2003 คือ repo ต้นฉบับ มี schema เหมือนเดิมทุกอย่าง
      (tokens / pos_tags / chunk_tags / ner_tags)
"""

import argparse
import os
import sys
import tempfile
from pathlib import Path

# ── เพิ่ม backend root เข้า sys.path เพื่อให้ import core.* ได้ ──
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND_ROOT))

from datasets import load_dataset  # type: ignore[import-untyped]

from core.config import settings
from core.minio_client import ensure_bucket, upload_file


def load_hf_dataset(dataset_name: str, trust_remote_code: bool):
    """
    โหลด dataset จาก HF Hub — พยายามใช้ branch parquet อัตโนมัติก่อน
    (เลี่ยงปัญหา "Dataset scripts are no longer supported" ใน datasets v4+)
    ถ้า dataset นั้นไม่มี branch parquet หรือ id ไม่มี namespace ให้ fallback
    ไปโหลดแบบปกติ
    """
    try:
        print("   → ลองโหลดจาก revision 'refs/convert/parquet' (ไม่รัน script ใด ๆ)")
        return load_dataset(dataset_name, revision="refs/convert/parquet")
    except Exception as e:
        print(f"   ⚠️  โหลดจาก refs/convert/parquet ไม่สำเร็จ ({e})")
        print("   → fallback ไปโหลดแบบปกติ ...")
        try:
            return load_dataset(dataset_name, trust_remote_code=trust_remote_code)
        except RuntimeError as e2:
            if "Dataset scripts are no longer supported" in str(e2):
                print(
                    "\n❌ Dataset นี้ใช้ loading script แบบเก่าที่ datasets v4+ ไม่รองรับแล้ว\n"
                    "   ลองวิธีใดวิธีหนึ่ง:\n"
                    "   1) ใช้ dataset ที่มี namespace เช่น --dataset eriktks/conll2003\n"
                    "   2) หรือ pin เวอร์ชันใน pyproject.toml เป็น datasets>=2.19.0,<4.0.0\n"
                    "      แล้วรัน `uv lock && uv sync` ใหม่\n"
                )
            raise


def main():
    parser = argparse.ArgumentParser(
        description="โหลด dataset จาก Hugging Face Hub แล้วอัปโหลดเข้า MinIO"
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default="eriktks/conll2003",
        help="ชื่อ dataset บน Hugging Face Hub (default: eriktks/conll2003)",
    )
    parser.add_argument(
        "--trust-remote-code",
        action="store_true",
        default=False,
        help="อนุญาตให้รัน remote code ของ dataset (สำหรับบาง dataset ที่ต้องการ)",
    )
    args = parser.parse_args()

    dataset_name: str = args.dataset
    bucket_name: str = settings.minio_datasets_bucket

    print(f"📦 กำลังโหลด dataset '{dataset_name}' จาก Hugging Face Hub ...")
    ds = load_hf_dataset(dataset_name, args.trust_remote_code)

    # ── สร้าง bucket ถ้ายังไม่มี ──
    ensure_bucket(bucket_name)

    # ── Save + Upload แต่ละ split ──
    # ใช้ตัวหลังสุดของชื่อ dataset (หลัง "/") เป็นชื่อ folder ใน MinIO
    # เพื่อไม่ให้ path มี "/" ซ้อนจาก namespace เช่น eriktks/conll2003
    dataset_folder = dataset_name.split("/")[-1]

    with tempfile.TemporaryDirectory() as tmpdir:
        for split_name in ds:
            split_ds = ds[split_name]
            parquet_filename = f"{split_name}.parquet"
            local_path = os.path.join(tmpdir, parquet_filename)

            print(f"  💾 Saving {split_name} ({len(split_ds)} rows) → {parquet_filename}")
            split_ds.to_parquet(local_path)

            object_name = f"{dataset_folder}/{parquet_filename}"
            print(f"  ☁️  Uploading → {bucket_name}/{object_name}")
            upload_file(bucket_name, object_name, local_path)

    print(f"\n✅ เสร็จสิ้น! Dataset '{dataset_name}' อยู่ใน MinIO bucket '{bucket_name}'")
    print(f"   ดูได้ที่ MinIO Console: http://localhost:9001 → bucket '{bucket_name}'")


if __name__ == "__main__":
    main()