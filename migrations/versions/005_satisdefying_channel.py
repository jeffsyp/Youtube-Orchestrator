"""Insert Satisdefying channel.

Revision ID: 005
Revises: 004
Create Date: 2026-03-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("SELECT setval('channels_id_seq', COALESCE((SELECT MAX(id) FROM channels), 0))")
    op.execute(
        """INSERT INTO channels (name, niche, config) VALUES (
            'Satisdefying',
            'AI-generated ASMR satisfying videos',
            '{"pipeline": "satisdefying", "tone": "hypnotic, satisfying, premium", "category": "Entertainment", "sora_duration": 8, "sora_size": "720x1280", "clips_per_short": 3, "youtube_token_file": "youtube_token_satisdefying.json", "made_for_kids": false}'
        )"""
    )


def downgrade() -> None:
    op.execute("DELETE FROM channels WHERE name = 'Satisdefying'")
