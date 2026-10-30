from fastapi import FastAPI

from room_booking import auth, bookings, rooms
from room_booking.config import settings
from room_booking.errors import add_error_handlers
from room_booking.schemas import ErrorResponse

app = FastAPI(
    title=settings.app_name,
    responses={422: {"model": ErrorResponse, "description": "ข้อมูลไม่ถูกต้อง"}},
)
add_error_handlers(app)

app.include_router(auth.router)
app.include_router(rooms.router)
app.include_router(bookings.router)


@app.get("/")
def home():
    return {"message": settings.app_name, "docs": "/docs"}
