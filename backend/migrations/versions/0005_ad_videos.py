"""Ad videos: storyboards Claude writes from the Knowledge Base.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-16
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ad_videos",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("brief", sa.Text()),
        sa.Column("language", sa.String(8), nullable=False, server_default="en"),
        sa.Column("aspect", sa.String(8), nullable=False, server_default="9:16"),
        sa.Column("title", sa.String(200), nullable=False, server_default="New ad"),
        sa.Column("status", sa.String(16), nullable=False, server_default="building"),
        sa.Column("error", sa.Text()),
        sa.Column("storyboard", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_ad_videos_status", "ad_videos", ["status"])
    op.create_index("ix_ad_videos_created_at", "ad_videos", ["created_at"])


def downgrade() -> None:
    op.drop_table("ad_videos")
