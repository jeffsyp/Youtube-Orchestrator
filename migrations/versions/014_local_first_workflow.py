"""Add local-first workflow tables and concept linkage.

Revision ID: 014
Revises: 013
Create Date: 2026-04-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE content_runs ADD COLUMN IF NOT EXISTS content_type VARCHAR(50) DEFAULT 'unified'")
    op.execute("ALTER TABLE content_runs ADD COLUMN IF NOT EXISTS log_entries TEXT")

    op.create_table(
        "concepts",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("channel_id", sa.Integer, sa.ForeignKey("channels.id"), nullable=False),
        sa.Column("origin", sa.String(32), nullable=False, server_default="manual"),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("form_type", sa.String(16), nullable=False, server_default="short"),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("concept_json", sa.Text, nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("priority", sa.Integer, nullable=False, server_default="100"),
        sa.Column("latest_run_id", sa.Integer, sa.ForeignKey("content_runs.id"), nullable=True),
        sa.Column("published_run_id", sa.Integer, sa.ForeignKey("content_runs.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_concepts_channel_status", "concepts", ["channel_id", "status"])
    op.create_index("ix_concepts_status_priority", "concepts", ["status", "priority", "created_at"])

    op.add_column("concept_drafts", sa.Column("concept_id", sa.Integer, sa.ForeignKey("concepts.id"), nullable=True))
    op.add_column("content_bank", sa.Column("concept_id", sa.Integer, sa.ForeignKey("concepts.id"), nullable=True))
    op.add_column("content_runs", sa.Column("concept_id", sa.Integer, sa.ForeignKey("concepts.id"), nullable=True))
    op.add_column("content_runs", sa.Column("trigger_type", sa.String(32), nullable=True, server_default="manual"))
    op.add_column("content_runs", sa.Column("run_dir", sa.Text, nullable=True))
    op.add_column("content_runs", sa.Column("manifest_path", sa.Text, nullable=True))
    op.add_column("content_runs", sa.Column("resume_from_stage", sa.String(100), nullable=True))

    op.create_table(
        "review_tasks",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.Integer, sa.ForeignKey("content_runs.id"), nullable=False),
        sa.Column("concept_id", sa.Integer, sa.ForeignKey("concepts.id"), nullable=True),
        sa.Column("channel_id", sa.Integer, sa.ForeignKey("channels.id"), nullable=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("payload_json", sa.Text, nullable=True),
        sa.Column("resolution_json", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_review_tasks_status_kind", "review_tasks", ["status", "kind", "created_at"])
    op.create_index("ix_review_tasks_run_kind", "review_tasks", ["run_id", "kind", "status"])

    op.create_table(
        "run_events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.Integer, sa.ForeignKey("content_runs.id"), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("level", sa.String(16), nullable=False, server_default="info"),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("stage", sa.String(100), nullable=True),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("data_json", sa.Text, nullable=True),
    )
    op.create_index("ix_run_events_run_id", "run_events", ["run_id", "id"])

    op.execute(
        """
        INSERT INTO concepts (channel_id, origin, status, form_type, title, concept_json, priority, created_at, updated_at)
        SELECT channel_id,
               'auto',
               CASE
                   WHEN status = 'pending' THEN 'draft'
                   WHEN status = 'approved' THEN 'approved'
                   WHEN status = 'rejected' THEN 'rejected'
                   ELSE COALESCE(status, 'draft')
               END,
               COALESCE(form_type, 'short'),
               title,
               concept_json,
               100,
               COALESCE(created_at, NOW()),
               COALESCE(resolved_at, created_at, NOW())
        FROM concept_drafts
        """
    )

    op.execute(
        """
        UPDATE concept_drafts cd
        SET concept_id = c.id
        FROM concepts c
        WHERE c.channel_id = cd.channel_id
          AND c.title = cd.title
          AND c.concept_json = cd.concept_json
          AND cd.concept_id IS NULL
        """
    )

    op.execute(
        """
        INSERT INTO concepts (channel_id, origin, status, form_type, title, concept_json, priority, latest_run_id, created_at, updated_at)
        SELECT cb.channel_id,
               'manual',
               CASE
                   WHEN cb.status = 'queued' THEN 'queued'
                   WHEN cb.status IN ('locked', 'generating') THEN 'running'
                   WHEN cb.status = 'generated' THEN 'ready'
                   WHEN cb.status = 'uploaded' THEN 'published'
                   WHEN cb.status = 'failed' THEN 'failed'
                   WHEN cb.status = 'rejected' THEN 'rejected'
                   ELSE COALESCE(cb.status, 'draft')
               END,
               COALESCE(cb.form_type, 'short'),
               cb.title,
               cb.concept_json,
               COALESCE(cb.priority, 100),
               cb.run_id,
               COALESCE(cb.created_at, NOW()),
               COALESCE(cb.created_at, NOW())
        FROM content_bank cb
        WHERE NOT EXISTS (
            SELECT 1
            FROM concepts c
            WHERE c.channel_id = cb.channel_id
              AND c.title = cb.title
              AND c.concept_json = cb.concept_json
        )
        """
    )

    op.execute(
        """
        UPDATE content_bank cb
        SET concept_id = c.id
        FROM concepts c
        WHERE c.channel_id = cb.channel_id
          AND c.title = cb.title
          AND c.concept_json = cb.concept_json
          AND cb.concept_id IS NULL
        """
    )

    op.execute(
        """
        UPDATE content_runs cr
        SET concept_id = cb.concept_id
        FROM content_bank cb
        WHERE cb.run_id = cr.id
          AND cr.concept_id IS NULL
        """
    )

    op.execute(
        """
        UPDATE concepts c
        SET latest_run_id = cb.run_id
        FROM content_bank cb
        WHERE cb.concept_id = c.id
          AND cb.run_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_run_events_run_id", table_name="run_events")
    op.drop_table("run_events")

    op.drop_index("ix_review_tasks_run_kind", table_name="review_tasks")
    op.drop_index("ix_review_tasks_status_kind", table_name="review_tasks")
    op.drop_table("review_tasks")

    op.drop_column("content_runs", "resume_from_stage")
    op.drop_column("content_runs", "manifest_path")
    op.drop_column("content_runs", "run_dir")
    op.drop_column("content_runs", "trigger_type")
    op.drop_column("content_runs", "concept_id")
    op.drop_column("content_bank", "concept_id")
    op.drop_column("concept_drafts", "concept_id")

    op.drop_index("ix_concepts_status_priority", table_name="concepts")
    op.drop_index("ix_concepts_channel_status", table_name="concepts")
    op.drop_table("concepts")
