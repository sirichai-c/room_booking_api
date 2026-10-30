from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from room_booking.exceptions import Conflict
from room_booking.models import Booking, Room
from room_booking.services import now

# กฎของห้อง แยกจาก router: ไม่รู้จัก HTTP, โยน error จาก exceptions.py แทน HTTPException


def ensure_name_is_free(db: Session, name: str, ignore_id: int | None = None) -> None:
    """ชื่อห้องต้องไม่ซ้ำกับห้องอื่น (ไม่สนตัวพิมพ์เล็ก-ใหญ่)"""
    stmt = select(Room.id).where(func.lower(Room.name) == name.lower())
    if ignore_id is not None:
        stmt = stmt.where(Room.id != ignore_id)
    if db.scalar(stmt) is not None:
        raise Conflict(f"มีห้องชื่อ {name} อยู่แล้ว")


def ensure_fits_upcoming_bookings(db: Session, room_id: int, capacity: int) -> None:
    """ลดความจุห้องจนการจองที่ยังไม่ถึงเวลาไม่พอที่นั่งไม่ได้"""
    biggest = db.scalar(
        select(func.max(Booking.attendees)).where(Booking.room_id == room_id, Booking.end > now())
    )
    if biggest is not None and biggest > capacity:
        raise Conflict(f"มีการจองที่มีผู้เข้าร่วม {biggest} คน ลดความจุต่ำกว่านั้นไม่ได้")


def ensure_room_is_unused(db: Session, room_id: int) -> None:
    """ลบห้องไม่ได้ถ้ายังมีการจองอยู่"""
    if db.scalar(select(Booking.id).where(Booking.room_id == room_id).limit(1)) is not None:
        raise Conflict("ห้องนี้ยังมีการจองอยู่ ยกเลิกการจองก่อน")


def save_room(db: Session, room: Room) -> Room:
    try:
        db.commit()
    except IntegrityError:
        # อีก request สร้างชื่อเดียวกันตัดหน้าไปก่อน
        db.rollback()
        raise Conflict(f"มีห้องชื่อ {room.name} อยู่แล้ว")
    return room
