from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from conftest import DAY, TEST_DATABASE_URL, at, book
from room_booking.models import Booking


# ---------- วันที่และ timezone (ข้อ 1) ----------

def test_create_booking(client, alice):
    res = book(client, alice, attendees=5)
    assert res.status_code == 201
    assert res.json() == {
        "id": 1,
        "room_id": 1,
        "username": "alice",
        "attendees": 5,
        "start": f"{DAY}T09:00:00+07:00",
        "end": f"{DAY}T11:00:00+07:00",
    }


def test_same_time_on_another_day_is_allowed(client, alice, bob):
    assert book(client, alice).status_code == 201
    assert book(client, bob, day="2099-03-03").status_code == 201


def test_explicit_timezone_is_respected(client, alice, bob):
    assert book(client, alice).status_code == 201
    # 02:00 UTC = 09:00 เวลาไทย ต้องชนกับการจองแรก
    res = client.post("/bookings", json={
        "room_id": 1, "start": f"{DAY}T02:00:00Z", "end": f"{DAY}T03:00:00Z",
    }, headers=bob)
    assert res.status_code == 409


def test_overlap_and_back_to_back(client, alice, bob):
    assert book(client, alice, start="09:00", end="11:00").status_code == 201
    assert book(client, bob, start="10:30", end="12:00").status_code == 409
    assert book(client, bob, start="11:00", end="13:00").status_code == 201
    # ห้องอื่นเวลาเดียวกันได้
    assert book(client, bob, room_id=2, start="09:00", end="11:00").status_code == 201


def test_minutes_are_supported(client, alice, bob):
    assert book(client, alice, start="09:15", end="10:45").status_code == 201
    assert book(client, bob, start="10:45", end="11:30").status_code == 201


@pytest.mark.parametrize("start, end, day", [
    ("07:00", "09:00", DAY),         # ก่อนเปิด
    ("19:00", "21:00", DAY),         # หลังปิด
    ("09:00", "14:00", DAY),         # เกิน 4 ชั่วโมง
    ("09:00", "10:00", "2020-01-06"),  # ย้อนหลัง
])
def test_booking_rules(client, alice, start, end, day):
    res = book(client, alice, start=start, end=end, day=day)
    assert res.status_code == 422
    assert isinstance(res.json()["detail"], str)


def test_booking_cannot_span_two_days(client, alice):
    res = client.post("/bookings", json={
        "room_id": 1, "start": at("19:00"), "end": at("09:00", "2099-03-03"),
    }, headers=alice)
    assert res.status_code == 422


def test_end_before_start(client, alice):
    res = book(client, alice, start="11:00", end="09:00")
    assert res.status_code == 422
    assert res.json()["errors"] == [{"field": "", "message": "เวลาจบต้องหลังเวลาเริ่ม"}]


def test_booking_unknown_room(client, alice):
    assert book(client, alice, room_id=99).status_code == 404


def test_booking_requires_login(client):
    assert book(client, {}).status_code == 401


# ---------- ความจุ (ข้อ 9) ----------

def test_attendees_over_capacity(client, alice):
    res = book(client, alice, room_id=3, attendees=5)
    assert res.status_code == 422
    assert "4" in res.json()["detail"]
    assert book(client, alice, room_id=3, attendees=4).status_code == 201


def test_patch_attendees_over_capacity(client, alice):
    book(client, alice, room_id=3, attendees=2)
    assert client.patch("/bookings/1", json={"attendees": 10}, headers=alice).status_code == 422


# ---------- ความเป็นส่วนตัวและเจ้าของ (ข้อ 8) ----------

def test_user_sees_only_own_bookings(client, alice, bob):
    book(client, alice)
    book(client, bob, room_id=2)

    mine = client.get("/bookings", headers=alice).json()
    assert [b["username"] for b in mine] == ["alice"]
    assert [b["username"] for b in client.get("/bookings/me", headers=bob).json()] == ["bob"]


