"""The CrewAI crew that turns a request ("export all customers to Excel") into a plan.

Two agents work in order:

    Automation architect  designs the smallest plan that does what was asked,
                          using only the tool catalog.
    Safety reviewer       checks the plan against the request and the rules and
                          returns the final version.

Neither agent ever sees customer data or runs anything. They only write a plan;
app/automations/executor.py checks it and runs it.

CrewAI reaches Claude through ClaudeForCrew below, which uses the same official
Anthropic SDK as the AI agent. That keeps one SDK version for the whole backend.
"""

import json
import os
from dataclasses import dataclass, field
from typing import Any

# CrewAI sends usage data to its own servers unless told not to.
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("CREWAI_DISABLE_TRACKING", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")

import anthropic  # noqa: E402
from crewai import Agent, Crew, Process, Task  # noqa: E402
from crewai.llms.base_llm import BaseLLM  # noqa: E402
from pydantic import BaseModel, Field, PrivateAttr  # noqa: E402

from app.automations.tools import catalog_for_prompt  # noqa: E402

FALLBACK_BETA = "server-side-fallback-2026-07-01"


# --- What the crew must return -------------------------------------------------------


class PlanStep(BaseModel):
    id: str = Field(description="s1, s2, s3 ... in order")
    tool: str = Field(description="A tool name from the catalog")
    params_json: str = Field(description="The tool's parameters as a JSON object, in a string")


class PlanDraft(BaseModel):
    title: str = Field(description="Short title in the user's language, at most 8 words")
    summary: str = Field(
        description="One or two sentences, in the user's language, on what it does"
    )
    steps: list[PlanStep]
    unsupported_reason: str = Field(
        description="Empty if the plan does what was asked; otherwise why it cannot, and what can"
    )
    review_notes: str = Field(
        description="What the reviewer checked or changed; empty from the architect"
    )


@dataclass
class BuildResult:
    plan: PlanDraft
    steps: list[dict] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0


class BuildError(Exception):
    """The crew could not produce a plan."""


# --- CrewAI -> Claude --------------------------------------------------------------


class ClaudeForCrew(BaseLLM):
    """A CrewAI LLM that calls Claude with the official Anthropic SDK."""

    effort: str = "medium"
    _client: Any = PrivateAttr(default=None)
    _input_tokens: int = PrivateAttr(default=0)
    _output_tokens: int = PrivateAttr(default=0)

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        self._client = anthropic.Anthropic(api_key=self.api_key, timeout=120.0, max_retries=2)

    @property
    def usage(self) -> tuple[int, int]:
        return self._input_tokens, self._output_tokens

    def supports_stop_words(self) -> bool:
        return False

    def get_context_window_size(self) -> int:
        return 200_000

    def call(
        self,
        messages,
        tools=None,
        callbacks=None,
        available_functions=None,
        from_task=None,
        from_agent=None,
        response_model=None,
    ):
        system, turns = _split_messages(messages)
        output_config: dict[str, Any] = {"effort": self.effort}
        if response_model is not None:
            output_config["format"] = {
                "type": "json_schema",
                "schema": strict_schema(response_model),
            }
        try:
            response = self._client.beta.messages.create(
                model=self.model,
                max_tokens=16_000,
                system=system or anthropic.NOT_GIVEN,
                messages=turns,
                output_config=output_config,
                betas=[FALLBACK_BETA],
                fallbacks="default",
            )
        except anthropic.AuthenticationError:
            raise BuildError("Anthropic rejected the API key. Check ANTHROPIC_API_KEY.") from None
        except anthropic.RateLimitError:
            raise BuildError("Anthropic rate limit reached. Try again in a minute.") from None
        except anthropic.APIStatusError as error:
            raise BuildError(f"Anthropic returned an error ({error.status_code}).") from None
        except anthropic.APIConnectionError:
            raise BuildError("Could not reach the Anthropic API.") from None

        usage = response.usage
        self._input_tokens += (usage.input_tokens or 0) + (usage.cache_creation_input_tokens or 0)
        self._input_tokens += usage.cache_read_input_tokens or 0
        self._output_tokens += usage.output_tokens or 0

        if response.stop_reason == "refusal":
            raise BuildError("The AI model declined this request.")
        return "".join(block.text for block in response.content if block.type == "text")


def _split_messages(messages) -> tuple[str, list[dict]]:
    """CrewAI messages -> (system text, alternating user/assistant turns starting with user)."""
    if isinstance(messages, str):
        return "", [{"role": "user", "content": messages}]

    system_parts: list[str] = []
    turns: list[dict] = []
    for message in messages:
        role = message.get("role", "user")
        content = message.get("content") or ""
        if isinstance(content, list):
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        if role == "system":
            system_parts.append(content)
            continue
        role = "assistant" if role == "assistant" else "user"
        if turns and turns[-1]["role"] == role:
            turns[-1]["content"] += "\n\n" + content
        else:
            turns.append({"role": role, "content": content})
    while turns and turns[0]["role"] != "user":
        turns.pop(0)
    if not turns:
        turns = [{"role": "user", "content": "Continue."}]
    return "\n\n".join(system_parts), turns


def strict_schema(model: type[BaseModel]) -> dict:
    """A Pydantic model's JSON schema in the strict form structured outputs needs:
    references inlined, every property required, no extra properties."""
    schema = model.model_json_schema()
    definitions = schema.pop("$defs", {})

    def walk(node):
        """`node` is always a schema here, never a `properties` mapping."""
        if isinstance(node, list):
            return [walk(item) for item in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            return walk(definitions[node["$ref"].split("/")[-1]])
        out = {}
        for key, value in node.items():
            if key in ("title", "default"):
                continue  # schema metadata, not a field
            if key == "properties":
                # Field names stay as they are, even one called "title".
                out[key] = {name: walk(sub) for name, sub in value.items()}
            else:
                out[key] = walk(value)
        if out.get("type") == "object":
            out["additionalProperties"] = False
            out["required"] = list(out.get("properties", {}).keys())
        return out

    return walk(schema)


# --- The crew ------------------------------------------------------------------------

RULES = """\
Rules for every plan:
- Use only tools from the catalog, with parameters exactly as their schema allows.
- Step ids are s1, s2, s3 ... A step's "source" must be the id of an EARLIER find step.
- Start with a find step. Use filters only when the request asks for them.
- Exports: one export_excel step per file. Give files a short English file name
  that says what is inside, such as "customers" or "open-conversations".
- Anything that contacts customers or changes data must be an action tool. Never
  pretend a read tool does it. Actions are shown to a person and only happen after
  they approve, so plan them when the request clearly asks for them.
- send_message: use the wording the user gave. If they did not give exact wording,
  write a short, polite message in the language the customers are addressed in by
  the request, and say in the summary that the wording can be checked before approval.
- Keep plans minimal. At most 10 steps.
- If the catalog cannot do what was asked, return no steps and explain in
  unsupported_reason what is possible instead, in the user's language.
- Write title and summary in the language of the request (Arabic or English).
- params_json must be a JSON object written as a string, for example
  "{\\"channel\\": \\"whatsapp\\"}" or "{}"."""


def build_plan(
    request_text: str, *, api_key: str, model: str, effort: str = "medium"
) -> BuildResult:
    """Run the crew. Raises BuildError if it cannot produce a usable plan."""
    llm = ClaudeForCrew(model=model, api_key=api_key, effort=effort)
    catalog = catalog_for_prompt()

    architect = Agent(
        role="Automation architect",
        goal=(
            "Turn a business request into the smallest correct "
            "automation plan using the NEXUS tools"
        ),
        backstory=(
            "You design automations for a marketing agency's customer platform. You know its "
            "tools exactly and never invent capabilities it does not have."
        ),
        llm=llm,
        allow_delegation=False,
        verbose=False,
    )
    reviewer = Agent(
        role="Automation safety reviewer",
        goal="Make sure each plan does exactly what was asked, no more, with valid parameters",
        backstory=(
            "You review automations before they run against real customer data. You check every "
            "step against the request and the catalog, fix mistakes, and make sure anything that "
            "contacts customers or changes data is an action that waits for approval."
        ),
        llm=llm,
        allow_delegation=False,
        verbose=False,
    )

    design = Task(
        description=(
            f"The user asked (possibly by voice, so allow for small transcription errors):\n"
            f"<request>\n{request_text}\n</request>\n\n"
            f"Tool catalog:\n{catalog}\n\n{RULES}\n\n"
            "Design the plan. Leave review_notes empty."
        ),
        expected_output="An automation plan in the required structure.",
        agent=architect,
        output_pydantic=PlanDraft,
    )
    review = Task(
        description=(
            "Review the architect's plan for this request:\n"
            f"<request>\n{request_text}\n</request>\n\n"
            f"Tool catalog:\n{catalog}\n\n{RULES}\n\n"
            "Check: does it do what was asked and nothing more? Are tool names and parameters "
            "valid? Does each source point to an earlier find step? Is every customer contact "
            "or data change an action tool? Fix anything wrong and return the final plan. In "
            "review_notes, say in one or two sentences what you checked or changed."
        ),
        expected_output="The final, corrected automation plan in the required structure.",
        agent=reviewer,
        output_pydantic=PlanDraft,
        context=[design],
    )

    try:
        result = Crew(
            agents=[architect, reviewer],
            tasks=[design, review],
            process=Process.sequential,
            verbose=False,
        ).kickoff()
    except BuildError:
        raise
    except Exception as error:  # noqa: BLE001 - CrewAI raises many kinds of errors
        raise BuildError(f"The crew could not finish: {error}"[:300]) from None

    plan = result.pydantic if isinstance(result.pydantic, PlanDraft) else _parse(result.raw)
    steps = []
    for step in plan.steps:
        try:
            params = json.loads(step.params_json or "{}")
        except ValueError:
            raise BuildError(f"Step {step.id} has parameters that are not valid JSON.") from None
        if not isinstance(params, dict):
            raise BuildError(f"Step {step.id} parameters must be a JSON object.")
        steps.append({"id": step.id, "tool": step.tool, "params": params})

    input_tokens, output_tokens = llm.usage
    return BuildResult(
        plan=plan, steps=steps, input_tokens=input_tokens, output_tokens=output_tokens
    )


def _parse(raw: str) -> PlanDraft:
    try:
        return PlanDraft.model_validate_json(raw)
    except Exception:  # noqa: BLE001
        raise BuildError("The crew's answer was not a valid plan.") from None
