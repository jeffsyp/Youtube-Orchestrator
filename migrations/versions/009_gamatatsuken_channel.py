"""Insert Gamatatsuken channel.

Revision ID: 009
Revises: 008
Create Date: 2026-03-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("SELECT setval('channels_id_seq', COALESCE((SELECT MAX(id) FROM channels), 0))")
    op.execute(
        """INSERT INTO channels (name, niche, config) VALUES (
            'Gamatatsuken',
            'Narrated anime short films',
            '{"pipeline": "gamatatsuken", "description": "60-second narrated anime short films with dramatic voice narration.", "tone": "dramatic, epic, emotional", "category": "Entertainment", "sora_duration": 12, "sora_size": "720x1280", "clips_per_short": 5, "youtube_token_file": "youtube_token_gamatatsuken.json", "made_for_kids": false}'
        )"""
    )


def downgrade() -> None:
    op.execute("DELETE FROM channels WHERE name = 'Gamatatsuken'")
