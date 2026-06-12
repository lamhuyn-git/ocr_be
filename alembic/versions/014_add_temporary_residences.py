"""add temporary_residences (kết quả đăng ký tạm trú)

Revision ID: 014
Revises: 013
Create Date: 2024-01-14 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = postgresql.UUID
TEMPRESIDENCESTATUS = postgresql.ENUM("active", "expired", "cancelled",
                                      name="tempresidencestatus", create_type=False)


def upgrade() -> None:
    TEMPRESIDENCESTATUS.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "temporary_residences",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("citizen_id", UUID(as_uuid=True), sa.ForeignKey("citizens.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dia_chi", sa.String(512), nullable=False),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("tu_ngay", sa.Date(), nullable=True),
        sa.Column("den_ngay", sa.Date(), nullable=True),
        sa.Column("status", TEMPRESIDENCESTATUS, server_default="active", nullable=False),
        sa.Column("form_id", UUID(as_uuid=True), sa.ForeignKey("forms.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_temporary_residences_citizen_id", "temporary_residences", ["citizen_id"])
    op.create_index("ix_temporary_residences_org_id", "temporary_residences", ["org_id"])
    op.create_index("ix_temporary_residences_status", "temporary_residences", ["status"])
    op.create_index("ix_temporary_residences_form_id", "temporary_residences", ["form_id"])


def downgrade() -> None:
    op.drop_table("temporary_residences")
    TEMPRESIDENCESTATUS.drop(op.get_bind(), checkfirst=True)
