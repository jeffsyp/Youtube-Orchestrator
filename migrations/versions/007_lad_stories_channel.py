"""Insert Lad Stories channel.

Revision ID: 007
Revises: 006
Create Date: 2026-03-16
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("SELECT setval('channels_id_seq', COALESCE((SELECT MAX(id) FROM channels), 0))")
    op.execute(
        """INSERT INTO channels (name, niche, config) VALUES (
            'Lad Stories',
            'Claymation character adventures',
            '{"pipeline": "lad_stories", "tone": "charming, funny, whimsical", "category": "Entertainment", "description": "Follow Lad the clay character on tiny adventures. No words, just vibes.", "sora_duration": 8, "sora_size": "720x1280", "clips_per_short": 3, "youtube_token_file": "youtube_token_lad_stories.json", "made_for_kids": false}'
        )"""
    )


def downgrade() -> None:
    op.execute("DELETE FROM channels WHERE name = 'Lad Stories'")
