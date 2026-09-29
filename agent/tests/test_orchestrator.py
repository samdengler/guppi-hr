"""The orchestrator: routing policy, events, state, and the four scenarios of docs/plan.md
against a scripted router and fake sub-agents (nothing reaches Bedrock or a gateway)."""

from __future__ import annotations

import pytest
from ag_ui.core import AssistantMessage, EventType, RunAgentInput, UserMessage
from hr_agent.orchestrator import (
    Decision,
    Orchestrator,
    Route,
    Settings,
    SubAgentReply,
    clarifying_question,
    decide,
)

PROPOSAL_ID = "5fa4fa460a624723902ee08c116caf0e"
PROPOSAL = {
    "proposalId": PROPOSAL_ID,
    "field": "home_address",
    "from": "88 Lake Shore Dr, Chicago, IL 60611",
    "to": "419 Glendale Ave, Decatur, GA 30030",
    "expiresAt": "2026-09-29T03:00:00+00:00",
}


def route(domain, confidence="high", alternatives=(), follow_up=False):
    return Route(domain, confidence, list(alternatives), follow_up)


# ---- policy ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("r", "active", "pending", "expected"),
    [
        (route("pay"), None, None, Decision("delegate", "pay")),
        (route("pay", "medium"), None, None, Decision("clarify")),
        (route("pay", "medium"), "pay", None, Decision("delegate", "pay")),
        (route("pay", "low"), "pay", None, Decision("clarify")),
        (route("general"), "pay", None, Decision("answer")),
        (route("general", "low", alternatives=["profile", "pay"]), None, None, Decision("clarify")),
        (route("general", "low"), None, None, Decision("answer")),
        # a follow-up never re-routes, whatever the router guessed
        (route("pay", "high", follow_up=True), "profile", None, Decision("delegate", "profile")),
        # a reply to a pending change goes back to the domain that proposed it
        (route("general", "low", follow_up=True), None, "profile", Decision("delegate", "profile")),
        (route("profile", "medium"), "profile", "profile", Decision("delegate", "profile")),
        # a clear topic shift re-routes even with a change pending
        (route("travel"), "profile", "profile", Decision("delegate", "travel")),
        # a follow-up with no active domain has nowhere to stick
        (route("pay", "low", follow_up=True), None, None, Decision("clarify")),
    ],
)
def test_routing_policy(r, active, pending, expected):
    assert decide(r, active, pending) == expected


def test_the_clarifying_question_names_the_two_candidates():
    question = clarifying_question(route("profile", "low", alternatives=["pay"]))
    assert "home address" in question and "direct deposit" in question


def test_route_parsing_is_defensive():
    parsed = Route.parse({"domain": "salary", "confidence": "sure", "alternatives": ["pay", "x"]})
    assert (parsed.domain, parsed.confidence, parsed.alternatives) == ("general", "low", ["pay"])


# ---- runs ------------------------------------------------------------------------------


class Script:
    """Plays the router and the sub-agents from a fixed list of turns."""

    def __init__(self, routes, replies):
        self.routes = list(routes)
        self.replies = list(replies)
        self.sent = []

    async def router(self, turns, active, pending, settings):
        return self.routes.pop(0)

    async def sender(self, domain, token, thread_id, text, history, pending, settings):
        self.sent.append(
            {"domain": domain, "token": token, "thread": thread_id, "text": text,
             "history": history, "pending": pending}
        )
        return self.replies.pop(0)


class GeneralRun:
    def __init__(self, token):
        self.token = token

    async def run(self, run_input):
        from ag_ui.core import RunFinishedEvent, RunStartedEvent

        yield RunStartedEvent(type=EventType.RUN_STARTED, thread_id="t", run_id="r")
        yield RunFinishedEvent(type=EventType.RUN_FINISHED, thread_id="t", run_id="r")

    def usage(self):
        return {"input_tokens": 5}


class Conversation:
    """A page stand-in: resends the thread and the last state, like app.js."""

    def __init__(self, script):
        self.script = script
        self.messages = []
        self.state = {}
        self.records = []

    async def say(self, text):
        self.messages.append(UserMessage(id=str(len(self.messages)), role="user", content=text))
        run = RunAgentInput(
            thread_id="thread-1",
            run_id=f"run-{len(self.messages)}",
            state=self.state,
            messages=list(self.messages),
            tools=[],
            context=[],
            forwarded_props={},
        )
        orchestrator = Orchestrator(
            "user-token",
            Settings(agents_gateway_url="https://agents.example"),
            router=self.script.router,
            sender=self.script.sender,
            general_factory=GeneralRun,
        )
        events = [event async for event in orchestrator.run(run)]
        self.records.append(orchestrator.usage())
        text = "".join(e.delta for e in events if e.type == EventType.TEXT_MESSAGE_CONTENT)
        snapshots = [e.snapshot for e in events if e.type == EventType.STATE_SNAPSHOT]
        if snapshots:
            self.state = snapshots[-1]
        self.messages.append(
            AssistantMessage(id=str(len(self.messages)), role="assistant", content=text)
        )
        return events, text


