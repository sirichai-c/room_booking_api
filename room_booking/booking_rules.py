import threading
from datetime import datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from room_booking.config import settings
from room_booking.exceptions import Conflict, Forbidden, RuleViolation
from room_booking.models import Booking, Room, User
from room_booking.services import find_room_or_404, now

# กฎของการจอง แยกจาก router: ไม่รู้จัก HTTP, โยน error จาก exceptions.py แทน HTTPException

# กันสอง request เช็กเวลาว่างพร้อมกันแล้วผ่านทั้งคู่จนจองซ้อนกัน ต้องครอบตั้งแต่ check_booking ถึง save_booking
# lock ใช้ได้ภายใน process เดียว ถ้ารันหลาย worker บน PostgreSQL มี exclusion constraint กันไว้อีกชั้น
booking_lock = threading.Lock()


def _fmt(value: datetime, pattern: str = "%Y-%m-%d %H:%M") -> str:
    return value.astimezone(settings.tz).strftime(pattern)


def ensure_within_rules(start: datetime, end: datetime) -> None:
    """กฎจาก .env: จองล่วงหน้าเท่านั้น, อยู่ในเวลาเปิด-ปิดของวันเดียวกัน, ไม่เกินจำนวนชั่วโมงสูงสุด"""
    if end <= start:
        raise RuleViolation("เวลาจบต้องหลังเวลาเริ่ม")
    if start <= now():
        raise RuleViolation("จองย้อนหลังไม่ได้")

    day = datetime.combine(start.astimezone(settings.tz).date(), time(), settings.tz)
    opens = day + timedelta(hours=settings.open_hour)
    closes = day + timedelta(hours=settings.close_hour)
    if start < opens or end > closes:
        raise RuleViolation(
            f"จองได้ช่วง {settings.open_hour:02d}:00-{settings.close_hour:02d}:00 ภายในวันเดียวกันเท่านั้น"
        )
    if end - start > timedelta(hours=settings.max_booking_hours):
        raise RuleViolation(f"จองได้ไม่เกิน {settings.max_booking_hours} ชั่วโมง")


def ensure_room_fits(room: Room, attendees: int) -> None:
    if attendees > room.capacity:
        raise RuleViolation(f"ห้อง {room.name} จุได้ {room.capacity} คน แต่จองมา {attendees} คน")


def ensure_no_overlap(
        db: Session, room_id: int, start: datetime, end: datetime, ignore_id: int | None = None,
) -> None:
    """เวลาต้องไม่ชนกับการจองอื่นของห้องเดียวกัน (ignore_id = ไม่เทียบกับตัวเอง ตอนแก้)"""
    stmt = select(Booking).where(Booking.room_id == room_id, Booking.start < end, Booking.end > start)
    if ignore_id is not None:
        stmt = stmt.where(Booking.id != ignore_id)
    other = db.scalars(stmt.limit(1)).first()
    if other is not None:
        raise Conflict(f"ห้องนี้ถูกจองช่วง {_fmt(other.start)}-{_fmt(other.end, '%H:%M')} แล้ว")


def ensure_can_access(booking: Booking, user: User) -> None:
    """เจ้าของหรือแอดมินเท่านั้นที่ดู/แก้/ยกเลิกการจองได้"""
    if booking.user_id != user.id and not user.is_admin:
        raise Forbidden("ไม่มีสิทธิ์จัดการการจองนี้")


def check_booking(
        db: Session,
        room_id: int,
        start: datetime,
        end: datetime,
        attendees: int,
        ignore_id: int | None = None,
) -> Room:
    """ตรวจกฎทั้งหมดของการจองหนึ่งรายการ ใช้ทั้งตอนจองใหม่และตอนแก้ คืนห้องที่จอง"""
    room = find_room_or_404(db, room_id)
    ensure_within_rules(start, end)
    ensure_room_fits(room, attendees)
    ensure_no_overlap(db, room_id, start, end, ignore_id=ignore_id)
    return room


def save_booking(db: Session, booking: Booking) -> Booking:
    try:
        db.commit()
    except IntegrityError:
        # PostgreSQL exclusion constraint จับการจองซ้อนที่หลุด lock มาได้ (เช่นรันหลาย worker)
        db.rollback()
        raise Conflict("ห้องนี้ถูกจองช่วงเวลานี้แล้ว")
    return booking
