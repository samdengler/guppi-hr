# Claude Code Instructions

This repository is the HR Super Agent MVP, an iteration of guppi-gpt
(`~/src/github.com/samdengler/guppi-gpt`) focused on the conversational agent and
sub-agent experience.

Read `docs/handoff.md` first. It explains the MVP, the sources, and how to start.
Then work `docs/plan.md` phase by phase and record choices in `docs/decision-log.md`.

Until phase 1 rewrites it, the project rules are guppi-gpt's `AGENTS.md`: no Lambda in
the request path without Sam's approval, no secrets in files or context values, the
page renders plain text only, prose has no em-dashes or en-dashes and no second person,
`uv run -- pytest` and `cdk synth` stay green on every change.
