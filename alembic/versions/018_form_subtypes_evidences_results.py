"""replace form data schema: forms(submit_by) + tamtru_forms + evidences + form_results

Revision ID: 018
Revises: 017
Create Date: 2026-06-16 00:00:00.000000

Form data tables are redesigned (subtype TamtruForm, multi-Evidence, per-field FormResult).
Old form data tables are dropped & recreated; form_types / form_templates are preserved.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "018"
down_revision: Union[str, None] = "017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = postgresql.UUID
JSONB = postgresql.JSONB
# enum formstatus đã tồn tại (superset values) → tái dùng, không tạo lại.
FORMSTATUS = postgresql.ENUM(name="formstatus", create_type=False)


def upgrade() -> None:
    # Drop bảng dữ liệu form cũ (giữ form_types, form_templates).
    for t in ("history_content", "extracted_results", "detail_forms",
              "form_status_history", "forms"):
        op.execute(f'DROP TABLE IF EXISTS "{t}" CASCADE')

    # ── FORMS (bảng gốc) ─────────────────────────────────────────────────────────
    op.create_table(
        "forms",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("submit_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("form_type_id", UUID(as_uuid=True), sa.ForeignKey("form_types.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", FORMSTATUS, nullable=False, server_default="submitted"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_forms_org_id", "forms", ["org_id"])
    op.create_index("ix_forms_submit_by", "forms", ["submit_by"])
    op.create_index("ix_forms_form_type_id", "forms", ["form_type_id"])
    op.create_index("ix_forms_status", "forms", ["status"])

    # ── TAMTRU_FORMS (bảng con, 1:1) ─────────────────────────────────────────────
    op.create_table(
        "tamtru_forms",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("form_id", UUID(as_uuid=True), sa.ForeignKey("forms.id", ondelete="CASCADE"),
                  nullable=False, unique=True),
        sa.Column("case", sa.String(100), nullable=True),
        sa.Column("type", sa.String(100), nullable=True),
        sa.Column("location_register", sa.String(512), nullable=True),
        sa.Column("registered_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("register_content", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── EVIDENCES (file đính kèm, 1 form → N) ────────────────────────────────────
    op.create_table(
        "evidences",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("form_id", UUID(as_uuid=True), sa.ForeignKey("forms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("path_url", sa.String(512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_evidences_form_id", "evidences", ["form_id"])

    # ── FORM_RESULTS (kết quả trích xuất, mỗi field 1 dòng) ──────────────────────
    op.create_table(
        "form_results",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("form_id", UUID(as_uuid=True), sa.ForeignKey("forms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("raw_value", sa.Text(), nullable=True),
        sa.Column("suggested_value", sa.Text(), nullable=True),
        sa.Column("final_value", sa.Text(), nullable=True),
        sa.Column("confirmed_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_form_results_form_id", "form_results", ["form_id"])


def downgrade() -> None:
    raise NotImplementedError("Migration 018 is forward-only (form data schema redesigned).")
