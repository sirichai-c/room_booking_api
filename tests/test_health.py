from room_booking.database import get_db
from room_booking.main import app


def test_health_ok(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "database": "ok"}


def test_health_reports_database_down(client, tmp_path):
    from sqlalchemy.orm import sessionmaker
    from room_booking.database import make_engine

    # ชี้ไปที่ไฟล์ในโฟลเดอร์ที่ไม่มีอยู่ SQLite จะเปิดไม่ได้
    broken = make_engine(f"sqlite:///{tmp_path / 'missing' / 'x.db'}")

    def broken_db():
        with sessionmaker(bind=broken)() as db:
            yield db

    app.dependency_overrides[get_db] = broken_db
    res = client.get("/health")
    assert res.status_code == 503
    assert res.json()["status"] == "error"


def test_request_id_is_returned(client):
    generated = client.get("/rooms").headers["x-request-id"]
    assert len(generated) == 32

    assert client.get("/rooms", headers={"X-Request-ID": "abc-123"}).headers["x-request-id"] == "abc-123"
    # ค่าที่อาจใช้แทรก log ปลอมจะถูกแทนด้วยค่าใหม่
    forged = client.get("/rooms", headers={"X-Request-ID": "x\tforged log line"}).headers["x-request-id"]
    assert forged != "x\tforged log line"
