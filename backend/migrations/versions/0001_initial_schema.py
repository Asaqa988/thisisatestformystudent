"""Initial schema: webhook events and conversation references.

Revision ID: 0001
Revises:
Create Date: 2026-11-10
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "webhook_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("dedupe_key", sa.String(255), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("external_account_id", sa.String(64)),
        sa.Column("external_conversation_id", sa.String(64)),
        sa.Column("summary", sa.String(300), nullable=False, server_default=""),
        sa.Column("status", sa.String(16), nullable=False, server_default="processed"),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("duplicate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_duplicate_at", sa.DateTime(timezone=True)),
        sa.Column(
            "received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        # The duplicate guard: one row per delivery per source.
        sa.UniqueConstraint("source", "dedupe_key", name="uq_webhook_events_source_dedupe_key"),
    )
    op.create_index("ix_webhook_events_event_type", "webhook_events", ["event_type"])
    op.create_index(
        "ix_webhook_events_external_conversation_id", "webhook_events", ["external_conversation_id"]
    )
    op.create_index("ix_webhook_events_received_at", "webhook_events", ["received_at"])

    op.create_table(
        "conversations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("external_id", sa.String(64), nullable=False),
        sa.Column("external_account_id", sa.String(64)),
        sa.Column("channel", sa.String(32), nullable=False, server_default="unknown"),
        sa.Column("inbox_name", sa.String(120)),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.Column("contact_name", sa.String(200), nullable=False, server_default="Unknown contact"),
        sa.Column("contact_email", sa.String(320)),
        sa.Column("contact_avatar_url", sa.Text()),
        sa.Column("last_message_preview", sa.String(280)),
        sa.Column("last_message_direction", sa.String(16)),
        sa.Column("last_message_at", sa.DateTime(timezone=True)),
        sa.Column("unread_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("source", "external_id", name="uq_conversations_source_external_id"),
    )
    op.create_index("ix_conversations_status", "conversations", ["status"])
    op.create_index("ix_conversations_updated_at", "conversations", ["updated_at"])


def downgrade() -> None:
    op.drop_table("conversations")
    op.drop_table("webhook_events")
