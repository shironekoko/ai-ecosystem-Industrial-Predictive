"""
Training Pipeline for YOLOv8 Classification on Nonastreda Optical Tool Images (tool/)
Protocol: Leave-One-Tool-Out (Tools 1-9 for Training/Validation, Tool 10 for Held-Out Test)
Model: Ultralytics YOLOv8-cls (Transfer Learning from ImageNet)
"""

import os
import shutil
import re
import pandas as pd

def prepare_yolo_dataset(base_dataset_dir, output_dir, test_tool=10):
    print("Preparing YOLO classification dataset structure...")
    df_labels = pd.read_csv(os.path.join(base_dataset_dir, 'labels.csv'))
    tool_img_dir = os.path.join(base_dataset_dir, 'tool')
    
    # YOLO-cls requires:
    # output_dir/
    #   train/
    #     sharp/
    #     used/
    #     dulled/
    #   val/
    #     sharp/
    #     used/
    #     dulled/
    
    classes = ['sharp', 'used', 'dulled']
    for split in ['train', 'val']:
        for cls in classes:
            os.makedirs(os.path.join(output_dir, split, cls), exist_ok=True)
            
    for _, row in df_labels.iterrows():
        img_id = row['id']
        label = row['image_label'].lower()
        img_file = f"{img_id}.jpg"
        src_path = os.path.join(tool_img_dir, img_file)
        
        m = re.match(r'T(\d+)R(\d+)B(\d+)', img_id)
        tool_id = int(m.group(1)) if m else 1
        
        split = 'val' if tool_id == test_tool else 'train'
        dest_path = os.path.join(output_dir, split, label, img_file)
        
        if os.path.exists(src_path):
            shutil.copy2(src_path, dest_path)
            
    print(f"Dataset prepared successfully at: {output_dir}")
    print(f"Val/Test folder strictly contains Tool #{test_tool}")

def train_yolov8(data_dir, epochs=20, imgsz=224):
    try:
        from ultralytics import YOLO
    except ImportError:
        print("Ultralytics not installed. Run: pip install ultralytics")
        return

    print("Loading pretrained YOLOv8n-cls model...")
    model = YOLO('yolov8n-cls.pt')
    
    print(f"Starting Transfer Learning for {epochs} epochs...")
    results = model.train(
        data=data_dir,
        epochs=epochs,
        imgsz=imgsz,
        project='models',
        name='yolov8_tool_wear',
        exist_ok=True
    )
    print("YOLOv8 Training Complete! Model saved in models/yolov8_tool_wear/weights/best.pt")

if __name__ == '__main__':
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'dataset', 'Nonastreda Multimodal Dataset for Identifying Tool Wear Condition (1)', 'Nonastreda Multimodal Dataset for Identifying Tool Wear Condition'))
    formatted_data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data_yolo_tool'))
    
    prepare_yolo_dataset(base_dir, formatted_data_dir, test_tool=10)
    # train_yolov8(formatted_data_dir, epochs=15)
