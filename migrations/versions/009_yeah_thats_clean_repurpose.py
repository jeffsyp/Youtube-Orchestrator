"""Repurpose Yeah Thats Clean from cleaning videos to stick figure action cartoons.

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
    # Update channel niche, description, and config
    op.execute(
        """UPDATE channels SET
            niche = 'AI-generated stick figure action cartoons',
            config = '{"pipeline": "yeah_thats_clean", "description": "Stick figure action that hits different. Clean moves, clean fights, clean wins.", "tone": "intense, kinetic, epic", "category": "Entertainment", "sora_duration": 8, "sora_size": "720x1280", "clips_per_short": 3, "youtube_token_file": "youtube_token_yeah_thats_clean.json", "made_for_kids": false}'
        WHERE name = 'Yeah Thats Clean'"""
    )

    # Clear old cleaning-related feedback since it no longer applies
    op.execute(
        """DELETE FROM assets WHERE channel_id = (
            SELECT id FROM channels WHERE name = 'Yeah Thats Clean'
        ) AND asset_type IN ('video_feedback', 'concept_feedback')"""
    )


def downgrade() -> None:
    op.execute(
        """UPDATE channels SET
            niche = 'AI-generated satisfying cleaning videos',
            config = '{"pipeline": "yeah_thats_clean", "description": "From filthy to flawless. Every clean is pure satisfaction.", "tone": "satisfying, dramatic, transformative", "category": "Entertainment", "sora_duration": 8, "sora_size": "720x1280", "clips_per_short": 3, "youtube_token_file": "youtube_token_yeah_thats_clean.json", "made_for_kids": false}'
        WHERE name = 'Yeah Thats Clean'"""
    )
