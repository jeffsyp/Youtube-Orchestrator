"""Insert Techognize channel.

Revision ID: 013
Revises: 012
Create Date: 2026-04-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("SELECT setval('channels_id_seq', COALESCE((SELECT MAX(id) FROM channels), 1))")
    op.execute(
        """INSERT INTO channels (name, niche, config) VALUES (
            'Techognize',
            'AI and technology education',
            '{"pipeline": "techognize", "description": "Making complex tech concepts click. AI, science, and the future — explained.", "tone": "clear, educational, engaging", "category": "Science & Technology", "youtube_token_file": "youtube_token_techognize.json", "made_for_kids": false}'
        )"""
    )


def downgrade() -> None:
    op.execute("DELETE FROM channels WHERE name = 'Techognize'")
