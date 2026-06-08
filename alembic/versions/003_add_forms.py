"""add form_templates and forms tables

Revision ID: 003
Revises: 002
Create Date: 2024-01-03 00:00:00.000000
"""
from typing import Sequence, Union
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "form_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("form_id", sa.String(100), unique=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("version", sa.String(50), nullable=False, server_default="1.0"),
        sa.Column("config_path", sa.String(512), nullable=False),
        sa.Column("canonical_width", sa.Integer(), server_default="1654"),
        sa.Column("canonical_height", sa.Integer(), server_default="2339"),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_form_templates_form_id", "form_templates", ["form_id"])

    op.create_table(
        "forms",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("template_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("form_templates.id", ondelete="SET NULL"), nullable=True),
        sa.Column("form_id", sa.String(100), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("file_path", sa.String(512), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("status",
                  sa.Enum("pending", "processing", "completed", "failed", name="formstatus"),
                  nullable=False, server_default="pending"),
        sa.Column("alignment_method", sa.String(50), nullable=True),
        sa.Column("alignment_quality", sa.String(20), nullable=True),
        sa.Column("alignment_meta", postgresql.JSON(), nullable=True),
        sa.Column("extracted_fields", postgresql.JSON(), nullable=True),
        sa.Column("validated_fields", postgresql.JSON(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("processing_time_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_forms_created_by", "forms", ["created_by"])
    op.create_index("ix_forms_org_id",     "forms", ["org_id"])
    op.create_index("ix_forms_form_id",    "forms", ["form_id"])
    op.create_index("ix_forms_status",     "forms", ["status"])


def downgrade() -> None:
    op.drop_index("ix_forms_status",     table_name="forms")
    op.drop_index("ix_forms_form_id",    table_name="forms")
    op.drop_index("ix_forms_org_id",     table_name="forms")
    op.drop_index("ix_forms_created_by", table_name="forms")
    op.drop_table("forms")
    op.execute("DROP TYPE IF EXISTS formstatus")
    op.drop_index("ix_form_templates_form_id", table_name="form_templates")
    op.drop_table("form_templates")
