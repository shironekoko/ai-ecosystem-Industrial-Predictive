# auth — สมัครสมาชิก / เข้าสู่ระบบ (JWT)

```
signup → login → access token (JWT, เก็บใน localStorage ของเว็บ) → ส่ง Authorization: Bearer … กับทุก endpoint
ออกจากระบบ = เว็บลบ token (JWT แบบ stateless) · token หมดอายุ/ไม่ถูกต้อง (401 / WebSocket 4401) → เว็บล้าง session แล้วพากลับหน้า login
```

ไม่ต้องล็อกอินเฉพาะ `GET /health`, `POST /auth/signup`, `POST /auth/login` — นอกนั้นต้องล็อกอินทั้งหมด (รายละเอียดใน [features/README](../README.md))

| Method | Path | หน้าที่ |
|---|---|---|
| POST | `/auth/signup` | สมัครสมาชิก (แท็บ Create Account ในหน้า login) |
| POST | `/auth/login` | ตรวจอีเมล + รหัสผ่าน → `{access_token, token_type, user}` |
| GET | `/auth/me` | ผู้ใช้ของ token (เว็บเรียกตอนเปิดเพื่อตรวจว่ายังล็อกอินอยู่) |

| ไฟล์ | หน้าที่ |
|---|---|
| `router.py` | endpoint ข้างบน |
| `service.py` | ค้นหาผู้ใช้, ตรวจอีเมล/ชื่อซ้ำ, สร้างผู้ใช้, ตรวจรหัสผ่าน |
| `security.py` | hash/ตรวจรหัสผ่าน (bcrypt), สร้าง/ถอดรหัส access token |
| `dependencies.py` | `get_current_user` / `get_current_active_user` — dependency ของ endpoint ที่ต้องล็อกอิน · `get_current_admin_user` — งานของ admin (`403` ถ้าไม่ใช่) · `actor_name` — ชื่อผู้ทำรายการใน audit จาก token · `websocket_user` — ตรวจ token ที่ส่งมาในข้อความแรกของ WebSocket |
| `models.py` | ตาราง `users` (ใช้ร่วมกับ feature `users`) |
| `schemas.py` | `SignUpRequest`, `LoginRequest`, `UserResponse`, `TokenResponse` |

- อายุ token: `ACCESS_TOKEN_EXPIRE_MINUTES` (ค่าเริ่มต้น 30 นาที)
- `JWT_SECRET_KEY` ควรตั้งใน `.env` — ถ้าไม่ตั้ง ระบบสุ่มใหม่ทุกครั้งที่ backend เริ่ม ทำให้ทุกคนต้องล็อกอินใหม่หลัง restart
