"""Initial schema with all Phase 1 tables.

Revision ID: 001
Revises: None
Create Date: 2026-03-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "channels",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("niche", sa.String(255), nullable=False),
        sa.Column("config", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "content_runs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("channel_id", sa.Integer, sa.ForeignKey("channels.id"), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("current_step", sa.String(100), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text, nullable=True),
    )

    op.create_table(
        "source_candidates",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.Integer, sa.ForeignKey("content_runs.id"), nullable=False),
        sa.Column("channel_id", sa.Integer, sa.ForeignKey("channels.id"), nullable=False),
        sa.Column("video_id", sa.String(50), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("channel_name", sa.String(255), nullable=False),
        sa.Column("channel_subscribers", sa.Integer, nullable=True),
        sa.Column("views", sa.Integer, nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer, nullable=True),
        sa.Column("tags", sa.Text, nullable=True),
        sa.Column("breakout_score", sa.Float, nullable=True, server_default="0"),
    )

    op.create_table(
        "templates",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.Integer, sa.ForeignKey("content_runs.id"), nullable=False),
        sa.Column("channel_id", sa.Integer, sa.ForeignKey("channels.id"), nullable=False),
        sa.Column("pattern_name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("hook_style", sa.String(255), nullable=True),
        sa.Column("structure", sa.Text, nullable=True),
        sa.Column("source_video_ids", sa.Text, nullable=True),
    )

    op.create_table(
        "ideas",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.Integer, sa.ForeignKey("content_runs.id"), nullable=False),
        sa.Column("channel_id", sa.Integer, sa.ForeignKey("channels.id"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("hook", sa.Text, nullable=True),
        sa.Column("angle", sa.Text, nullable=True),
        sa.Column("target_length_seconds", sa.Integer, nullable=True),
        sa.Column("score", sa.Float, nullable=True, server_default="0"),
        sa.Column("selected", sa.Boolean, nullable=False, server_default="false"),
    )

    op.create_table(
        "scripts",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.Integer, sa.ForeignKey("content_runs.id"), nullable=False),
        sa.Column("channel_id", sa.Integer, sa.ForeignKey("channels.id"), nullable=False),
        sa.Column("idea_title", sa.String(500), nullable=True),
        sa.Column("stage", sa.String(50), nullable=False),
        sa.Column("content", sa.Text, nullable=True),
        sa.Column("word_count", sa.Integer, nullable=True, server_default="0"),
        sa.Column("critique_notes", sa.Text, nullable=True),
    )

    op.create_table(
        "assets",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.Integer, sa.ForeignKey("content_runs.id"), nullable=False),
        sa.Column("channel_id", sa.Integer, sa.ForeignKey("channels.id"), nullable=False),
        sa.Column("asset_type", sa.String(100), nullable=False),
        sa.Column("content", sa.Text, nullable=True),
    )

    op.create_table(
        "packages",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.Integer, sa.ForeignKey("content_runs.id"), nullable=False),
        sa.Column("channel_id", sa.Integer, sa.ForeignKey("channels.id"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("tags", sa.Text, nullable=True),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="draft"),
    )

    op.create_table(
        "performance_snapshots",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("package_id", sa.Integer, sa.ForeignKey("packages.id"), nullable=False),
        sa.Column("channel_id", sa.Integer, sa.ForeignKey("channels.id"), nullable=False),
        sa.Column("views", sa.Integer, nullable=True, server_default="0"),
        sa.Column("ctr", sa.Float, nullable=True),
        sa.Column("retention_pct", sa.Float, nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("performance_snapshots")
    op.drop_table("packages")
    op.drop_table("assets")
    op.drop_table("scripts")
    op.drop_table("ideas")
    op.drop_table("templates")
    op.drop_table("source_candidates")
    op.drop_table("content_runs")
    op.drop_table("channels")
