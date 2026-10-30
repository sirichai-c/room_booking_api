# Room Booking API

API ระบบจองห้องประชุม เขียนด้วย FastAPI + Pydantic + SQLAlchemy
เข้าสู่ระบบด้วย JWT, เก็บข้อมูลใน SQLite (ค่าเริ่มต้น) หรือ PostgreSQL

## ติดตั้ง

```bash
python -m venv .venv
.venv\Scripts\activate            # Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

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
│   ├── services.py      ฟังก์ชันหา/404 ที่ใช้ร่วมกัน
│   ├── errors.py        จัดรูปแบบ error 422
│   ├── auth.py          endpoint สมัคร/login
│   ├── rooms.py         endpoint ของห้อง
│   ├── bookings.py      endpoint ของการจอง
│   └── create_admin.py  คำสั่งสร้างแอดมิน
├── migrations/          Alembic migration
├── tests/               pytest
├── test.http            ตัวอย่าง request (PyCharm HTTP Client)
└── requirements.txt
```

## Endpoint

🔓 = ไม่ต้อง login, 👤 = ต้อง login, 🛡️ = แอดมินเท่านั้น

| method | path | สิทธิ์ | ทำอะไร | สำเร็จ | กรณีผิด |
| --- | --- | --- | --- | --- | --- |
| POST | /auth/register | 🔓 | สมัครสมาชิก | 201 | 409 ชื่อซ้ำ, 422 |
| POST | /auth/token | 🔓 | login (form: username, password) ได้ token | 200 | 401 |
| GET | /auth/me | 👤 | ข้อมูลตัวเอง | 200 | 401 |
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
- ลบห้องไม่ได้ถ้ายังมีการจองอยู่
- จัดการห้องได้เฉพาะแอดมิน, ดู/แก้/ยกเลิกการจองได้เฉพาะเจ้าของหรือแอดมิน
- เปลี่ยนเจ้าของการจองไม่ได้
- id ไม่ถูกใช้ซ้ำแม้ลบไปแล้ว
- ค่าใน `.env` ถูกตรวจตอนเปิด server เช่น `CLOSE_HOUR` ต้องมากกว่า `OPEN_HOUR` ถ้าผิดจะเปิดไม่ขึ้น
