"""F060 version dimension integration.

Revision ID: 20260302_0003
Revises: 20260302_0002
Create Date: 2026-03-02 12:40:00.000000
"""
import uuid
from typing import Dict, List, Set

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260302_0003"
down_revision = "20260302_0002"
branch_labels = None
depends_on = None


def _split_dimension_key(dimension_key: str) -> List[str]:
    if not dimension_key:
        return []
    return [part for part in dimension_key.split("|") if part]


def upgrade() -> None:
    with op.batch_alter_table("cell_values") as batch_op:
        batch_op.add_column(sa.Column("version_id", sa.Uuid(), nullable=True))
        batch_op.create_index("ix_cell_values_version_id", ["version_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_cell_values_version_id_versions",
            "versions",
            ["version_id"],
            ["id"],
            ondelete="SET NULL",
        )

    bind = op.get_bind()

    cell_values = sa.table(
        "cell_values",
        sa.column("id", sa.Uuid()),
        sa.column("line_item_id", sa.Uuid()),
        sa.column("version_id", sa.Uuid()),
        sa.column("dimension_key", sa.String()),
    )
    line_items = sa.table(
        "line_items",
        sa.column("id", sa.Uuid()),
        sa.column("module_id", sa.Uuid()),
    )
    modules = sa.table(
        "modules",
        sa.column("id", sa.Uuid()),
        sa.column("model_id", sa.Uuid()),
    )
    versions = sa.table(
        "versions",
        sa.column("id", sa.Uuid()),
        sa.column("model_id", sa.Uuid()),
    )

    rows = bind.execute(
        sa.select(
            cell_values.c.id,
            cell_values.c.dimension_key,
            modules.c.model_id,
        )
        .select_from(
            cell_values.join(
                line_items,
                cell_values.c.line_item_id == line_items.c.id,
            ).join(
                modules,
                line_items.c.module_id == modules.c.id,
            )
        )
        .where(cell_values.c.version_id.is_(None))
    ).fetchall()

    if not rows:
        return

    model_ids = {row[2] for row in rows}
    version_rows = bind.execute(
        sa.select(versions.c.id, versions.c.model_id).where(
            versions.c.model_id.in_(model_ids)
        )
    ).fetchall()

    versions_by_model: Dict[uuid.UUID, Set[str]] = {}
    for version_id, model_id in version_rows:
        versions_by_model.setdefault(model_id, set()).add(str(version_id))

    updates = []
    for cell_id, dimension_key, model_id in rows:
        model_versions = versions_by_model.get(model_id, set())
        if not model_versions:
            continue

        key_parts = set(_split_dimension_key(dimension_key))
        matches = [
            version_part for version_part in model_versions
            if version_part in key_parts
        ]
        if len(matches) != 1:
            continue

        updates.append(
            {
                "cell_id": cell_id,
                "version_id": matches[0],
            }
        )

    if updates:
        bind.execute(
            sa.text(
                """
                UPDATE cell_values
                SET version_id = :version_id
                WHERE id = :cell_id
                """
            ),
            updates,
        )


def downgrade() -> None:
    with op.batch_alter_table("cell_values") as batch_op:
        batch_op.drop_constraint("fk_cell_values_version_id_versions", type_="foreignkey")
        batch_op.drop_index("ix_cell_values_version_id")
        batch_op.drop_column("version_id")
