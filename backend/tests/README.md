# tests — pytest

```bash
cd backend && uv run --no-sync pytest tests/ -q            # เครื่องที่ไม่มี torch: test ที่ต้องใช้ torch ถูกข้าม
docker compose exec trainer-worker sh -c "cd /app && .venv/bin/python -m pytest tests/ -q"   # ครบทุก test (มี torch)
```
test ที่ต้องใช้ชุดข้อมูล/แบบจำลองจะข้ามเองถ้าไม่พบไฟล์

| ไฟล์ | ตรวจอะไร |
|---|---|
| `test_auth_guard.py` | ทุก endpoint ต้องมี Bearer token ยกเว้น health / signup / login (ตรวจจาก OpenAPI + เรียกจริงได้ 401) · งานของ admin ตอบ 403 กับ engineer · `actor` ใน audit มาจาก token ไม่ใช่ body · WebSocket ปิดด้วย 4401 เมื่อไม่มี token ที่ถูกต้อง (ไม่ต้องใช้ DB / MinIO / Redis) |
| `test_tool_life.py` | `tool_life/runtime.py` ตรงกับต้นฉบับใน `timeseries_docs` · self-test ของแบบจำลองที่ส่งออก · ฟีเจอร์ที่ backend คำนวณจาก .h5 ระหว่างสตรีม = ฟีเจอร์ที่ใช้ฝึก · ตารางสตรีมไม่มี VB · การเล่นสตรีมให้ผลเท่ากับการประเมินแบบออฟไลน์ทุกรัน |
| `test_tool_vision.py` | การแบ่งดอก (ฝึก/val/ดอกบนเครื่อง ไม่ทับกัน) · ใช้เฉพาะภาพช่วงท้ายอายุที่สึกใกล้ดอกจริง · บริบทจาก RUL ไม่มีค่าจริง · เกณฑ์ 103/140 ตรงกับ RUL · ระดับดอก = เฉลี่ย 4 ใบ · ช่วงความไม่แน่นอน · payload ไม่สปอย label/ค่าที่ bench วัด · checkpoint (เดี่ยว/ensemble), augmentation, crop, normalization |
