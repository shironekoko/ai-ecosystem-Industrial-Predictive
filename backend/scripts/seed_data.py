"""
Seed Data Script — สร้างข้อมูลตัวอย่างสำหรับทดสอบระบบ

วิธีใช้:
    cd backend
    uv run python scripts/seed_data.py
"""

import sys
from pathlib import Path

# เพิ่ม backend root เข้า sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import settings
from core.database import SessionLocal, Base, engine
from app.features.auth.security import hash_password
from app.features.auth.models import User


def seed_users():
    """สร้าง user ตัวอย่าง"""
    db = SessionLocal()
    try:
        # ตรวจสอบว่ามี user อยู่แล้วหรือไม่
        existing = db.query(User).filter(User.email == "admin@example.com").first()
        if existing:
            print("ℹ️  มี user ตัวอย่างอยู่แล้ว — ข้าม")
            return

        users = [
            User(
                email="admin@example.com",
                username="admin",
                hashed_password=hash_password("admin1234"),
                full_name="Admin User",
                bio="ผู้ดูแลระบบ AI Ecosystem",
            ),
            User(
                email="test@example.com",
                username="testuser",
                hashed_password=hash_password("test1234"),
                full_name="Test User",
                bio="บัญชีทดสอบ",
            ),
        ]

        for user in users:
            db.add(user)

        db.commit()
        print(f"✅ สร้าง {len(users)} users ตัวอย่างเรียบร้อย")

    except Exception as e:
        db.rollback()
        print(f"❌ Seed users failed: {e}")
    finally:
        db.close()


def main():
    print("🌱 Seeding data...\n")

    # สร้าง tables ถ้ายังไม่มี
    import app.features.auth.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables ready\n")

    seed_users()

    print("\n🎉 Seed complete!")


if __name__ == "__main__":
    main()
