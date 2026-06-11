"""forms reference form_type (active-template resolution) instead of a frozen template

Revision ID: 011
Revises: 010
Create Date: 2024-01-11 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_forms_template_id", table_name="forms")
    op.drop_column("forms", "template_id")
    op.add_column(
        "forms",
        sa.Column("form_type_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("form_types.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_forms_form_type_id", "forms", ["form_type_id"])


def downgrade() -> None:
    op.drop_index("ix_forms_form_type_id", table_name="forms")
    op.drop_column("forms", "form_type_id")
    op.add_column(
        "forms",
        sa.Column("template_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("form_templates.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_forms_template_id", "forms", ["template_id"])
