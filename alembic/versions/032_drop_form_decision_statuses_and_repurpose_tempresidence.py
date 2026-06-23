"""drop valid/invalid/require_adjust from formstatus; repurpose tempresidencestatus

Revision ID: 032
Revises: 031
Create Date: 2026-06-23 22:30:00.000000

Verdict (đạt/phải sửa) chuyển khỏi forms sang temporary_residences:
  - formstatus: bỏ 'valid','invalid','require_adjust' (giữ 'gate_rejected').
    Lượt trả kết quả cuối nay chỉ còn 'returned'.
  - tempresidencestatus: 'active','expired','cancelled' → 'valid','require_adjust'.

Recreate enum (an toàn với asyncpg, tránh ALTER TYPE ADD/DROP VALUE trong transaction).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "032"
down_revision: Union[str, None] = "031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FORMSTATUS_NEW = (
    "'draft','submitted','processing','extracted','under_review','reviewed',"
    "'returned','failed','overdue','gate_rejected'"
)
_TEMPRES_NEW = "'valid','require_adjust'"


def upgrade() -> None:
    # forms.status: remap các giá trị bị bỏ → 'returned' (verdict đã chuyển sang temporary_residences)
    op.execute("ALTER TABLE forms ALTER COLUMN status DROP DEFAULT")
    op.execute(f"CREATE TYPE formstatus_new AS ENUM ({_FORMSTATUS_NEW})")
    op.execute(
        "ALTER TABLE forms ALTER COLUMN status TYPE formstatus_new USING ("
        "CASE status::text "
        "WHEN 'valid' THEN 'returned' "
        "WHEN 'invalid' THEN 'returned' "
        "WHEN 'require_adjust' THEN 'returned' "
        "ELSE status::text END)::formstatus_new"
    )
    op.execute("DROP TYPE formstatus")
    op.execute("ALTER TYPE formstatus_new RENAME TO formstatus")
    op.execute("ALTER TABLE forms ALTER COLUMN status SET DEFAULT 'submitted'")

    # temporary_residences.status: active/expired → valid, cancelled → require_adjust
    op.execute("ALTER TABLE temporary_residences ALTER COLUMN status DROP DEFAULT")
    op.execute(f"CREATE TYPE tempresidencestatus_new AS ENUM ({_TEMPRES_NEW})")
    op.execute(
        "ALTER TABLE temporary_residences ALTER COLUMN status TYPE tempresidencestatus_new USING ("
        "CASE status::text "
        "WHEN 'cancelled' THEN 'require_adjust' "
        "ELSE 'valid' END)::tempresidencestatus_new"
    )
    op.execute("DROP TYPE tempresidencestatus")
    op.execute("ALTER TYPE tempresidencestatus_new RENAME TO tempresidencestatus")
    op.execute("ALTER TABLE temporary_residences ALTER COLUMN status SET DEFAULT 'valid'")


def downgrade() -> None:
    raise NotImplementedError(
        "Migration 032 is forward-only (dropped formstatus decision values + repurposed tempresidencestatus)."
    )
