from datetime import date

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from room_booking.deps import AdminUser, DbSession
from room_booking.models import Booking, Room
from room_booking.schemas import BookingSlot, RoomCreate, RoomOut, RoomUpdate
from room_booking.services import find_room_or_404, now, where_on_date

router = APIRouter(prefix="/rooms", tags=["rooms"])


def ensure_name_is_free(db: Session, name: str, ignore_id: int | None = None) -> None:
    """ชื่อห้องต้องไม่ซ้ำกับห้องอื่น (ไม่สนตัวพิมพ์เล็ก-ใหญ่)"""
    stmt = select(Room.id).where(func.lower(Room.name) == name.lower())
    if ignore_id is not None:
        stmt = stmt.where(Room.id != ignore_id)
    if db.scalar(stmt) is not None:
        raise HTTPException(status_code=409, detail=f"มีห้องชื่อ {name} อยู่แล้ว")


def ensure_fits_upcoming_bookings(db: Session, room_id: int, capacity: int) -> None:
    """ลดความจุห้องจนการจองที่ยังไม่ถึงเวลาไม่พอที่นั่งไม่ได้"""
    biggest = db.scalar(
        select(func.max(Booking.attendees)).where(Booking.room_id == room_id, Booking.end > now())
    )
    if biggest is not None and biggest > capacity:
        raise HTTPException(
            status_code=409,
            detail=f"มีการจองที่มีผู้เข้าร่วม {biggest} คน ลดความจุต่ำกว่านั้นไม่ได้",
        )


def save_room(db: Session, room: Room) -> Room:
    try:
        db.commit()
    except IntegrityError:
        # อีก request สร้างชื่อเดียวกันตัดหน้าไปก่อน
        db.rollback()
        raise HTTPException(status_code=409, detail=f"มีห้องชื่อ {room.name} อยู่แล้ว")
    return room


@router.get("", response_model=list[RoomOut])
def list_rooms(
        db: DbSession,
        min_capacity: int = Query(default=0, ge=0),
        name: str | None = Query(default=None, max_length=50),
):
    stmt = select(Room).where(Room.capacity >= min_capacity).order_by(Room.id)
    if name is not None:
        stmt = stmt.where(Room.name.icontains(name))
    return db.scalars(stmt).all()


@router.get("/{room_id}", response_model=RoomOut)
def get_room(room_id: int, db: DbSession):
    return find_room_or_404(db, room_id)


@router.get("/{room_id}/bookings", response_model=list[BookingSlot])
def list_room_bookings(
        room_id: int,
        db: DbSession,
        on: date | None = Query(default=None, alias="date"),
):
    """ช่วงเวลาที่ห้องถูกจองแล้ว (ไม่เปิดเผยว่าใครจอง)"""
    find_room_or_404(db, room_id)
    stmt = select(Booking).where(Booking.room_id == room_id).order_by(Booking.start)
    if on is not None:
        stmt = where_on_date(stmt, on)
    return db.scalars(stmt).all()


@router.post("", status_code=201, response_model=RoomOut)
def create_room(data: RoomCreate, db: DbSession, _: AdminUser):
    ensure_name_is_free(db, data.name)

    room = Room(**data.model_dump())
    db.add(room)
    return save_room(db, room)


@router.patch("/{room_id}", response_model=RoomOut)
def update_room(room_id: int, data: RoomUpdate, db: DbSession, _: AdminUser):
    room = find_room_or_404(db, room_id)
    changes = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None}

    if "name" in changes:
        ensure_name_is_free(db, changes["name"], ignore_id=room_id)
    if "capacity" in changes:
        ensure_fits_upcoming_bookings(db, room_id, changes["capacity"])

    for key, value in changes.items():
        setattr(room, key, value)
    return save_room(db, room)


@router.delete("/{room_id}", status_code=204)
def delete_room(room_id: int, db: DbSession, _: AdminUser):
    room = find_room_or_404(db, room_id)

    if db.scalar(select(Booking.id).where(Booking.room_id == room_id).limit(1)) is not None:
        raise HTTPException(status_code=409, detail="ห้องนี้ยังมีการจองอยู่ ยกเลิกการจองก่อน")

    db.delete(room)
    db.commit()
