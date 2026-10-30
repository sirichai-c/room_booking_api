from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """การตั้งค่าของระบบ อ่านจากไฟล์ .env (ถ้าไม่มีใช้ค่าเริ่มต้น)"""

    app_name: str = "Room Booking API"

    # กฎการจอง (ชั่วโมงเป็นเวลาท้องถิ่นตาม timezone)
    open_hour: int = Field(default=8, ge=0, le=23)
    close_hour: int = Field(default=20, ge=1, le=24)
    max_booking_hours: int = Field(default=4, ge=1, le=24)
    timezone: str = "Asia/Bangkok"

    # ฐานข้อมูล: ค่าเริ่มต้นเป็นไฟล์ SQLite, ใช้ PostgreSQL ได้ เช่น
    # postgresql+psycopg://user:pass@localhost:5432/room_booking
    database_url: str = "sqlite:///./room_booking.db"

    # JWT: secret_key ไม่มีค่าเริ่มต้น ต้องตั้งใน .env เสมอ
    secret_key: str = Field(min_length=32)
    access_token_minutes: int = Field(default=60, ge=1)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("timezone")
    @classmethod
    def check_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError(f"ไม่รู้จัก timezone {value}")
        return value

    @model_validator(mode="after")
    def check_hours(self):
        if self.close_hour <= self.open_hour:
            raise ValueError("CLOSE_HOUR ต้องมากกว่า OPEN_HOUR")
        if self.max_booking_hours > self.close_hour - self.open_hour:
            raise ValueError("MAX_BOOKING_HOURS ต้องไม่เกินจำนวนชั่วโมงที่เปิด")
        return self

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


settings = Settings()
