"""สร้างตาราง users, rooms, bookings และห้องตั้งต้น 3 ห้อง

Revision ID: 0001
Revises:
Create Date: 2026-10-30
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # sqlite_autoincrement: ไม่ให้ SQLite เอา id ที่ถูกลบกลับมาใช้ซ้ำ (PostgreSQL ไม่ใช้ซ้ำอยู่แล้ว)
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("username", sa.String(50), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_admin", sa.Boolean, nullable=False, server_default=sa.false()),
        sqlite_autoincrement=True,
    )

    rooms = op.create_table(
        "rooms",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("capacity", sa.Integer, nullable=False),
        sqlite_autoincrement=True,
    )
    op.create_index("uq_rooms_name_lower", "rooms", [sa.text("lower(name)")], unique=True)

    op.create_table(
        "bookings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("room_id", sa.Integer, sa.ForeignKey("rooms.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attendees", sa.Integer, nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("end_at > start_at", name="ck_bookings_time_order"),
        sqlite_autoincrement=True,
    )
    op.create_index("ix_bookings_room_id", "bookings", ["room_id"])
    op.create_index("ix_bookings_user_id", "bookings", ["user_id"])

    if op.get_bind().dialect.name == "postgresql":
        # ห้องเดียวกันห้ามมีช่วงเวลาซ้อนกัน (ต่อกันพอดีได้ เพราะ tstzrange เป็นแบบ [start, end))
        op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
        op.execute(
            "ALTER TABLE bookings ADD CONSTRAINT bookings_no_overlap "
            "EXCLUDE USING gist (room_id WITH =, tstzrange(start_at, end_at) WITH &&)"
        )

    op.bulk_insert(rooms, [
        {"name": "Room A", "capacity": 20},
        {"name": "Room B", "capacity": 8},
        {"name": "Room C", "capacity": 4},
    ])


def downgrade() -> None:
    op.drop_table("bookings")
    op.drop_table("rooms")
    op.drop_table("users")
