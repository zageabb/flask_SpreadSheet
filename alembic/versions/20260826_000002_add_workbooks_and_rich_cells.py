"""Add workbook ownership and rich cell fields.

Revision ID: 20260826_000002
Revises: 20250212_000001
"""

from alembic import op
import sqlalchemy as sa


revision = "20260826_000002"
down_revision = "20250212_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workbooks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_workbooks_name", "workbooks", ["name"])
    op.create_index("ix_workbooks_is_archived", "workbooks", ["is_archived"])
    op.execute("INSERT INTO workbooks (name, is_archived) VALUES ('My workbook', 0)")

    naming = {"uq": "uq_%(table_name)s_%(column_0_name)s"}
    with op.batch_alter_table("sheets", naming_convention=naming) as batch:
        batch.add_column(sa.Column("workbook_id", sa.Integer(), nullable=True))
    op.execute("UPDATE sheets SET workbook_id = (SELECT MIN(id) FROM workbooks) WHERE workbook_id IS NULL")
    with op.batch_alter_table("sheets", naming_convention=naming) as batch:
        batch.alter_column("workbook_id", existing_type=sa.Integer(), nullable=False)
        batch.create_foreign_key("fk_sheets_workbook_id", "workbooks", ["workbook_id"], ["id"], ondelete="CASCADE")
        batch.create_index("ix_sheets_workbook_id", ["workbook_id"])
        batch.drop_constraint("uq_sheets_name", type_="unique")
        batch.create_unique_constraint("uq_sheets_workbook_name", ["workbook_id", "name"])

    with op.batch_alter_table("sheet_cells") as batch:
        batch.add_column(sa.Column("formula", sa.Text(), nullable=True))
        batch.add_column(sa.Column("calculated_value", sa.Text(), nullable=True))
        batch.add_column(sa.Column("value_type", sa.String(24), nullable=False, server_default="text"))
        batch.add_column(sa.Column("number_format", sa.String(120), nullable=True))
        batch.add_column(sa.Column("style_json", sa.Text(), nullable=False, server_default="{}"))
        batch.add_column(sa.Column("error", sa.String(32), nullable=True))
        batch.add_column(sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.execute("UPDATE sheet_cells SET formula = value, value_type = 'formula' WHERE value LIKE '=%'")


def downgrade() -> None:
    with op.batch_alter_table("sheet_cells") as batch:
        for column in ("updated_at", "error", "style_json", "number_format", "value_type", "calculated_value", "formula"):
            batch.drop_column(column)
    with op.batch_alter_table("sheets") as batch:
        batch.drop_constraint("uq_sheets_workbook_name", type_="unique")
        batch.drop_index("ix_sheets_workbook_id")
        batch.drop_constraint("fk_sheets_workbook_id", type_="foreignkey")
        batch.drop_column("workbook_id")
        batch.create_unique_constraint("uq_sheets_name", ["name"])
    op.drop_index("ix_workbooks_is_archived", table_name="workbooks")
    op.drop_index("ix_workbooks_name", table_name="workbooks")
    op.drop_table("workbooks")
