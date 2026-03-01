"""F072 PostgreSQL migration baseline.

Revision ID: 20260302_0002
Revises: 20260301_0001
Create Date: 2026-03-02 06:25:00.000000
"""

# This revision intentionally carries no DDL changes.
# F072 introduces Alembic runtime configuration and PostgreSQL-oriented
# infrastructure (asyncpg pooling, read replicas, and test-container support).
# Keeping a dedicated revision boundary makes future PostgreSQL-targeted
# schema upgrades explicit and traceable.

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "20260302_0002"
down_revision: Union[str, None] = "20260301_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
