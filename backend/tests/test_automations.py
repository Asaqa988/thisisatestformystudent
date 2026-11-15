"""Automation builder. The crew is replaced by fixed plans: no network, no cost."""

import io
import json

import pytest
from openpyxl import load_workbook
from sqlalchemy import select

from app.automations import crew, service
from app.automations.crew import BuildError, BuildResult, PlanDraft, PlanStep
from app.automations.executor import PlanError, validate_plan
from app.core.db import SessionLocal
from app.models import Automation, Conversation
from tests import samples
from tests.conftest import WEBHOOK_PATH, make_settings, signed

EXPORT_PLAN = [
    {"id": "s1", "tool": "find_customers", "params": {}},
    {"id": "s2", "tool": "export_excel", "params": {"source": "s1", "filename": "customers"}},
]
MESSAGE_PLAN = [
    {"id": "s1", "tool": "find_customers", "params": {}},
    {
        "id": "s2",
        "tool": "send_message",
        "params": {"source": "s1", "text": "We are open on Friday!"},
    },
]


def seed_customers(client, count=2):
    for n in range(count):
        payload = samples.webhook_message_created(message_id=500 + n, conversation_id=40 + n)
        sender = {
            **samples.CONTACT,
            "id": 70 + n,
            "name": f"Customer {n + 1}",
            "phone_number": f"+96279000000{n}",
        }
        payload["conversation"]["meta"]["sender"] = sender
        client.post(WEBHOOK_PATH, **signed(payload, delivery=f"seed-{n}"))


def fake_builder(steps, *, title="Export customers", unsupported=""):
    def build(request_text, **_kwargs):
        plan = PlanDraft(
            title=title,
            summary="Puts every customer in an Excel sheet.",
            steps=[
                PlanStep(id=s["id"], tool=s["tool"], params_json=json.dumps(s["params"]))
                for s in steps
            ],
            unsupported_reason=unsupported,
            review_notes="Checked tools and parameters.",
        )
        return BuildResult(plan=plan, steps=steps, input_tokens=3000, output_tokens=800)

    return build


@pytest.fixture
def builder(monkeypatch):
    """Replace the crew; returns a setter for the plan it should produce."""
    monkeypatch.setattr(service, "get_settings", lambda: make_settings(anthropic_api_key="test"))

    def use(steps, **kwargs):
        monkeypatch.setattr(service, "build_plan", fake_builder(steps, **kwargs))

    return use


def build(client, request="Convert all customers to an Excel sheet"):
    created = client.post("/api/v1/automations", json={"request": request, "language": "en"})
    assert created.status_code == 202
    return client.get(f"/api/v1/automations/{created.json()['id']}").json()


# --- Checking plans ------------------------------------------------------------------------


def test_a_valid_plan_passes():
    assert [s.tool for s in validate_plan(EXPORT_PLAN)] == ["find_customers", "export_excel"]


@pytest.mark.parametrize(
    "steps, message",
    [
        ([{"id": "s1", "tool": "delete_everything", "params": {}}], "unknown tool"),
        (
            [{"id": "s1", "tool": "export_excel", "params": {"source": "s0", "filename": "x"}}],
            "not an earlier step",
        ),
        ([{"id": "s1", "tool": "find_customers", "params": {"colour": "red"}}], "colour"),
        (
            [{"id": "s1", "tool": "find_customers", "params": {"channel": "carrier pigeon"}}],
            "channel",
        ),
        ([], "no steps"),
        (
            [{"id": f"s{i}", "tool": "find_customers", "params": {}} for i in range(11)],
            "more than 10",
        ),
    ],
)
def test_invalid_plans_are_refused(steps, message):
    with pytest.raises(PlanError, match=message):
        validate_plan(steps)


def test_an_action_cannot_use_a_file_as_its_source():
    steps = [
        *EXPORT_PLAN,
        {"id": "s3", "tool": "send_message", "params": {"source": "s2", "text": "hi"}},
    ]
    with pytest.raises(PlanError, match="customers or conversations"):
        validate_plan(steps)


# --- Building and running a read-only automation ------------------------------------------


