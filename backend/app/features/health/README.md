# health — สถานะของระบบ

| ไฟล์ | หน้าที่ |
|---|---|
| `router.py` | `GET /health` → `{"status": "healthy", "timestamp", "version"}` — healthcheck ของ Docker (`compose.yml`: frontend เริ่มเมื่อ backend healthy) · endpoint เดียวที่ไม่ต้องล็อกอิน (นอกจาก signup / login) |
| `service.py` | ตรวจการเชื่อมต่อ PostgreSQL / Redis / MinIO (`check_all_components`) — ใช้โดย `telemetry.py` |
| `telemetry.py` | gauge ของชุด observability (ทำงานเมื่อเปิด `compose.observability.yml`): การเชื่อมต่อบริการ, แบบจำลองที่โหลด, RUL / drift / สถานะรายเครื่อง, ผลประเมินหลังถอดดอก, งานรอผู้ตรวจ, ใบสั่งงานค้าง, pool retrain, MAE ของ AI เทียบค่าวัดจริง — ดูใน Grafana |
| `schemas.py` | `HealthResponse`, `ComponentStatus` |
