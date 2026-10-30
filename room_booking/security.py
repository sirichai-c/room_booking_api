from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from room_booking.config import settings

ALGORITHM = "HS256"

password_hash = PasswordHash.recommended()

# ใช้ตรวจรหัสผ่านหลอกตอนไม่พบผู้ใช้ เวลาตอบจะได้เท่ากัน เดาไม่ได้ว่าชื่อไหนมีอยู่จริง
DUMMY_HASH = password_hash.hash("dummy-password")


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return password_hash.verify(password, hashed)


def create_access_token(user_id: int) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_minutes)
    return jwt.encode({"sub": str(user_id), "exp": expire}, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> int | None:
    """คืน id ผู้ใช้ หรือ None ถ้า token ปลอม/หมดอายุ"""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        return int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        return None
