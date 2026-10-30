from datetime import UTC, date, datetime, time, timedelta

from fastapi import HTTPException
from sqlalchemy import Select
from sqlalchemy.orm import Session

from room_booking.config import settings
from room_booking.models import Booking, Room

# ฟังก์ชันที่ทั้ง rooms.py และ bookings.py ใช้ร่วมกัน


def now() -> datetime:
    return datetime.now(UTC)


def find_room_or_404(db: Session, room_id: int) -> Room:
    room = db.get(Room, room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="ไม่พบห้อง")
    return room


def find_booking_or_404(db: Session, booking_id: int) -> Booking:
    booking = db.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail="ไม่พบการจอง")
    return booking


def where_on_date(stmt: Select, day: date) -> Select:
    """กรองเฉพาะการจองที่อยู่ในวันนั้น (วันตามเวลาท้องถิ่น)"""
    day_start = datetime.combine(day, time(), settings.tz)
    day_end = day_start + timedelta(days=1)
    return stmt.where(Booking.start < day_end, Booking.end > day_start)
