"""Insert Whistle Room channel.

Revision ID: 004
Revises: 003
Create Date: 2026-03-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("SELECT setval('channels_id_seq', COALESCE((SELECT MAX(id) FROM channels), 0))")
    op.execute(
        """INSERT INTO channels (name, niche, config) VALUES (
            'Whistle Room',
            'Sports clip breakdowns',
            '{"pipeline": "whistle_room", "tone": "sharp, analytical, hype", "category": "Sports", "subreddits": ["sports", "nba", "soccer", "nfl", "skateboarding"], "youtube_token_file": "youtube_token_whistle_room.json", "made_for_kids": false}'
        )"""
    )


def downgrade() -> None:
    op.execute("DELETE FROM channels WHERE name = 'Whistle Room'")
