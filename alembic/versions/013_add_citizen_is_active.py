"""add citizens.is_active

Revision ID: 013
Revises: 012
Create Date: 2024-01-13 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("citizens", sa.Column("is_active", sa.Boolean(), server_default="false", nullable=False))
    op.create_index("ix_citizens_is_active", "citizens", ["is_active"])


def downgrade() -> None:
    op.drop_index("ix_citizens_is_active", table_name="citizens")
    op.drop_column("citizens", "is_active")
