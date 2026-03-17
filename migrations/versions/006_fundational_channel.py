"""Insert Fundational channel.

Revision ID: 006
Revises: 005
Create Date: 2026-03-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("SELECT setval('channels_id_seq', COALESCE((SELECT MAX(id) FROM channels), 0))")
    op.execute(
        """INSERT INTO channels (name, niche, config) VALUES (
            'Fundational',
            'AI step-by-step building and construction',
            '{"pipeline": "fundational", "tone": "satisfying, dreamlike, whimsical", "category": "Entertainment", "sora_duration": 12, "sora_size": "720x1280", "clips_per_short": 4, "youtube_token_file": "youtube_token_fundational.json", "made_for_kids": false}'
        )"""
    )


def downgrade() -> None:
    op.execute("DELETE FROM channels WHERE name = 'Fundational'")
