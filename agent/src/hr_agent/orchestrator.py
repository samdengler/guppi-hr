"""The orchestrator (phase 4): route each turn, then delegate, clarify, or answer.

One run:

1. The page sends the thread and the state from the previous run (`activeDomain`,
   `pendingAction`, D6).
2. The router, a single structured-output call to Sonnet (D8), names a domain, a
   confidence band, the alternatives, and whether the message is a follow-up.
3. `decide` applies the routing policy in code (docs/plan.md, "Routing policy, first
   cut"): a follow-up or a reply to a pending change stays in the active domain; high
   confidence delegates; medium delegates only within the active domain; otherwise one
   clarifying question ends the run.
4. A delegation is one A2A `message/send` through the agents gateway with the user's
   token, recent turns, and the pending change, between STEP_STARTED and STEP_FINISHED;
   the sub-agent's reply is the turn's text. A general question goes to the knowledge
   base agent in agent.py.
5. STATE_SNAPSHOT carries the active domain and the pending change back to the page, and
   the run log line gains domain, confidence, alternatives, delegated_to, and confirmed.
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from ag_ui.core import (
    BaseEvent,
    EventType,
    RunAgentInput,
    RunFinishedEvent,
    RunStartedEvent,
    StateSnapshotEvent,
    StepFinishedEvent,
    StepStartedEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
)

from hr_agent.agents.domains import DOMAINS
from hr_agent.obo import ExchangeError, TokenExchanger
from hr_agent.pending import PENDING_KEY, parse_pending

log = logging.getLogger("hr_agent")
# The employee's Okta token traded, through the bridge's client, for an agents token that
# only the one sub-agent accepts (D47; critique of the build, finding 3).
AGENTS_TOKENS = {domain: TokenExchanger(scopes=[f"hr.agents.{domain}"]) for domain in DOMAINS}
SIGNIN_LINE = "HR could not confirm the sign-in. Try again in a minute."

ACTIVE_KEY = "activeDomain"
GENERAL = "general"
CONFIDENCE = ("high", "medium", "low")
DEFAULT_ROUTER_MODEL_ID = "us.anthropic.claude-sonnet-4-6"
ROUTER_TURNS = 6  # recent turns the router reads
SUB_AGENT_TURNS = 10  # recent turns a sub-agent receives
A2A_TIMEOUT_SECONDS = 120

GENERAL_DESCRIPTION = (
    "Anything outside the three areas: greetings, questions about this assistant, time off "
    "and sick time, benefits enrollment, how to contact HR, and requests to talk to a person "
    "when no area is active."
)

CLARIFY_LABELS = {
    "profile": "your personal details, such as your home address or emergency contact",
    "pay": "your pay, such as your direct deposit account or pay statements",
    "travel": "your travel benefits, such as pass travel or buddy passes",
}

ROUTER_SYSTEM = """You route one message in a conversation with an HR assistant to the
area that should handle it. Call the route tool exactly once.

Areas:
{areas}
- general: {general}

Rules:
- follow_up is true when the message only makes sense as a continuation of the previous
  turn: a confirmation or refusal ("yes", "no, use my savings account"), a pronoun or an
  ellipsis ("what about my emergency contact?", "and the next one?"), or a request to talk
  to a person about what was just discussed.
- confidence is high when one area clearly fits, medium when one area fits better than
  the others but another is plausible, low when two or more areas fit about equally or the
  message is too vague to tell.
- alternatives lists the other areas that could plausibly fit, most likely first.
- clarifying_question is one short question that would settle a low-confidence case,
  naming the candidate areas in plain words.
