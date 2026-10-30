import threading
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from room_booking.config import settings
from room_booking.deps import CurrentUser, DbSession
from room_booking.models import Booking, Room, User
from room_booking.schemas import BookingCreate, BookingOut, BookingUpdate
from room_booking.services import find_booking_or_404, find_room_or_404, now, where_on_date

router = APIRouter(prefix="/bookings", tags=["bookings"])

# กันสอง request เช็กเวลาว่างพร้อมกันแล้วผ่านทั้งคู่จนจองซ้อนกัน
# lock ใช้ได้ภายใน process เดียว ถ้ารันหลาย worker บน PostgreSQL มี exclusion constraint กันไว้อีกชั้น
_booking_lock = threading.Lock()


# ---------- ฟังก์ชันช่วย ----------

def _fmt(value: datetime, pattern: str = "%Y-%m-%d %H:%M") -> str:
    return value.astimezone(settings.tz).strftime(pattern)


def ensure_within_rules(start: datetime, end: datetime) -> None:
    """กฎจาก .env: จองล่วงหน้าเท่านั้น, อยู่ในเวลาเปิด-ปิดของวันเดียวกัน, ไม่เกินจำนวนชั่วโมงสูงสุด"""
    if start <= now():
        raise HTTPException(status_code=422, detail="จองย้อนหลังไม่ได้")

    day = datetime.combine(start.astimezone(settings.tz).date(), time(), settings.tz)
    opens = day + timedelta(hours=settings.open_hour)
    closes = day + timedelta(hours=settings.close_hour)
    if start < opens or end > closes:
        raise HTTPException(
            status_code=422,
            detail=f"จองได้ช่วง {settings.open_hour:02d}:00-{settings.close_hour:02d}:00 ภายในวันเดียวกันเท่านั้น",
        )
    if end - start > timedelta(hours=settings.max_booking_hours):
        raise HTTPException(
            status_code=422,
            detail=f"จองได้ไม่เกิน {settings.max_booking_hours} ชั่วโมง",
        )


def ensure_room_fits(room: Room, attendees: int) -> None:
    if attendees > room.capacity:
        raise HTTPException(
            status_code=422,
            detail=f"ห้อง {room.name} จุได้ {room.capacity} คน แต่จองมา {attendees} คน",
        )


def ensure_no_overlap(
        db: Session, room_id: int, start: datetime, end: datetime, ignore_id: int | None = None,
) -> None:
    """เวลาต้องไม่ชนกับการจองอื่นของห้องเดียวกัน (ignore_id = ไม่เทียบกับตัวเอง ตอนแก้)"""
    stmt = select(Booking).where(Booking.room_id == room_id, Booking.start < end, Booking.end > start)
    if ignore_id is not None:
        stmt = stmt.where(Booking.id != ignore_id)
    other = db.scalars(stmt.limit(1)).first()
    if other is not None:
        raise HTTPException(
            status_code=409,
            detail=f"ห้องนี้ถูกจองช่วง {_fmt(other.start)}-{_fmt(other.end, '%H:%M')} แล้ว",
        )


def ensure_can_access(booking: Booking, user: User) -> None:
    """เจ้าของหรือแอดมินเท่านั้นที่ดู/แก้/ยกเลิกการจองได้"""
    if booking.user_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="ไม่มีสิทธิ์จัดการการจองนี้")


def save_booking(db: Session, booking: Booking) -> Booking:
    try:
        db.commit()
    except IntegrityError:
        # PostgreSQL exclusion constraint จับการจองซ้อนที่หลุด lock มาได้ (เช่นรันหลาย worker)
        db.rollback()
        raise HTTPException(status_code=409, detail="ห้องนี้ถูกจองช่วงเวลานี้แล้ว")
    return booking


# ---------- endpoint ----------

@router.get("", response_model=list[BookingOut])
def list_bookings(
        db: DbSession,
        user: CurrentUser,
        username: str | None = Query(default=None, max_length=50, alias="user"),
        room_id: int | None = Query(default=None, gt=0),
        on: date | None = Query(default=None, alias="date"),
):
    """แอดมินเห็นการจองของทุกคน ผู้ใช้ทั่วไปเห็นเฉพาะของตัวเอง"""
    stmt = select(Booking).order_by(Booking.start)
    if not user.is_admin:
        if username is not None and username != user.username:
            raise HTTPException(status_code=403, detail="ดูการจองของคนอื่นไม่ได้")
        stmt = stmt.where(Booking.user_id == user.id)
    elif username is not None:
        stmt = stmt.join(Booking.user).where(User.username == username)
    if room_id is not None:
        stmt = stmt.where(Booking.room_id == room_id)
    if on is not None:
        stmt = where_on_date(stmt, on)
    return db.scalars(stmt).all()


# ⚠️ ต้องอยู่เหนือ /{booking_id} ไม่งั้น FastAPI จะพยายามแปลง "me" เป็น int แล้วได้ 422
@router.get("/me", response_model=list[BookingOut])
def list_my_bookings(db: DbSession, user: CurrentUser):
    stmt = select(Booking).where(Booking.user_id == user.id).order_by(Booking.start)
    return db.scalars(stmt).all()


@router.get("/{booking_id}", response_model=BookingOut)
def get_booking(booking_id: int, db: DbSession, user: CurrentUser):
    booking = find_booking_or_404(db, booking_id)
    ensure_can_access(booking, user)
    return booking


@router.post("", status_code=201, response_model=BookingOut)
def create_booking(data: BookingCreate, db: DbSession, user: CurrentUser):
    with _booking_lock:
        room = find_room_or_404(db, data.room_id)
        ensure_within_rules(data.start, data.end)
        ensure_room_fits(room, data.attendees)
        ensure_no_overlap(db, data.room_id, data.start, data.end)

        booking = Booking(user=user, **data.model_dump())
        db.add(booking)
        return save_booking(db, booking)


@router.patch("/{booking_id}", response_model=BookingOut)
def update_booking(booking_id: int, data: BookingUpdate, db: DbSession, user: CurrentUser):
    with _booking_lock:
        booking = find_booking_or_404(db, booking_id)
        ensure_can_access(booking, user)

        changes = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None}

        # รวมของเดิมกับของใหม่ แล้วตรวจผลลัพธ์ทั้งก้อนก่อนบันทึกจริง
        room_id = changes.get("room_id", booking.room_id)
        start = changes.get("start", booking.start)
        end = changes.get("end", booking.end)
        attendees = changes.get("attendees", booking.attendees)

        room = find_room_or_404(db, room_id)
        if end <= start:
            raise HTTPException(status_code=422, detail="เวลาจบต้องหลังเวลาเริ่ม")
        ensure_within_rules(start, end)
        ensure_room_fits(room, attendees)
        ensure_no_overlap(db, room_id, start, end, ignore_id=booking_id)

        for key, value in changes.items():
            setattr(booking, key, value)
        return save_booking(db, booking)


@router.delete("/{booking_id}", status_code=204)
def delete_booking(booking_id: int, db: DbSession, user: CurrentUser):
    booking = find_booking_or_404(db, booking_id)
    ensure_can_access(booking, user)
    db.delete(booking)
    db.commit()
