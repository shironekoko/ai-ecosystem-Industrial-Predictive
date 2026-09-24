# Workers (Background Jobs)

โมดูลนี้รับผิดชอบในการจัดการ Background Jobs ของ AI Ecosystem ผ่าน ARQ และ Redis

## หน้าที่ของโมดูล

จัดการคิวการทำงาน (Task Queue) และการประมวลผลงานแบบ Asynchronous ในแบคกราวด์ด้วย Redis ทำให้ API หลักสามารถตอบสนองผู้ใช้ได้อย่างรวดเร็ว โดยผลักภาระงานที่ใช้เวลานานไปให้ Worker เป็นผู้จัดการ

## Endpoints

- `POST /workers/jobs`: เพิ่ม Job เข้าคิว (Enqueue)
- `GET /workers/jobs/{job_id}`: ตรวจสอบสถานะของ Job
- `GET /workers/redis/ping`: ทดสอบการเชื่อมต่อกับ Redis
- `GET /workers/redis/info`: ตรวจสอบสถานะและสถิติการใช้งาน Redis

## สถาปัตยกรรม (Architecture)

**FastAPI (API Router & Service)** -> ส่งงานเข้า -> **Redis (Queue)** -> รับงานจากคิว -> **ARQ Worker (Tasks)**

1. **API**: รับ Request และสร้าง Job ใน Redis ผ่าน `arq.create_pool`
2. **Redis**: จัดเก็บและจัดการคิว
3. **Worker**: รันงานตามกำหนดการ (ใช้ไฟล์ `tasks.py`)

## วิธีการรัน ARQ Worker

เปิด Terminal หรือ Command Prompt แยกอีก 1 หน้าต่าง, เข้าไปยังไดเรกทอรี `backend` จากนั้นรันคำสั่ง:

```bash
arq app.features.workers.tasks.WorkerSettings
```

## ตัวอย่างการใช้งาน

1. เริ่มต้น Worker ให้พร้อมรับงาน
2. เรียกใช้งาน API `POST /workers/jobs` พร้อม Payload:
   ```json
   {
       "job_name": "simple_work",
       "job_data": "ทดสอบประมวลผลข้อมูล 123"
   }
   ```
3. นำ `job_id` ที่ได้รับไปเช็คสถานะที่ `GET /workers/jobs/{job_id}`
