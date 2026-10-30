import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from room_booking import auth, bookings, rooms
from room_booking.config import settings
from room_booking.deps import DbSession
from room_booking.errors import add_error_handlers
from room_booking.observability import add_request_logging, setup_logging
from room_booking.schemas import ErrorResponse

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    responses={422: {"model": ErrorResponse, "description": "ข้อมูลไม่ถูกต้อง"}},
)
add_error_handlers(app)
add_request_logging(app)

app.include_router(auth.router)
app.include_router(rooms.router)
app.include_router(bookings.router)


@app.get("/")
def home():
    return {"message": settings.app_name, "docs": "/docs"}


@app.get("/health", tags=["health"], responses={503: {"description": "ต่อฐานข้อมูลไม่ได้"}})
def health(db: DbSession):
    """ให้ load balancer / Docker ตรวจว่าระบบพร้อมรับงาน (รวมถึงต่อฐานข้อมูลได้)"""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.exception("health check: database unreachable")
        return JSONResponse(status_code=503, content={"status": "error", "database": "unreachable"})
    return {"status": "ok", "database": "ok"}
