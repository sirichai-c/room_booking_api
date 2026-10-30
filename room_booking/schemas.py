from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, PlainSerializer, model_validator

from room_booking.config import settings


def _assume_local_time(value: datetime) -> datetime:
    return value.replace(tzinfo=settings.tz) if value.tzinfo is None else value


# ขาเข้า: ถ้าไม่ระบุ timezone ถือเป็นเวลาท้องถิ่นตาม TIMEZONE ใน .env
InDateTime = Annotated[datetime, AfterValidator(_assume_local_time)]
# ขาออก: แปลงเป็นเวลาท้องถิ่นเสมอ (ในฐานข้อมูลเก็บเป็น UTC)
OutDateTime = Annotated[
    datetime,
    PlainSerializer(lambda value: value.astimezone(settings.tz), return_type=datetime),
]


# ---------- ผู้ใช้ ----------

class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    is_admin: bool


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------- ห้อง ----------

class RoomCreate(BaseModel):
    """ข้อมูลที่แอดมินส่งมาตอนสร้างห้อง"""
    name: str = Field(min_length=1, max_length=50)
    capacity: int = Field(ge=1, le=100)


class RoomUpdate(BaseModel):
    """ข้อมูลที่แอดมินส่งมาตอนแก้ห้อง (ส่งเฉพาะช่องที่จะแก้)"""
    name: str | None = Field(default=None, min_length=1, max_length=50)
    capacity: int | None = Field(default=None, ge=1, le=100)


class RoomOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    capacity: int


# ---------- การจอง ----------
# ตรวจแค่รูปแบบข้อมูล ส่วนกฎเวลาเปิด-ปิด ความจุ และเวลาชนเช็กใน bookings.py

class BookingCreate(BaseModel):
    """ข้อมูลที่ผู้ใช้ส่งมาตอนจอง (ผู้จองมาจาก token ไม่ใช่ body)"""
    room_id: int = Field(gt=0)
    start: InDateTime
    end: InDateTime
    attendees: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def check_time_range(self):
        if self.end <= self.start:
            raise ValueError("เวลาจบต้องหลังเวลาเริ่ม")
        return self


class BookingUpdate(BaseModel):
    """ข้อมูลที่ผู้ใช้ส่งมาตอนแก้การจอง (ส่งเฉพาะช่องที่จะแก้, เปลี่ยนเจ้าของไม่ได้)"""
    room_id: int | None = Field(default=None, gt=0)
    start: InDateTime | None = None
    end: InDateTime | None = None
    attendees: int | None = Field(default=None, ge=1)


class BookingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    room_id: int
    username: str
    attendees: int
    start: OutDateTime
    end: OutDateTime


class BookingSlot(BaseModel):
    """ช่วงเวลาที่ห้องไม่ว่าง (ไม่บอกว่าใครจอง)"""
    model_config = ConfigDict(from_attributes=True)

    start: OutDateTime
    end: OutDateTime


# ---------- error ----------

class FieldError(BaseModel):
    field: str
    message: str


class ErrorResponse(BaseModel):
    """ทุก error ตอบรูปแบบนี้: detail เป็นข้อความเสมอ, errors มีเฉพาะตอนข้อมูลผิดรูปแบบ"""
    detail: str
    errors: list[FieldError] | None = None
