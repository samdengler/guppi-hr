# /// script
# requires-python = ">=3.12"
# dependencies = ["boto3", "websocket-client"]
# ///
"""Run hr-super-agent's 60 labeled utterances through the canvas over Connect chat.

Each utterance is one chat. A context case (an `active` domain, `history`, a pending
change) first sends its history's user turn so the canvas is in the same state, then the
labeled text. The outcome is read from the reply:

    profile / pay / travel  a reply from that sub-agent (every mock reply carries its tag)
    clarify                 ClarifyFlow's question
    escalation              EscalationFlow's hand-off line
    general                 anything else (PolicyFlow's journey answered)

Scoring follows evals/route.py in hr-super-agent: a write domain (profile, pay) on
either side counts twice. Writes .deploy/route-eval.json and prints the table.

    uv run scripts/route_eval.py [--workers 5]
"""

from __future__ import annotations

import argparse
import json
import secrets
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from chat import Chat  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT.parent / "hr-super-agent" / "evals" / "utterances.jsonl"
WRITE_DOMAINS = {"profile", "pay"}
OUTCOMES = ("profile", "pay", "travel", "general", "clarify", "escalation")
GREETING = "Hi, I'm the HR assistant"


def outcome(replies: list[str]) -> str:
    text = " ".join(r for r in replies if not r.startswith(GREETING) and not r.startswith("[flow]"))
    if "Do you want to update your profile" in text or 'Please say "profile"' in text:
        return "clarify"
    for domain in ("profile", "pay", "travel"):
        if f"[mock {domain} agent]" in text:
            return domain
    if "Connecting you to the HR service desk" in text:
        return "escalation"
    return "general" if text.strip() else "none"


def weight(expected: str, actual: str) -> int:
    return 2 if expected in WRITE_DOMAINS or actual in WRITE_DOMAINS else 1


def run_one(item: dict, flow_id: str) -> dict:
    chat = Chat(flow_id, f"guppi-dummy-{secrets.token_hex(8)}", "spike-employee-1")
    try:
        chat.wait_quiet(3.0, 30.0)
        for role, content in item.get("history", []):
            if role == "user":
                chat.say(content)
                chat.wait_quiet(3.5, 40.0)
            elif role == "assistant" and content.startswith("Done") and not item.get("pending_domain"):
                # The labeled history has the change committed; the replay's first turn
                # only produced the proposal, so confirm it to reach the same state.
                chat.say("yes")
                chat.wait_quiet(3.5, 40.0)
        before = len(chat.events)
        chat.say(item["text"])
        chat.wait_quiet(3.5, 45.0)
        replies = [e["text"] for e in chat.events[before:]]
    finally:
        chat.close()
    actual = outcome(replies)
    return {**item, "actual": actual, "replies": replies, "contactId": chat.contact_id}


def report(results: list[dict]) -> str:
    lines = [f"{'expected':10} {'n':>3} {'correct':>7} {'accuracy':>9}"]
    by = Counter(r["expect"] for r in results)
    ok = Counter(r["expect"] for r in results if r["actual"] == r["expect"])
    for e in sorted(by):
        lines.append(f"{e:10} {by[e]:>3} {ok[e]:>7} {ok[e] / by[e]:>9.0%}")
    n, c = len(results), sum(1 for r in results if r["actual"] == r["expect"])
    wn = sum(weight(r["expect"], r["actual"]) for r in results)
    wc = sum(weight(r["expect"], r["actual"]) for r in results if r["actual"] == r["expect"])
    lines.append(f"overall: {c} of {n} ({c / n:.0%}); weighted {wc} of {wn} ({wc / wn:.0%})")
    misses = [r for r in results if r["actual"] != r["expect"]]
    if misses:
        lines.append("misroutes:")
        for r in sorted(misses, key=lambda r: r["id"]):
            lines.append(f"  {r['id']} expected {r['expect']:8} got {r['actual']:10} {r['text']}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--only", nargs="*", help="utterance ids to run")
    args = parser.parse_args()
    state = json.loads((ROOT / ".deploy" / "acxd.json").read_text())
    items = [json.loads(line) for line in CORPUS.read_text().splitlines() if line.strip()]
    if args.only:
        items = [i for i in items if i["id"] in args.only]
    started = time.time()
    import builtins

    quiet_print = builtins.print
    builtins.print = lambda *a, **k: None  # Chat narrates every message; keep the table readable
    try:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            results = list(pool.map(lambda i: run_one(i, state["contactFlowId"]), items))
    finally:
        builtins.print = quiet_print
    out = {"build": state.get("buildId"), "seconds": round(time.time() - started), "results": results}
    (ROOT / ".deploy" / "route-eval.json").write_text(json.dumps(out, indent=2))
    print(report(results))
    print(f"{len(results)} chats in {out['seconds']} s; details in .deploy/route-eval.json")


if __name__ == "__main__":
    main()
