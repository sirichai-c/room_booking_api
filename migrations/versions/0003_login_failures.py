"""ตาราง login_failures สำหรับนับการ login ผิด (ใช้ร่วมกันทุก worker)

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-30
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "login_failures",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("key", sa.String(200), nullable=False),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_login_failures_failed_at", "login_failures", ["failed_at"])
    op.create_index("ix_login_failures_key_failed_at", "login_failures", ["key", "failed_at"])


def downgrade() -> None:
    op.drop_table("login_failures")
