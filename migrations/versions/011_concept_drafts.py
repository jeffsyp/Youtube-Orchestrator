"""Concept drafts table for auto-generated concepts per channel.

Revision ID: 011
"""

from alembic import op
import sqlalchemy as sa

revision = "011"
down_revision = "010"


def upgrade():
    op.execute("""
        CREATE TABLE concept_drafts (
            id              SERIAL PRIMARY KEY,
            channel_id      INTEGER NOT NULL REFERENCES channels(id),
            title           VARCHAR(500) NOT NULL,
            concept_json    TEXT NOT NULL,
            brief           TEXT,
            score           FLOAT DEFAULT 0,
            status          VARCHAR(50) DEFAULT 'pending',
            created_at      TIMESTAMPTZ DEFAULT NOW(),
            resolved_at     TIMESTAMPTZ,
            content_bank_id INTEGER REFERENCES content_bank(id),
            rejection_reason TEXT
        );
        CREATE INDEX ix_concept_drafts_channel_status ON concept_drafts (channel_id, status);
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS concept_drafts")
