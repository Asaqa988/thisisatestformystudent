"""The tool catalog: everything an automation is allowed to do.

The crew never writes or runs code. It can only chain these tools together. Each
tool has typed parameters (validated before anything runs) and a kind:

    read     looks at NEXUS data or makes a file. Runs immediately.
    action   changes something or contacts customers. Waits for a person to approve.

To give automations a new ability, add a tool here. Nothing else needs to change:
the crew is shown this catalog, and the executor runs it.
"""

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.automations.excel import COLUMN_SETS, build_workbook
from app.models import Conversation, Customer

Channel = Literal[
    "whatsapp", "instagram", "facebook", "web_widget", "email", "api", "telegram", "sms"
]
MAX_ROWS = 5000
MAX_RECIPIENTS = 300


class Params(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- Parameters ----------------------------------------------------------------------


class FindCustomersParams(Params):
    search: str | None = Field(None, description="Text in the name, phone, email or company")
    channel: Channel | None = Field(None, description="Only customers who used this channel")
    has_phone: bool | None = Field(None, description="true: only with a phone; false: only without")
    has_email: bool | None = Field(
        None, description="true: only with an email; false: only without"
    )
    active_within_days: int | None = Field(
        None, ge=1, le=3650, description="Wrote in the last N days"
    )
    inactive_for_days: int | None = Field(
        None, ge=1, le=3650, description="Silent for at least N days"
    )
    limit: int = Field(MAX_ROWS, ge=1, le=MAX_ROWS)


class FindConversationsParams(Params):
    status: Literal["open", "pending", "snoozed", "resolved", "any"] = "any"
    channel: Channel | None = None
    awaiting_reply: bool | None = Field(None, description="true: the customer spoke last")
    active_within_days: int | None = Field(None, ge=1, le=3650)
    inactive_for_days: int | None = Field(None, ge=1, le=3650)
    limit: int = Field(MAX_ROWS, ge=1, le=MAX_ROWS)


class ExportExcelParams(Params):
    source: str = Field(description="Id of an earlier find_customers or find_conversations step")
    filename: str = Field(min_length=1, max_length=80, description="File name without extension")
    sheet_name: str | None = Field(None, max_length=31)
    columns: list[str] | None = Field(None, description="Subset of the available columns, in order")


class SummarizeParams(Params):
    source: str
    group_by: Literal["channel", "status", "country", "none"] = "none"


class SendMessageParams(Params):
    source: str = Field(description="Id of an earlier find_customers or find_conversations step")
    text: str = Field(min_length=1, max_length=1000, description="The exact message to send")


class AddNoteParams(Params):
    source: str
    text: str = Field(min_length=1, max_length=1000)


class SetStatusParams(Params):
    source: str
    status: Literal["open", "resolved"]


class SetAIParams(Params):
    source: str
    enabled: bool


# --- What steps produce ------------------------------------------------------------------


@dataclass
class StepResult:
    kind: Literal["customers", "conversations", "file", "summary"]
    count: int = 0
    rows: list[dict] | None = None  # customers or conversations, ready for export
    ids: list[str] | None = None  # NEXUS ids, so actions can find the rows again
    summary: str = ""
    file: tuple[str, bytes] | None = None  # (filename, content)
    table: list[dict] | None = None


@dataclass
class ToolSpec:
    name: str
    kind: Literal["read", "action"]
    description: str
    params: type[Params]
    produces: str
    run: Callable | None = None  # read tools: (db, params, results) -> StepResult
    label: str = ""


# --- Read tools --------------------------------------------------------------------------


def _since(days: int) -> datetime:
    return datetime.now(tz=UTC) - timedelta(days=days)


def find_customers(db: Session, p: FindCustomersParams, _results) -> StepResult:
    last_message = (
        select(Conversation.customer_id, func.max(Conversation.last_message_at).label("last_at"))
        .group_by(Conversation.customer_id)
        .subquery()
    )
    counts = (
        select(
            Conversation.customer_id,
            func.count().label("total"),
            func.count().filter(Conversation.status != "resolved").label("open"),
        )
        .group_by(Conversation.customer_id)
        .subquery()
    )
    activity = func.coalesce(last_message.c.last_at, Customer.last_seen_at)
    query = (
        select(Customer, activity.label("last_at"), counts.c.total, counts.c.open)
        .outerjoin(last_message, last_message.c.customer_id == Customer.id)
        .outerjoin(counts, counts.c.customer_id == Customer.id)
    )
    if p.search:
        like = f"%{p.search.strip()}%"
        query = query.where(
            Customer.name.ilike(like)
            | Customer.email.ilike(like)
            | Customer.phone.ilike(like)
            | Customer.company.ilike(like)
        )
    if p.channel:
        query = query.where(Customer.channels.contains([p.channel]))
    if p.has_phone is not None:
        query = query.where(
            Customer.phone.is_not(None) if p.has_phone else Customer.phone.is_(None)
        )
    if p.has_email is not None:
        query = query.where(
            Customer.email.is_not(None) if p.has_email else Customer.email.is_(None)
        )
    if p.active_within_days:
        query = query.where(activity >= _since(p.active_within_days))
    if p.inactive_for_days:
        query = query.where((activity < _since(p.inactive_for_days)) | activity.is_(None))

    rows = db.execute(query.order_by(activity.desc().nulls_last()).limit(p.limit)).all()
    records = [
        {
            "Name": c.name,
            "Phone": c.phone or "",
            "Email": c.email or "",
            "Channels": ", ".join(c.channels or []),
            "City": c.city or "",
            "Country": c.country or "",
            "Company": c.company or "",
            "Conversations": total or 0,
            "Open conversations": open_ or 0,
            "Last message": last_at,
            "First contact": c.first_seen_at,
        }
        for c, last_at, total, open_ in rows
    ]
    return StepResult(
        kind="customers",
        count=len(records),
        rows=records,
        ids=[str(c.id) for c, *_ in rows],
        summary=f"Found {len(records)} customer{'' if len(records) == 1 else 's'}",
    )


def find_conversations(db: Session, p: FindConversationsParams, _results) -> StepResult:
    activity = func.coalesce(Conversation.last_message_at, Conversation.updated_at)
    query = select(Conversation)
    if p.status != "any":
        query = query.where(Conversation.status == p.status)
    if p.channel:
        query = query.where(Conversation.channel == p.channel)
    if p.awaiting_reply is not None:
        condition = Conversation.last_message_direction == "inbound"
        query = query.where(condition if p.awaiting_reply else ~condition)
    if p.active_within_days:
        query = query.where(activity >= _since(p.active_within_days))
    if p.inactive_for_days:
        query = query.where(activity < _since(p.inactive_for_days))

    conversations = list(db.scalars(query.order_by(activity.desc()).limit(p.limit)))
    who = {"inbound": "Customer", "outbound": "Team", "system": "System"}
    records = [
        {
            "Customer": c.contact_name,
            "Channel": c.channel,
            "Inbox": c.inbox_name or "",
            "Status": c.status,
            "Last message": c.last_message_preview or "",
            "Last message from": who.get(c.last_message_direction or "", ""),
            "Last message at": c.last_message_at,
            "AI": "On" if c.ai_enabled else "Paused",
        }
        for c in conversations
    ]
    return StepResult(
        kind="conversations",
        count=len(records),
        rows=records,
        ids=[str(c.id) for c in conversations],
        summary=f"Found {len(records)} conversation{'' if len(records) == 1 else 's'}",
    )


def export_excel(_db: Session, p: ExportExcelParams, results: dict[str, StepResult]) -> StepResult:
    source = results[p.source]
    content, used_columns = build_workbook(
        source.rows or [], kind=source.kind, columns=p.columns, sheet_name=p.sheet_name
    )
    filename = safe_filename(p.filename) + ".xlsx"
    return StepResult(
        kind="file",
        count=source.count,
        file=(filename, content),
        summary=f"Created {filename} with {source.count} row{'' if source.count == 1 else 's'} "
        f"and {len(used_columns)} columns",
    )


def summarize(_db: Session, p: SummarizeParams, results: dict[str, StepResult]) -> StepResult:
    source = results[p.source]
    rows = source.rows or []
    if p.group_by == "none":
        return StepResult(kind="summary", count=len(rows), summary=f"{len(rows)} in total")

    def key(row: dict) -> str:
        if p.group_by == "channel":
            return row.get("Channel") or row.get("Channels") or "unknown"
        if p.group_by == "status":
            return row.get("Status") or "unknown"
        return row.get("Country") or "unknown"

    counts = Counter()
    for row in rows:
        values = (
            [v.strip() for v in str(key(row)).split(",")] if p.group_by == "channel" else [key(row)]
        )
        counts.update(v or "unknown" for v in values)
    table = [{"group": group, "count": n} for group, n in counts.most_common()]
    parts = ", ".join(f"{t['group']}: {t['count']}" for t in table) or "nothing to count"
    return StepResult(
        kind="summary", count=len(rows), table=table, summary=f"By {p.group_by}: {parts}"
    )


def safe_filename(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_ " else "_" for ch in name).strip()
    return (cleaned or "export")[:80]


# --- The catalog ---------------------------------------------------------------------------

TOOLS: dict[str, ToolSpec] = {
    spec.name: spec
    for spec in [
        ToolSpec(
            name="find_customers",
            kind="read",
            label="Find customers",
            description="Select customers (people who have written in), optionally filtered.",
            params=FindCustomersParams,
            produces="customers",
            run=find_customers,
        ),
        ToolSpec(
            name="find_conversations",
            kind="read",
            label="Find conversations",
            description="Select conversations, optionally filtered by status, channel or activity.",
            params=FindConversationsParams,
            produces="conversations",
            run=find_conversations,
        ),
        ToolSpec(
            name="export_excel",
            kind="read",
            label="Export to Excel",
            description=(
                "Make an .xlsx file from an earlier find step. Customer columns: "
                + ", ".join(COLUMN_SETS["customers"])
                + ". Conversation columns: "
                + ", ".join(COLUMN_SETS["conversations"])
                + "."
            ),
            params=ExportExcelParams,
            produces="file",
            run=export_excel,
        ),
        ToolSpec(
            name="summarize",
            kind="read",
            label="Count and group",
            description="Count the results of an earlier find step, optionally grouped.",
            params=SummarizeParams,
            produces="summary",
            run=summarize,
        ),
        ToolSpec(
            name="send_message",
            kind="action",
            label="Send a message",
            description=(
                "Send the same message to each customer or conversation from an earlier find step. "
                "For customers, it goes to their most recent conversation. Needs approval. "
                f"At most {MAX_RECIPIENTS} recipients."
            ),
            params=SendMessageParams,
            produces="action",
        ),
        ToolSpec(
            name="add_note",
            kind="action",
            label="Add an internal note",
            description=(
                "Add a private note (customers never see it) to each conversation. Needs approval."
            ),
            params=AddNoteParams,
            produces="action",
        ),
        ToolSpec(
            name="set_conversation_status",
            kind="action",
            label="Open or resolve conversations",
            description="Mark each conversation open or resolved. Needs approval.",
            params=SetStatusParams,
            produces="action",
        ),
        ToolSpec(
            name="set_ai",
            kind="action",
            label="Turn the AI agent on or off",
            description="Turn the AI agent on or off for each conversation. Needs approval.",
            params=SetAIParams,
            produces="action",
        ),
    ]
}


def catalog_for_prompt() -> str:
    """The catalog as the crew sees it: names, purpose and exact parameter schemas."""
    import json

    lines = []
    for spec in TOOLS.values():
        schema = spec.params.model_json_schema()
        props = {
            name: {
                k: v
                for k, v in prop.items()
                if k
                in (
                    "type",
                    "enum",
                    "description",
                    "anyOf",
                    "default",
                    "minimum",
                    "maximum",
                    "items",
                )
            }
            for name, prop in schema.get("properties", {}).items()
        }
        lines.append(
            f"- {spec.name} ({spec.kind}; produces {spec.produces}): {spec.description}\n"
            f"  params: {json.dumps(props, ensure_ascii=False)}\n"
            f"  required: {schema.get('required', [])}"
        )
    return "\n".join(lines)
