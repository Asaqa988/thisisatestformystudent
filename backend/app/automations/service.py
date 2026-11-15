"""Building automations in the background, and shaping them for the API."""

import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.automations.crew import BuildError, build_plan
from app.automations.executor import PlanError, Step, describe_step, start_run, validate_plan
from app.automations.tools import TOOLS
from app.core.config import Settings, get_settings
from app.core.db import SessionLocal
from app.integrations.base import MessagingAdapter
from app.models import Automation, AutomationFile, AutomationRun

log = logging.getLogger("nexus.automations")


def build_and_run(
    automation_id: uuid.UUID,
    *,
    adapter: MessagingAdapter | None = None,
    config: Settings | None = None,
    builder: Callable | None = None,
) -> None:
    """Ask the crew for a plan, check it, save it, and run it once. Never raises."""
    config = config or get_settings()
    builder = builder or build_plan  # looked up now, so tests can replace it
    with SessionLocal() as db:
        automation = db.get(Automation, automation_id)
        if automation is None:
            return
        try:
            _build(db, automation, config, builder, adapter)
        except Exception:  # noqa: BLE001 - background task: record, never crash
            log.exception("Building automation %s failed", automation_id)
            db.rollback()
            automation = db.get(Automation, automation_id)
            automation.status = "failed"
            automation.error = "Unexpected error while building the automation."
            automation.updated_at = datetime.now(tz=UTC)
            db.commit()


def _build(
    db: Session,
    automation: Automation,
    config: Settings,
    builder: Callable,
    adapter: MessagingAdapter | None,
) -> None:
    if not config.anthropic_api_key:
        return _fail(db, automation, "No ANTHROPIC_API_KEY is configured on the server.")

    try:
        result = builder(
            automation.request_text,
            api_key=config.anthropic_api_key,
            model=config.ai_model,
            effort="medium",
        )
    except BuildError as error:
        return _fail(db, automation, str(error))

    plan = result.plan
    automation.title = (plan.title or "Automation").strip()[:200]
    automation.summary = plan.summary.strip() or None
    automation.review_notes = plan.review_notes.strip() or None
    automation.input_tokens = result.input_tokens
    automation.output_tokens = result.output_tokens
    automation.plan = result.steps

    if not result.steps:
        automation.status = "unsupported"
        automation.error = (
            plan.unsupported_reason.strip() or "This request cannot be automated yet."
        )
        automation.updated_at = datetime.now(tz=UTC)
        db.commit()
        return

    try:
        validate_plan(result.steps)
    except PlanError as error:
        return _fail(db, automation, f"The plan was not valid: {error}")

    automation.status = "ready"
    automation.error = None
    automation.updated_at = datetime.now(tz=UTC)
    db.commit()
    start_run(db, automation, adapter)


def _fail(db: Session, automation: Automation, reason: str) -> None:
    automation.status = "failed"
    automation.error = reason[:2000]
    automation.updated_at = datetime.now(tz=UTC)
    db.commit()


# --- Shapes for the API -------------------------------------------------------------------


def steps_for_display(automation: Automation) -> list[dict]:
    shown = []
    for position, raw in enumerate(automation.plan or [], start=1):
        spec = TOOLS.get(raw.get("tool"))
        description = spec.label if spec else str(raw.get("tool"))
        if spec is not None:
            try:
                description = describe_step(
                    Step(
                        id=raw.get("id"),
                        tool=spec.name,
                        params=spec.params.model_validate(raw.get("params") or {}),
                    )
                )
            except Exception:  # noqa: BLE001 - show the raw step if it no longer validates
                pass
        shown.append(
            {
                "id": raw.get("id") or f"s{position}",
                "tool": raw.get("tool"),
                "kind": spec.kind if spec else "unknown",
                "description": description,
                "params": raw.get("params") or {},
            }
        )
    return shown


def run_out(db: Session, run: AutomationRun, title: str | None = None) -> dict:
    files = db.execute(
        select(AutomationFile.id, AutomationFile.filename, AutomationFile.size).where(
            AutomationFile.run_id == run.id
        )
    ).all()
    return {
        "id": run.id,
        "automation_id": run.automation_id,
        "automation_title": title,
        "status": run.status,
        "outputs": run.outputs or [],
        "pending_actions": [
            {**action, "targets": action["targets"][:50]} for action in (run.pending_actions or [])
        ],
        "error": run.error,
        "files": [{"id": f.id, "filename": f.filename, "size": f.size} for f in files],
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "decided_at": run.decided_at,
    }


def automation_out(db: Session, automation: Automation, *, with_runs: bool) -> dict:
    latest = db.scalars(
        select(AutomationRun)
        .where(AutomationRun.automation_id == automation.id)
        .order_by(AutomationRun.started_at.desc())
        .limit(10 if with_runs else 1)
    ).all()
    data = {
        "id": automation.id,
        "title": automation.title,
        "request_text": automation.request_text,
        "language": automation.language,
        "summary": automation.summary,
        "status": automation.status,
        "error": automation.error,
        "review_notes": automation.review_notes,
        "needs_approval": any(
            TOOLS.get(s.get("tool")) and TOOLS[s["tool"]].kind == "action"
            for s in automation.plan or []
        ),
        "input_tokens": automation.input_tokens,
        "output_tokens": automation.output_tokens,
        "run_count": automation.run_count,
        "last_run_at": automation.last_run_at,
        "last_run_status": latest[0].status if latest else None,
        "created_at": automation.created_at,
    }
    if with_runs:
        data["steps"] = steps_for_display(automation)
        data["runs"] = [run_out(db, run) for run in latest]
    return data
