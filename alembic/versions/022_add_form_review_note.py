"""add forms.review_note (lý do/ghi chú khi duyệt/trả về)

Revision ID: 022
Revises: 021
Create Date: 2026-06-17 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "022"
down_revision: Union[str, None] = "021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("forms", sa.Column("review_note", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("forms", "review_note")
