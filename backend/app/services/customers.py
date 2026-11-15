"""Customers: everyone who has written to the business, on any channel."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.errors import AppError, NotFound
from app.integrations.base import MessagingAdapter
from app.models import Conversation, Customer
from app.schemas import CustomerDetail, CustomerSnapshot, CustomerSummary

UNKNOWN = "Unknown contact"
REFRESH_LIMIT = 300  # customers whose full details one sync fetches from the source

# Fields copied as-is from the source. An empty value from the source clears ours,
# so a phone number removed in Chatwoot disappears from NEXUS too.
_PLAIN_FIELDS = (
    "email",
    "phone",
    "avatar_url",
    "identifier",
    "city",
    "country",
    "company",
    "description",
    "social_profiles",
    "custom_attributes",
    "blocked",
)


def upsert_customer(
    db: Session, source: str, snapshot: CustomerSnapshot, channel: str | None = None
) -> Customer:
    """Create the customer if new, then bring them up to date.

    Same pattern as conversations: INSERT ... ON CONFLICT DO NOTHING lets only one
    of two simultaneous webhooks create the row; then the row is locked and updated.
    """
    db.execute(
        pg_insert(Customer)
        .values(
            id=uuid.uuid4(),
            source=source,
            external_id=snapshot.external_id,
            name=snapshot.name,
        )
        .on_conflict_do_nothing(constraint="uq_customers_source_external_id")
    )
    row = db.scalars(
        select(Customer)
        .where(Customer.source == source, Customer.external_id == snapshot.external_id)
        .with_for_update()
    ).one()

    if snapshot.name != UNKNOWN or not row.name:
        row.name = snapshot.name
    for field in _PLAIN_FIELDS:
        setattr(row, field, getattr(snapshot, field))

    # Channels only ever grow: a customer who wrote on WhatsApp and Instagram has both.
    channels = list(row.channels or [])
    for value in [*snapshot.channels, channel]:
        if value and value != "unknown" and value not in channels:
            channels.append(value)
    row.channels = channels

    if snapshot.first_seen_at and (
        row.first_seen_at is None or snapshot.first_seen_at < row.first_seen_at
    ):
        row.first_seen_at = snapshot.first_seen_at
    if snapshot.last_seen_at and (
        row.last_seen_at is None or snapshot.last_seen_at > row.last_seen_at
    ):
        row.last_seen_at = snapshot.last_seen_at

    row.updated_at = datetime.now(tz=UTC)
    return row


# --- Reading ---------------------------------------------------------------------


def _stats_query():
    """Per-customer conversation numbers, as a subquery to join against."""
    return (
        select(
            Conversation.customer_id.label("customer_id"),
            func.count().label("conversation_count"),
            func.count().filter(Conversation.status != "resolved").label("open_conversations"),
            func.max(Conversation.last_message_at).label("last_message_at"),
        )
        .where(Conversation.customer_id.is_not(None))
        .group_by(Conversation.customer_id)
        .subquery()
    )


def _latest_previews(db: Session, customer_ids: list[uuid.UUID]) -> dict[uuid.UUID, str | None]:
    if not customer_ids:
        return {}
    rows = db.execute(
        select(Conversation.customer_id, Conversation.last_message_preview)
        .where(Conversation.customer_id.in_(customer_ids))
        .order_by(
            Conversation.customer_id,
            Conversation.last_message_at.desc().nulls_last(),
        )
        .distinct(Conversation.customer_id)
    ).all()
    return {customer_id: preview for customer_id, preview in rows}


def _summary(customer: Customer, stats, preview: str | None) -> dict:
    return dict(
        id=customer.id,
        source=customer.source,
        external_id=customer.external_id,
        name=customer.name,
        email=customer.email,
        phone=customer.phone,
        avatar_url=customer.avatar_url,
        city=customer.city,
        country=customer.country,
        company=customer.company,
        channels=list(customer.channels or []),
        # A customer with no conversations yet comes back from the outer join with NULLs.
        conversation_count=(stats.conversation_count or 0) if stats else 0,
        open_conversations=(stats.open_conversations or 0) if stats else 0,
        last_message_at=stats.last_message_at if stats else None,
        last_message_preview=preview,
        first_seen_at=customer.first_seen_at,
    )


def list_customers(
    db: Session,
    query: str | None = None,
    channel: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[CustomerSummary], int]:
    stats = _stats_query()
    base = select(Customer, stats).outerjoin(stats, stats.c.customer_id == Customer.id)

    if query and query.strip():
        like = f"%{query.strip()}%"
        base = base.where(
            or_(
                Customer.name.ilike(like),
                Customer.email.ilike(like),
                Customer.phone.ilike(like),
                Customer.company.ilike(like),
            )
        )
    if channel:
        base = base.where(Customer.channels.contains([channel]))

    total = db.scalar(select(func.count()).select_from(base.subquery()))
    rows = db.execute(
        base.order_by(
            func.coalesce(stats.c.last_message_at, Customer.last_seen_at).desc().nulls_last(),
            Customer.name,
        )
        .limit(limit)
        .offset(offset)
    ).all()

    previews = _latest_previews(db, [row[0].id for row in rows])
    items = [CustomerSummary(**_summary(row[0], row, previews.get(row[0].id))) for row in rows]
    return items, total


def get_customer(db: Session, customer_id: uuid.UUID) -> Customer:
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise NotFound("That customer does not exist in NEXUS.")
    return customer


def customer_detail(db: Session, customer_id: uuid.UUID) -> CustomerDetail:
    from app.services.inbox import to_out  # local import: inbox imports this module

    customer = get_customer(db, customer_id)
    stats = _stats_query()
    row = db.execute(select(stats).where(stats.c.customer_id == customer.id)).first()
    conversations = list(
        db.scalars(
            select(Conversation)
            .where(Conversation.customer_id == customer.id)
            .order_by(func.coalesce(Conversation.last_message_at, Conversation.updated_at).desc())
        )
    )
    preview = conversations[0].last_message_preview if conversations else None
    return CustomerDetail(
        **_summary(customer, row, preview),
        identifier=customer.identifier,
        description=customer.description,
        social_profiles=customer.social_profiles or {},
        custom_attributes=customer.custom_attributes or {},
        blocked=customer.blocked,
        updated_at=customer.updated_at,
        conversations=[to_out(c) for c in conversations],
    )


# --- Fetching from the source --------------------------------------------------------


def refresh_customer(db: Session, adapter: MessagingAdapter, customer_id: uuid.UUID) -> Customer:
    """Re-read one customer's full details from the source system."""
    customer = get_customer(db, customer_id)
    snapshot = adapter.get_customer(customer.external_id)
    if snapshot is not None:
        upsert_customer(db, customer.source, snapshot)
    db.commit()
    return customer


def sync_customers(db: Session, adapter: MessagingAdapter) -> tuple[int, int]:
    """Bring every customer who has ever written in into NEXUS.

    Conversations name their customer, so syncing them creates the customers.
    Each customer is then re-read once for details only the contact record has,
    such as every channel they used. A failure on one customer does not stop the rest.
    """
    from app.services.inbox import sync_from_source  # local import, as above

    conversations = sync_from_source(db, adapter)
    customers = list(
        db.scalars(
            select(Customer)
            .where(Customer.source == adapter.key)
            .order_by(Customer.last_seen_at.desc().nulls_last())
            .limit(REFRESH_LIMIT)
        )
    )
    for customer in customers:
        try:
            snapshot = adapter.get_customer(customer.external_id)
        except AppError:
            continue
        if snapshot is not None:
            upsert_customer(db, customer.source, snapshot)
    db.commit()
    total = db.scalar(select(func.count()).select_from(Customer))
    return total, conversations
