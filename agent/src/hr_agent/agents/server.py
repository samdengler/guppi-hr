"""A sub-agent as an A2A server on the AgentCore Runtime A2A contract (port 9000, JSON-RPC at
the root, agent card at /.well-known/agent-card.json, D2).

Each request builds its own Strands agent: the MCP client to the tools gateway carries the
caller's token (from the A2A request's Authorization header, which the runtime validated)
and the conversation's thread id (the A2A contextId), so no tool call can act for anyone
but the caller or bind a proposal to another conversation. The orchestrator sends recent
turns and any pending change in the message metadata; the reply is a text part plus a
data part with the pending change this run left, which the orchestrator carries in AG-UI
state (D23).
"""

from __future__ import annotations

import asyncio
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
from hr_agent.pending import (
    PENDING_KEY,
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
Reply in concise plain text for the employee. The page renders no Markdown, so write no
headings, bullet markers, bold, code fences, or links; use short paragraphs and plain
sentences. If the request is outside your area, say in one sentence what you can help with
and do not guess.
"""

WRITE_RULE = """
Your tools act on this employee's own records. A change always takes two turns: first call
the matching propose tool, then tell the employee the exact change it returned and ask
them to confirm. Call commit_change with that proposal_id only when their next message
clearly says yes; if they decline or change the details, do not commit. Never say a change
is done unless commit_change succeeded. When the employee asks for a person, or you cannot
help, open a ticket and give them its id.
"""

TICKET_RULE = """
When the employee asks for a person or needs a change you cannot make, open a ticket and
give them its id.
"""


def system_prompt(domain: Domain, pending: dict[str, str] | None = None) -> str:
    writes = any(name.startswith("propose_") for name in domain.hr_tools)
    prompt = PROMPT_TEMPLATE.format(
        title=domain.title,
        scope=domain.scope,
        write_rule=WRITE_RULE if writes else TICKET_RULE,
    )
    return prompt + (pending_paragraph(pending) if writes else "")


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
    from strands.tools.mcp import MCPClient

    settings = settings or Settings()
    if not settings.tools_gateway_url:
        raise RuntimeError("TOOLS_GATEWAY_URL is not set")
    client = MCPClient(
        url=settings.tools_gateway_url,
        headers={
            "Authorization": f"Bearer {token}",
            "X-Hr-User-Token": token,
            "X-Hr-Thread-Id": thread_id,
        },
    )
    await asyncio.to_thread(client.start)
    try:
        listed = await asyncio.to_thread(client.list_tools_sync)
        allowed = domain.tool_names(settings.hr_tool_prefix)
        tools = [tool for tool in listed if tool.tool_name in allowed]
        missing = allowed - {tool.tool_name for tool in tools}
        if missing:
            log.warning("%s: tools not offered by the gateway: %s", domain.name, sorted(missing))
        agent = Agent(
            model=BedrockModel(
                model_id=settings.model_id,
                region_name=settings.region,
                max_tokens=1024,
                temperature=0.3,
            ),
            system_prompt=system_prompt(domain, pending),
            tools=tools,
            messages=[dict(message) for message in history],
            callback_handler=None,
        )
        before = len(agent.messages)
        result = await agent.invoke_async(text)
        added = agent.messages[before:]
        tool_calls = sum(
            1 for message in added for block in message.get("content", []) if "toolUse" in block
        )
        return DomainResult(
            reply=str(result).strip(),
            pending=pending_after_messages(added, settings.hr_tool_prefix),
            tool_calls=tool_calls,
        )
    finally:
        await asyncio.to_thread(client.stop, None, None, None)


Runner = Callable[..., Awaitable[DomainResult]]


class DomainExecutor(AgentExecutor):
    def __init__(self, domain: Domain, runner: Runner = run_domain) -> None:
        self.domain = domain
        self._run = runner

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        started = time.monotonic()
        state = context.call_context.state if context.call_context else {}
        headers = state.get("headers") or {}
        metadata = (context.message.metadata if context.message else None) or {}
        record: dict[str, Any] = {"domain": self.domain.name, "context": context.context_id}
        token = bearer_token(headers)
        try:
            if token is None:
                raise PermissionError("no bearer token on the request")
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
                Part(root=DataPart(data={"domain": self.domain.name, PENDING_KEY: result.pending})),
            ]
        except Exception:
            log.exception("%s run failed", self.domain.name)
            record["outcome"] = "error"
            failed = f"The {self.domain.title} could not complete the request."
            parts = [
                Part(root=TextPart(text=failed)),
                Part(root=DataPart(data={"domain": self.domain.name, "error": "agent_failed"})),
            ]
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


def build_app(domain_name: str, runner: Runner = run_domain):
    """The Starlette app: JSON-RPC at /, the card, /ping, and the AgentCore header glue."""
    from bedrock_agentcore.runtime.a2a import build_a2a_app

    domain = DOMAINS[domain_name]
    return build_a2a_app(DomainExecutor(domain, runner), agent_card(domain))


def serve(domain_name: str) -> None:
    import uvicorn

    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    uvicorn.run(build_app(domain_name), host="0.0.0.0", port=9000)


