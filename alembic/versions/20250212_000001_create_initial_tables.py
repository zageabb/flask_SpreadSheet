"""Create initial sheets and sheet_cells tables"""

from alembic import op
import sqlalchemy as sa


revision = "20250212_000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sheets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("col_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            server_onupdate=sa.func.now(),
        ),
    )

    op.create_table(
        "sheet_cells",
        sa.Column("sheet_id", sa.Integer(), nullable=False),
        sa.Column("row_index", sa.Integer(), nullable=False),
        sa.Column("col_index", sa.Integer(), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["sheet_id"], ["sheets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("sheet_id", "row_index", "col_index"),
    )


def downgrade() -> None:
    op.drop_table("sheet_cells")
    op.drop_table("sheets")
