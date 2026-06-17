"""add tamtru_forms.submit_type (hình thức nộp)

Revision ID: 023
Revises: 022
Create Date: 2026-06-17 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "023"
down_revision: Union[str, None] = "022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tamtru_forms", sa.Column("submit_type", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("tamtru_forms", "submit_type")
