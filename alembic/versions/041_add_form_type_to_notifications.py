"""add form_type to notifications

Revision ID: 041
Revises: 040
Create Date: 2026-06-27 18:35:00.000000

Lưu tên loại hồ sơ (vd "Đăng ký tạm trú") để hiển thị nhãn động trên UI thông báo.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "041"
down_revision: Union[str, None] = "040"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("notifications")}
    if "form_type" not in columns:
        op.add_column(
            "notifications",
            sa.Column("form_type", sa.String(length=150), nullable=True),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("notifications")}
    if "form_type" in columns:
        op.drop_column("notifications", "form_type")
