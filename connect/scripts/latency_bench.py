# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx>=0.27"]
# ///
"""Repeated, client-side latency runs against /p/hr/ (critique finding 11).

Each round is one new chat as the page makes it: a warm start (unless --no-warm), a pause
for typing, a first question, then a follow-up in the same thread. Times are taken on this
machine from the request's start: `first_ms` to the first text, `done_ms` to RUN_FINISHED.
The trace id of every run is kept, so each can be joined with the bridge's run line and the
spans in Dynatrace. A round's warm start names the previous round's thread, as the page
does, so the bridge ends that contact.

With --click a round is a suggestion pressed on a new chat: the page sends the warm start on
the pill's pointerdown and the question on its click, about 0.1 s later, so the question
waits for the contact's start. The questions are the manifest's suggestions, with no
follow-up. --press-after sets the time from the warm start to the press instead: with the
warm start sent at page load (D50), a reader presses a pill some seconds after the page opens.

The token comes from guppi-gpt's scripts/test-token.sh (the test session); it stays in this
process and is never printed or written.

    uv run connect/scripts/latency_bench.py --rounds 10 --label baseline
    uv run connect/scripts/latency_bench.py --rounds 10 --no-warm --label no-warm
    uv run connect/scripts/latency_bench.py --rounds 8 --click --label click
    uv run connect/scripts/latency_bench.py --rounds 8 --click --press-after 6 --label loaded
    uv run connect/scripts/latency_bench.py --rounds 1 --debug --label debug

With --debug every question carries `forwardedProps.debug`, and the bridge's guppi.timing
event of each (D54) is printed and kept with the run.

Results go to connect/.deploy/latency/<label>-<time>.json with a summary on stdout.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import statistics
import subprocess
import threading
import time
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
GUPPI_GPT = Path(os.environ.get("GUPPI_GPT_DIR", ROOT.parents[1] / "guppi-gpt"))
URL = os.environ.get("HR_AGENT_URL", "https://chat.dengler.io/api/hr/invocations")
QUESTIONS = [
    ("What is my home address on file?", "And what is my emergency contact?"),
    ("How many buddy passes do I get?", "Can my parents use them?"),
    # PolicyFlow's generative journey (added 3 Oct with L21).
    ("How much PTO do I earn per year?", "Does unused PTO carry over?"),
]
MANIFEST = ROOT / "web" / "manifest.json"
PRESS_SECONDS = 0.1  # pointerdown to click on a pill


def suggestions() -> list[str]:
    return [s["prompt"] for s in json.loads(MANIFEST.read_text())["suggestions"]]


def token() -> str:
    script = GUPPI_GPT / "scripts" / "test-token.sh"
    return subprocess.run([str(script)], check=True, capture_output=True, text=True).stdout.strip()


def traceparent() -> tuple[str, str]:
    seconds = f"{int(time.time()):08x}"
    trace_id = seconds + secrets.token_hex(12)
    return trace_id, f"00-{trace_id}-{secrets.token_hex(8)}-01"


def run(client: httpx.Client, bearer: str, session: str, thread: str, messages: list[dict], props: dict) -> dict:
    trace_id, parent = traceparent()
    body = {
        "threadId": thread,
        "runId": str(uuid.uuid4()),
        "messages": messages,
        "tools": [],
        "context": [],
        "state": {},
        "forwardedProps": {"project": "hr", **props},
    }
    headers = {
        "authorization": f"Bearer {bearer}",
        "content-type": "application/json",
        "accept": "text/event-stream",
        "x-amzn-bedrock-agentcore-runtime-session-id": session,
        "traceparent": parent,
    }
    started = time.monotonic()
    first = None
    started_event = None
    text = []
    timing = None
    outcome = "unfinished"
    with client.stream("POST", URL, json=body, headers=headers, timeout=60) as response:
        if response.status_code != 200:
            return {"trace_id": trace_id, "outcome": f"http {response.status_code}", "done_ms": None, "first_ms": None, "text": ""}
        for line in response.iter_lines():
            if not line.startswith("data:"):
                continue
            event = json.loads(line[5:])
            kind = event.get("type")
            if kind == "RUN_STARTED" and started_event is None:
                started_event = time.monotonic()
            if kind == "TEXT_MESSAGE_CONTENT":
                if first is None:
                    first = time.monotonic()
                text.append(event.get("delta", ""))
            elif kind == "CUSTOM" and event.get("name") == "guppi.timing":
                timing = event.get("value")
            elif kind == "RUN_FINISHED":
                outcome = "finished"
            elif kind == "RUN_ERROR":
                outcome = f"error {event.get('code')}"
    done = time.monotonic()
    return {
        "trace_id": trace_id,
        "outcome": outcome,
        "first_ms": round((first - started) * 1000) if first else None,
        # The bridge sends RUN_STARTED at once, so this is the round trip into it, on one clock.
        "started_ms": round((started_event - started) * 1000) if started_event else None,
        "done_ms": round((done - started) * 1000),
        "text": " ".join(text)[:160],
        **({"timing": timing} if timing is not None else {}),
    }


def print_timing(what: str, result: dict | None) -> None:
    timing = (result or {}).get("timing")
    if timing:
        print(f"  {what} guppi.timing: {json.dumps(timing)}")


def summary(values: list[int]) -> str:
    values = sorted(v for v in values if v is not None)
    if not values:
        return "no data"
    p90 = values[min(len(values) - 1, round(0.9 * (len(values) - 1)))]
    return f"median {statistics.median(values) / 1000:.2f} s, p90 {p90 / 1000:.2f} s, min {values[0] / 1000:.2f}, max {values[-1] / 1000:.2f} (n={len(values)})"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=10)
    parser.add_argument("--pause", type=float, default=6.0, help="seconds between the warm start and the question")
    parser.add_argument("--no-warm", action="store_true")
    parser.add_argument("--click", action="store_true", help="press a suggestion: the warm start and the question together")
    parser.add_argument("--press-after", type=float, default=PRESS_SECONDS, help="seconds from the warm start to the press (--click)")
    parser.add_argument("--label", default="run")
    parser.add_argument("--debug", action="store_true", help="ask the bridge for its timings (D54)")
    args = parser.parse_args()

    bearer = token()
    prompts = suggestions()
    results = []
    previous = None
    asked = {"debug": True} if args.debug else {}
    with httpx.Client(http2=False) as client:
        for i in range(args.rounds):
            first_q, follow_q = (prompts[i % len(prompts)], None) if args.click else QUESTIONS[i % len(QUESTIONS)]
            session = f"{uuid.uuid4()}-{uuid.uuid4()}"  # one page load per round
            thread = str(uuid.uuid4())
            warm = None
            pressed = None
            if not args.no_warm:
                props = {"warm": True, **({"previousThreadId": previous} if previous else {})}
                if args.click:
                    box: dict = {}

                    def press(box=box, props=props, session=session, thread=thread) -> None:
                        with httpx.Client(http2=False) as own:
                            box["warm"] = run(own, bearer, session, thread, [], props)

                    pressed = threading.Thread(target=press)
                    pressed.start()
                    time.sleep(args.press_after)
                else:
                    warm = run(client, bearer, session, thread, [], props)
                    time.sleep(max(0.0, args.pause - warm["done_ms"] / 1000))
            m1 = {"id": str(uuid.uuid4()), "role": "user", "content": first_q}
            first = run(client, bearer, session, thread, [m1], asked)
            if pressed is not None:
                pressed.join()
                warm = box.get("warm")
            follow = None
            if follow_q:
                time.sleep(2.0)
                a1 = {"id": str(uuid.uuid4()), "role": "assistant", "content": first["text"] or "(none)"}
                m2 = {"id": str(uuid.uuid4()), "role": "user", "content": follow_q}
                follow = run(client, bearer, session, thread, [m1, a1, m2], asked)
            results.append({"round": i, "question": first_q, "warm": warm, "first": first, "follow": follow})
            print(
                f"round {i}: warm {warm and warm['done_ms']} ms | first {first['first_ms']} / {first['done_ms']} ms"
                f" {first['outcome']}"
                + (f" | follow-up {follow['first_ms']} / {follow['done_ms']} ms {follow['outcome']}" if follow else "")
            )
            print_timing("first", first)
            print_timing("follow-up", follow)
            previous = thread
            time.sleep(2.0)

    out = ROOT / ".deploy" / "latency" / f"{args.label}-{time.strftime('%Y%m%d-%H%M%S')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"label": args.label, "url": URL, "pause": args.pause, "warm": not args.no_warm, "click": args.click, "press_after": args.press_after, "results": results}, indent=2))
    print(f"\n{args.label}: {len(results)} rounds -> {out}")
    print("first reply, new chat:  " + summary([r["first"]["first_ms"] for r in results]))
    print("first reply, follow-up: " + summary([r["follow"]["first_ms"] for r in results if r["follow"]]))
    print("turn done, new chat:    " + summary([r["first"]["done_ms"] for r in results]))
    print("turn done, follow-up:   " + summary([r["follow"]["done_ms"] for r in results if r["follow"]]))
    print("RUN_STARTED (hop in):   " + summary([r[k].get("started_ms") for r in results for k in ("first", "follow") if r[k]]))
    if not args.no_warm:
        print("warm start:             " + summary([r["warm"]["done_ms"] for r in results if r["warm"]]))


if __name__ == "__main__":
    main()
