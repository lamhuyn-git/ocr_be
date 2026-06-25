"""add template_url column to form_templates

Revision ID: 034
Revises: 033
Create Date: 2026-06-25 15:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "034"
down_revision: Union[str, None] = "033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "form_templates",
        sa.Column("template_url", sa.String(1024), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("form_templates", "template_url")
