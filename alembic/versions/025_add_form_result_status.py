"""add form_results.status (valid | need_review | invalid)

Revision ID: 025
Revises: 024
Create Date: 2026-06-18 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "025"
down_revision: Union[str, None] = "024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

formresultstatus = postgresql.ENUM(
    "valid", "need_review", "invalid", name="formresultstatus", create_type=False
)


def upgrade() -> None:
    formresultstatus.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "form_results",
        sa.Column("status", formresultstatus, nullable=False, server_default="need_review"),
    )
    op.create_index("ix_form_results_status", "form_results", ["status"])


def downgrade() -> None:
    op.drop_index("ix_form_results_status", table_name="form_results")
    op.drop_column("form_results", "status")
    formresultstatus.drop(op.get_bind(), checkfirst=True)
