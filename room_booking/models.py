from datetime import datetime

from sqlalchemy import DDL, CheckConstraint, ForeignKey, Index, String, event, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from room_booking.database import Base, UTCDateTime

# ตารางในฐานข้อมูล (SQLAlchemy) ส่วนรูปแบบข้อมูลขาเข้า-ขาออกของ API อยู่ใน schemas.py

# SQLite ปกติจะเอา id ที่มากที่สุดซึ่งถูกลบไปแล้วกลับมาใช้ใหม่ ต้องเปิด AUTOINCREMENT ให้ id ไม่ซ้ำ
NO_ID_REUSE = {"sqlite_autoincrement": True}


class User(Base):
    __tablename__ = "users"
    __table_args__ = NO_ID_REUSE

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(default=False)


# แอปเก็บ username เป็นตัวพิมพ์เล็กอยู่แล้ว index นี้กันอีกชั้นเผื่อมีข้อมูลเข้าทางอื่น
Index("uq_users_username_lower", func.lower(User.username), unique=True)


class Room(Base):
    __tablename__ = "rooms"
    __table_args__ = NO_ID_REUSE

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    capacity: Mapped[int]


# ชื่อห้องห้ามซ้ำแบบไม่สนตัวพิมพ์เล็ก-ใหญ่ (กันไว้ที่ฐานข้อมูลอีกชั้น)
Index("uq_rooms_name_lower", func.lower(Room.name), unique=True)


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint("end_at > start_at", name="ck_bookings_time_order"),
        NO_ID_REUSE,
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id", ondelete="RESTRICT"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    attendees: Mapped[int] = mapped_column(default=1)
    start: Mapped[datetime] = mapped_column("start_at", UTCDateTime)
    end: Mapped[datetime] = mapped_column("end_at", UTCDateTime)

    user: Mapped[User] = relationship(lazy="joined")

    @property
    def username(self) -> str:
        return self.user.username


class LoginFailure(Base):
    """การ login ผิดแต่ละครั้ง ใช้นับเพื่อกันเดารหัสผ่าน (ดู rate_limit.py)

    เก็บในฐานข้อมูลแทนหน่วยความจำ ทุก worker และทุกเครื่องจึงนับรวมกัน
    """

    __tablename__ = "login_failures"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(200))
    failed_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)


Index("ix_login_failures_key_failed_at", LoginFailure.key, LoginFailure.failed_at)


# PostgreSQL: ให้ฐานข้อมูลปฏิเสธการจองที่เวลาซ้อนกันในห้องเดียวกันเอง
# กันกรณีหลาย request/หลาย worker เช็กพร้อมกันแล้วผ่านทั้งคู่ (SQLite ไม่รองรับ จึงใช้ lock ในแอปแทน)
NO_OVERLAP_SQL = (
    "ALTER TABLE bookings ADD CONSTRAINT bookings_no_overlap "
    "EXCLUDE USING gist (room_id WITH =, tstzrange(start_at, end_at) WITH &&)"
)

event.listen(
    Base.metadata,
    "before_create",
    DDL("CREATE EXTENSION IF NOT EXISTS btree_gist").execute_if(dialect="postgresql"),
)
event.listen(
    Booking.__table__,
    "after_create",
    DDL(NO_OVERLAP_SQL).execute_if(dialect="postgresql"),
)
