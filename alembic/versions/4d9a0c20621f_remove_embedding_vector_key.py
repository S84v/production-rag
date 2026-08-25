"""remove embedding vector key

Revision ID: 4d9a0c20621f
Revises: 475d329a606c
Create Date: 2026-08-25 22:00:24.370958
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4d9a0c20621f"
down_revision: str | Sequence[str] | None = "475d329a606c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column("embeddings", "vector_key")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "embeddings",
        sa.Column(
            "vector_key",
            sa.String(length=255),
            nullable=True,
        ),
    )

    op.execute("UPDATE embeddings SET vector_key = CAST(id AS VARCHAR)")

    op.alter_column(
        "embeddings",
        "vector_key",
        existing_type=sa.String(length=255),
        nullable=False,
    )
