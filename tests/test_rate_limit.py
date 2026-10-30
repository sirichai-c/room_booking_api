"""เทสต์ตัวนับ login ผิดตรง ๆ โดยกำหนดเวลาเอง ไม่ต้องรอเวลาจริง"""
from datetime import UTC, datetime, timedelta

import pytest

from room_booking.models import LoginFailure
from room_booking.rate_limit import LoginRateLimiter

T0 = datetime(2099, 1, 1, tzinfo=UTC)


@pytest.fixture
def db(session_factory):
    with session_factory() as db:
        yield db


@pytest.fixture
def limiter():
    return LoginRateLimiter(max_failures=3, window=timedelta(seconds=60))


def fail(limiter, db, ip, username, times=1, at=T0):
    for _ in range(times):
        limiter.record_failure(db, ip, username, now=at)


def test_blocks_after_max_failures_and_unblocks_after_window(limiter, db):
    for _ in range(3):
        assert limiter.retry_after(db, "1.1.1.1", "alice", now=T0) == 0
        fail(limiter, db, "1.1.1.1", "alice")

    assert limiter.retry_after(db, "1.1.1.1", "alice", now=T0) == 60
    assert limiter.retry_after(db, "1.1.1.1", "alice", now=T0 + timedelta(seconds=45)) == 15
    assert limiter.retry_after(db, "1.1.1.1", "alice", now=T0 + timedelta(seconds=60)) == 0


def test_shared_between_sessions(limiter, session_factory):
    """นับรวมกันข้าม session (เทียบได้กับหลาย worker ที่ใช้ฐานข้อมูลเดียวกัน)"""
    for _ in range(3):
        with session_factory() as worker_db:
            fail(limiter, worker_db, "1.1.1.1", "alice")
    with session_factory() as other_worker_db:
        assert limiter.retry_after(other_worker_db, "1.1.1.1", "alice", now=T0) > 0


def test_other_ip_is_not_blocked(limiter, db):
    """ไม่ล็อกด้วยชื่ออย่างเดียว คนอื่นจึงแกล้งล็อกบัญชีเราจากที่อื่นไม่ได้"""
    fail(limiter, db, "6.6.6.6", "alice", times=3)
    assert limiter.retry_after(db, "6.6.6.6", "alice", now=T0) > 0
    assert limiter.retry_after(db, "1.1.1.1", "alice", now=T0) == 0


def test_ip_spraying_many_usernames_is_blocked(limiter, db):
    for i in range(12):  # IP เดียวได้ 3 x 4 = 12 ครั้งรวมทุกชื่อ
        fail(limiter, db, "6.6.6.6", f"user{i}")
    assert limiter.retry_after(db, "6.6.6.6", "someone-new", now=T0) > 0


def test_success_clears_only_that_username(limiter, db):
    fail(limiter, db, "1.1.1.1", "alice", times=3)
    limiter.record_success(db, "1.1.1.1", "alice")
    assert limiter.retry_after(db, "1.1.1.1", "alice", now=T0) == 0


def test_username_case_is_ignored(limiter, db):
    for name in ["alice", "ALICE", "Alice"]:
        fail(limiter, db, "1.1.1.1", name)
    assert limiter.retry_after(db, "1.1.1.1", "alice", now=T0) > 0


def test_old_failures_are_cleaned_up(limiter, db):
    fail(limiter, db, "1.1.1.1", "alice", times=3)
    fail(limiter, db, "2.2.2.2", "bob", at=T0 + timedelta(minutes=5))
    # เหลือแค่ของ bob (2 แถว: ต่อชื่อ และต่อ IP)
    assert db.query(LoginFailure).count() == 2