def test_user_cannot_filter_other_users(client, alice):
    assert client.get("/bookings?user=bob", headers=alice).status_code == 403
    assert client.get("/bookings?user=alice", headers=alice).status_code == 200


def test_admin_sees_everyone_and_filters(client, alice, bob, admin):
    book(client, alice)
    book(client, bob, room_id=2)
    assert len(client.get("/bookings", headers=admin).json()) == 2
    assert [b["username"] for b in client.get("/bookings?user=bob", headers=admin).json()] == ["bob"]
    assert len(client.get("/bookings?room_id=1", headers=admin).json()) == 1
    assert len(client.get("/bookings?date=2099-03-03", headers=admin).json()) == 0


def test_cannot_touch_other_users_booking(client, alice, bob):
    book(client, alice)
    assert client.get("/bookings/1", headers=bob).status_code == 403
    assert client.patch("/bookings/1", json={"attendees": 2}, headers=bob).status_code == 403
    assert client.delete("/bookings/1", headers=bob).status_code == 403


def test_admin_can_manage_any_booking(client, alice, admin):
    book(client, alice)
    assert client.get("/bookings/1", headers=admin).status_code == 200
    assert client.patch("/bookings/1", json={"attendees": 3}, headers=admin).status_code == 200
    assert client.delete("/bookings/1", headers=admin).status_code == 204


# ---------- แก้และยกเลิก ----------

def test_patch_booking(client, alice):
    book(client, alice, start="09:00", end="11:00")
    # เลื่อนเวลาทับช่วงเดิมของตัวเองได้
    res = client.patch("/bookings/1", json={"start": at("10:00"), "end": at("12:00")}, headers=alice)
    assert res.status_code == 200
    assert res.json()["start"] == f"{DAY}T10:00:00+07:00"


def test_patch_into_someone_elses_slot(client, alice, bob):
    book(client, alice, start="09:00", end="11:00")
    book(client, bob, start="13:00", end="14:00")
    res = client.patch("/bookings/2", json={"start": at("10:00")}, headers=bob)
    assert res.status_code == 409


def test_patch_end_before_start(client, alice):
    book(client, alice, start="09:00", end="11:00")
    assert client.patch("/bookings/1", json={"end": at("08:30")}, headers=alice).status_code == 422


def test_patch_cannot_change_owner(client, alice):
    book(client, alice)
    res = client.patch("/bookings/1", json={"username": "bob", "user_id": 99}, headers=alice)
    assert res.status_code == 200
    assert res.json()["username"] == "alice"


def test_delete_booking_and_ids_not_reused(client, alice):
    book(client, alice)
    book(client, alice, start="13:00", end="14:00")
    assert client.delete("/bookings/2", headers=alice).status_code == 204
    assert client.get("/bookings/2", headers=alice).status_code == 404
    assert book(client, alice, start="15:00", end="16:00").json()["id"] == 3


# ---------- จองพร้อมกัน (ข้อ 5) ----------

def test_concurrent_bookings_only_one_wins(client, make_user):
    users = [make_user(f"user{i}") for i in range(8)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        codes = list(pool.map(lambda h: book(client, h).status_code, users))
    assert sorted(codes) == [201] + [409] * 7


@pytest.mark.skipif(
    not (TEST_DATABASE_URL or "").startswith("postgresql"),
    reason="ต้องใช้ PostgreSQL (ตั้ง TEST_DATABASE_URL)",
)
def test_database_rejects_overlap_on_postgres(client, alice, session_factory):
    """ถึงจะข้ามการเช็กในแอปไปเขียนฐานข้อมูลตรง ๆ ก็ยังจองซ้อนไม่ได้"""
    book(client, alice)
    with session_factory() as db:
        db.add(Booking(
            room_id=1, user_id=1, attendees=1,
            start=datetime(2099, 3, 2, 3, 0, tzinfo=UTC),  # 10:00 เวลาไทย
            end=datetime(2099, 3, 2, 5, 0, tzinfo=UTC),
        ))
        with pytest.raises(IntegrityError):
            db.commit()
