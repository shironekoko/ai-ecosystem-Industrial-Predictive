# tests — pytest

```bash
cd backend && uv run --no-sync pytest tests/ -q            # เครื่องที่ไม่มี torch: test ที่ต้องใช้ torch ถูกข้าม
docker compose exec trainer-worker sh -c "cd /app && .venv/bin/python -m pytest tests/ -q"   # test ที่ต้องใช้ torch (มี GPU/torch)
```
test ที่ต้องใช้ชุดข้อมูล/แบบจำลองจะข้ามเองถ้าไม่พบไฟล์

| ไฟล์ | test | ตรวจอะไร |
|---|---|---|
| `test_auth_guard.py` | 9 | ทุก endpoint ต้องมี Bearer token ยกเว้น health / signup / login (ตรวจจาก OpenAPI + เรียกจริงได้ 401) · token ผิดได้ 401 · งานของ admin ตอบ 403 กับ engineer · `actor` ใน audit มาจาก token ไม่ใช่ body · WebSocket ปิดด้วย 4401 เมื่อไม่มี token ที่ถูกต้อง / ไม่ส่งข้อความแรก · `install` ใบเบิกแล้วเครื่องพร้อมในสถานะหยุดชั่วคราว (ไม่ต้องใช้ DB / MinIO / Redis) |
| `test_tool_life.py` | 6 | `tool_life/runtime.py` ตรงกับต้นฉบับใน `timeseries_docs` · self-test ของแบบจำลองที่ส่งออก · ฟีเจอร์ที่ backend คำนวณจาก .h5 ระหว่างสตรีม = ฟีเจอร์ที่ใช้ฝึก · ตารางสตรีมไม่มี VB · การเล่นสตรีมให้ผลเท่ากับการประเมินแบบออฟไลน์ทุกรัน · ติดตั้งดอกใหม่ = รอบใหม่ `PAUSED` จนผู้ควบคุมกดเริ่มตัด (`start` ดอกที่ถอดแล้วได้ 409) |
| `test_tool_vision.py` | 17 | การแบ่งดอก (ฝึก/val/ดอกบนเครื่อง ไม่ทับกัน) · ใช้เฉพาะภาพช่วงท้ายอายุที่สึกใกล้ดอกจริง · บริบทจาก RUL ไม่มีค่าจริง · เกณฑ์ 103/140 ตรงกับ RUL · ระดับดอก = เฉลี่ย 4 ใบ · ช่วงความไม่แน่นอน · payload ไม่สปอย label/ค่า VB จริงของชุดข้อมูล · checkpoint (เดี่ยว/ensemble), augmentation, crop, normalization (2 test ที่ต้องใช้ torch) · retrain กันดอกตรวจ gate ทั้งดอก · retrain อัตโนมัตินับเป็นดอกใหม่ (ไม่ใช่ภาพ) และเริ่มเมื่อครบเกณฑ์เท่านั้น · ข้อมูลใบเบิก + การจัดการดอกที่ถอด · ค่าเริ่มต้นของช่องกรอกค่าที่วัด = flank wear ของภาพนั้น |

ผลล่าสุด: **34 test** — บนเครื่อง (ไม่มี torch) 32 ผ่าน + 2 ข้าม (test ที่ต้องใช้ torch) · ใน trainer-worker 30 ผ่าน + 4 ข้าม (container ไม่ได้ mount `timeseries_docs/`) → รันทั้งสองที่แล้วผ่านครบทุก test
