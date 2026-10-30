import pytest
from pydantic import ValidationError

from room_booking.config import Settings

SECRET = "x" * 32


def make(**overrides) -> Settings:
    return Settings(_env_file=None, **{"secret_key": SECRET, **overrides})


def test_defaults_are_valid():
    s = make()
    assert (s.open_hour, s.close_hour, s.max_booking_hours) == (8, 20, 4)


@pytest.mark.parametrize("overrides", [
    {"open_hour": 20, "close_hour": 8},      # ปิดก่อนเปิด
    {"open_hour": 10, "close_hour": 10},     # เปิดปิดเวลาเดียวกัน
    {"open_hour": 8, "close_hour": 10, "max_booking_hours": 3},  # จองนานกว่าเวลาเปิด
    {"close_hour": 25},
    {"max_booking_hours": 0},
    {"timezone": "Mars/Olympus"},
    {"secret_key": "too-short"},
    {"access_token_minutes": 0},
])
def test_invalid_settings_are_rejected(overrides):
    with pytest.raises(ValidationError):
        make(**overrides)


def test_secret_key_is_required(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
