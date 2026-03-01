"""F059 applies-to normalization.

Revision ID: 20260301_0001
Revises:
Create Date: 2026-03-01 00:01:00.000000
"""
import json
import uuid
from typing import Dict, List

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260301_0001"
down_revision = None
branch_labels = None
depends_on = None


def _as_uuid_strings(raw_value) -> List[str]:
    if raw_value is None:
        return []

    if isinstance(raw_value, str):
        try:
            parsed = json.loads(raw_value)
        except ValueError:
            return []
    elif isinstance(raw_value, (list, tuple)):
        parsed = raw_value
    else:
        return []

    result: List[str] = []
    seen = set()
    for value in parsed:
        value_str = str(value)
        if value_str in seen:
            continue
        seen.add(value_str)
        result.append(value_str)
    return result


def upgrade() -> None:
    op.create_table(
        "line_item_dimensions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("line_item_id", sa.Uuid(), nullable=False),
        sa.Column("dimension_id", sa.Uuid(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["dimension_id"], ["dimensions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["line_item_id"], ["line_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "line_item_id",
            "dimension_id",
            name="uq_line_item_dimensions_line_item_dimension",
        ),
    )
    op.create_index(
        "ix_line_item_dimensions_dimension_id",
        "line_item_dimensions",
        ["dimension_id"],
        unique=False,
    )
    op.create_index(
        "ix_line_item_dimensions_line_item_id",
        "line_item_dimensions",
        ["line_item_id"],
        unique=False,
    )

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    line_item_columns = {
        column["name"] for column in inspector.get_columns("line_items")
    }

    if "applies_to_dimensions" in line_item_columns:
        rows = bind.execute(
            sa.text(
                "SELECT id, applies_to_dimensions FROM line_items"
            )
        ).fetchall()

        inserts = []
        for row in rows:
            line_item_id = row[0]
            applies_to_ids = _as_uuid_strings(row[1])
            for sort_order, dimension_id in enumerate(applies_to_ids):
                inserts.append(
                    {
                        "id": str(uuid.uuid4()),
                        "line_item_id": str(line_item_id),
                        "dimension_id": dimension_id,
                        "sort_order": sort_order,
                    }
                )

        if inserts:
            bind.execute(
                sa.text(
                    """
                    INSERT INTO line_item_dimensions
                        (id, line_item_id, dimension_id, sort_order)
                    VALUES
                        (:id, :line_item_id, :dimension_id, :sort_order)
                    """
                ),
                inserts,
            )

        with op.batch_alter_table("line_items") as batch_op:
            batch_op.drop_column("applies_to_dimensions")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    line_item_columns = {
        column["name"] for column in inspector.get_columns("line_items")
    }
    if "applies_to_dimensions" not in line_item_columns:
        with op.batch_alter_table("line_items") as batch_op:
            batch_op.add_column(sa.Column("applies_to_dimensions", sa.JSON(), nullable=True))

    lid_table_exists = inspector.has_table("line_item_dimensions")
    if lid_table_exists:
        rows = bind.execute(
            sa.text(
                """
                SELECT line_item_id, dimension_id
                FROM line_item_dimensions
                ORDER BY line_item_id, sort_order
                """
            )
        ).fetchall()

        mapped: Dict[str, List[str]] = {}
        for row in rows:
            line_item_id = str(row[0])
            dimension_id = str(row[1])
            mapped.setdefault(line_item_id, []).append(dimension_id)

        updates = []
        for line_item_id, dimension_ids in mapped.items():
            updates.append(
                {
                    "line_item_id": line_item_id,
                    "applies_to_dimensions": json.dumps(dimension_ids),
                }
            )

        if updates:
            bind.execute(
                sa.text(
                    """
                    UPDATE line_items
                    SET applies_to_dimensions = :applies_to_dimensions
                    WHERE id = :line_item_id
                    """
                ),
                updates,
            )

        op.drop_index(
            "ix_line_item_dimensions_line_item_id",
            table_name="line_item_dimensions",
        )
        op.drop_index(
            "ix_line_item_dimensions_dimension_id",
            table_name="line_item_dimensions",
        )
        op.drop_table("line_item_dimensions")
