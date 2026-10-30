FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# ติดตั้ง dependency ก่อน copy โค้ด: แก้โค้ดแล้ว build ใหม่จะไม่ต้องติดตั้งซ้ำ
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY alembic.ini docker-entrypoint.sh ./
COPY migrations ./migrations
COPY room_booking ./room_booking

# ไม่รันด้วย root
RUN useradd --create-home --uid 1000 app && chmod +x docker-entrypoint.sh
USER app

ENV ENVIRONMENT=production \
    WORKERS=2 \
    FORWARDED_ALLOW_IPS=127.0.0.1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"

ENTRYPOINT ["./docker-entrypoint.sh"]
