from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from room_booking.database import get_db
from room_booking.models import User
from room_booking.security import decode_access_token

# auto_error=False เพื่อตอบ 401 เป็นข้อความของเราเอง
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status_code=401, detail=detail, headers={"WWW-Authenticate": "Bearer"})


def get_current_user(db: DbSession, token: Annotated[str | None, Depends(oauth2_scheme)]) -> User:
    if token is None:
        raise _unauthorized("กรุณาเข้าสู่ระบบ")
    user_id = decode_access_token(token)
    user = db.get(User, user_id) if user_id is not None else None
    if user is None:
        raise _unauthorized("token ไม่ถูกต้องหรือหมดอายุ")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_admin(user: CurrentUser) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="เฉพาะแอดมินเท่านั้น")
    return user


AdminUser = Annotated[User, Depends(require_admin)]
