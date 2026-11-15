"""Checks automation plans and runs them.

A run has two phases:

1. Read phase, straight away: every read step runs (find, export, count). Each
   action step is worked out but not performed. The exact targets and wording
   are recorded on the run.
2. Action phase, only after a person approves: the recorded actions are
   performed on exactly the recorded targets, nothing more.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.automations.tools import MAX_RECIPIENTS, TOOLS, Params, StepResult
from app.core.errors import AppError
from app.integrations.base import MessagingAdapter
from app.models import Automation, AutomationFile, AutomationRun, Conversation

MAX_STEPS = 10
WINDOW_REASON = (
    "outside the channel's reply window (Meta allows replies only within 24 hours "
    "of the customer's last message)"
)
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class PlanError(Exception):
    """The plan cannot be run as written."""


@dataclass
class Step:
    id: str
    tool: str
    params: Params


# --- Checking a plan ---------------------------------------------------------------


def validate_plan(raw_steps: list[dict]) -> list[Step]:
    """Turn stored plan steps into checked steps, or raise PlanError saying why not."""
    if not raw_steps:
        raise PlanError("The plan has no steps.")
    if len(raw_steps) > MAX_STEPS:
        raise PlanError(f"The plan has more than {MAX_STEPS} steps.")

    steps: list[Step] = []
    produced: dict[str, str] = {}
    for position, raw in enumerate(raw_steps, start=1):
        step_id = str(raw.get("id") or f"s{position}")
        tool_name = raw.get("tool")
        spec = TOOLS.get(tool_name)
        if spec is None:
            raise PlanError(f"Step {step_id} uses an unknown tool: {tool_name!r}.")
        if step_id in produced:
            raise PlanError(f"Two steps share the id {step_id}.")
        try:
            params = spec.params.model_validate(raw.get("params") or {})
        except ValidationError as error:
            first = error.errors()[0]
            field = ".".join(str(p) for p in first.get("loc", []))
            raise PlanError(f"Step {step_id} ({tool_name}): {field} {first.get('msg')}.") from None

        source = getattr(params, "source", None)
        if source is not None:
            if source not in produced:
                raise PlanError(f"Step {step_id} uses {source}, which is not an earlier step.")
            if produced[source] not in ("customers", "conversations"):
                raise PlanError(f"Step {step_id} needs customers or conversations from {source}.")

        produced[step_id] = spec.produces
        steps.append(Step(id=step_id, tool=tool_name, params=params))
    return steps


def describe_step(step: Step) -> str:
    """A one-line, human description of a step for the interface."""
    spec = TOOLS[step.tool]
    details = {
        k: v
        for k, v in step.params.model_dump(exclude_none=True).items()
        if k not in ("limit",) and v not in ("any",)
    }
    if not details:
        return spec.label
    parts = ", ".join(f"{k.replace('_', ' ')}: {v}" for k, v in details.items())
    return f"{spec.label} ({parts})"


# --- Running ----------------------------------------------------------------------------


def start_run(
    db: Session, automation: Automation, adapter: MessagingAdapter | None = None
) -> AutomationRun:
    """Run the read phase now; hold any actions for approval."""
    run = AutomationRun(id=uuid.uuid4(), automation_id=automation.id, status="running")
    db.add(run)
    automation.run_count += 1
    automation.last_run_at = datetime.now(tz=UTC)
    db.commit()

    try:
        steps = validate_plan(automation.plan)
        results: dict[str, StepResult] = {}
        outputs: list[dict] = []
        pending: list[dict] = []

        for step in steps:
            spec = TOOLS[step.tool]
            if spec.kind == "read":
                result = spec.run(db, step.params, results)
                results[step.id] = result
                output = {
                    "step_id": step.id,
                    "tool": step.tool,
                    "kind": result.kind,
                    "count": result.count,
                    "summary": result.summary,
                }
                if result.table:
                    output["table"] = result.table
                if result.file:
                    filename, content = result.file
                    stored = AutomationFile(
                        id=uuid.uuid4(),
                        run_id=run.id,
                        filename=filename,
                        content_type=XLSX,
                        size=len(content),
                        data=content,
                    )
                    db.add(stored)
                    output.update(file_id=str(stored.id), filename=filename, size=len(content))
                outputs.append(output)
            else:
                action = _prepare_action(db, step, results, adapter)
                pending.append(action)
                outputs.append(
                    {
                        "step_id": step.id,
                        "tool": step.tool,
                        "kind": "action",
                        "count": action["target_count"],
                        "summary": _action_summary(action),
                    }
                )

        run.outputs = outputs
        run.pending_actions = pending
        if pending and any(a["target_count"] for a in pending):
            run.status = "awaiting_approval"
        else:
            run.status = "succeeded"
            run.finished_at = datetime.now(tz=UTC)
    except (PlanError, KeyError, ValueError) as error:
        run.status = "failed"
        run.error = str(error) or "The plan could not be run."
        run.finished_at = datetime.now(tz=UTC)
    db.commit()
    return run


def _prepare_action(
    db: Session,
    step: Step,
    results: dict[str, StepResult],
    adapter: MessagingAdapter | None = None,
) -> dict:
    """Work out exactly which conversations an action step would touch."""
    source = results[step.params.source]
    if source.kind == "customers":
        conversations = _latest_conversation_per_customer(db, source.ids or [])
    else:
        ids = [uuid.UUID(i) for i in source.ids or []]
        found = {c.id: c for c in db.scalars(select(Conversation).where(Conversation.id.in_(ids)))}
        conversations = [found[i] for i in ids if i in found]

    # Customers can only be written to inside the channel's reply window
    # (Meta: 24 hours after their last message). Leave the others out now and
    # say so, instead of sending messages that are certain to fail.
    skipped: list[dict] = []
    if step.tool == "send_message" and adapter is not None:
        windows = _reply_windows(adapter)
        reachable = []
        for conversation in conversations:
            if windows.get(conversation.external_id) is False:
                skipped.append(_target(conversation) | {"reason": WINDOW_REASON})
            else:
                reachable.append(conversation)
        conversations = reachable

    if step.tool == "send_message" and len(conversations) > MAX_RECIPIENTS:
        raise PlanError(
            f"This would message {len(conversations)} conversations; the limit is {MAX_RECIPIENTS}."
        )

    params = step.params.model_dump()
    params.pop("source", None)
    return {
        "step_id": step.id,
        "tool": step.tool,
        "label": TOOLS[step.tool].label,
        **params,  # text, status or enabled, so the approver sees exactly what will happen
        "target_count": len(conversations),
        "targets": [_target(c) for c in conversations],
        "skipped": skipped,
    }


def _action_summary(action: dict) -> str:
    count = action["target_count"]
    skipped = len(action.get("skipped") or [])
    left_out = f" ({skipped} left out: outside the 24-hour reply window)" if skipped else ""
    if count == 0:
        return (
            f"Nothing to do for {action['label'].lower()}: no conversation can receive it{left_out}"
        )
    plural = "" if count == 1 else "s"
    label = action["label"].lower()
    return f"Waiting for approval: {label} for {count} conversation{plural}{left_out}"


def _target(conversation: Conversation) -> dict:
    return {
        "conversation_id": str(conversation.id),
        "name": conversation.contact_name,
        "channel": conversation.channel,
        "status": conversation.status,
    }


def _reply_windows(adapter: MessagingAdapter) -> dict[str, bool]:
    """Ask the channel which conversations accept a message now. If it cannot say,
    assume they all do: the send itself will then report what failed."""
    try:
        return adapter.reply_windows()
    except AppError:
        return {}


def _latest_conversation_per_customer(db: Session, customer_ids: list[str]) -> list[Conversation]:
    ids = [uuid.UUID(i) for i in customer_ids]
    if not ids:
        return []
    rows = db.scalars(
        select(Conversation)
        .where(Conversation.customer_id.in_(ids))
        .order_by(
            Conversation.customer_id,
            Conversation.last_message_at.desc().nulls_last(),
        )
        .distinct(Conversation.customer_id)
    ).all()
    by_customer = {c.customer_id: c for c in rows}
    return [by_customer[i] for i in ids if i in by_customer]


# --- Approval ---------------------------------------------------------------------------


def approve_run(db: Session, adapter: MessagingAdapter, run_id: uuid.UUID) -> AutomationRun:
    run = db.scalars(
        select(AutomationRun).where(AutomationRun.id == run_id).with_for_update()
    ).one_or_none()
    if run is None:
        raise RunNotFound("That run does not exist.")
    if run.status != "awaiting_approval":
        raise RunStateError(
            f"This run is {run.status.replace('_', ' ')}, not waiting for approval."
        )

    run.status = "running"
    run.decided_at = datetime.now(tz=UTC)
    db.commit()

    total = done = 0
    failures: list[str] = []
    outputs = _decided(run.outputs, "Approved")
    actions = [dict(a, targets=[dict(t) for t in a["targets"]]) for a in run.pending_actions]
    # The window may have closed while the run waited for approval.
    windows = _reply_windows(adapter) if any(a["tool"] == "send_message" for a in actions) else {}
    for action in actions:
        ok = 0
        for target in action["targets"]:
            total += 1
            conversation = db.get(Conversation, uuid.UUID(target["conversation_id"]))
            if conversation is None:
                failures.append(f"{target['name']}: conversation no longer exists")
                continue
            if action["tool"] == "send_message" and windows.get(conversation.external_id) is False:
                target["result"] = "skipped"
                failures.append(f"{target['name']}: {WINDOW_REASON}")
                continue
            try:
                message_id = _perform(adapter, action, conversation)
                if message_id:
                    target["message_id"] = message_id  # to match a later delivery failure
                target["result"] = "sent" if message_id else "done"
                ok += 1
            except AppError as error:
                target["result"] = "failed"
                failures.append(f"{target['name']}: {error.message}")
        done += ok
        db.commit()
        outputs.append(
            {
                "step_id": action["step_id"],
                "tool": action["tool"],
                "kind": "action_result",
                "count": ok,
                "summary": f"{action['label']}: done for {ok} of {action['target_count']}",
            }
        )

    run.outputs = outputs
    run.pending_actions = actions
    run.finished_at = datetime.now(tz=UTC)
    if failures:
        shown = "; ".join(failures[:10]) + (
            f"; and {len(failures) - 10} more" if len(failures) > 10 else ""
        )
        run.error = f"{len(failures)} of {total} could not be done: {shown}"
    run.status = "failed" if total and done == 0 else "succeeded"
    db.commit()
    return run


def _perform(adapter: MessagingAdapter, action: dict, conversation: Conversation) -> str | None:
    """Do one action for one conversation. Returns the message id when a message was sent."""
    tool = action["tool"]
    message_id = None
    if tool == "send_message":
        sent = adapter.send_message(conversation.external_id, action["text"])
        message_id = sent.id
        conversation.last_message_preview = " ".join(action["text"].split())[:140]
        conversation.last_message_direction = "outbound"
        conversation.last_message_at = sent.sent_at
    elif tool == "add_note":
        adapter.add_private_note(conversation.external_id, action["text"])
    elif tool == "set_conversation_status":
        adapter.set_conversation_status(conversation.external_id, action["status"])
        conversation.status = action["status"]
    elif tool == "set_ai":
        conversation.ai_enabled = action["enabled"]
        conversation.ai_paused_reason = (
            None if action["enabled"] else "Turned off by an automation."
        )
    conversation.updated_at = datetime.now(tz=UTC)
    return message_id


def record_delivery_failure(db: Session, external_message_id: str, error: str) -> bool:
    """A message an automation sent was accepted, then the channel refused it.

    Chatwoot reports this a moment after sending (a message_updated webhook with an
    error). Mark it on the run, so "done" never hides a message nobody received.
    Returns True when the message belonged to an automation run.
    """
    run = db.scalars(
        select(AutomationRun)
        .where(
            AutomationRun.pending_actions.contains(
                [{"targets": [{"message_id": external_message_id}]}]
            )
        )
        .with_for_update()
    ).first()
    if run is None:
        return False

    actions = [dict(a, targets=[dict(t) for t in a["targets"]]) for a in run.pending_actions]
    name = "a customer"
    for action in actions:
        for target in action["targets"]:
            if target.get("message_id") == external_message_id:
                if target.get("result") == "not_delivered":
                    return True  # already recorded (a repeated update)
                target["result"] = "not_delivered"
                target["error"] = error
                name = target["name"]
    run.pending_actions = actions
    run.outputs = [
        *run.outputs,
        {
            "step_id": "delivery",
            "tool": "send_message",
            "kind": "delivery_failure",
            "count": 1,
            "summary": f"Not delivered to {name}: {error}",
        },
    ]
    sent = [t for a in actions for t in a["targets"] if t.get("message_id")]
    if sent and all(t.get("result") == "not_delivered" for t in sent):
        run.status = "failed"
    note = f"Not delivered to {name}: {error}"
    run.error = f"{run.error}; {note}" if run.error else note
    return True


def reject_run(db: Session, run_id: uuid.UUID) -> AutomationRun:
    run = db.get(AutomationRun, run_id)
    if run is None:
        raise RunNotFound("That run does not exist.")
    if run.status != "awaiting_approval":
        raise RunStateError(
            f"This run is {run.status.replace('_', ' ')}, not waiting for approval."
        )
    run.status = "rejected"
    run.outputs = _decided(run.outputs, "Rejected, nothing done")
    run.decided_at = run.finished_at = datetime.now(tz=UTC)
    db.commit()
    return run


def _decided(outputs: list[dict], verdict: str) -> list[dict]:
    """Rewrite the "Waiting for approval" lines once a person has decided."""
    return [
        {**o, "summary": o["summary"].replace("Waiting for approval", verdict, 1)}
        if o.get("kind") == "action"
        else o
        for o in outputs
    ]


def is_automation_message(db: Session, conversation_id: uuid.UUID, content: str) -> bool:
    """True when an outgoing message was sent by an approved automation.

    Such a message is not a team member taking over, so the AI agent stays on.
    """
    recent = datetime.now(tz=UTC) - timedelta(minutes=15)
    candidates = db.scalars(
        select(AutomationRun).where(
            AutomationRun.decided_at >= recent,
            AutomationRun.pending_actions.contains(
                [{"tool": "send_message", "text": content.strip()}]
            ),
        )
    ).all()
    target = str(conversation_id)
    return any(
        any(t["conversation_id"] == target for a in run.pending_actions for t in a["targets"])
        for run in candidates
    )


class RunNotFound(AppError):
    status_code = 404
    code = "not_found"


class RunStateError(AppError):
    status_code = 409
    code = "invalid_state"
