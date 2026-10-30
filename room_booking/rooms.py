from datetime import date

from fastapi import APIRouter, Query
from sqlalchemy import select

from room_booking.deps import AdminUser, DbSession
from room_booking.models import Booking, Room
from room_booking.room_rules import (
    ensure_fits_upcoming_bookings,
    ensure_name_is_free,
    ensure_room_is_unused,
    save_room,
)
from room_booking.schemas import BookingSlot, RoomCreate, RoomOut, RoomUpdate
from room_booking.services import find_room_or_404, where_on_date

router = APIRouter(prefix="/rooms", tags=["rooms"])


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
    ensure_room_is_unused(db, room_id)

    db.delete(room)
    db.commit()
