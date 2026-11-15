"""Automations, their runs, and the files they produce.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-15
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def _timestamps():
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


def upgrade() -> None:
    op.create_table(
        "automations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("request_text", sa.Text(), nullable=False),
        sa.Column("language", sa.String(16)),
        sa.Column("title", sa.String(200), nullable=False, server_default="New automation"),
        sa.Column("summary", sa.Text()),
        sa.Column("status", sa.String(16), nullable=False, server_default="building"),
        sa.Column("error", sa.Text()),
        sa.Column("plan", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("review_notes", sa.Text()),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("run_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_run_at", sa.DateTime(timezone=True)),
        _timestamps(),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_automations_status", "automations", ["status"])
    op.create_index("ix_automations_created_at", "automations", ["created_at"])

    op.create_table(
        "automation_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "automation_id",
            sa.Uuid(),
            sa.ForeignKey("automations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(24), nullable=False, server_default="running"),
        sa.Column("outputs", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("pending_actions", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("error", sa.Text()),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_automation_runs_automation_id", "automation_runs", ["automation_id"])
    op.create_index("ix_automation_runs_status", "automation_runs", ["status"])

    op.create_table(
        "automation_files",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "run_id",
            sa.Uuid(),
            sa.ForeignKey("automation_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(200), nullable=False),
        sa.Column("content_type", sa.String(120), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        _timestamps(),
    )
    op.create_index("ix_automation_files_run_id", "automation_files", ["run_id"])


def downgrade() -> None:
    op.drop_table("automation_files")
    op.drop_table("automation_runs")
    op.drop_table("automations")
