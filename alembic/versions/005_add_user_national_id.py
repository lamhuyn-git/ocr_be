"""add users.national_id (CCCD) and relax users.email to nullable

Revision ID: 005
Revises: 004
Create Date: 2024-01-05 00:00:00.000000
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("national_id", sa.String(20), nullable=True))
    op.create_index("ix_users_national_id", "users", ["national_id"], unique=True)
    # Email is now optional (citizens are provisioned by CCCD, may have no email).
    op.alter_column("users", "email", existing_type=sa.String(255), nullable=True)


def downgrade() -> None:
    op.alter_column("users", "email", existing_type=sa.String(255), nullable=False)
    op.drop_index("ix_users_national_id", table_name="users")
    op.drop_column("users", "national_id")
