"""Add form_type column to content_bank.

Revision ID: 012
Revises: 011
"""

from alembic import op
import sqlalchemy as sa

revision = "012"
down_revision = "011"


def upgrade():
    op.add_column("content_bank", sa.Column("form_type", sa.String(10), server_default="short"))


def downgrade():
    op.drop_column("content_bank", "form_type")
