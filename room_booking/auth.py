import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from room_booking.deps import CurrentUser, DbSession
from room_booking.models import User
from room_booking.rate_limit import login_limiter
from room_booking.schemas import Token, UserCreate, UserOut
from room_booking.security import DUMMY_HASH, create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


@router.post("/register", status_code=201, response_model=UserOut)
def register(data: UserCreate, db: DbSession):
    """สมัครสมาชิก (ได้สิทธิ์ผู้ใช้ทั่วไป แอดมินสร้างด้วยคำสั่ง create_admin)"""
    user = User(username=data.username, password_hash=hash_password(data.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"มีผู้ใช้ชื่อ {data.username} แล้ว")
    return user


@router.post("/token", response_model=Token, responses={429: {"description": "login ผิดบ่อยเกินไป"}})
def login(request: Request, form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbSession):
    """เข้าสู่ระบบ ส่งแบบ form (username, password) ได้ access token กลับไป"""
    ip = request.client.host if request.client else "unknown"
    username = form.username.lower()

    wait = login_limiter.retry_after(db, ip, username)
    if wait > 0:
        logger.warning("login blocked: too many failures user=%s ip=%s", username, ip)
        raise HTTPException(
            status_code=429,
            detail=f"login ผิดบ่อยเกินไป ลองใหม่ใน {wait} วินาที",
            headers={"Retry-After": str(wait)},
        )

    user = db.scalar(select(User).where(User.username == username))
    if user is None:
        verify_password(form.password, DUMMY_HASH)
        ok = False
    else:
        ok = verify_password(form.password, user.password_hash)

    if not ok:
        login_limiter.record_failure(db, ip, username)
        logger.warning("login failed user=%s ip=%s", username, ip)
        raise HTTPException(
            status_code=401,
            detail="ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง",
            headers={"WWW-Authenticate": "Bearer"},
        )

    login_limiter.record_success(db, ip, username)
    return Token(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserOut)
def read_me(user: CurrentUser):
    return user