def test_voice_request_to_excel_file(client, builder):
    seed_customers(client)
    builder(EXPORT_PLAN)

    automation = build(client)

    assert automation["status"] == "ready"
    assert automation["title"] == "Export customers"
    assert automation["needs_approval"] is False
    assert [s["tool"] for s in automation["steps"]] == ["find_customers", "export_excel"]
    [run] = automation["runs"]
    assert run["status"] == "succeeded"
    assert run["outputs"][0]["summary"] == "Found 2 customers"
    [file] = run["files"]
    assert file["filename"] == "customers.xlsx"

    download = client.get(f"/api/v1/automation-files/{file['id']}")
    assert download.status_code == 200
    assert "customers.xlsx" in download.headers["content-disposition"]
    sheet = load_workbook(io.BytesIO(download.content)).active
    rows = list(sheet.values)
    assert rows[0][:3] == ("Name", "Phone", "Email")
    assert sorted(r[0] for r in rows[1:]) == ["Customer 1", "Customer 2"]


def test_run_again_uses_fresh_data_without_the_ai(client, builder, monkeypatch):
    seed_customers(client, count=1)
    builder(EXPORT_PLAN)
    automation = build(client)

    seed_customers(client, count=3)  # two more customers write in
    monkeypatch.setattr(service, "build_plan", lambda *a, **k: pytest.fail("the AI was called"))
    run = client.post(f"/api/v1/automations/{automation['id']}/run").json()

    assert run["outputs"][0]["summary"] == "Found 3 customers"
    assert client.get(f"/api/v1/automations/{automation['id']}").json()["run_count"] == 2


def test_exports_can_choose_columns(client, builder):
    seed_customers(client, count=1)
    plan = [
        {"id": "s1", "tool": "find_customers", "params": {"has_phone": True}},
        {
            "id": "s2",
            "tool": "export_excel",
            "params": {
                "source": "s1",
                "filename": "phones",
                "columns": ["Name", "Phone", "Nonsense"],
            },
        },
    ]
    builder(plan)
    run = build(client)["runs"][0]

    content = client.get(f"/api/v1/automation-files/{run['files'][0]['id']}").content
    header = next(load_workbook(io.BytesIO(content)).active.values)
    assert header == ("Name", "Phone")


def test_summarize_counts_by_channel(client, builder):
    seed_customers(client)
    builder(
        [
            {"id": "s1", "tool": "find_customers", "params": {}},
            {"id": "s2", "tool": "summarize", "params": {"source": "s1", "group_by": "channel"}},
        ]
    )

    outputs = build(client)["runs"][0]["outputs"]

    assert outputs[1]["summary"] == "By channel: api: 2"


def test_requests_the_tools_cannot_do_are_explained(client, builder):
    builder([], unsupported="I can't post on Instagram yet. I can export or message customers.")

    automation = build(client, "Post a photo on Instagram")

    assert automation["status"] == "unsupported"
    assert "can't post on Instagram" in automation["error"]
    assert automation["runs"] == []


def test_crew_failure_is_recorded(client, monkeypatch):
    monkeypatch.setattr(service, "get_settings", lambda: make_settings(anthropic_api_key="test"))

    def broken(*_args, **_kwargs):
        raise BuildError("Anthropic rate limit reached. Try again in a minute.")

    monkeypatch.setattr(service, "build_plan", broken)

    automation = build(client)

    assert automation["status"] == "failed"
    assert "rate limit" in automation["error"]


def test_missing_api_key_is_explained(client, monkeypatch):
    monkeypatch.setattr(service, "get_settings", lambda: make_settings())

    automation = build(client)

    assert automation["status"] == "failed"
    assert "ANTHROPIC_API_KEY" in automation["error"]


def test_an_invalid_plan_from_the_crew_is_not_run(client, builder):
    builder([{"id": "s1", "tool": "drop_database", "params": {}}])

    automation = build(client)

    assert automation["status"] == "failed"
    assert "unknown tool" in automation["error"]
    assert automation["runs"] == []


# --- Actions wait for approval ----------------------------------------------------------


def posted_messages(fake_chatwoot):
    return [json.loads(r.content) for r in fake_chatwoot.requests if r.method == "POST"]


def test_actions_wait_for_approval_and_show_exactly_what_will_happen(
    client, builder, fake_chatwoot
):
    seed_customers(client)
    builder(MESSAGE_PLAN, title="Tell customers we open Friday")

    automation = build(client)
    [run] = automation["runs"]

    assert automation["needs_approval"] is True
    assert run["status"] == "awaiting_approval"
    [action] = run["pending_actions"]
    assert action["tool"] == "send_message"
    assert action["text"] == "We are open on Friday!"
    assert action["target_count"] == 2
    assert sorted(t["name"] for t in action["targets"]) == ["Customer 1", "Customer 2"]
    assert posted_messages(fake_chatwoot) == []  # nothing sent yet

    approvals = client.get("/api/v1/approvals").json()["items"]
    assert [a["automation_title"] for a in approvals] == ["Tell customers we open Friday"]


