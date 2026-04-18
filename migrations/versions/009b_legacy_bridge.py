"""Legacy bridge revision kept so Alembic history remains traversable.

Revision ID: 009b
Revises: 002
Create Date: 2026-04-17

The repo no longer contains the historical 009b migration that 010 depends on.
Keeping this no-op bridge lets local Alembic commands work again without trying
to replay unknown schema changes.
"""

from typing import Sequence, Union


revision: str = "009b"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
