from datetime import date

from fastapi import APIRouter, Query
from sqlalchemy import select

from room_booking.booking_rules import booking_lock, check_booking, ensure_can_access, save_booking
from room_booking.deps import CurrentUser, DbSession
from room_booking.exceptions import Forbidden
from room_booking.models import Booking, User
from room_booking.schemas import BookingCreate, BookingOut, BookingUpdate
from room_booking.services import find_booking_or_404, where_on_date

# router ทำแค่รับ request, เรียกกฎใน booking_rules.py, แล้วบันทึก/ตอบกลับ

router = APIRouter(prefix="/bookings", tags=["bookings"])


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
            raise Forbidden("ดูการจองของคนอื่นไม่ได้")
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
    with booking_lock:
        check_booking(db, data.room_id, data.start, data.end, data.attendees)

        booking = Booking(user=user, **data.model_dump())
        db.add(booking)
        return save_booking(db, booking)


@router.patch("/{booking_id}", response_model=BookingOut)
def update_booking(booking_id: int, data: BookingUpdate, db: DbSession, user: CurrentUser):
    with booking_lock:
        booking = find_booking_or_404(db, booking_id)
        ensure_can_access(booking, user)

        changes = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None}

        # รวมของเดิมกับของใหม่ แล้วตรวจผลลัพธ์ทั้งก้อนก่อนบันทึกจริง
        check_booking(
            db,
            room_id=changes.get("room_id", booking.room_id),
            start=changes.get("start", booking.start),
            end=changes.get("end", booking.end),
            attendees=changes.get("attendees", booking.attendees),
            ignore_id=booking_id,
        )

        for key, value in changes.items():
            setattr(booking, key, value)
        return save_booking(db, booking)


@router.delete("/{booking_id}", status_code=204)
def delete_booking(booking_id: int, db: DbSession, user: CurrentUser):
    booking = find_booking_or_404(db, booking_id)
    ensure_can_access(booking, user)
    db.delete(booking)
    db.commit()
