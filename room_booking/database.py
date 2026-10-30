from collections.abc import Iterator
from datetime import UTC

from sqlalchemy import DateTime, Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.types import TypeDecorator

from room_booking.config import settings


class Base(DeclarativeBase):
    pass


class UTCDateTime(TypeDecorator):
    """เก็บเวลาเป็น UTC เสมอ และอ่านกลับมาเป็น datetime ที่มี timezone

    SQLite ไม่เก็บ timezone ให้ จึงเก็บเป็นเวลา UTC แบบไม่มี timezone แล้วเติมกลับตอนอ่าน
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        value = value.astimezone(UTC)
        return value.replace(tzinfo=None) if dialect.name == "sqlite" else value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def make_engine(url: str) -> Engine:
    if not url.startswith("sqlite"):
        return create_engine(url, pool_pre_ping=True)

    engine = create_engine(url, connect_args={"check_same_thread": False})

    # SQLite ปิดการเช็ก foreign key ไว้เป็นค่าเริ่มต้น
    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    return engine


engine = make_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    with SessionLocal() as db:
        yield db
