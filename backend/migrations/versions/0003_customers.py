"""Customers, and the link from each conversation to its customer.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-15
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("external_id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(200), nullable=False, server_default="Unknown contact"),
        sa.Column("email", sa.String(320)),
        sa.Column("phone", sa.String(40)),
        sa.Column("avatar_url", sa.Text()),
        sa.Column("identifier", sa.String(200)),
        sa.Column("city", sa.String(120)),
        sa.Column("country", sa.String(120)),
        sa.Column("company", sa.String(200)),
        sa.Column("description", sa.Text()),
        sa.Column("social_profiles", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("custom_attributes", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("channels", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("blocked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("first_seen_at", sa.DateTime(timezone=True)),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("source", "external_id", name="uq_customers_source_external_id"),
    )
    op.create_index("ix_customers_email", "customers", ["email"])
    op.create_index("ix_customers_phone", "customers", ["phone"])

    op.add_column(
        "conversations",
        sa.Column("customer_id", sa.Uuid(), sa.ForeignKey("customers.id", ondelete="SET NULL")),
    )
    op.create_index("ix_conversations_customer_id", "conversations", ["customer_id"])


def downgrade() -> None:
    op.drop_index("ix_conversations_customer_id", table_name="conversations")
    op.drop_column("conversations", "customer_id")
    op.drop_table("customers")
