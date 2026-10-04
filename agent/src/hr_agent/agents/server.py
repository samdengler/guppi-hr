"""A sub-agent as an A2A server on the AgentCore Runtime A2A contract (port 9000, JSON-RPC at
the root, agent card at /.well-known/agent-card.json, D2).

Each request builds its own Strands agent. Its MCP session to the tools gateway carries the
caller's token (from the A2A request's Authorization header, which the runtime validated)
and the conversation's thread id (the A2A contextId), so no tool call can act for anyone
but the caller or bind a proposal to another conversation; the session is kept open for
that caller and thread between requests (mcp_sessions.py, D38). The orchestrator sends recent
turns and any pending change in the message metadata; the reply is a text part plus a
data part with the pending change this run left, which the orchestrator carries in AG-UI
state (D23).
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
    DataPart,
    Message,
    Part,
    Role,
    TextPart,
)

from hr_agent.agents.domains import DOMAINS, Domain
from hr_agent.agents.mcp_sessions import McpSessions
from hr_agent.obo import TokenExchanger
from hr_agent.agents.snapshot import (
    RECORD_READS,
    WARM_SEARCHES,
    Snapshots,
    prompt_paragraph,
    read_record,
    search_policy,
)
from hr_agent.pending import (
    PENDING_KEY,
    committed_in_messages,
    parse_pending,
    pending_after_messages,
    pending_paragraph,
)

log = logging.getLogger("hr_agent.agents")

DEFAULT_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
HISTORY_TURNS = 10  # the most recent turns a sub-agent sees, both roles counted
HISTORY_TEXT_LIMIT = 4000

PROMPT_TEMPLATE = """You are the {title} inside the HR Assistant, helping one signed-in
employee with {scope}

The HR Assistant sent this message to you because it concerns your area. Earlier turns of
the conversation, when there are any, come before it.

You have a search over the HR policy documents. When a question concerns policy, search
first and answer once from what the search returns, saying so when the passages do not
settle it.
{write_rule}
Reply in at most two short sentences of plain text for the employee, unless you are
listing a change for them to confirm. The page renders no Markdown, so write no
headings, bullet markers, bold, code fences, or links; use short paragraphs and plain
sentences. If the request is outside your area, say in one sentence what you can help with
and do not guess.
"""

WRITE_RULE = """
Your tools act on this employee's own records. When the employee asks about one of their
details ("what about my emergency contact?"), look it up (in the record sent with the message,
when there is one) and say what is on file before anything else; ask for new values only if they
want to change it. A change always takes
two turns: first call
the matching propose tool, then tell the employee the exact change it returned and ask
them to confirm. Call commit_change with that proposal_id only when their next message
clearly says yes; if they decline or change the details, do not commit. Never say a change
is done unless commit_change succeeded.

When the employee asks to talk to a person, open a ticket right away with a one-line
summary of the conversation so far, and give them its id; do not ask what it is about
first. Do the same when you cannot help.
"""

TICKET_RULE = """
When the employee asks to talk to a person, or needs a change you cannot make, open a
ticket right away with a one-line summary of the conversation so far, and give them its
id; do not ask what it is about first.
"""


def system_prompt(domain: Domain, pending: dict[str, str] | None = None) -> str:
    """The domain's fixed instructions. Nothing about the employee goes here: Strands copies
    the system prompt into the `system_prompt` span attribute, which its redaction does not
    cover (aws-feedback A8), so the record, passages and a pending change travel with the
    message instead (turn_context). `pending` is accepted for callers that still pass it."""
    writes = any(name.startswith("propose_") for name in domain.hr_tools)
    return PROMPT_TEMPLATE.format(
        title=domain.title,
        scope=domain.scope,
        write_rule=WRITE_RULE if writes else TICKET_RULE,
    )


def turn_context(
    domain: Domain, pending: dict[str, str] | None, record: str | None, passages: str | None
) -> str:
    """What the model needs about this employee for this turn, sent as a content block
    before the employee's message, where the trace keeps it redacted."""
    writes = any(name.startswith("propose_") for name in domain.hr_tools)
    return ((pending_paragraph(pending) if writes else "") + prompt_paragraph(record, passages)).strip()


@dataclass
class Settings:
    tools_gateway_url: str = field(default_factory=lambda: os.environ.get("TOOLS_GATEWAY_URL", ""))
    model_id: str = field(default_factory=lambda: os.environ.get("MODEL_ID", DEFAULT_MODEL_ID))
    hr_tool_prefix: str = field(default_factory=lambda: os.environ.get("HR_TOOL_PREFIX", "hr___"))
    region: str = field(default_factory=lambda: os.environ.get("AWS_REGION", "us-east-1"))


@dataclass
class DomainResult:
    reply: str
    pending: dict[str, Any] | None
    tool_calls: int = 0
    committed: bool = False