def test_approving_performs_the_actions(client, builder, fake_chatwoot):
    seed_customers(client)
    builder(MESSAGE_PLAN)
    run = build(client)["runs"][0]

    approved = client.post(f"/api/v1/automation-runs/{run['id']}/approve").json()

    assert approved["status"] == "succeeded"
    assert approved["outputs"][-1]["summary"] == "Send a message: done for 2 of 2"
    sent = posted_messages(fake_chatwoot)
    assert [m["content"] for m in sent] == ["We are open on Friday!"] * 2
    assert all(m["private"] is False for m in sent)
    assert client.get("/api/v1/approvals").json()["items"] == []


def test_a_run_can_only_be_approved_once(client, builder, fake_chatwoot):
    seed_customers(client, count=1)
    builder(MESSAGE_PLAN)
    run = build(client)["runs"][0]

    client.post(f"/api/v1/automation-runs/{run['id']}/approve")
    again = client.post(f"/api/v1/automation-runs/{run['id']}/approve")

    assert again.status_code == 409
    assert len(posted_messages(fake_chatwoot)) == 1


def test_rejecting_sends_nothing(client, builder, fake_chatwoot):
    seed_customers(client)
    builder(MESSAGE_PLAN)
    run = build(client)["runs"][0]

    rejected = client.post(f"/api/v1/automation-runs/{run['id']}/reject").json()

    assert rejected["status"] == "rejected"
    assert posted_messages(fake_chatwoot) == []


def test_failures_are_reported_per_customer(client, builder, fake_chatwoot):
    seed_customers(client)
    builder(MESSAGE_PLAN)
    run = build(client)["runs"][0]
    fake_chatwoot.mode = "error"

    result = client.post(f"/api/v1/automation-runs/{run['id']}/approve").json()

    assert result["status"] == "failed"
    assert "2 of 2 could not be done" in result["error"]


def test_status_and_ai_actions(client, builder, fake_chatwoot):
    seed_customers(client, count=1)
    builder(
        [
            {"id": "s1", "tool": "find_conversations", "params": {"status": "open"}},
            {
                "id": "s2",
                "tool": "set_conversation_status",
                "params": {"source": "s1", "status": "resolved"},
            },
            {"id": "s3", "tool": "set_ai", "params": {"source": "s1", "enabled": False}},
        ]
    )
    run = build(client)["runs"][0]
    client.post(f"/api/v1/automation-runs/{run['id']}/approve")

    toggles = [r for r in fake_chatwoot.requests if r.url.path.endswith("/toggle_status")]
    assert [json.loads(r.content) for r in toggles] == [{"status": "resolved"}]
    with SessionLocal() as db:
        conversation = db.scalars(select(Conversation)).one()
    assert conversation.status == "resolved"
    assert conversation.ai_enabled is False


def test_an_automation_broadcast_does_not_pause_the_ai(client, builder, fake_chatwoot):
    seed_customers(client, count=1)
    builder(MESSAGE_PLAN)
    run = build(client)["runs"][0]
    client.post(f"/api/v1/automation-runs/{run['id']}/approve")

    echo = samples.webhook_message_created(
        message_id=900,
        conversation_id=40,
        message_type="outgoing",
        content="We are open on Friday!",
    )
    client.post(WEBHOOK_PATH, **signed(echo, delivery="echo"))

    with SessionLocal() as db:
        assert db.scalars(select(Conversation)).one().ai_enabled is True


def test_deleting_an_automation(client, builder):
    builder(EXPORT_PLAN)
    automation = build(client)

    assert client.delete(f"/api/v1/automations/{automation['id']}").status_code == 204
    with SessionLocal() as db:
        assert db.scalars(select(Automation)).all() == []


# --- The CrewAI -> Claude bridge -------------------------------------------------------------


def test_crew_messages_become_alternating_claude_turns():
    system, turns = crew._split_messages(
        [
            {"role": "system", "content": "You are an architect."},
            {"role": "assistant", "content": "dropped: Claude turns must start with the user"},
            {"role": "user", "content": "Design it."},
            {"role": "user", "content": "Use the catalog."},
            {"role": "assistant", "content": "Done."},
        ]
    )

    assert system == "You are an architect."
    assert turns == [
        {"role": "user", "content": "Design it.\n\nUse the catalog."},
        {"role": "assistant", "content": "Done."},
    ]


