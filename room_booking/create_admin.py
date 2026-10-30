"""สร้างแอดมิน หรือเลื่อนผู้ใช้ที่มีอยู่แล้วเป็นแอดมิน

    python -m room_booking.create_admin <username>
"""
import argparse
import getpass
import sys

from pydantic import ValidationError
from sqlalchemy import select

from room_booking.database import SessionLocal
from room_booking.models import User
from room_booking.schemas import UserCreate
from room_booking.security import hash_password


def main() -> None:
    parser = argparse.ArgumentParser(description="สร้างหรือเลื่อนผู้ใช้เป็นแอดมิน")
    parser.add_argument("username")
    args = parser.parse_args()
    username = args.username.lower()

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == username))
        if user is None:
            password = getpass.getpass("รหัสผ่าน: ")
            try:
                data = UserCreate(username=username, password=password)
            except ValidationError as e:
                sys.exit(f"ข้อมูลไม่ถูกต้อง: {e}")
            db.add(User(username=data.username, password_hash=hash_password(data.password), is_admin=True))
            print(f"สร้างแอดมิน {username} แล้ว")
        else:
            user.is_admin = True
            print(f"เลื่อน {username} เป็นแอดมินแล้ว")
        db.commit()


if __name__ == "__main__":
    main()
