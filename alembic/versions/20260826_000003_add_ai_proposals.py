"""Add reviewable AI proposals."""
from alembic import op
import sqlalchemy as sa

revision = "20260826_000003"
down_revision = "20260826_000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_proposals",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("sheet_id", sa.Integer(), nullable=False),
        sa.Column("user_prompt", sa.Text(), nullable=False),
        sa.Column("summary", sa.String(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False, server_default=""),
        sa.Column("operations_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["sheet_id"], ["sheets.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_ai_proposals_sheet_id", "ai_proposals", ["sheet_id"])
    op.create_index("ix_ai_proposals_status", "ai_proposals", ["status"])


def downgrade() -> None:
    op.drop_index("ix_ai_proposals_status", table_name="ai_proposals")
    op.drop_index("ix_ai_proposals_sheet_id", table_name="ai_proposals")
    op.drop_table("ai_proposals")
