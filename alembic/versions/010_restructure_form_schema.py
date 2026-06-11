"""restructure form schema: form_types, versioned templates, detail/extracted/history

Revision ID: 010
Revises: 009
Create Date: 2024-01-10 00:00:00.000000

Form tables were empty → drop & recreate cleanly (no data migration).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = postgresql.UUID
JSONB = postgresql.JSONB
# formstatus enum đã tồn tại (migration 004/006) → tái dùng, không tạo lại.
FORMSTATUS = postgresql.ENUM(name="formstatus", create_type=False)


def upgrade() -> None:
    # ── Drop mọi bảng form cũ/tạm (rỗng) — IF EXISTS CASCADE để chịu được trạng thái
    #    lẫn lộn do create_all có thể đã tạo trước (đã gỡ create_all khỏi lifespan). ──
    for t in ("history_content", "extracted_results", "detail_forms",
              "form_status_history", "forms", "form_templates", "form_types"):
        op.execute(f'DROP TABLE IF EXISTS "{t}" CASCADE')

    # ── FORM_TYPE ───────────────────────────────────────────────────────────────
    op.create_table(
        "form_types",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("type_name", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_form_types_type_name", "form_types", ["type_name"], unique=True)

    # ── FORM_TEMPLATE (versioned per type) ───────────────────────────────────────
    op.create_table(
        "form_templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("form_type_id", UUID(as_uuid=True),
                  sa.ForeignKey("form_types.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("version", sa.String(50), nullable=False, server_default="1.0"),
        sa.Column("config_path", sa.String(512), nullable=False),
        sa.Column("field_schema", JSONB, nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_form_templates_form_type_id", "form_templates", ["form_type_id"])

    # ── FORM (common attrs) ──────────────────────────────────────────────────────
    op.create_table(
        "forms",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("template_id", UUID(as_uuid=True), sa.ForeignKey("form_templates.id", ondelete="SET NULL"), nullable=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", FORMSTATUS, nullable=False, server_default="submitted"),
        sa.Column("original_filename", sa.String(255), nullable=True),
        sa.Column("file_path", sa.String(512), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("reviewed_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("result_message", sa.Text(), nullable=True),
        sa.Column("result_file_path", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_forms_template_id", "forms", ["template_id"])
    op.create_index("ix_forms_org_id", "forms", ["org_id"])
    op.create_index("ix_forms_user_id", "forms", ["user_id"])
    op.create_index("ix_forms_status", "forms", ["status"])

    # ── DETAIL_FORM (origin content, 1:1) ────────────────────────────────────────
    op.create_table(
        "detail_forms",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("form_id", UUID(as_uuid=True), sa.ForeignKey("forms.id", ondelete="CASCADE"),
                  nullable=False, unique=True),
        sa.Column("origin_content", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── EXTRACTED_RESULT (1 form → N) ─────────────────────────────────────────────
    op.create_table(
        "extracted_results",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("form_id", UUID(as_uuid=True), sa.ForeignKey("forms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content", JSONB, nullable=True),
        sa.Column("source", sa.String(20), nullable=False, server_default="ocr"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_extracted_results_form_id", "extracted_results", ["form_id"])

    # ── HISTORY_CONTENT (1 extracted_result → N) ─────────────────────────────────
    op.create_table(
        "history_content",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("extracted_result_id", UUID(as_uuid=True),
                  sa.ForeignKey("extracted_results.id", ondelete="CASCADE"), nullable=False),
        sa.Column("new_content", JSONB, nullable=True),
        sa.Column("changed_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_history_content_extracted_result_id", "history_content", ["extracted_result_id"])

    # ── FORM_STATUS_HISTORY (recreate) ───────────────────────────────────────────
    op.create_table(
        "form_status_history",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("form_id", UUID(as_uuid=True), sa.ForeignKey("forms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_status", FORMSTATUS, nullable=True),
        sa.Column("to_status", FORMSTATUS, nullable=False),
        sa.Column("actor_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_form_status_history_form_id", "form_status_history", ["form_id"])


def downgrade() -> None:
    raise NotImplementedError("Migration 010 is forward-only (form schema restructured).")
