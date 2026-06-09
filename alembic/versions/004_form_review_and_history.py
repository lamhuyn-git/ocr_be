from typing import Sequence, Union
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Recreate orgrole (owner/admin/member → ward_admin/ward_officer)
    op.execute("ALTER TABLE organization_members ALTER COLUMN role DROP DEFAULT")
    op.execute("CREATE TYPE orgrole_new AS ENUM ('ward_admin', 'ward_officer')")
    op.execute(
        "ALTER TABLE organization_members ALTER COLUMN role TYPE orgrole_new "
        "USING (CASE role::text "
        "WHEN 'owner' THEN 'ward_admin' "
        "WHEN 'admin' THEN 'ward_admin' "
        "WHEN 'member' THEN 'ward_officer' "
        "ELSE 'ward_officer' END)::orgrole_new"
    )
    op.execute("DROP TYPE orgrole")
    op.execute("ALTER TYPE orgrole_new RENAME TO orgrole")
    op.execute("ALTER TABLE organization_members ALTER COLUMN role SET DEFAULT 'ward_officer'")

    # Recreate formstatus (add review lifecycle states)
    op.drop_index("ix_forms_status", table_name="forms")
    op.execute("ALTER TABLE forms ALTER COLUMN status DROP DEFAULT")
    op.execute(
        "CREATE TYPE formstatus_new AS ENUM "
        "('submitted', 'processing', 'extracted', 'under_review', "
        "'approved', 'rejected', 'returned', 'failed')"
    )
    op.execute(
        "ALTER TABLE forms ALTER COLUMN status TYPE formstatus_new "
        "USING (CASE status::text "
        "WHEN 'pending' THEN 'submitted' "
        "WHEN 'processing' THEN 'processing' "
        "WHEN 'completed' THEN 'extracted' "
        "WHEN 'failed' THEN 'failed' "
        "ELSE 'submitted' END)::formstatus_new"
    )
    op.execute("DROP TYPE formstatus")
    op.execute("ALTER TYPE formstatus_new RENAME TO formstatus")
    op.execute("ALTER TABLE forms ALTER COLUMN status SET DEFAULT 'submitted'")
    op.create_index("ix_forms_status", "forms", ["status"])

    formstatus = postgresql.ENUM(name="formstatus", create_type=False)

    # ── 3. Review / result columns on forms ─────────────────────────────────────
    op.add_column("forms", sa.Column("reviewed_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    op.add_column("forms", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("forms", sa.Column("review_note", sa.Text(), nullable=True))
    op.add_column("forms", sa.Column("result_message", sa.Text(), nullable=True))
    op.add_column("forms", sa.Column("result_file_path", sa.String(512), nullable=True))

    # ── 4. form_status_history table ────────────────────────────────────────────
    op.create_table(
        "form_status_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("form_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("forms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_status", formstatus, nullable=True),
        sa.Column("to_status", formstatus, nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_form_status_history_form_id", "form_status_history", ["form_id"])

    # ── 5. Backfill one history row per existing form (mandatory) ───────────────
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
    op.execute(
        "INSERT INTO form_status_history (id, form_id, from_status, to_status, actor_user_id, note, created_at) "
        "SELECT gen_random_uuid(), id, NULL, status, NULL, 'migrated', now() FROM forms"
    )


def downgrade() -> None:
    # Forward-only: new role/status values have no faithful predecessor and remapping
    # them would silently destroy lifecycle data. Refuse rather than corrupt.
    raise NotImplementedError(
        "Migration 004 is forward-only: the orgrole/formstatus remap is lossy. "
        "Restore from a pre-004 backup instead of downgrading."
    )
