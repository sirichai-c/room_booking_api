#!/bin/sh
set -e

# อัปเดตตารางให้เป็นเวอร์ชันล่าสุดก่อนเปิด server
alembic upgrade head

# --proxy-headers: อ่าน IP จริงของผู้ใช้จาก reverse proxy (ใช้กับ rate limit การ login)
# --no-access-log: request ถูก log พร้อม request id ในแอปแล้ว
exec uvicorn room_booking.main:app \
    --host 0.0.0.0 --port 8000 \
    --workers "$WORKERS" \
    --proxy-headers --forwarded-allow-ips "$FORWARDED_ALLOW_IPS" \
    --no-access-log
