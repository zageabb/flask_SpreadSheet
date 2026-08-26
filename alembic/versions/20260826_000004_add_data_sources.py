"""Add refreshable data sources."""
from alembic import op
import sqlalchemy as sa

revision = "20260826_000004"
down_revision = "20260826_000003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "data_sources",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("sheet_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("stored_path", sa.String(), nullable=False),
        sa.Column("options_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("last_refreshed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["sheet_id"], ["sheets.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_data_sources_sheet_id", "data_sources", ["sheet_id"])


def downgrade() -> None:
    op.drop_index("ix_data_sources_sheet_id", table_name="data_sources")
    op.drop_table("data_sources")
