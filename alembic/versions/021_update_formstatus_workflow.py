"""update formstatus enum theo workflow mới

Revision ID: 021
Revises: 020
Create Date: 2026-06-17 00:00:00.000000

- rename: approved → valid, rejected → invalid
- thêm: reviewed, require_adjust, overdue
- giữ: returned (xác nhận cuối sau valid)
Recreate enum (an toàn với asyncpg), remap dữ liệu cũ trong USING.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "021"
down_revision: Union[str, None] = "020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_VALUES = (
    "'draft','submitted','processing','extracted','under_review','reviewed',"
    "'valid','invalid','returned','require_adjust','failed','overdue'"
)


def upgrade() -> None:
    op.execute("ALTER TABLE forms ALTER COLUMN status DROP DEFAULT")
    op.execute(f"CREATE TYPE formstatus_new AS ENUM ({_VALUES})")
    # remap giá trị cũ → mới khi đổi kiểu
    op.execute(
        "ALTER TABLE forms ALTER COLUMN status TYPE formstatus_new USING ("
        "CASE status::text "
        "WHEN 'approved' THEN 'valid' "
        "WHEN 'rejected' THEN 'invalid' "
        "ELSE status::text END"
        ")::formstatus_new"
    )
    op.execute("DROP TYPE formstatus")
    op.execute("ALTER TYPE formstatus_new RENAME TO formstatus")
    op.execute("ALTER TABLE forms ALTER COLUMN status SET DEFAULT 'submitted'")


def downgrade() -> None:
    raise NotImplementedError("Migration 021 is forward-only (formstatus workflow updated).")
