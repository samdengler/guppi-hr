# Latency harness and timeline analysis

The scripts behind `docs/latency-timelines-2026-10-04*.md`. They were written in a session
scratchpad and moved here on 4 Oct 2026 so another machine can rerun them. Paths and time
windows inside some scripts are the 4 Oct ones; set them per run.

## Prerequisites

- AWS SSO for account 009080466601 (`aws sso login`).
- The harness session file `~/.config/guppi/test-session.json` (the headless Okta session the
  harness client uses; `abbench/signin.mjs` creates it). The harness client id and token URL
  come from SSM (`/guppi/okta/harness-client-id`, `/guppi/okta/token-url`).
- guppi-gpt checked out at `~/src/github.com/samdengler/guppi-gpt` with `web/node_modules`
  installed: the harness loads Playwright from there.
- For Dynatrace spans, `DT_PLATFORM_TOKEN` in the environment from 1Password item
  "Dynatrace MCP" (`op read "op://Personal/Dynatrace MCP/credential"`). Never print it.

## Benchmark (costs Connect messages, about $0.01 each)

From a working folder that holds a copy of `timelines/` next to a copy of `abbench/`:

    node timeline.mjs smoke   # one "Change my address" chat and its follow-up
    node timeline.mjs main    # 22 chats: the four suggestions five times, two Pay chats
    node timeline.mjs reuse   # three pairs of chats 66 s apart

Each run writes `results-<mode>.json` and stops every contact it opened.

## Analysis, in order

    uv run --with boto3 python fetch.py <since ISO> <until ISO>   # raw/: CloudWatch, X-Ray, Dynatrace, designer logs
    python3 join.py && python3 agg.py && python3 mkjson.py         # joined.json, paths, latency-timelines.json
    python3 evidence.py                                            # evidence.json with every id
    uv run --with boto3 python ct_fetch.py && python3 ct_join.py   # CloudTrail ids (set the window)
    uv run --with boto3 python rt_app_fetch.py && python3 rt_app_join.py   # the runtimes' InvokeAgentRuntime records (set the window)
    uv run --with boto3 python ac_spans_fetch.py && python3 ac_spans_summary.py   # AgentCore's own spans in aws/spans
    python3 evidence_md.py                                         # evidence.md
    python3 clockcheck.py                                          # runtime receipt to container split

`report/` builds the review page: `md2html.py` turns a report into an HTML fragment,
`lt-build.py` adds the waterfalls, `ev-build.py` the evidence page. Set `LATENCY_WORK` to the
working folder.

On Runtime V2 the runtime log streams are `runtime-logs-<session id>` (one per session) and
`build-logs-<id>` (the snapshot build); on V1 they are `<date>/[runtime-logs]<microVM id>`.
The scripts here are the V2-aware versions.
