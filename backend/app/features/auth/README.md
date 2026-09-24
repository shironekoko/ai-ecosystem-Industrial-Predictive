# Auth Feature

โมดูลสำหรับการจัดการ Authentication และ Authorization ในระบบ

## ระบบนี้ทำอะไรบ้าง
ฟีเจอร์นี้ดูแลเรื่องการสมัครสมาชิก การเข้าสู่ระบบ การสร้างและการตรวจสอบ JWT Token สำหรับยืนยันตัวตนก่อนเข้าถึงระบบในส่วนอื่นๆ

## Auth Flow Diagram
กระบวนการทำงานพื้นฐาน:
```text
Signup -> Login -> รับ JWT (Access + Refresh) -> นำ Access Token ไปเรียกใช้ API อื่นๆ
-> เมื่อ Access Token หมดอายุ -> ใช้ Refresh Token ขอใหม่ -> Logout
```

## API Endpoints
| Path | Method | คำอธิบาย |
| --- | --- | --- |
| `/auth/signup` | POST | สมัครสมาชิกใหม่ (ลงทะเบียน) |
| `/auth/login` | POST | เข้าสู่ระบบและรับ JWT Token |
| `/auth/refresh` | POST | ขอ Access Token ใหม่ด้วย Refresh Token |
| `/auth/logout` | POST | ออกจากระบบ (Invalidate token ถ้ามีการบันทึก) |

## JWT Strategy
- **Access Token:** มีอายุ 30 นาที (ปรับเปลี่ยนได้ในตั้งค่า)
- **Refresh Token:** มีอายุ 7 วัน (สำหรับขอ Access Token ใหม่โดยไม่ต้องล็อกอินซ้ำ)
- **Password Hashing:** ใช้ `bcrypt` เพื่อความปลอดภัยของการเก็บรหัสผ่าน

## ไฟล์ที่เกี่ยวข้อง
- `router.py`: นิยาม API Endpoints
- `service.py`: ตรรกะของฟีเจอร์ เช่น การสร้าง Token, ตรวจสอบรหัสผ่าน
- `models.py`: โครงสร้างฐานข้อมูลสำหรับเก็บข้อมูลผู้ใช้ (ถ้าเก็บแยกที่นี่)
- `schemas.py`: Pydantic Models สำหรับรับและตอบกลับข้อมูล
- `security.py`: ฟังก์ชันที่เกี่ยวกับความปลอดภัย (Hash Password, Verify)
- `dependencies.py`: สำหรับ Injection เพื่อดึงข้อมูลผู้ใช้จาก Token (`get_current_user`)

## หมายเหตุด้านความปลอดภัย (Security Notes)
- รหัสผ่านทุกตัวจะต้องถูก Hash เสมอ ไม่เก็บเป็น Plain text
- Secret Key ของ JWT ควรมีความยาวและซับซ้อนเพียงพอ และเก็บไว้ใน Environment Variable เท่านั้น
