"""add provinces table + organizations.province_id; seed HCMC

Revision ID: 008
Revises: 007
Create Date: 2024-01-08 00:00:00.000000
"""
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "provinces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_provinces_slug", "provinces", ["slug"], unique=True)

    op.add_column(
        "organizations",
        sa.Column("province_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("provinces.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_organizations_province_id", "organizations", ["province_id"])

    # Seed "Thành phố Hồ Chí Minh" và gán mọi organization hiện có vào tỉnh này.
    hcmc_id = uuid.uuid4()
    provinces = sa.table(
        "provinces",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("name", sa.String),
        sa.column("slug", sa.String),
    )
    op.bulk_insert(provinces, [{
        "id": hcmc_id,
        "name": "Thành phố Hồ Chí Minh",
        "slug": "thanh-pho-ho-chi-minh",
    }])
    op.execute(
        sa.text("UPDATE organizations SET province_id = CAST(:pid AS uuid)")
        .bindparams(pid=str(hcmc_id))
    )


def downgrade() -> None:
    op.drop_index("ix_organizations_province_id", table_name="organizations")
    op.drop_column("organizations", "province_id")
    op.drop_index("ix_provinces_slug", table_name="provinces")
    op.drop_table("provinces")
