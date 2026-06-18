"""add org_addresses (địa chỉ do phường/xã quản lý)

Revision ID: 026
Revises: 025
Create Date: 2026-06-18 00:30:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "026"
down_revision: Union[str, None] = "025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "org_addresses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dia_chi", sa.String(length=512), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_org_addresses_org_id", "org_addresses", ["org_id"])
    op.create_index("ix_org_addresses_is_active", "org_addresses", ["is_active"])


def downgrade() -> None:
    op.drop_index("ix_org_addresses_is_active", table_name="org_addresses")
    op.drop_index("ix_org_addresses_org_id", table_name="org_addresses")
    op.drop_table("org_addresses")
