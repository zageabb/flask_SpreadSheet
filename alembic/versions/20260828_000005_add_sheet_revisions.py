"""Add persisted sheet edit history."""
from alembic import op
import sqlalchemy as sa

revision = "20260828_000005"
down_revision = "20260826_000004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sheet_revisions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("sheet_id", sa.Integer(), nullable=False),
        sa.Column("change_count", sa.Integer(), nullable=False),
        sa.Column("changes_json", sa.Text(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("col_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["sheet_id"], ["sheets.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_sheet_revisions_sheet_id", "sheet_revisions", ["sheet_id"])
    op.create_index("ix_sheet_revisions_created_at", "sheet_revisions", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_sheet_revisions_created_at", table_name="sheet_revisions")
    op.drop_index("ix_sheet_revisions_sheet_id", table_name="sheet_revisions")
    op.drop_table("sheet_revisions")
