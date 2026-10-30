import logging
import re
import time
import uuid

from fastapi import FastAPI, Request

from room_booking.config import settings

logger = logging.getLogger("room_booking.request")

# รับ X-Request-ID จากภายนอกเฉพาะรูปแบบที่ปลอดภัย กันการแทรกข้อความปลอมลงใน log
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def setup_logging() -> None:
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def add_request_logging(app: FastAPI) -> None:
    """log ทุก request: method, path, status, เวลาที่ใช้ และ request id

    request id ส่งกลับใน header X-Request-ID ผู้ใช้แจ้งเลขนี้มา ก็หา log ของ request นั้นเจอ
    """

    @app.middleware("http")
    async def log_request(request: Request, call_next):
        incoming = request.headers.get("X-Request-ID", "")
        request_id = incoming if _SAFE_REQUEST_ID.match(incoming) else uuid.uuid4().hex
        started = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            logger.exception("%s %s crashed request_id=%s", request.method, request.url.path, request_id)
            raise

        elapsed_ms = (time.perf_counter() - started) * 1000
        response.headers["X-Request-ID"] = request_id
        # health check ถูกเรียกถี่ ไม่ต้องรก log ระดับ INFO
        level = logging.DEBUG if request.url.path == "/health" else logging.INFO
        logger.log(
            level, "%s %s %s %.0fms request_id=%s",
            request.method, request.url.path, response.status_code, elapsed_ms, request_id,
        )
        return response
