import os

# ตั้งค่าก่อน import แอป ไม่ให้ค่าใน .env ของเครื่องมีผลกับเทสต์
os.environ.update({
    "OPEN_HOUR": "8",
    "CLOSE_HOUR": "20",
    "MAX_BOOKING_HOURS": "4",
    "TIMEZONE": "Asia/Bangkok",
    "DATABASE_URL": "sqlite://",
    "SECRET_KEY": "test-secret-key-that-is-long-enough-123456",
    "ACCESS_TOKEN_MINUTES": "60",
})

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from room_booking.database import Base, get_db, make_engine
from room_booking.main import app
from room_booking.models import Room, User
from room_booking.security import hash_password

# ตั้ง TEST_DATABASE_URL เป็น PostgreSQL เพื่อทดสอบกับฐานข้อมูลจริง (ค่าเริ่มต้นใช้ไฟล์ SQLite ชั่วคราว)
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

PASSWORD = "password123"
DAY = "2099-03-02"  # วันในอนาคต (จันทร์) ใช้จองในเทสต์


@pytest.fixture
def engine(tmp_path):
    engine = make_engine(TEST_DATABASE_URL or f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def session_factory(engine):
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        db.add_all([
            Room(name="Room A", capacity=20),
            Room(name="Room B", capacity=8),
            Room(name="Room C", capacity=4),
        ])
        db.commit()
    return factory


@pytest.fixture
def client(session_factory):
    def override_get_db():
        with session_factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def make_user(client, session_factory):
    """สร้างผู้ใช้ในฐานข้อมูลแล้วคืน header Authorization ของผู้ใช้นั้น"""
    def _make(username: str, is_admin: bool = False) -> dict[str, str]:
        with session_factory() as db:
            db.add(User(username=username, password_hash=hash_password(PASSWORD), is_admin=is_admin))
            db.commit()
        res = client.post("/auth/token", data={"username": username, "password": PASSWORD})
        assert res.status_code == 200, res.text
        return {"Authorization": f"Bearer {res.json()['access_token']}"}

    return _make


@pytest.fixture
def alice(make_user):
    return make_user("alice")


@pytest.fixture
def bob(make_user):
    return make_user("bob")


@pytest.fixture
def admin(make_user):
    return make_user("admin", is_admin=True)


def at(hour_min: str, day: str = DAY) -> str:
    return f"{day}T{hour_min}:00"


def book(client, headers, room_id=1, start="09:00", end="11:00", day=DAY, **extra):
    body = {"room_id": room_id, "start": at(start, day), "end": at(end, day), **extra}
    return client.post("/bookings", json=body, headers=headers)
