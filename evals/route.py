"""Offline routing evaluation (D13): run every labeled utterance through the orchestrator's
routing step and policy, against Bedrock, and print accuracy per expected outcome.

Usage: uv run python evals/route.py [utterances.jsonl]

Each line of the corpus is {"id", "text", "expect", "active"?, "history"?, "pending_domain"?}
where expect is a sub-agent (profile, pay, travel), "general" (answered by the knowledge
base agent), or "clarify" (one clarifying question). An utterance whose expected or actual
outcome is a write domain (profile, pay) counts twice in the weighted accuracy: a misroute
there can put a change in front of the wrong agent. Needs AWS credentials with Bedrock
access to the router model; a run is about 60 Converse calls.
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections import Counter
from pathlib import Path

from hr_agent.orchestrator import Settings, decide, route_turn

WRITE_DOMAINS = {"profile", "pay"}
OUTCOMES = ("profile", "pay", "travel", "general", "clarify")


def outcome(decision) -> str:
    if decision.action == "delegate":
        return decision.domain
    return "general" if decision.action == "answer" else "clarify"


def weight(expected: str, actual: str) -> int:
    return 2 if expected in WRITE_DOMAINS or actual in WRITE_DOMAINS else 1


async def evaluate(path: Path, settings: Settings, concurrency: int = 4) -> list[dict]:
    items = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    gate = asyncio.Semaphore(concurrency)

    async def one(item: dict) -> dict:
        turns = [{"role": r, "content": c} for r, c in item.get("history", [])]
        turns.append({"role": "user", "content": item["text"]})
        pending_domain = item.get("pending_domain")
        pending = (
            {"field": "a pending change", "to": "(see the conversation)", "domain": pending_domain}
            if pending_domain
            else None
        )
        async with gate:
            route = await route_turn(turns, item.get("active"), pending, settings)
        actual = outcome(decide(route, item.get("active"), pending_domain))
        return {**item, "actual": actual, "confidence": route.confidence, "route": route.domain}

    return await asyncio.gather(*(one(item) for item in items))


def report(results: list[dict]) -> str:
    lines = [f"{'expected':10} {'n':>3} {'correct':>7} {'accuracy':>9}"]
    for expected in OUTCOMES:
        rows = [r for r in results if r["expect"] == expected]
        if rows:
            correct = sum(r["actual"] == expected for r in rows)
            lines.append(f"{expected:10} {len(rows):3} {correct:7} {correct / len(rows):9.0%}")
    total = sum(r["actual"] == r["expect"] for r in results)
    weights = [weight(r["expect"], r["actual"]) for r in results]
    weighted = sum(w for w, r in zip(weights, results, strict=True) if r["actual"] == r["expect"])
    lines.append(f"{'all':10} {len(results):3} {total:7} {total / len(results):9.0%}")
    lines.append(f"weighted accuracy (write domains count twice): {weighted / sum(weights):.0%}")

    lines.append("")
    lines.append("confusion (rows expected, columns actual)")
    lines.append(" " * 10 + "".join(f"{o:>9}" for o in OUTCOMES))
    for expected in OUTCOMES:
        counts = Counter(r["actual"] for r in results if r["expect"] == expected)
        lines.append(f"{expected:10}" + "".join(f"{counts.get(o, 0):9}" for o in OUTCOMES))

    bands = Counter(r["confidence"] for r in results)
    lines.append("")
    band_counts = ", ".join(f"{b} {bands.get(b, 0)}" for b in ("high", "medium", "low"))
    lines.append(f"confidence bands: {band_counts}")

    misses = [r for r in results if r["actual"] != r["expect"]]
    if misses:
        lines.append("")
        lines.append("misses")
        for r in misses:
            lines.append(
                f"  {r['id']} expected {r['expect']}, got {r['actual']} "
                f"(router {r['route']}, {r['confidence']}): {r['text']}"
            )
    return "\n".join(lines)


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("utterances.jsonl")
    results = asyncio.run(evaluate(path, Settings()))
    print(report(results))


if __name__ == "__main__":
    main()
