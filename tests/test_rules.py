"""เทสต์กฎธุรกิจตรง ๆ โดยไม่ผ่าน HTTP (ข้อดีของการแยกกฎออกจาก router)"""
from datetime import datetime, timedelta

import pytest

from room_booking.booking_rules import (
    check_booking,
    ensure_can_access,
    ensure_no_overlap,
    ensure_room_fits,
    ensure_within_rules,
)
from room_booking.config import settings
from room_booking.exceptions import Conflict, Forbidden, NotFound, RuleViolation
from room_booking.models import Booking, Room, User
from room_booking.room_rules import ensure_fits_upcoming_bookings, ensure_name_is_free, ensure_room_is_unused


def t(hour: int, minute: int = 0, day: int = 2) -> datetime:
    """เวลาไทยวันที่ day มี.ค. 2099"""
    return datetime(2099, 3, day, hour, minute, tzinfo=settings.tz)


# ---------- กฎเวลา (ไม่ต้องใช้ฐานข้อมูล) ----------

def test_within_rules_accepts_valid_slot():
    ensure_within_rules(t(8), t(12))   # เริ่มตอนเปิดพอดี, 4 ชั่วโมงพอดี
    ensure_within_rules(t(16), t(20))  # จบตอนปิดพอดี


@pytest.mark.parametrize("start, end", [
    (t(11), t(9)),                           # จบก่อนเริ่ม
    (t(9), t(9)),                            # ยาว 0 นาที
    (t(7, 59), t(9)),                        # ก่อนเปิด 1 นาที
    (t(19), t(20, 1)),                       # หลังปิด 1 นาที
    (t(19), t(9, day=3)),                    # ข้ามวัน
    (t(9), t(13, 1)),                        # เกิน 4 ชั่วโมง 1 นาที
    (datetime.now(settings.tz) - timedelta(hours=1), datetime.now(settings.tz)),  # ย้อนหลัง
])
def test_within_rules_rejects(start, end):
    with pytest.raises(RuleViolation):
        ensure_within_rules(start, end)


def test_room_fits():
    room = Room(name="Room C", capacity=4)
    ensure_room_fits(room, 4)
    with pytest.raises(RuleViolation, match="จุได้ 4 คน"):
        ensure_room_fits(room, 5)


def test_can_access():
    owner = User(id=1, username="alice", is_admin=False)
    other = User(id=2, username="bob", is_admin=False)
    admin = User(id=3, username="admin", is_admin=True)
    booking = Booking(user_id=1)

    ensure_can_access(booking, owner)
    ensure_can_access(booking, admin)
    with pytest.raises(Forbidden):
        ensure_can_access(booking, other)


# ---------- กฎที่ต้องดูข้อมูลในฐานข้อมูล ----------

@pytest.fixture
def db(session_factory):
    with session_factory() as db:
        db.add(User(id=1, username="alice", password_hash="x"))
        db.add(Booking(room_id=1, user_id=1, attendees=6, start=t(9), end=t(11)))
        db.commit()
        yield db


@pytest.mark.parametrize("start, end, overlaps", [
    (t(10), t(12), True),    # ทับท้าย
    (t(8), t(10), True),     # ทับหัว
    (t(9, 30), t(10), True), # อยู่ข้างใน
    (t(8), t(12), True),     # ครอบทั้งหมด
    (t(11), t(12), False),   # ต่อท้ายพอดี
    (t(8), t(9), False),     # ต่อหัวพอดี
    (t(9, day=3), t(11, day=3), False),  # เวลาเดียวกันแต่คนละวัน
])
def test_no_overlap(db, start, end, overlaps):
    if overlaps:
        with pytest.raises(Conflict):
            ensure_no_overlap(db, 1, start, end)
    else:
        ensure_no_overlap(db, 1, start, end)


def test_no_overlap_ignores_itself_and_other_rooms(db):
    ensure_no_overlap(db, 1, t(10), t(12), ignore_id=1)
    ensure_no_overlap(db, 2, t(9), t(11))


def test_check_booking_runs_every_rule(db):
    assert check_booking(db, 2, t(9), t(11), attendees=8).name == "Room B"
    with pytest.raises(NotFound):
        check_booking(db, 99, t(9), t(11), attendees=1)
    with pytest.raises(RuleViolation):
        check_booking(db, 2, t(9), t(11), attendees=9)
    with pytest.raises(Conflict):
        check_booking(db, 1, t(10), t(12), attendees=1)


def test_room_rules(db):
    with pytest.raises(Conflict):
        ensure_name_is_free(db, "ROOM a")
    ensure_name_is_free(db, "Room A", ignore_id=1)

    with pytest.raises(Conflict):
        ensure_fits_upcoming_bookings(db, 1, 5)
    ensure_fits_upcoming_bookings(db, 1, 6)

    with pytest.raises(Conflict):
        ensure_room_is_unused(db, 1)
    ensure_room_is_unused(db, 2)
