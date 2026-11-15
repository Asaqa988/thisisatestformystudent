"""Automation builder endpoints: describe it (by voice or text), the crew builds it,
NEXUS runs it; actions wait for approval."""

import uuid
from datetime import datetime
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_adapter
from app.automations import executor, service
from app.automations.tools import TOOLS
from app.core.db import get_db
from app.core.errors import AppError, NotFound
from app.integrations.base import MessagingAdapter
from app.models import Automation, AutomationFile, AutomationRun

router = APIRouter(prefix="/api/v1", tags=["automations"])


class AutomationIn(BaseModel):
    request: str = Field(min_length=3, max_length=2000)
    language: str | None = Field(None, max_length=16)


class RunOut(BaseModel):
    id: uuid.UUID
    automation_id: uuid.UUID
    automation_title: str | None = None
    status: str
    outputs: list[dict[str, Any]]
    pending_actions: list[dict[str, Any]]
    error: str | None
    files: list[dict[str, Any]]
    started_at: datetime
    finished_at: datetime | None
    decided_at: datetime | None


class AutomationSummaryOut(BaseModel):
    id: uuid.UUID
    title: str
    request_text: str
    language: str | None
    summary: str | None
    status: str
    error: str | None
    review_notes: str | None
    needs_approval: bool
    input_tokens: int
    output_tokens: int
    run_count: int
    last_run_at: datetime | None
    last_run_status: str | None
    created_at: datetime


class AutomationDetailOut(AutomationSummaryOut):
    steps: list[dict[str, Any]]
    runs: list[RunOut]


class AutomationList(BaseModel):
    items: list[AutomationSummaryOut]


class RunList(BaseModel):
    items: list[RunOut]


class ToolOut(BaseModel):
    name: str
    label: str
    kind: str
    description: str


def _get(db: Session, automation_id: uuid.UUID) -> Automation:
    automation = db.get(Automation, automation_id)
    if automation is None:
        raise NotFound("That automation does not exist.")
    return automation


@router.get("/automations/tools", response_model=list[ToolOut])
def list_tools():
    """What automations can do, for the help text in the interface."""
    return [
        ToolOut(name=s.name, label=s.label, kind=s.kind, description=s.description)
        for s in TOOLS.values()
    ]


@router.post(
    "/automations", response_model=AutomationDetailOut, status_code=status.HTTP_202_ACCEPTED
)
def create_automation(
    data: AutomationIn,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    adapter: MessagingAdapter = Depends(get_adapter),
):
    """Save the request and let the crew build it in the background. Poll GET /automations/{id}."""
    automation = Automation(
        id=uuid.uuid4(),
        request_text=data.request.strip(),
        language=data.language,
        title=data.request.strip()[:80],
        status="building",
    )
    db.add(automation)
    db.commit()
    # The same connection this request uses, so the build sees the same channel.
    background.add_task(service.build_and_run, automation.id, adapter=adapter)
    return service.automation_out(db, automation, with_runs=True)


@router.get("/automations", response_model=AutomationList)
def list_automations(limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)):
    rows = db.scalars(select(Automation).order_by(Automation.created_at.desc()).limit(limit)).all()
    return AutomationList(items=[service.automation_out(db, a, with_runs=False) for a in rows])


@router.get("/automations/{automation_id}", response_model=AutomationDetailOut)
def get_automation(automation_id: uuid.UUID, db: Session = Depends(get_db)):
    return service.automation_out(db, _get(db, automation_id), with_runs=True)


@router.post("/automations/{automation_id}/run", response_model=RunOut)
def run_automation(
    automation_id: uuid.UUID,
    db: Session = Depends(get_db),
    adapter: MessagingAdapter = Depends(get_adapter),
):
    """Run the saved plan again on fresh data. No AI is involved, so it is instant and free."""
    automation = _get(db, automation_id)
    if automation.status != "ready":
        raise NotReady("This automation has no plan to run.")
    return service.run_out(db, executor.start_run(db, automation, adapter), automation.title)


@router.delete("/automations/{automation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_automation(automation_id: uuid.UUID, db: Session = Depends(get_db)):
    db.delete(_get(db, automation_id))
    db.commit()


@router.get("/approvals", response_model=RunList)
def pending_approvals(db: Session = Depends(get_db)):
    rows = db.execute(
        select(AutomationRun, Automation.title)
        .join(Automation, Automation.id == AutomationRun.automation_id)
        .where(AutomationRun.status == "awaiting_approval")
        .order_by(AutomationRun.started_at.desc())
    ).all()
    return RunList(items=[service.run_out(db, run, title) for run, title in rows])


@router.post("/automation-runs/{run_id}/approve", response_model=RunOut)
def approve(
    run_id: uuid.UUID,
    db: Session = Depends(get_db),
    adapter: MessagingAdapter = Depends(get_adapter),
):
    run = executor.approve_run(db, adapter, run_id)
    return service.run_out(db, run)


@router.post("/automation-runs/{run_id}/reject", response_model=RunOut)
def reject(run_id: uuid.UUID, db: Session = Depends(get_db)):
    return service.run_out(db, executor.reject_run(db, run_id))


@router.get("/automation-files/{file_id}")
def download(file_id: uuid.UUID, db: Session = Depends(get_db)):
    stored = db.get(AutomationFile, file_id)
    if stored is None:
        raise NotFound("That file does not exist.")
    return Response(
        content=stored.data,
        media_type=stored.content_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(stored.filename)}",
            "Cache-Control": "no-store",
        },
    )


class NotReady(AppError):
    status_code = 409
    code = "invalid_state"
