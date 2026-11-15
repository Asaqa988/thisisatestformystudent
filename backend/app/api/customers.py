"""Customers endpoints: everyone who has written in, with their details and conversations."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_adapter
from app.core.db import get_db
from app.integrations.base import MessagingAdapter
from app.schemas import CustomerDetail, CustomerList, CustomerSyncResult
from app.services import customers

router = APIRouter(prefix="/api/v1/customers", tags=["customers"])


@router.get("", response_model=CustomerList)
def list_customers(
    q: str | None = Query(None, max_length=100, description="Search name, email, phone or company"),
    channel: str | None = Query(None, max_length=32),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    items, total = customers.list_customers(db, q, channel, limit, offset)
    return CustomerList(items=items, total=total)


@router.post("/sync", response_model=CustomerSyncResult)
def sync_customers(db: Session = Depends(get_db), adapter: MessagingAdapter = Depends(get_adapter)):
    total, conversations = customers.sync_customers(db, adapter)
    return CustomerSyncResult(customers=total, conversations=conversations)


@router.get("/{customer_id}", response_model=CustomerDetail)
def get_customer(customer_id: uuid.UUID, db: Session = Depends(get_db)):
    return customers.customer_detail(db, customer_id)


@router.post("/{customer_id}/refresh", response_model=CustomerDetail)
def refresh_customer(
    customer_id: uuid.UUID,
    db: Session = Depends(get_db),
    adapter: MessagingAdapter = Depends(get_adapter),
):
    customers.refresh_customer(db, adapter, customer_id)
    return customers.customer_detail(db, customer_id)
