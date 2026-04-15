"""Content factory — content bank, scheduling, and upload tracking.

Revision ID: 010
Revises: 009
Create Date: 2026-03-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "010"
down_revision: Union[str, None] = "009b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Content bank — pre-written concepts waiting to be generated
    op.create_table(
        "content_bank",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("channel_id", sa.Integer, sa.ForeignKey("channels.id"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("concept_json", sa.Text, nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="queued"),
        sa.Column("priority", sa.Integer, nullable=False, server_default="100"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("run_id", sa.Integer, sa.ForeignKey("content_runs.id"), nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("attempt_count", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_index("ix_content_bank_status_priority", "content_bank", ["status", "priority", "created_at"])
    op.create_index("ix_content_bank_channel", "content_bank", ["channel_id", "status"])

    # Per-channel schedule config
    op.create_table(
        "channel_schedules",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("channel_id", sa.Integer, sa.ForeignKey("channels.id"), nullable=False, unique=True),
        sa.Column("videos_per_day", sa.Integer, nullable=False, server_default="2"),
        sa.Column("time_windows", sa.Text, nullable=False,
                  server_default='[{"start":"09:00","end":"12:00"},{"start":"17:00","end":"21:00"}]'),
        sa.Column("auto_upload", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("upload_privacy", sa.String(20), nullable=False, server_default="private"),
        sa.Column("paused", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("timezone", sa.String(50), nullable=False, server_default="America/New_York"),
        sa.Column("voice_id", sa.String(100), nullable=False, server_default="56bWURjYFHyYyVf490Dp"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Scheduled uploads — upload or make public at a specific time
    op.create_table(
        "scheduled_uploads",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.Integer, sa.ForeignKey("content_runs.id"), nullable=False),
        sa.Column("channel_id", sa.Integer, sa.ForeignKey("channels.id"), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("youtube_video_id", sa.String(100), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text, nullable=True),
    )
    op.create_index("ix_scheduled_uploads_pending", "scheduled_uploads", ["status", "scheduled_at"])

    # Add columns to content_runs
    op.add_column("content_runs", sa.Column("content_bank_id", sa.Integer, nullable=True))
    op.add_column("content_runs", sa.Column("pipeline_type", sa.String(20), server_default="deity"))


def downgrade() -> None:
    op.drop_column("content_runs", "pipeline_type")
    op.drop_column("content_runs", "content_bank_id")
    op.drop_table("scheduled_uploads")
    op.drop_table("channel_schedules")
    op.drop_table("content_bank")
