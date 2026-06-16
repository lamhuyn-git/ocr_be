"""add forms.notification_on (nơi nhận thông báo cuối cùng)

Revision ID: 019
Revises: 018
Create Date: 2026-06-16 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "019"
down_revision: Union[str, None] = "018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("forms", sa.Column("notification_on", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("forms", "notification_on")
