from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "035"
down_revision: Union[str, None] = "034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("form_results", sa.Column("db_value", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("form_results", "db_value")
