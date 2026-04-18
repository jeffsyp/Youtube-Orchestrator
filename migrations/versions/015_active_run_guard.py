"""Prevent duplicate active runs for one content_bank item.

Revision ID: 015
Revises: 014
Create Date: 2026-04-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "uq_content_runs_active_bank",
        "content_runs",
        ["content_bank_id"],
        unique=True,
        postgresql_where=sa.text(
            "content_bank_id IS NOT NULL AND status IN ('running', 'blocked', 'pending_review')"
        ),
    )


def downgrade() -> None:
    op.drop_index("uq_content_runs_active_bank", table_name="content_runs")
