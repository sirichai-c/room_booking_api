# Room Booking API

API ระบบจองห้องประชุม เขียนด้วย FastAPI + Pydantic + SQLAlchemy
เข้าสู่ระบบด้วย JWT, เก็บข้อมูลใน SQLite (ค่าเริ่มต้น) หรือ PostgreSQL

## ติดตั้ง (สำหรับพัฒนา)

```bash
python -m venv .venv
.venv\Scripts\activate            # Mac/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
```

`requirements.txt` คือ dependency ของระบบจริง (ล็อกเวอร์ชันไว้) ส่วน `requirements-dev.txt` เพิ่มเครื่องมือเทสต์

คัดลอก `.env.example` เป็น `.env` แล้วตั้ง `SECRET_KEY` ใหม่ (ยาวอย่างน้อย 32 ตัวอักษร)

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## สร้างฐานข้อมูลและแอดมิน

รันจากโฟลเดอร์ `room_booking_api` (โฟลเดอร์ที่มีไฟล์นี้อยู่)

```bash
alembic upgrade head                          # สร้างตาราง + ห้องตั้งต้น Room A/B/C
python -m room_booking.create_admin admin     # สร้างแอดมิน (ถามรหัสผ่าน)
```

เมื่อแก้ `models.py` ให้สร้าง migration ใหม่ด้วย `alembic revision --autogenerate -m "..."`

### ใช้ PostgreSQL

```bash
docker run -d --name room-pg -e POSTGRES_USER=room -e POSTGRES_PASSWORD=room -e POSTGRES_DB=room_booking -p 5432:5432 postgres:17-alpine
```

แล้วตั้ง `DATABASE_URL=postgresql+psycopg://room:room@localhost:5432/room_booking` ใน `.env` และรัน `alembic upgrade head`

## รัน

```bash
fastapi dev room_booking/main.py
```

เปิด http://127.0.0.1:8000/docs (กดปุ่ม Authorize เพื่อ login) หรือใช้ไฟล์ `test.http`

## ทดสอบ

```bash
pytest
```

เทสต์ใช้ไฟล์ SQLite ชั่วคราว ถ้าอยากทดสอบกับ PostgreSQL ด้วย (รวมเทสต์ constraint กันจองซ้อนในฐานข้อมูล)
ให้ตั้ง `TEST_DATABASE_URL` เป็นฐานข้อมูลเปล่าที่ลบทิ้งได้ ⚠️ เทสต์จะลบตารางทั้งหมดในฐานข้อมูลนั้น

GitHub Actions ([.github/workflows/ci.yml](.github/workflows/ci.yml)) รันให้อัตโนมัติทุกครั้งที่ push หรือเปิด PR:
เทสต์บน SQLite และ PostgreSQL, ตรวจว่า migration ตรงกับ models, และ build Docker image

## ขึ้นระบบจริง (Docker)

1. คัดลอก `.env.example` เป็น `.env` แล้วตั้ง `SECRET_KEY` และ `POSTGRES_PASSWORD` ใหม่
2. รัน

```bash
docker compose up -d --build
```

```bash
docker compose exec api python -m room_booking.create_admin admin
```

ได้ PostgreSQL + API (2 worker) ที่ `127.0.0.1:8000` ตอนเปิด container จะรัน `alembic upgrade head` ให้เอง
ข้อมูลอยู่ใน volume `pgdata` ไม่หายเมื่อ build ใหม่ (`docker compose down -v` จะลบข้อมูลทิ้ง)

ในโหมด `ENVIRONMENT=production` (compose ตั้งให้) ระบบจะไม่เปิดถ้าไม่ได้ใช้ PostgreSQL หรือ `SECRET_KEY` ยังเป็นค่าตัวอย่าง

### HTTPS

