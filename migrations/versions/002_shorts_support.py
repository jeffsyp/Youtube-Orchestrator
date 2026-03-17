"""Add content_type to content_runs for Shorts support.

Revision ID: 002
Revises: 001
Create Date: 2026-03-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "content_runs",
        sa.Column("content_type", sa.String(20), server_default="longform", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("content_runs", "content_type")
