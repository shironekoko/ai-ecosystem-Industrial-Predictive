# Core Layer

โฟลเดอร์ `core/` ทำหน้าที่เป็น Infrastructure Layer ของโปรเจกต์ ซึ่งจัดการการเชื่อมต่อกับระบบภายนอก ฐานข้อมูล และการตั้งค่าพื้นฐาน

**คำเตือน:** โฟลเดอร์นี้ไม่ควรมี Business Logic ของแอปพลิเคชันอยู่ แต่ละฟีเจอร์จะนำส่วนประกอบจาก `core/` ไปใช้งานเอง

## รายละเอียดของแต่ละไฟล์

### `__init__.py`
- ทำให้ `core` เป็น package (ไม่มีโค้ด)

### `config.py`
- ใช้ `pydantic-settings` (BaseSettings) โหลดค่าจาก `.env` ที่รากโปรเจกต์ (ตัวอย่าง: `.env.example`)
- ค่า: `DATABASE_URL`, `MINIO_*` + bucket แบบจำลอง (`models`), `REDIS_URL`, `JWT_SECRET_KEY` / `ACCESS_TOKEN_EXPIRE_MINUTES`, CORS

### `database.py`
- ตั้งค่า SQLAlchemy 2.0 Engine
- สร้าง `SessionLocal` (Session Factory) เพื่อเชื่อมต่อ PostgreSQL
- สร้างคลาส `Base` แบบ Declarative สำหรับให้ Models อื่นๆ สืบทอด

### `minio_client.py`
- `get_minio_client()` (timeout สั้น — MinIO ล่มแล้ว request ไม่ค้าง) และ `ensure_bucket()`
- bucket ที่ระบบใช้: `models` (แบบจำลอง `tool-rul/`, `tool-vision/`) และ `inspections` (ภาพตรวจใบมีด)

### `redis_client.py`
- `get_arq_redis_settings()` — ค่าการเชื่อมต่อคิวงาน ARQ (backend ส่งงาน retrain → trainer-worker)

### `observability.py`
- OpenTelemetry (trace + metric + log) → OTel Collector → Tempo / Prometheus / Loki → Grafana — **เปิดเฉพาะเมื่อมี `OTEL_EXPORTER_OTLP_ENDPOINT`** (ตั้งใน `compose.observability.yml`) ไม่เช่นนั้นทุกฟังก์ชันเป็น no-op
- `METRICS` = รายชื่อ metric ของระบบ (RUL, vision, retrain) · ฟีเจอร์เรียก `inc()` / `observe()` / `timed()` / `span()` และลงทะเบียน gauge ด้วย `register_gauge()` (ดู `app/features/health/telemetry.py`)
- `inject_trace_context()` ส่ง trace ไปกับงานในคิว ARQ ให้ retrain ต่อเป็น trace เดียวกับ request ที่สั่ง

## การใช้งานโดยโมดูลฟีเจอร์
โมดูลฟีเจอร์ (เช่น `features/auth/`, `features/tool_vision/`) จะทำการ `import` เครื่องมือจาก `core/` เหล่านี้ เพื่อไปประกอบใน Business Logic (Services)

## Configuration Variables (ตัวอย่าง)
| ตัวแปร | หน้าที่ |
| --- | --- |
| `DATABASE_URL` | String เชื่อมต่อกับ PostgreSQL |
| `REDIS_URL` | String เชื่อมต่อกับ Redis |
| `MINIO_ENDPOINT` | URL ของ MinIO Server |
| `JWT_SECRET_KEY` | รหัสลับสำหรับเซ็น JWT |
