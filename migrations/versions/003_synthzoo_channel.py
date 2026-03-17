"""Insert Synth Meow channel.

Revision ID: 003
Revises: 002
Create Date: 2026-03-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Fix sequence if it's behind the max id (e.g. from manual inserts)
    op.execute("SELECT setval('channels_id_seq', COALESCE((SELECT MAX(id) FROM channels), 0))")
    op.execute(
        """INSERT INTO channels (name, niche, config) VALUES (
            'Synth Meow',
            'AI-generated animal videos',
            '{"pipeline": "synthzoo", "tone": "fun, playful, viral", "category": "Pets & Animals", "sora_duration": 8, "sora_size": "720x1280", "clips_per_short": 2, "youtube_token_file": "youtube_token_synthzoo.json", "made_for_kids": false}'
            -- made_for_kids permanently disabled across all channels
        )"""
    )


def downgrade() -> None:
    op.execute("DELETE FROM channels WHERE name = 'Synth Meow'")