def history_messages(history: object) -> list[dict]:
    """Recent turns as Strands messages: user first, roles alternating, ending on the
    assistant so the new message follows. Anything malformed is dropped."""
    turns: list[dict] = []
    for turn in history if isinstance(history, list) else []:
        if not isinstance(turn, dict) or turn.get("role") not in ("user", "assistant"):
            continue
        text = str(turn.get("content", ""))[:HISTORY_TEXT_LIMIT]
        if not text.strip():
            continue
        if turns and turns[-1]["role"] == turn["role"]:
            turns[-1]["content"][0]["text"] += "\n\n" + text
        else:
            turns.append({"role": turn["role"], "content": [{"text": text}]})
    turns = turns[-HISTORY_TURNS:]
    while turns and turns[0]["role"] != "user":
        turns.pop(0)
    while turns and turns[-1]["role"] != "assistant":
        turns.pop()
    return turns


def token_expires_at(token: str) -> float:
    """The token's `exp`, unverified (the runtime's authorizer verified it), or an hour
    from now when it cannot be read."""
    try:
        payload = token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        return float(claims["exp"])
    except Exception:  # noqa: BLE001
        return time.time() + 3600


def _open_session(key: tuple[str, str], settings: Settings | None = None):
    """A started MCP client to the tools gateway for (token, thread id), and its tools."""
    from strands.tools.mcp import MCPClient

    settings = settings or Settings()
    if not settings.tools_gateway_url:
        raise RuntimeError("TOOLS_GATEWAY_URL is not set")
    token, thread_id = key
    # The tools token alone (D47): the gateway's authorizer and Policy read it, and the
    # gateway exchanges it again for the tools runtime, so no second copy rides along.
    client = MCPClient(
        url=settings.tools_gateway_url,
        headers={"Authorization": f"Bearer {token}", "X-Hr-Thread-Id": thread_id},
    )
    client.start()
    try:
        return client, client.list_tools_sync()
    except BaseException:
        client.stop(None, None, None)
        raise


SESSIONS = McpSessions(_open_session)
SNAPSHOTS = Snapshots()
# This sub-agent's credential provider trades the agents token it receives for its own
# domain's tools token (D47); the stack sets OBO_PROVIDER, OBO_WORKLOAD and OBO_SCOPES.
TOOLS_TOKENS = TokenExchanger(scopes=os.environ.get("OBO_SCOPES", "").split())


def bearer_token(headers: dict[str, str]) -> str | None:
    lowered = {key.lower(): value for key, value in headers.items()}
    scheme, _, token = lowered.get("authorization", "").partition(" ")
    return token.strip() if scheme.lower() == "bearer" and token.strip() else None


async def run_domain(
    domain: Domain,
    token: str,
    thread_id: str,
    history: list[dict],
    text: str,
    pending: dict[str, str] | None,
    settings: Settings | None = None,
) -> DomainResult:
    """One sub-agent run against Bedrock and the tools gateway. Tests replace this."""
    from strands import Agent
    from strands.models import BedrockModel

    settings = settings or Settings()
    tools_token = await TOOLS_TOKENS.aexchange(token)
    async with SESSIONS.lease((tools_token, thread_id), token_expires_at=token_expires_at(tools_token)) as (
        client,
        listed,
    ):
        # What is on file, or for travel the policy passages for the question, read before
        # the model so a read is one model call (snapshot.py; latency log L15, L16).
        key = (token, thread_id, domain.name)
        record = SNAPSHOTS.get(key)
        if record is None and domain.name in RECORD_READS:
            record = await asyncio.to_thread(read_record, client, domain.name, settings.hr_tool_prefix)
            if record:
                SNAPSHOTS.put(key, record)
        passages = None
        if domain.name not in RECORD_READS:
            passages = SNAPSHOTS.get(key) or await asyncio.to_thread(search_policy, client, text)
        allowed = domain.tool_names(settings.hr_tool_prefix)
        tools = [tool for tool in listed if tool.tool_name in allowed]
        missing = allowed - {tool.tool_name for tool in tools}
        if missing:
            log.warning("%s: tools not offered by the gateway: %s", domain.name, sorted(missing))
        agent = Agent(
            model=BedrockModel(
                model_id=settings.model_id,
                region_name=settings.region,
                # Short answers come back sooner (L21); a proposal still fits.
                max_tokens=400,
                temperature=0.3,
            ),
            system_prompt=system_prompt(domain),
            tools=tools,
            messages=[dict(message) for message in history],
            callback_handler=None,
        )
        before = len(agent.messages)
        context = turn_context(domain, pending, record, passages)
        message = [{"text": context}, {"text": text}] if context else text
        result = await agent.invoke_async(message)
        added = agent.messages[before:]
        tool_calls = sum(
            1 for message in added for block in message.get("content", []) if "toolUse" in block
        )
        committed = committed_in_messages(added, settings.hr_tool_prefix)
        if committed:
            SNAPSHOTS.drop(key)
        return DomainResult(
            reply=str(result).strip(),
            pending=pending_after_messages(added, settings.hr_tool_prefix),
            tool_calls=tool_calls,
            committed=committed,
        )


