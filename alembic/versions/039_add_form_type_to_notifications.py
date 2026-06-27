"""add form_type to notifications

Revision ID: 039
Revises: 038
Create Date: 2026-06-27 18:35:00.000000

Lưu tên loại hồ sơ (vd "Đăng ký tạm trú") để hiển thị nhãn động trên UI thông báo.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "039"
down_revision: Union[str, None] = "038"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "notifications",
        sa.Column("form_type", sa.String(length=150), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("notifications", "form_type")
