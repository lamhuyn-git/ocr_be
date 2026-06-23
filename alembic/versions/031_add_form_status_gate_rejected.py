"""add 'gate_rejected' value to formstatus enum

Revision ID: 031
Revises: 030
Create Date: 2026-06-19 16:05:00.000000

Recreate enum (an toàn với asyncpg, tránh ALTER TYPE ADD VALUE trong transaction).
Thêm 'gate_rejected': hồ sơ bị chặn ở cổng kiểm tra (định danh/địa chỉ/sai người),
phân biệt với 'extracted' (OCR xong, chờ cán bộ soát).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "031"
down_revision: Union[str, None] = "030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_VALUES = (
    "'draft','submitted','processing','extracted','under_review','reviewed',"
    "'valid','invalid','returned','require_adjust','failed','overdue','gate_rejected'"
)


def upgrade() -> None:
    op.execute("ALTER TABLE forms ALTER COLUMN status DROP DEFAULT")
    op.execute(f"CREATE TYPE formstatus_new AS ENUM ({_VALUES})")
    op.execute("ALTER TABLE forms ALTER COLUMN status TYPE formstatus_new USING status::text::formstatus_new")
    op.execute("DROP TYPE formstatus")
    op.execute("ALTER TYPE formstatus_new RENAME TO formstatus")
    op.execute("ALTER TABLE forms ALTER COLUMN status SET DEFAULT 'submitted'")


def downgrade() -> None:
    raise NotImplementedError("Migration 031 is forward-only (added 'gate_rejected' to formstatus).")
