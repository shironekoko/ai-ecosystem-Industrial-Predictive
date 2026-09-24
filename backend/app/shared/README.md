# Shared Module

โฟลเดอร์ `shared/` ใช้สำหรับเก็บคอมโพเนนต์ ฟังก์ชัน โค้ด เครื่องมือ หรือ Pydantic Models ที่ถูกเรียกใช้งานร่วมกันจากหลายๆ Feature Modules

## จุดประสงค์
เพื่อลดการเขียนโค้ดซ้ำ (DRY - Don't Repeat Yourself) ระหว่างโมดูลฟีเจอร์ต่างๆ 

## สถานะปัจจุบัน
*(ปัจจุบันโฟลเดอร์นี้อาจยังว่างเปล่า หรือมีเพียงตัวอย่างเริ่มต้นเท่านั้น จะถูกเพิ่มเติมเมื่อโปรเจกต์ขยายใหญ่ขึ้น)*

## สิ่งที่ควรนำมาใส่ใน shared/
- **Pagination Helpers:** โครงสร้าง `Page[T]` หรือฟังก์ชันคำนวณหน้า
- **Common Response Models:** เช่น โมเดลตอบกลับมาตรฐาน `SuccessResponse`, `ErrorResponse`
- **Shared Enums:** ตัวแปร Enum ที่ใช้ร่วมกัน เช่น สถานะงาน (Pending, Running, Failed) ที่ Worker และ Profile ต่างก็อ้างอิงถึง
- **Base Schemas:** Pydantic Base Model ที่ตั้งค่า Config ไว้ล่วงหน้า
