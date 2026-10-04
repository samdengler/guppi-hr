"""The bridge's own timings for one run (guppi-hr D54, debug mode steps 1 and 2).

Every ConnectTurn keeps a Timing from the moment it is built, which is the moment the
bridge takes the request: a list of steps, each a name, a start and an end in milliseconds
from then on `time.monotonic()`, and a lane ("bridge", "exchange" or "connect"). A step with
no end is a point. The turn records its own waits and marks; TimedClients records each
Connect call and WebSocket open the turn makes. Recording is a few appends per run, so it
is always on; some marks also go to the run line. Only a run whose forwardedProps has
`debug: true` sends the steps to the page, as one CUSTOM event named `guppi.timing`
just before the run ends.

The event carries step names, times, fixed notes and ids (the contact id, the run's trace
id, the run id), never a token, an email address, a name or message text.
"""

from __future__ import annotations

import functools
import time
from collections.abc import Callable
from typing import Any

from ag_ui.core import CustomEvent, EventType, RunAgentInput

EVENT_NAME = "guppi.timing"


def debug_requested(run_input: RunAgentInput) -> bool:
    props = run_input.forwarded_props
    return isinstance(props, dict) and props.get("debug") is True


def trace_id() -> str | None:
    """The W3C trace id of the run's span, or None outside a trace."""
    try:
        from opentelemetry import trace

        context = trace.get_current_span().get_span_context()
        return f"{context.trace_id:032x}" if context.is_valid else None
    except Exception:  # noqa: BLE001 - timing never fails a run
        return None


class Timing:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self.clock = clock
        self.t0 = clock()
        self.steps: list[dict[str, Any]] = []
        self.notes: list[str] = []
        self.contact: str | None = None

    def ms(self) -> int:
        return max(0, round((self.clock() - self.t0) * 1000))

    def begin(self, name: str, lane: str) -> dict[str, Any]:
        """A step under way; `end` records it."""
        return {"name": name, "start_ms": self.ms(), "end_ms": None, "lane": lane}

    def end(self, step: dict[str, Any], failed: bool = False) -> dict[str, Any]:
        step["end_ms"] = max(step["start_ms"], self.ms())
        if failed:
            step["name"] += " (failed)"
        self.steps.append(step)
        return step

    def add(self, name: str, start_ms: int, end_ms: int | None, lane: str) -> None:
        self.steps.append({"name": name, "start_ms": start_ms, "end_ms": end_ms, "lane": lane})

    def point(self, name: str, lane: str) -> int:
        at = self.ms()
        self.add(name, at, None, lane)
        return at

    def call(self, name: str, lane: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """`fn(*args, **kwargs)` recorded as one step, whether it returns or raises."""
        step = self.begin(name, lane)
        try:
            result = fn(*args, **kwargs)
        except BaseException:
            self.end(step, failed=True)
            raise
        self.end(step)
        return result

    def note(self, text: str) -> None:
        if text not in self.notes:
            self.notes.append(text)

    def first_start(self, name: str, after: int = 0) -> int | None:
        starts = [
            s["start_ms"] for s in list(self.steps) if s["name"] == name and s["start_ms"] >= after
        ]
        return min(starts) if starts else None

    def last_end(self, name: str) -> int | None:
        ends = [
            s["end_ms"] for s in list(self.steps) if s["name"] == name and s["end_ms"] is not None
        ]
        return max(ends) if ends else None

    def value(self, run_id: str) -> dict[str, Any]:
        total = self.ms()
        steps = sorted(list(self.steps), key=lambda s: (s["start_ms"], s["end_ms"] is None))
        steps.append({"name": "total", "start_ms": 0, "end_ms": total, "lane": "bridge"})
        return {
            "steps": [dict(s) for s in steps],
            "total_ms": total,
            "ids": {"contact": self.contact, "trace": trace_id(), "run": run_id},
            "notes": list(self.notes),
        }

    def event(self, run_id: str) -> CustomEvent:
        return CustomEvent(type=EventType.CUSTOM, name=EVENT_NAME, value=self.value(run_id))


# The calls TimedClients records, by client attribute: the step name and its lane. Reads of
# the transcript and of a socket are many short waits, so the turn records those as the
# greeting wait and the reply marks instead.
CLIENT_STEPS: dict[str, Any] = {
    "start_flow": ("flow socket", "connect"),
    "open_websocket": ("reply socket", "connect"),
    "connect": {
        "start_chat_contact": ("StartChatContact", "connect"),
        "update_contact_attributes": ("token blanking", "connect"),
        "stop_contact": ("StopContact", "connect"),
    },
    "participant": {
        "create_participant_connection": ("CreateParticipantConnection", "connect"),
        "send_message": ("SendMessage", "connect"),
    },
}


class TimedClients:
    """The turn's clients, with the calls in CLIENT_STEPS recorded on `timing`. Attributes
    are looked up on the wrapped object at each use, so a client replaced on it is seen."""

    def __init__(self, target: Any, timing: Timing, steps: dict[str, Any] | None = None) -> None:
        self._target = target
        self._timing = timing
        self._steps = CLIENT_STEPS if steps is None else steps

    def __getattr__(self, attr: str) -> Any:
        value = getattr(self._target, attr)
        spec = self._steps.get(attr)
        if isinstance(spec, dict):
            return TimedClients(value, self._timing, spec)
        if isinstance(spec, tuple) and callable(value):
            name, lane = spec
            return functools.partial(self._timing.call, name, lane, value)
        return value
