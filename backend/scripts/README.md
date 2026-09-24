# Scripts

โฟลเดอร์ `scripts/` เก็บสคริปต์สำหรับการจัดการโปรเจกต์ที่มักจะรันผ่าน Command Line แยกต่างหาก ไม่อยู่ในส่วนที่ผู้ใช้ทั่วไป (End-User) เข้าถึง

## สคริปต์ที่มีอยู่

### 1. `openapi_to_csv.py`
แปลงไฟล์ OpenAPI Specification ของ FastAPI ให้อยู่ในรูปแบบของ CSV (หรือ Excel) ซึ่งมีประโยชน์สำหรับการทำเอกสารส่งต่อหรือการตรวจสอบ API Endpoints ทั่วทั้งโปรเจกต์
- **วิธีใช้งาน:**
  ```bash
  uv run python scripts/openapi_to_csv.py --output api_list.csv
  ```

### 2. `seed_data.py`
สคริปต์สำหรับสร้างข้อมูลตัวอย่าง (Mock Data) ลงในฐานข้อมูล เช่น ผู้ใช้ทดสอบ ข้อมูลโปรเจกต์ เพื่ออำนวยความสะดวกในการทดสอบระบบหรือการตั้งค่าสภาพแวดล้อม Development
- **วิธีใช้งาน:**
  ```bash
  uv run python scripts/seed_data.py --users 10
  ```

## Command Line Arguments
ในแต่ละสคริปต์สามารถใช้ `--help` เพื่อดูตัวเลือกอาร์กิวเมนต์ที่รองรับได้:
```bash
uv run python scripts/seed_data.py --help
```