def test_strict_schema_keeps_a_field_named_title():
    schema = crew.strict_schema(PlanDraft)

    assert "title" in schema["properties"]
    assert schema["required"] == ["title", "summary", "steps", "unsupported_reason", "review_notes"]
    assert schema["properties"]["steps"]["items"]["additionalProperties"] is False


# --- Delivery: reply windows and failures reported after sending ---------------------------


def _window(fake_chatwoot, **can_reply_by_conversation):
    """Make the fake Chatwoot report which conversations accept a message now."""
    conversations = []
    for conversation_id, can_reply in can_reply_by_conversation.items():
        raw = samples.rest_conversation(conversation_id=int(conversation_id.removeprefix("c")))
        raw["can_reply"] = can_reply
        conversations.append(raw)
    fake_chatwoot.conversations = conversations


def test_customers_outside_the_reply_window_are_left_out_before_approval(
    client, builder, fake_chatwoot
):
    seed_customers(client)  # conversations 40 and 41
    _window(fake_chatwoot, c40=True, c41=False)
    builder(MESSAGE_PLAN)

    [action] = build(client)["runs"][0]["pending_actions"]

    assert action["target_count"] == 1
    assert [t["name"] for t in action["targets"]] == ["Customer 1"]
    assert [s["name"] for s in action["skipped"]] == ["Customer 2"]
    assert "24 hours" in action["skipped"][0]["reason"]


def test_nobody_reachable_means_nothing_to_approve(client, builder, fake_chatwoot):
    seed_customers(client, count=1)
    _window(fake_chatwoot, c40=False)
    builder(MESSAGE_PLAN)

    run = build(client)["runs"][0]

    assert run["status"] == "succeeded"
    assert run["pending_actions"][0]["target_count"] == 0
    assert posted_messages(fake_chatwoot) == []


def test_the_window_is_checked_again_at_approval(client, builder, fake_chatwoot):
    seed_customers(client, count=1)
    _window(fake_chatwoot, c40=True)
    builder(MESSAGE_PLAN)
    run = build(client)["runs"][0]
    _window(fake_chatwoot, c40=False)  # the customer's 24 hours ran out while waiting

    result = client.post(f"/api/v1/automation-runs/{run['id']}/approve").json()

    assert result["status"] == "failed"
    assert "24 hours" in result["error"]
    assert posted_messages(fake_chatwoot) == []


def _failure_webhook(message_id, conversation_id, error):
    payload = samples.webhook_message_created(
        message_id=message_id,
        conversation_id=conversation_id,
        message_type="outgoing",
        content="We are open on Friday!",
    )
    payload["event"] = "message_updated"
    payload["content_attributes"] = {"external_error": error}
    return payload


def test_a_delivery_failure_reported_later_marks_the_run(client, builder, fake_chatwoot):
    seed_customers(client, count=1)
    builder(MESSAGE_PLAN)
    run = build(client)["runs"][0]
    approved = client.post(f"/api/v1/automation-runs/{run['id']}/approve").json()
    assert approved["status"] == "succeeded"
    assert approved["pending_actions"][0]["targets"][0]["message_id"] == "900"

    failure = _failure_webhook(900, 40, "Authentication Error")
    client.post(WEBHOOK_PATH, **signed(failure, delivery="fail-900"))
    client.post(WEBHOOK_PATH, **signed(failure, delivery="fail-900-again"))  # repeated update

    after = client.get(f"/api/v1/automations/{run['automation_id']}").json()["runs"][0]
    assert after["status"] == "failed"
    assert after["error"] == "Not delivered to Customer 1: Authentication Error"
    assert [o["summary"] for o in after["outputs"] if o["kind"] == "delivery_failure"] == [
        "Not delivered to Customer 1: Authentication Error"
    ]


def test_messages_show_their_delivery_status_and_error():
    from app.integrations.chatwoot import mapper

    failed = mapper.to_message(
        {
            **samples.rest_message(message_id=68, message_type=1),
            "status": "failed",
            "content_attributes": {
                "external_error": "10 - This message is sent outside of allowed window."
            },
        }
    )
    incoming = mapper.to_message({**samples.rest_message(), "status": "sent"})

    assert failed.delivery_status == "failed"
    assert failed.delivery_error.startswith("10 - This message is sent outside")
    assert incoming.delivery_status is None  # only outgoing messages carry one
