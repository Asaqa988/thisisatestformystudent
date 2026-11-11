"""Knowledge base, AI settings and AI reply log; per-conversation AI switch.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-11
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("ai_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column("conversations", sa.Column("ai_paused_reason", sa.String(300)))

    op.create_table(
        "knowledge_articles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "search",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('simple', title || ' ' || content)", persisted=True),
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_knowledge_articles_search", "knowledge_articles", ["search"], postgresql_using="gin"
    )

    op.create_table(
        "ai_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("business_name", sa.String(120), nullable=False, server_default=""),
        sa.Column("instructions", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    # The single settings row. The agent starts switched off.
    op.execute("INSERT INTO ai_settings (id, enabled) VALUES (1, false)")

    op.create_table(
        "ai_replies",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.Uuid(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("trigger_message_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("reply_text", sa.Text()),
        sa.Column("reason", sa.String(500)),
        sa.Column("external_message_id", sa.String(64)),
        sa.Column("model", sa.String(64)),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cache_read_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint(
            "conversation_id", "trigger_message_id", name="uq_ai_replies_conversation_trigger"
        ),
    )
    op.create_index("ix_ai_replies_conversation_id", "ai_replies", ["conversation_id"])
    op.create_index("ix_ai_replies_created_at", "ai_replies", ["created_at"])
    op.create_index("ix_ai_replies_external_message_id", "ai_replies", ["external_message_id"])


def downgrade() -> None:
    op.drop_table("ai_replies")
    op.drop_table("ai_settings")
    op.drop_table("knowledge_articles")
    op.drop_column("conversations", "ai_paused_reason")
    op.drop_column("conversations", "ai_enabled")
