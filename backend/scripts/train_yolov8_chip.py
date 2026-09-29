"""
Training Pipeline for YOLOv8 Classification on Optical Chip Images (chip/)
Dataset: Nonastreda Multimodal Dataset (Non-Time Series Vision)
Protocol: Leave-One-Tool-Out (Tools 1-9 for Train, Tool 10 for Held-Out Test/Val)
Model: Ultralytics YOLOv8-cls (Transfer Learning from ImageNet)
"""

import os
import sys
import shutil
import re
import argparse

# Fix Windows console UTF-8 output
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

import pandas as pd
from pathlib import Path


def prepare_chip_dataset(base_dataset_dir: str, output_dir: str, test_tool: int = 10) -> dict:
    """
    จัดโครงสร้างโฟลเดอร์สำหรับ YOLOv8 Classification จากภาพถ่ายเศษตัด (chip/)
    
    output_dir/
      train/
        sharp/
        used/
        dulled/
      val/
        sharp/
        used/
        dulled/
    """
    print(f"\n📂 [1/3] กำลังจัดเตรียมโครงสร้างชุดข้อมูล YOLO-cls จากโฟลเดอร์ chip...")
    labels_file = os.path.join(base_dataset_dir, 'labels.csv')
    chip_img_dir = os.path.join(base_dataset_dir, 'chip')
    
    if not os.path.exists(labels_file):
        raise FileNotFoundError(f"ไม่พบไฟล์ labels.csv ที่: {labels_file}")
    if not os.path.exists(chip_img_dir):
        raise FileNotFoundError(f"ไม่พบโฟลเดอร์ chip ที่: {chip_img_dir}")
        
    df_labels = pd.read_csv(labels_file)
    classes = ['sharp', 'used', 'dulled']
    
    # ล้างหรือสร้างโฟลเดอร์ปลายทาง
    for split in ['train', 'val']:
        for cls in classes:
            os.makedirs(os.path.join(output_dir, split, cls), exist_ok=True)
            
    stats = {
        'train': {'sharp': 0, 'used': 0, 'dulled': 0},
        'val': {'sharp': 0, 'used': 0, 'dulled': 0}
    }
    
    missing_files = 0
    copied_files = 0
    
    for _, row in df_labels.iterrows():
        img_id = str(row['id']).strip()
        label = str(row['image_label']).strip().lower()
        if label not in classes:
            continue
            
        img_file = f"{img_id}.jpg"
        src_path = os.path.join(chip_img_dir, img_file)
        
        m = re.match(r'T(\d+)R(\d+)B(\d+)', img_id)
        tool_id = int(m.group(1)) if m else 1
        
        split = 'val' if tool_id == test_tool else 'train'
        dest_path = os.path.join(output_dir, split, label, img_file)
        
        if os.path.exists(src_path):
            shutil.copy2(src_path, dest_path)
            stats[split][label] += 1
            copied_files += 1
        else:
            missing_files += 1
            
    print(f"✅ คัดลอกภาพเสร็จสิ้นทั้งหมด {copied_files} ภาพ (ไม่พบ {missing_files} ภาพ)")
    print(f"📊 สถิติ Train set (Tools 1-9): {stats['train']} (รวม {sum(stats['train'].values())} ภาพ)")
    print(f"📊 สถิติ Val/Test set (Tool {test_tool}): {stats['val']} (รวม {sum(stats['val'].values())} ภาพ)")
    return stats


def train_yolov8_chip(
    data_dir: str, 
    epochs: int = 15, 
    imgsz: int = 224, 
    batch_size: int = 16,
    project_dir: str = "models",
    experiment_name: str = "yolov8_chip_wear"
):
    """
    รัน Fine-tuning / Transfer Learning YOLOv8-cls
    """
    print(f"\n🚀 [2/3] กำลังโหลดโมเดล Pretrained 'yolov8n-cls.pt'...")
    from ultralytics import YOLO
    
    model = YOLO("yolov8n-cls.pt")
    
    print(f"\n⚙️ [3/3] เริ่มกระบวนการ Training (Transfer Learning) จำนวน {epochs} epochs...")
    results = model.train(
        data=data_dir,
        epochs=epochs,
        imgsz=imgsz,
        batch=batch_size,
        project=project_dir,
        name=experiment_name,
        exist_ok=True,
        workers=2,
        verbose=True
    )
    
    best_weights = os.path.join(project_dir, experiment_name, 'weights', 'best.pt')
    print("\n" + "="*60)
    print("🎉 Training Complete!")
    print(f"💾 โมเดลถูกบันทึกเรียบร้อยที่: {best_weights}")
    if hasattr(results, 'top1'):
        print(f"🎯 Validation Top-1 Accuracy: {results.top1 * 100:.2f}%")
        print(f"🎯 Validation Top-5 Accuracy: {results.top5 * 100:.2f}%")
    print("="*60 + "\n")
    return results


def run_sample_inference(model_path: str, sample_image_path: str):
    """
    ทดสอบรัน Inference ภาพเดี่ยวเพื่อดูผลลัพธ์
    """
    from ultralytics import YOLO
    if not os.path.exists(model_path):
        print(f"⚠️ ไม่พบโมเดลที่: {model_path}")
        return
        
    model = YOLO(model_path)
    results = model(sample_image_path)
    for r in results:
        top1_idx = r.probs.top1
        top1_label = r.names[top1_idx]
        top1_conf = float(r.probs.top1conf) * 100
        print(f"🔍 ทดสอบภาพ: {os.path.basename(sample_image_path)}")
        print(f"   ผลการทำนาย: {top1_label.upper()} (ความมั่นใจ {top1_conf:.2f}%)")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Train YOLOv8-cls on Chip Images")
    parser.add_argument('--epochs', type=int, default=15, help="Number of training epochs")
    parser.add_argument('--batch', type=int, default=16, help="Batch size")
    parser.add_argument('--test-tool', type=int, default=10, help="Tool ID held out for testing (LOTO)")
    args = parser.parse_args()

    # Paths
    base_script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(base_script_dir, '..', '..'))
    dataset_dir = os.path.join(
        project_root, 
        'dataset', 
        'Nonastreda Multimodal Dataset for Identifying Tool Wear Condition', 
        'Nonastreda Multimodal Dataset for Identifying Tool Wear Condition'
    )
    formatted_data_dir = os.path.abspath(os.path.join(base_script_dir, '..', 'data_yolo_chip'))
    models_dir = os.path.abspath(os.path.join(base_script_dir, '..', 'models'))
    
    # 1. จัดเตรียมชุดข้อมูล
    prepare_chip_dataset(dataset_dir, formatted_data_dir, test_tool=args.test_tool)
    
    # 2. รัน Training
    train_yolov8_chip(
        data_dir=formatted_data_dir, 
        epochs=args.epochs, 
        imgsz=224, 
        batch_size=args.batch,
        project_dir=models_dir,
        experiment_name='yolov8_chip_wear'
    )