async def warm_domain(token: str, thread_id: str, domain: str = "", settings: Settings | None = None) -> None:
    """A warm start (D41): open this caller's MCP session for the thread and list its tools,
    and read what is on file for the domain, so the thread's first real request finds all
    of it ready. No model call."""
    settings = settings or Settings()
    tools_token = await TOOLS_TOKENS.aexchange(token)
    async with SESSIONS.lease((tools_token, thread_id), token_expires_at=token_expires_at(tools_token)) as (
        client,
        _tools,
    ):
        key = (token, thread_id, domain)
        if SNAPSHOTS.get(key) is not None:
            return
        if domain in RECORD_READS:
            found = await asyncio.to_thread(read_record, client, domain, settings.hr_tool_prefix)
        elif domain in WARM_SEARCHES:
            found = await asyncio.to_thread(search_policy, client, WARM_SEARCHES[domain])
        else:
            found = None
        if found:
            SNAPSHOTS.put(key, found)


def mark_span(record: dict[str, Any], domain: str, thread_id: str) -> None:
    """Puts the thread (the Connect contact id behind the canvas) and the domain on the
    request's span, and the trace id in the run record, so this trace and the bridge's,
    which the canvas splits (aws-feedback TC1), join on `hr.thread_id` (critique finding 14)."""
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        span.set_attribute("hr.thread_id", thread_id)
        span.set_attribute("hr.domain", domain)
        span_context = span.get_span_context()
        if span_context.is_valid:
            record["trace_id"] = f"{span_context.trace_id:032x}"
    except Exception:  # noqa: BLE001 - tracing never fails a request
        pass


Runner = Callable[..., Awaitable[DomainResult]]
Warmer = Callable[[str, str, str], Awaitable[None]]


class DomainExecutor(AgentExecutor):
    def __init__(self, domain: Domain, runner: Runner = run_domain, warmer: Warmer = warm_domain) -> None:
        self.domain = domain
        self._run = runner
        self._warm = warmer

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        started = time.monotonic()
        state = context.call_context.state if context.call_context else {}
        headers = state.get("headers") or {}
        metadata = (context.message.metadata if context.message else None) or {}
        record: dict[str, Any] = {"domain": self.domain.name, "context": context.context_id}
        mark_span(record, self.domain.name, context.context_id or "")
        token = bearer_token(headers)
        try:
            if token is None:
                raise PermissionError("no bearer token on the request")
            if metadata.get("warm") is True:
                # The Connect bridge's warm start: the runtime session for this thread
                # exists from now on, and so does the caller's MCP session.
                await self._warm(token, context.context_id or "", self.domain.name)
                record.update(outcome="warm", tool_calls=0)
                warmed = [Part(root=DataPart(data={"domain": self.domain.name, "warm": True}))]
                await self._reply(context, event_queue, warmed, record, started)
                return
            result = await self._run(
                self.domain,
                token,
                context.context_id or "",
                history_messages(metadata.get("history")),
                context.get_user_input(),
                parse_pending(metadata.get(PENDING_KEY)),
            )
            record.update(outcome="finished", tool_calls=result.tool_calls)
            parts = [
                Part(root=TextPart(text=result.reply)),
                Part(
                    root=DataPart(
                        data={
                            "domain": self.domain.name,
                            PENDING_KEY: result.pending,
                            "committed": result.committed,
                        }
                    )
                ),
            ]
        except Exception:
            log.exception("%s run failed", self.domain.name)
            record["outcome"] = "error"
            failed = f"The {self.domain.title} could not complete the request."
            parts = [
                Part(root=TextPart(text=failed)),
                Part(root=DataPart(data={"domain": self.domain.name, "error": "agent_failed"})),
            ]
        await self._reply(context, event_queue, parts, record, started)

    async def _reply(self, context, event_queue, parts, record, started) -> None:
        record["duration_ms"] = int((time.monotonic() - started) * 1000)
        log.info(json.dumps(record, sort_keys=True))
        await event_queue.enqueue_event(
            Message(
                role=Role.agent,
                messageId=uuid.uuid4().hex,
                contextId=context.context_id,
                taskId=context.task_id,
                parts=parts,
            )
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError("sub-agent runs are short and not cancellable")


def agent_card(domain: Domain, url: str = "http://localhost:9000/") -> AgentCard:
    return AgentCard(
        name=domain.title,
        description=domain.description,
        url=url,
        version="0.1.0",
        capabilities=AgentCapabilities(streaming=False),
        defaultInputModes=["text"],
        defaultOutputModes=["text"],
        skills=[
            AgentSkill(
                id=skill.id,
                name=skill.name,
                description=skill.description,
                tags=[domain.name],
                examples=list(skill.examples),
            )
            for skill in domain.skills
        ],
    )


def build_app(domain_name: str, runner: Runner = run_domain, warmer: Warmer = warm_domain):
    """The Starlette app: JSON-RPC at /, the card, /ping, and the AgentCore header glue."""
    from bedrock_agentcore.runtime.a2a import build_a2a_app

    domain = DOMAINS[domain_name]
    return build_a2a_app(DomainExecutor(domain, runner, warmer), agent_card(domain))


def serve(domain_name: str) -> None:
    import uvicorn

    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    uvicorn.run(build_app(domain_name), host="0.0.0.0", port=9000)


