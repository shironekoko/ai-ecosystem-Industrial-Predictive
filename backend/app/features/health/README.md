# Health Check Feature

โมดูลสำหรับตรวจสอบสถานะของระบบ (Health Check) และส่วนประกอบที่ระบบต้องการในการทำงาน (Components)

## หน้าที่หลัก
1. ให้บริการ API สำหรับตรวจสอบว่า Backend ทำงานอยู่หรือไม่
2. ให้บริการ API สำหรับตรวจสอบสถานะการเชื่อมต่อกับ Service ภายนอกต่างๆ (Database, Redis, MinIO, Label Studio)

## Endpoints

### 1. `GET /health`
ตรวจสอบสถานะของ API เบื้องต้น

**Example Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-08-14T02:00:00Z",
  "version": "1.0.0",
  "components": null
}
```

### 2. `GET /health/components`
ตรวจสอบสถานะ API พร้อมเช็คการเชื่อมต่อส่วนประกอบต่างๆ อย่างละเอียด

**Example Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-08-14T02:00:00Z",
  "version": "1.0.0",
  "components": [
    {
      "name": "PostgreSQL",
      "status": "connected",
      "latency_ms": 5.2,
      "details": null
    },
    {
      "name": "Redis",
      "status": "connected",
      "latency_ms": 1.1,
      "details": null
    },
    {
      "name": "MinIO",
      "status": "connected",
      "latency_ms": 12.5,
      "details": null
    },
    {
      "name": "Label Studio",
      "status": "disconnected",
      "latency_ms": 25.0,
      "details": {
        "error": "Connection timeout"
      }
    }
  ]
}
```

## วิธีการทำงานของ Component Checks (Concurrent & Non-Blocking)
- **สถาปัตยกรรมทำงานแบบขนาน**: เรียกใช้ `ThreadPoolExecutor(max_workers=4)` เพื่อรันตรวจสอบ 4 Services พร้อมกัน ช่วยลดเวลาตอบสนองรวมจาก >25 วินาที เหลือเพียง ~0.6 วินาที
- **Fast TCP Reachability**: ก่อนจะเรียกคำสั่งหนักในแต่ละ SDK ระบบจะส่ง Socket Ping ตรวจสอบว่าพอร์ตเปิดอยู่หรือไม่ด้วย Timeout สั้น (0.3 วินาที) ทำให้หาก Service ออฟไลน์จะตอบกลับทันทีโดยไม่บล็อก
- **Database (SQLite / PostgreSQL)**: ทำการรันคำสั่ง `SELECT 1` ผ่าน SQLAlchemy engine
- **Redis**: ตรวจสอบ TCP Reachability ไปยัง Redis host:port
- **MinIO**: ตรวจสอบ TCP Reachability และทดสอบเรียก `list_buckets()` พร้อม timeout ป้องกัน thread ค้าง
- **Label Studio**: ตรวจสอบ TCP Reachability และเรียก `get_projects()` เมื่อพบ SDK
- ทุก Service จะมีการจับเวลาเพื่อวัด `latency_ms` อย่างแม่นยำ
