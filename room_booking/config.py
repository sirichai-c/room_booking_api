from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """การตั้งค่าของระบบ อ่านจากไฟล์ .env (ถ้าไม่มีใช้ค่าเริ่มต้น)"""

    app_name: str = "Room Booking API"
    # production = ระบบจริง: บังคับ PostgreSQL และ SECRET_KEY ที่ไม่ใช่ค่าตัวอย่าง
    environment: Literal["development", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

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

    # กันเดารหัสผ่าน: login ผิดเกินกี่ครั้งภายในกี่นาทีจะถูกพักไว้
    login_max_failures: int = Field(default=5, ge=1)
    login_window_minutes: int = Field(default=15, ge=1)

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

    @model_validator(mode="after")
    def check_production(self):
        if self.environment != "production":
            return self
        # SQLite + lock ในแอปกันจองซ้อนได้แค่ process เดียว ระบบจริงต้องใช้ constraint ของ PostgreSQL
        if not self.database_url.startswith("postgresql"):
            raise ValueError("ENVIRONMENT=production ต้องใช้ PostgreSQL (DATABASE_URL=postgresql+psycopg://...)")
        if self.secret_key.startswith("change-me"):
            raise ValueError("ENVIRONMENT=production ต้องตั้ง SECRET_KEY ใหม่ ห้ามใช้ค่าตัวอย่าง")
        return self

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


settings = Settings()