async def test_scenario_disambiguation_asks_once_and_delegates_nothing():
    # What Sonnet 4.6 answered for this message on 29 Sep 2026.
    script = Script([route("general", "low", alternatives=["profile", "pay"])], [])
    chat = Conversation(script)
    events, text = await chat.say("I need to update my information")
    assert "home address" in text and "direct deposit" in text
    assert script.sent == []
    assert not any(e.type == EventType.STEP_STARTED for e in events)
    record = chat.records[-1]
    assert record["confidence"] == "low"
    assert (record["action"], record["delegated_to"]) == ("clarify", None)


async def test_scenario_confirmation_commits_only_on_the_second_turn():
    script = Script(
        [route("profile"), route("general", "low", follow_up=True)],
        [
            SubAgentReply("Change to 419 Glendale Ave? Confirm?", pending=PROPOSAL),
            SubAgentReply("Your address is updated.", committed=True),
        ],
    )
    chat = Conversation(script)
    events, _ = await chat.say("Change my home address to 419 Glendale Ave, Decatur GA 30030")
    step_types = (EventType.STEP_STARTED, EventType.STEP_FINISHED)
    steps = [e.step_name for e in events if e.type in step_types]
    assert steps == ["profile", "profile"]
    assert chat.state["pendingAction"]["proposalId"] == PROPOSAL_ID
    assert chat.state["pendingAction"]["domain"] == "profile"
    assert chat.records[-1]["confirmed"] is False

    await chat.say("yes")
    second = script.sent[-1]
    assert second["domain"] == "profile" and second["pending"]["proposalId"] == PROPOSAL_ID
    assert second["token"] == "user-token" and second["thread"] == "thread-1"
    assert [t["role"] for t in second["history"]] == ["user", "assistant"]
    assert chat.state["pendingAction"] is None
    assert chat.records[-1]["confirmed"] is True


async def test_scenario_sticky_context_stays_in_profile():
    script = Script(
        [route("profile"), route("profile", "medium", follow_up=True)],
        [SubAgentReply("Your address is updated."), SubAgentReply("Your emergency contact is ...")],
    )
    chat = Conversation(script)
    await chat.say("Change my home address to 419 Glendale Ave, Decatur GA 30030")
    await chat.say("what about my emergency contact?")
    assert [s["domain"] for s in script.sent] == ["profile", "profile"]
    assert chat.state["activeDomain"] == "profile"


async def test_scenario_topic_shift_and_escalation():
    script = Script(
        [route("profile"), route("travel"), route("general", "medium", follow_up=True)],
        [
            SubAgentReply("Confirm the change?", pending=PROPOSAL),
            SubAgentReply("Each employee gets 8 buddy passes a year."),
            SubAgentReply("I opened ticket HR-123456; HR follows up within two business days."),
        ],
    )
    chat = Conversation(script)
    await chat.say("Change my home address to 419 Glendale Ave, Decatur GA 30030")
    await chat.say("How many buddy passes do I get?")
    assert script.sent[-1]["domain"] == "travel"
    assert script.sent[-1]["pending"] is None  # the shift drops the pending change
    assert chat.state == {"activeDomain": "travel", "pendingAction": None}
    _, text = await chat.say("I need to talk to someone")
    assert script.sent[-1]["domain"] == "travel"
    assert "HR-123456" in text


async def test_a_general_question_goes_to_the_knowledge_base_agent():
    script = Script([route("general")], [])
    chat = Conversation(script)
    events, _ = await chat.say("How much PTO do I get?")
    assert [e.type for e in events] == [EventType.RUN_STARTED, EventType.RUN_FINISHED]
    assert chat.records[-1]["action"] == "answer" and chat.records[-1]["input_tokens"] == 5


async def test_a_failed_sub_agent_offers_a_ticket_and_keeps_the_state():
    script = Script([route("pay")], [SubAgentReply("", error=True)])
    chat = Conversation(script)
    chat.state = {"activeDomain": "profile"}
    _, text = await chat.say("Where does my pay go?")
    assert "could not reach the Pay agent" in text and "ticket" in text
    assert chat.state["activeDomain"] == "profile"
    assert chat.records[-1]["sub_agent_error"] is True


async def test_a_pending_change_without_its_domain_is_ignored():
    script = Script([route("pay")], [SubAgentReply("Your deposit goes to ...")])
    chat = Conversation(script)
    chat.state = {"pendingAction": {k: v for k, v in PROPOSAL.items()}}  # no domain
    await chat.say("Where does my pay go?")
    assert script.sent[-1]["pending"] is None
