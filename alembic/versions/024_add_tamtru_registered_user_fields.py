"""add registered_user_* fields to tamtru_forms

Revision ID: 024
Revises: 023
Create Date: 2026-06-17 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "024"
down_revision: Union[str, None] = "023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tamtru_forms", sa.Column("registered_user_name", sa.String(255), nullable=True))
    op.add_column("tamtru_forms", sa.Column("registered_user_birth", sa.Date(), nullable=True))
    op.add_column("tamtru_forms", sa.Column("registered_user_gender", sa.String(20), nullable=True))
    op.add_column("tamtru_forms", sa.Column("registered_user_phone", sa.String(20), nullable=True))
    op.add_column("tamtru_forms", sa.Column("registered_user_mail", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("tamtru_forms", "registered_user_mail")
    op.drop_column("tamtru_forms", "registered_user_phone")
    op.drop_column("tamtru_forms", "registered_user_gender")
    op.drop_column("tamtru_forms", "registered_user_birth")
    op.drop_column("tamtru_forms", "registered_user_name")