"""

ROUTE_TOOL = {
    "toolSpec": {
        "name": "route",
        "description": "Record where the latest message should go.",
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "domain": {"type": "string", "enum": [*DOMAINS, GENERAL]},
                    "confidence": {"type": "string", "enum": list(CONFIDENCE)},
                    "alternatives": {
                        "type": "array",
                        "items": {"type": "string", "enum": [*DOMAINS, GENERAL]},
                    },
                    "follow_up": {"type": "boolean"},
                    "clarifying_question": {"type": "string"},
                },
                "required": ["domain", "confidence", "alternatives", "follow_up"],
            }
        },
    }
}


@dataclass
class Settings:
    agents_gateway_url: str = field(
        default_factory=lambda: os.environ.get("AGENTS_GATEWAY_URL", "").rstrip("/")
    )
    router_model_id: str = field(
        default_factory=lambda: os.environ.get("ROUTER_MODEL_ID", DEFAULT_ROUTER_MODEL_ID)
    )
    region: str = field(default_factory=lambda: os.environ.get("AWS_REGION", "us-east-1"))


@dataclass
class Route:
    domain: str
    confidence: str
    alternatives: list[str]
    follow_up: bool
    clarifying_question: str = ""

    @classmethod
    def parse(cls, data: dict[str, Any]) -> Route:
        known = {*DOMAINS, GENERAL}
        domain = data.get("domain") if data.get("domain") in known else GENERAL
        confidence = data.get("confidence") if data.get("confidence") in CONFIDENCE else "low"
        alternatives = [
            a for a in data.get("alternatives") or [] if a in known and a != domain
        ]
        return cls(
            domain=domain,
            confidence=confidence,
            alternatives=list(dict.fromkeys(alternatives)),
            follow_up=bool(data.get("follow_up")),
            clarifying_question=str(data.get("clarifying_question") or "").strip(),
        )


@dataclass
class Decision:
    action: str  # delegate, clarify, answer
    domain: str | None = None


def decide(route: Route, active: str | None, pending_domain: str | None) -> Decision:
    """The routing policy, first cut (docs/plan.md). Pure, so every rule is tested."""
    # A reply to a pending change, or a follow-up of any kind, never re-routes.
    if pending_domain and (route.follow_up or route.domain == pending_domain):
        return Decision("delegate", pending_domain)
    if route.follow_up and active in DOMAINS:
        return Decision("delegate", active)
    if route.domain == GENERAL:
        # A vague message the router cannot place, but that names real areas as
        # alternatives ("I need to update my information"), gets the question, not a guess.
        if route.confidence == "low" and any(a in DOMAINS for a in route.alternatives):
            return Decision("clarify")
        return Decision("answer")
    if route.confidence == "high":
        return Decision("delegate", route.domain)
    # Medium delegates within the active domain, or when no other area is a candidate:
    # a clarifying question needs two areas to choose between (D28, after the first
    # evals/route.py run).
    competing = [a for a in route.alternatives if a in DOMAINS]
    if route.confidence == "medium" and (route.domain == active or not competing):
        return Decision("delegate", route.domain)
    return Decision("clarify")


def clarifying_question(route: Route) -> str:
    candidates = [d for d in [route.domain, *route.alternatives] if d in CLARIFY_LABELS]
    if len(candidates) >= 2:
        first, second = candidates[:2]
        return (
            f"I can help with that. Is this about {CLARIFY_LABELS[first]}, or about "
            f"{CLARIFY_LABELS[second]}?"
        )
    if route.clarifying_question:
        return route.clarifying_question
    return (
        "I can help with your personal details, your pay, or your travel benefits. Which "
        "one is this about?"
    )


def turns_of(run_input: RunAgentInput) -> list[dict[str, str]]:
    turns = []
    for message in run_input.messages:
        if message.role in ("user", "assistant") and isinstance(message.content, str):
            turns.append({"role": message.role, "content": message.content})
    return turns


def transcript(turns: list[dict[str, str]]) -> str:
    return "\n".join(f"{t['role']}: {t['content']}" for t in turns)


async def route_turn(
    turns: list[dict[str, str]],
    active: str | None,
    pending: dict[str, str] | None,
    settings: Settings,
) -> Route:
    """One Converse call that must call the route tool. Tests replace this."""
    import boto3

    areas = "\n".join(f"- {name}: {domain.description}" for name, domain in DOMAINS.items())
    context = [f"Active area: {active or 'none'}."]
    if pending:
        context.append(
            f"A change is waiting for the employee's confirmation in the {pending['domain']} "
            f"area: {pending['field']} to \"{pending['to']}\"."
        )
    recent = turns[-ROUTER_TURNS:]
    prompt = (
        " ".join(context)
        + "\n\nConversation so far:\n"
        + transcript(recent[:-1] or [{"role": "none", "content": "(this is the first message)"}])
        + f"\n\nLatest message from the employee:\n{recent[-1]['content']}"
    )
    client = boto3.client("bedrock-runtime", region_name=settings.region)
    response = await asyncio.to_thread(
        client.converse,
        modelId=settings.router_model_id,
        system=[
            {
                "text": ROUTER_SYSTEM.format(areas=areas, general=GENERAL_DESCRIPTION),
            }
        ],
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        toolConfig={"tools": [ROUTE_TOOL], "toolChoice": {"tool": {"name": "route"}}},
        inferenceConfig={"maxTokens": 300, "temperature": 0},
    )
    for block in response["output"]["message"]["content"]:
        if "toolUse" in block:
            return Route.parse(block["toolUse"]["input"])
    return Route.parse({})


@dataclass
class SubAgentReply:
    text: str
    pending: dict[str, Any] | None = None
    committed: bool = False
    error: bool = False
    signin: bool = False  # the exchange failed, so nothing reached the sub-agent


async def send_to_sub_agent(
    domain: str,
    token: str,
    thread_id: str,
    text: str,
    history: list[dict[str, str]],
    pending: dict[str, str] | None,
    settings: Settings,
) -> SubAgentReply:
    """One A2A message/send through the agents gateway. Tests replace this."""
    import httpx

    # The agents gateway and the sub-agent accept only that sub-agent's agents token (D47).
    try:
        token = await AGENTS_TOKENS[domain].aexchange(token)
    except ExchangeError:
        return SubAgentReply(text="", error=True, signin=True)

    body = {
        "jsonrpc": "2.0",
        "id": uuid.uuid4().hex,
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "parts": [{"kind": "text", "text": text}],
                "messageId": uuid.uuid4().hex,
                "contextId": thread_id,
                "metadata": {"history": history, PENDING_KEY: pending},
            }
        },
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        # A runtime session id must be at least 33 characters; one per thread and domain.
        "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": f"{thread_id}-{domain}".ljust(33, "0"),
    }
    url = f"{settings.agents_gateway_url}/{domain}/invocations"
    async with httpx.AsyncClient(timeout=A2A_TIMEOUT_SECONDS) as client:
        response = await client.post(url, json=body, headers=headers)
    if response.status_code != 200:
        log.warning("sub-agent %s answered HTTP %s", domain, response.status_code)
        return SubAgentReply(text="", error=True)
    payload = response.json()
    result = payload.get("result")
    if not isinstance(result, dict):
        log.warning("sub-agent %s answered without a result: %s", domain, payload.get("error"))
        return SubAgentReply(text="", error=True)
    texts = [p.get("text", "") for p in result.get("parts", []) if p.get("kind") == "text"]
    data = next((p.get("data") for p in result.get("parts", []) if p.get("kind") == "data"), {})
    data = data if isinstance(data, dict) else {}
    return SubAgentReply(
        text="\n\n".join(t for t in texts if t).strip(),
        pending=data.get(PENDING_KEY) if isinstance(data.get(PENDING_KEY), dict) else None,
        committed=data.get("committed") is True,
        error="error" in data,
    )


Router = Callable[..., Awaitable[Route]]
Sender = Callable[..., Awaitable[SubAgentReply]]


class Orchestrator:
    """The runner app.py drives: run() yields AG-UI events, usage() adds log fields."""

    def __init__(
        self,
        token: str,
        settings: Settings | None = None,
        router: Router = route_turn,
        sender: Sender = send_to_sub_agent,
        general_factory: Callable[[str], Any] | None = None,
    ) -> None:
        self._token = token
        self._settings = settings or Settings()
        self._router = router
        self._sender = sender
        self._general_factory = general_factory
        self._general: Any = None
        self._record: dict[str, Any] = {}

    def usage(self) -> dict[str, Any]:
        fields = dict(self._record)
        if self._general is not None:
            fields.update(self._general.usage())
        return fields

    async def run(self, run_input: RunAgentInput) -> AsyncIterator[BaseEvent]:
        state = dict(run_input.state) if isinstance(run_input.state, dict) else {}
        active = state.get(ACTIVE_KEY) if state.get(ACTIVE_KEY) in DOMAINS else None
        raw_pending = state.get(PENDING_KEY) if isinstance(state.get(PENDING_KEY), dict) else {}
        pending = parse_pending(raw_pending)
        pending_domain = raw_pending.get("domain") if raw_pending.get("domain") in DOMAINS else None
        if pending and pending_domain:
            pending = {**pending, "domain": pending_domain}
        else:
            pending, pending_domain = None, None

        turns = turns_of(run_input)
        route = await self._router(turns, active, pending, self._settings)
        decision = decide(route, active, pending_domain)
        self._record.update(
            domain=route.domain,
            confidence=route.confidence,
            alternatives=route.alternatives,
            follow_up=route.follow_up,
            action=decision.action,
            delegated_to=decision.domain,
            confirmed=False,
        )

        if decision.action == "answer":
            self._general = self._general_factory(self._token)
            async for event in self._general.run(run_input):
                yield event
            return

        yield RunStartedEvent(
            type=EventType.RUN_STARTED, thread_id=run_input.thread_id, run_id=run_input.run_id
        )
        next_state = {**state, PENDING_KEY: None}
        if decision.action == "clarify":
            text = clarifying_question(route)
        else:
            domain = decision.domain
            yield StepStartedEvent(type=EventType.STEP_STARTED, step_name=domain)
            reply = await self._sender(
                domain,
                self._token,
                run_input.thread_id,
                turns[-1]["content"] if turns else "",
                turns[:-1][-SUB_AGENT_TURNS:],
                pending if pending_domain == domain else None,
                self._settings,
            )
            yield StepFinishedEvent(type=EventType.STEP_FINISHED, step_name=domain)
            if reply.signin:
                text = SIGNIN_LINE
                self._record["exchange_failed"] = True
            elif reply.error or not reply.text:
                title = DOMAINS[domain].title
                text = (
                    f"I could not reach the {title} just now. Please try again in a moment, "
                    "or ask me to open a ticket for the HR team."
                )
                self._record["sub_agent_error"] = True
            else:
                text = reply.text
                next_state[ACTIVE_KEY] = domain
                if reply.pending:
                    next_state[PENDING_KEY] = {**reply.pending, "domain": domain}
                self._record["confirmed"] = reply.committed
        message_id = uuid.uuid4().hex
        yield TextMessageStartEvent(
            type=EventType.TEXT_MESSAGE_START, message_id=message_id, role="assistant"
        )
        yield TextMessageContentEvent(
            type=EventType.TEXT_MESSAGE_CONTENT, message_id=message_id, delta=text
        )
        yield TextMessageEndEvent(type=EventType.TEXT_MESSAGE_END, message_id=message_id)
        yield StateSnapshotEvent(type=EventType.STATE_SNAPSHOT, snapshot=next_state)
        yield RunFinishedEvent(
            type=EventType.RUN_FINISHED, thread_id=run_input.thread_id, run_id=run_input.run_id
        )
