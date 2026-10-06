# users — จัดการผู้ใช้และสิทธิ์

หน้า Users & Access (admin) · ตารางผู้ใช้อยู่ใน `auth/models.py` (`users`)

| ไฟล์ | หน้าที่ |
|---|---|
| `router.py` | `GET /users` · `POST /users` · `PATCH /users/{id}/role` · `DELETE /users/{id}` — เฉพาะ admin ทุก endpoint |
| `service.py` | อ่าน / สร้าง (hash รหัสผ่านด้วย bcrypt) / เปลี่ยนสิทธิ์ / ลบ |
| `schemas.py` | `UserItem`, `CreateUserRequest`, `UpdateUserRoleRequest` |

สิทธิ์: `engineer` = ใช้งานหน้าเครื่อง/ตรวจใบมีด · `admin` = + retrain, promote/reject, สลับ/โหลดแบบจำลอง (RUL และภาพ), จัดการผู้ใช้
(ตรวจที่ backend ด้วย `get_current_admin_user` — หน้าเว็บซ่อน/ปิดปุ่มเพื่อความสะดวกเท่านั้น)
บัญชีตั้งต้นของเครื่องพัฒนาถูกสร้างใน `main.py` (ปุ่มกรอกอัตโนมัติในหน้า login)
