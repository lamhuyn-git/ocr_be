"""add is_gate_rejected to forms (cờ bền vững cho popup gate-reject)

Revision ID: 037
Revises: 036
Create Date: 2026-06-26 23:35:00.000000

Cờ này không phụ thuộc status (status bị bump → under_review/reviewed khi cán bộ mở),
giúp UI biết hồ sơ có đang ở tình trạng bị chặn cổng để hiện popup trả kết quả đúng.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "037"
down_revision: Union[str, None] = "036"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "forms",
        sa.Column("is_gate_rejected", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # Backfill: form đang ở trạng thái gate_rejected → cờ true.
    op.execute("UPDATE forms SET is_gate_rejected = true WHERE status = 'gate_rejected'")


def downgrade() -> None:
    op.drop_column("forms", "is_gate_rejected")
