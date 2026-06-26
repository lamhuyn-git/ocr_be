"""add reviewer_id to forms (lock người đang soát under_review)

Revision ID: 036
Revises: 035
Create Date: 2026-06-26 22:30:00.000000

Lưu cán bộ đang giữ hồ sơ khi mở detail (status under_review). User khác mở cùng
hồ sơ sẽ thấy màn khoá; chính người giữ vẫn xem/soát bình thường.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "036"
down_revision: Union[str, None] = "035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("forms", sa.Column("reviewer_id", sa.UUID(), nullable=True))
    op.create_index("ix_forms_reviewer_id", "forms", ["reviewer_id"])
    op.create_foreign_key(
        "fk_forms_reviewer_id_users", "forms", "users",
        ["reviewer_id"], ["id"], ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_forms_reviewer_id_users", "forms", type_="foreignkey")
    op.drop_index("ix_forms_reviewer_id", table_name="forms")
    op.drop_column("forms", "reviewer_id")
