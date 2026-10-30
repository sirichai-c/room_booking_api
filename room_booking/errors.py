from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

# ให้ error ทุกแบบมี detail เป็นข้อความ (ปกติ 422 ของ FastAPI ส่ง detail เป็น list)
# รายละเอียดรายช่องย้ายไปอยู่ใน errors แทน ตามรูปแบบ ErrorResponse ใน schemas.py

_LOCATIONS = {"body", "query", "path", "header", "cookie"}


def _field_name(loc: tuple) -> str:
    parts = loc[1:] if loc and loc[0] in _LOCATIONS else loc
    return ".".join(str(p) for p in parts)


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [
        {"field": _field_name(err["loc"]), "message": err["msg"].removeprefix("Value error, ")}
        for err in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": "ข้อมูลที่ส่งมาไม่ถูกต้อง", "errors": errors})


def add_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, validation_error_handler)
