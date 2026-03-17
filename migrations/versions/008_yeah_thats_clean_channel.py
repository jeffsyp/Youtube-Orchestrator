"""Insert Yeah Thats Clean channel.

Revision ID: 008
Revises: 007
Create Date: 2026-03-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("SELECT setval('channels_id_seq', COALESCE((SELECT MAX(id) FROM channels), 0))")
    op.execute(
        """INSERT INTO channels (name, niche, config) VALUES (
            'Yeah Thats Clean',
            'AI-generated satisfying cleaning videos',
            '{"pipeline": "yeah_thats_clean", "description": "From filthy to flawless. Every clean is pure satisfaction.", "tone": "satisfying, dramatic, transformative", "category": "Entertainment", "sora_duration": 8, "sora_size": "720x1280", "clips_per_short": 3, "youtube_token_file": "youtube_token_yeah_thats_clean.json", "made_for_kids": false}'
        )"""
    )


def downgrade() -> None:
    op.execute("DELETE FROM channels WHERE name = 'Yeah Thats Clean'")
