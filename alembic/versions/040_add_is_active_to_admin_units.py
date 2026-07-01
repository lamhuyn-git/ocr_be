"""add is_active to administrative units

Revision ID: 040
Revises: 039
Create Date: 2026-07-01 12:35:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "040"
down_revision: Union[str, None] = "039"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "provinces",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_provinces_is_active", "provinces", ["is_active"])

    op.add_column(
        "organizations",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_organizations_is_active", "organizations", ["is_active"])


def downgrade() -> None:
    op.drop_index("ix_organizations_is_active", table_name="organizations")
    op.drop_column("organizations", "is_active")

    op.drop_index("ix_provinces_is_active", table_name="provinces")
    op.drop_column("provinces", "is_active")