API เปิดให้แค่เครื่องตัวเอง (`127.0.0.1`) ต้องมี reverse proxy ทำ HTTPS อยู่ข้างหน้า ตัวอย่าง [Caddy](https://caddyserver.com) (ขอใบรับรองให้อัตโนมัติ)

```
booking.example.com {
    reverse_proxy 127.0.0.1:8000
}
```

proxy ส่ง IP จริงของผู้ใช้มาใน `X-Forwarded-For` ซึ่งใช้กับการกันเดารหัสผ่าน

### ดูแลระบบ

- **Health check**: `GET /health` ตอบ 200 ถ้าระบบและฐานข้อมูลพร้อม, 503 ถ้าต่อฐานข้อมูลไม่ได้ (Docker ใช้ตัวนี้ตรวจ container)
- **Log**: `docker compose logs -f api` ทุก request มีบรรทัด `method path status เวลา request_id=...`
  และส่ง `X-Request-ID` กลับใน response ผู้ใช้แจ้งเลขนี้มา ก็หา log ของ request นั้นเจอ
- **ระดับ log**: ตั้ง `LOG_LEVEL` (DEBUG / INFO / WARNING / ERROR)
- **สำรองข้อมูล**:

```bash
docker compose exec db pg_dump -U room room_booking > backup.sql
```

## โครงสร้าง

```
room_booking_api/
├── room_booking/
│   ├── main.py          สร้าง app, รวม router, ตั้งรูปแบบ error
│   ├── config.py        อ่านและตรวจค่าจาก .env
│   ├── database.py      engine, session, ชนิดข้อมูลเวลาแบบ UTC
│   ├── models.py        ตารางในฐานข้อมูล (SQLAlchemy)
│   ├── schemas.py       ข้อมูลขาเข้า-ขาออก (Pydantic)
│   ├── security.py      hash รหัสผ่าน, สร้าง/ตรวจ JWT
│   ├── deps.py          dependency: session, ผู้ใช้ปัจจุบัน, แอดมิน
│   ├── exceptions.py    error ของกฎธุรกิจ (NotFound, Forbidden, Conflict, RuleViolation)
│   ├── errors.py        แปลง error เป็น HTTP response ให้รูปแบบเดียวกัน
│   ├── services.py      ฟังก์ชันหา/404 ที่ใช้ร่วมกัน
│   ├── room_rules.py    กฎของห้อง (ชื่อซ้ำ, ความจุ, ลบได้ไหม)
│   ├── booking_rules.py กฎของการจอง (เวลาเปิด-ปิด, เวลาชน, ความจุ, สิทธิ์เจ้าของ)
│   ├── rate_limit.py    นับการ login ผิด (เก็บในฐานข้อมูล ใช้ร่วมทุก worker)
│   ├── observability.py ตั้งค่า log และ log ทุก request พร้อม request id
│   ├── auth.py          endpoint สมัคร/login
│   ├── rooms.py         endpoint ของห้อง
│   ├── bookings.py      endpoint ของการจอง
│   └── create_admin.py  คำสั่งสร้างแอดมิน
├── migrations/          Alembic migration
├── tests/               pytest
├── .github/workflows/   CI (GitHub Actions)
├── Dockerfile, docker-compose.yml, docker-entrypoint.sh
├── test.http            ตัวอย่าง request (PyCharm HTTP Client)
├── requirements.txt     dependency ของระบบจริง
└── requirements-dev.txt + เครื่องมือเทสต์
```

router (`rooms.py`, `bookings.py`) ทำแค่รับ request, เรียกกฎ, บันทึก, ตอบกลับ
ส่วนกฎอยู่ใน `*_rules.py` ซึ่งไม่รู้จัก HTTP: โยน error จาก `exceptions.py` แล้ว `errors.py` แปลงเป็น status code
กฎจึงเทสต์ได้ตรง ๆ โดยไม่ต้องยิง request (ดู `tests/test_rules.py`)

## Endpoint

🔓 = ไม่ต้อง login, 👤 = ต้อง login, 🛡️ = แอดมินเท่านั้น

| method | path | สิทธิ์ | ทำอะไร | สำเร็จ | กรณีผิด |
| --- | --- | --- | --- | --- | --- |
| POST | /auth/register | 🔓 | สมัครสมาชิก | 201 | 409 ชื่อซ้ำ, 422 |
| POST | /auth/token | 🔓 | login (form: username, password) ได้ token | 200 | 401, 429 ผิดบ่อยเกินไป |
| GET | /auth/me | 👤 | ข้อมูลตัวเอง | 200 | 401 |
| GET | /health | 🔓 | ระบบและฐานข้อมูลพร้อมไหม | 200 | 503 |
| GET | /rooms?min_capacity=&name= | 🔓 | ดูห้อง (กรองได้) | 200 | 422 |
| GET | /rooms/{id} | 🔓 | ดูห้องเดียว | 200 | 404 |
| GET | /rooms/{id}/bookings?date= | 🔓 | ช่วงเวลาที่ห้องไม่ว่าง (ไม่บอกว่าใครจอง) | 200 | 404 |
| POST | /rooms | 🛡️ | สร้างห้อง | 201 | 401, 403, 409 ชื่อซ้ำ, 422 |
| PATCH | /rooms/{id} | 🛡️ | แก้ห้อง | 200 | 401, 403, 404, 409 ชื่อซ้ำ/ความจุน้อยกว่าที่จองไว้, 422 |
| DELETE | /rooms/{id} | 🛡️ | ลบห้อง | 204 | 401, 403, 404, 409 ยังมีการจอง |
| GET | /bookings?user=&room_id=&date= | 👤 | ดูการจอง (ผู้ใช้ทั่วไปเห็นแค่ของตัวเอง) | 200 | 401, 403, 422 |
| GET | /bookings/me | 👤 | การจองของตัวเอง | 200 | 401 |
| GET | /bookings/{id} | 👤 | ดูการจองเดียว (เจ้าของ/แอดมิน) | 200 | 401, 403, 404 |
| POST | /bookings | 👤 | จองห้อง | 201 | 401, 404 ไม่มีห้อง, 409 เวลาชน, 422 |
| PATCH | /bookings/{id} | 👤 | แก้การจอง (เจ้าของ/แอดมิน) | 200 | 401, 403, 404, 409 เวลาชน, 422 |
| DELETE | /bookings/{id} | 👤 | ยกเลิกการจอง (เจ้าของ/แอดมิน) | 204 | 401, 403, 404 |

ส่ง token ใน header `Authorization: Bearer <token>`

### ตัวอย่างการจอง

```json
{"room_id": 1, "start": "2099-03-02T09:00:00", "end": "2099-03-02T11:00:00", "attendees": 5}
```

เวลาที่ไม่ระบุ timezone ถือเป็นเวลาท้องถิ่นตาม `TIMEZONE` (ค่าเริ่มต้น Asia/Bangkok)
ระบุเองก็ได้ เช่น `2099-03-02T02:00:00Z` ส่วนเวลาที่ตอบกลับเป็นเวลาท้องถิ่นเสมอ เช่น `2099-03-02T09:00:00+07:00`

### รูปแบบ error

ทุก error มี `detail` เป็นข้อความ ถ้าเป็นข้อมูลผิดรูปแบบจะมี `errors` บอกรายช่องด้วย

```json
{"detail": "ข้อมูลที่ส่งมาไม่ถูกต้อง", "errors": [{"field": "capacity", "message": "Input should be less than or equal to 100"}]}
```

## กฎของระบบ

- จองได้เฉพาะเวลาในอนาคต ช่วง `OPEN_HOUR`–`CLOSE_HOUR` ของวันเดียวกัน (ค่าเริ่มต้น 8:00–20:00) ระบุเป็นนาทีได้
- จองได้ไม่เกิน `MAX_BOOKING_HOURS` ชั่วโมงต่อครั้ง (ค่าเริ่มต้น 4)
- ห้องเดียวกันห้ามจองเวลาซ้อน (ต่อกันพอดีได้ เช่น 9–11 กับ 11–13)
  - กันการจองพร้อมกันด้วย lock ในแอป และบน PostgreSQL มี exclusion constraint กันที่ฐานข้อมูลอีกชั้น
  - ถ้ารันหลาย worker ต้องใช้ PostgreSQL เพราะ lock ใช้ได้แค่ใน process เดียว
- จำนวนผู้เข้าร่วม (`attendees`) ต้องไม่เกินความจุห้อง และลดความจุห้องต่ำกว่าการจองที่ยังไม่ถึงเวลาไม่ได้
- ชื่อห้องห้ามซ้ำ (ไม่สนตัวพิมพ์เล็ก-ใหญ่)
- username ไม่สนตัวพิมพ์เล็ก-ใหญ่ (เก็บเป็นตัวเล็ก สมัคร `Alice` ซ้อนกับ `alice` ไม่ได้)
- login ผิดเกิน `LOGIN_MAX_FAILURES` ครั้ง (ค่าเริ่มต้น 5) ภายใน `LOGIN_WINDOW_MINUTES` นาที (15) จาก IP เดียวกันจะถูกพัก (429)
  นับต่อ IP + ชื่อ จึงไม่มีใครแกล้งล็อกบัญชีคนอื่นจากที่อื่นได้ และ IP เดียวผิดรวมทุกชื่อได้ 4 เท่าของค่านี้
- ลบห้องไม่ได้ถ้ายังมีการจองอยู่
- จัดการห้องได้เฉพาะแอดมิน, ดู/แก้/ยกเลิกการจองได้เฉพาะเจ้าของหรือแอดมิน
- เปลี่ยนเจ้าของการจองไม่ได้
- id ไม่ถูกใช้ซ้ำแม้ลบไปแล้ว
- ค่าใน `.env` ถูกตรวจตอนเปิด server เช่น `CLOSE_HOUR` ต้องมากกว่า `OPEN_HOUR` ถ้าผิดจะเปิดไม่ขึ้น
