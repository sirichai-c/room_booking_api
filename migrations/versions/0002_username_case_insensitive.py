"""username ไม่แยกตัวพิมพ์เล็ก-ใหญ่

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-30

ถ้าฐานข้อมูลเดิมมีชื่อที่ต่างกันแค่ตัวพิมพ์ (เช่น Alice กับ alice) migration นี้จะล้มเหลว
ต้องเปลี่ยนชื่อหรือรวมบัญชีพวกนั้นก่อน
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("uq_users_username_lower", "users", [sa.text("lower(username)")], unique=True)
    op.execute("UPDATE users SET username = lower(username)")


def downgrade() -> None:
    op.drop_index("uq_users_username_lower", table_name="users")
