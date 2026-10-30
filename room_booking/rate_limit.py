import math
from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from room_booking.config import settings
from room_booking.models import LoginFailure
from room_booking.services import now as utc_now

# จำนวนครั้งที่ IP เดียว login ผิดได้รวมทุกชื่อ (กันไล่เดารหัสหลายบัญชี) เทียบกับต่อชื่อ
_IP_MULTIPLIER = 4


class LoginRateLimiter:
    """นับการ login ผิดในช่วงเวลาล่าสุด ถ้าเกินกำหนดให้รอก่อน

    นับสองแบบ:
    - IP + ชื่อผู้ใช้: กันเดารหัสบัญชีเดียว (ไม่นับแค่ชื่อ ไม่งั้นคนอื่นแกล้งล็อกบัญชีเราได้)
    - IP อย่างเดียว: กันไล่เดารหัสหลายบัญชีจากที่เดียว

    เก็บในฐานข้อมูล ไม่ใช่หน่วยความจำ เพราะระบบจริงรันหลาย worker ถ้าแต่ละตัวนับเอง
    request จะถูกกระจายไปหลายตัว จนเดารหัสได้มากกว่ากำหนดหลายเท่า
    """

    def __init__(self, max_failures: int, window: timedelta):
        self.max_failures = max_failures
        self.window = window

    def _limits(self, ip: str, username: str) -> list[tuple[str, int]]:
        return [
            (f"user:{ip}:{username.lower()}", self.max_failures),
            (f"ip:{ip}", self.max_failures * _IP_MULTIPLIER),
        ]

    def retry_after(self, db: Session, ip: str, username: str, now: datetime | None = None) -> int:
        """จำนวนวินาทีที่ต้องรอ (0 = login ได้)"""
        now = now or utc_now()
        wait = 0.0
        for key, limit in self._limits(ip, username):
            recent = db.scalars(
                select(LoginFailure.failed_at)
                .where(LoginFailure.key == key, LoginFailure.failed_at > now - self.window)
                .order_by(LoginFailure.failed_at.desc())
                .limit(limit)
            ).all()
            if len(recent) >= limit:
                # ต้องรอจนครั้งที่ผิดเก่าสุดในชุดล่าสุดหลุดออกจากช่วงเวลา
                wait = max(wait, (recent[-1] + self.window - now).total_seconds())
        return math.ceil(wait)

    def record_failure(self, db: Session, ip: str, username: str, now: datetime | None = None) -> None:
        now = now or utc_now()
        # ลบของที่พ้นช่วงเวลาไปแล้ว ตารางจะได้ไม่โตเรื่อย ๆ
        db.execute(delete(LoginFailure).where(LoginFailure.failed_at <= now - self.window))
        db.add_all(LoginFailure(key=key, failed_at=now) for key, _ in self._limits(ip, username))
        db.commit()

    def record_success(self, db: Session, ip: str, username: str) -> None:
        """login ถูกแล้วล้างตัวนับของชื่อนั้น (ตัวนับของ IP ยังอยู่)"""
        user_key = self._limits(ip, username)[0][0]
        db.execute(delete(LoginFailure).where(LoginFailure.key == user_key))
        db.commit()


login_limiter = LoginRateLimiter(settings.login_max_failures, timedelta(minutes=settings.login_window_minutes))
