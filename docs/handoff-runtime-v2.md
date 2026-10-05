# Handoff: AgentCore Runtime V2 cold start, 4 October 2026

Written at the end of the 4 Oct session for the session that continues on Sam's Mac mini
while he travels. Read `docs/handoff.md` and `AGENTS.md` first for the project rules. This
file covers only the Runtime V2 work and what Sam asked for next.

## Sam's instructions for this work

1. Stay on Runtime V2. Do not move the runtimes back to V1; Sam does not want to pivot off
   V2 yet. The repository and the deployed stack both say V2 (`PLATFORM_VERSION` in
   `infra/hr_super_agent_infra/runtime_role.py`).
2. Study the runtime's cold start in depth to learn how to optimize it. Start with a research
   sub-agent on the Fable model that collects the knowledge on Lambda SnapStart, SnapStart
   with container images, and AgentCore Runtime V2: the startup lifecycle under SnapStart
   (init, snapshot, restore, the runtime hooks), what a snapshot keeps and what it cannot
   (uniqueness, connections, credentials, clocks), language support (Python, Java, Node.js,
   Rust and custom runtimes), image size and memory effects, and anything published about
   how AgentCore Runtime V2 uses it.
3. From that knowledge, design a comprehensive set of experiments that run in isolation and
   show the tradeoffs, then run them in parallel with sub-agents on suitable models. Sam does
   not want to review the plan; he trusts the session to make it comprehensive and execute it.
4. No warm-up calls (requests made only to warm a session or a client, including a real call
   before the snapshot) until Sam approves them. Priming without network calls is in place
   and allowed.
5. Commit results, and record every measurement in `docs/latency-log.md`, every AWS finding
   in `docs/aws-feedback.md` and every choice in `docs/decision-log.md` the day it happens.

## Status of the research step

Done on 4 Oct: two Fable sub-agents researched snapshot restore (Lambda SnapStart,
Firecracker, language effects) and AgentCore Runtime V2 (mechanics, knobs, practitioner
reports, gateway MCP sessions, token caching). Their reports are in
`docs/runtime-v2-research.md`, with a list of measurements that separate the restore's
components and open questions for AWS. Skip the research step. The experiment plan is `docs/runtime-v2-experiments.md`
(4 Oct, evening); its fixtures are in `scripts/v2study/`. (The first single Fable attempt stalled while loading its web tools; if research is
ever rerun, tell each sub-agent to load WebSearch and WebFetch with ToolSearch first.)

## Status of the experiment step (5 Oct, 00:45 to 03:15 UTC)

Done. The plan is `docs/runtime-v2-experiments.md`; fourteen experiments ran (E1 to E14,
plus E15 added for the credentials question), six sub-agents in parallel and the main
session for E7, E13 and E15. Every measurement is in `docs/latency-log.md` L34 to L47, every
AWS finding in `docs/aws-feedback.md` A26 to A37 and CW1, the choices in
`docs/decision-log.md` D58 and D59 (both Proposed for Sam). Raw lines, per-experiment
tables and findings are under `docs/runtime-v2-evidence/<E>/`; the fixtures are in
`scripts/v2study/` (README there). All test resources were deleted at the end (runtimes,
gateways, roles, ECR repository, Cognito pool) except the security group
`sg-0b6c011914cb60048` (`hr-v2-study`, default VPC): two `agentic_ai` network interfaces of
the failed VPC runtimes still used it an hour after their runtimes were gone (A35), so
`aws ec2 delete-security-group --group-id sg-0b6c011914cb60048` needs to run once they are
released. The vended log group `/aws/vendedlogs/bedrock-agentcore/hr-v2-study` is kept as
evidence for 30 days.

The study's two code commits (6d18872, d403d0a) are in the rollback script's kept list (done
from the laptop on 5 Oct); `uv run -- pytest`, `cdk synth` and `scripts/obo-rollback.sh --check` are green. D58 and D59 are Proposed.

What the study says, in order of weight for /p/hr/:

1. The 1.8 s per new session is the platform's restore and nothing in the image moves it:
   not protocol, image size, memory, language, imports or priming (E1 to E6, L34 to L39).
   What we control is only the work the first request does after the restore (lazy imports
   cost 0.6 to 0.95 s, L38), which priming already removed (L33).
2. Fewer restores is the lever. Gateway MCP sessions (E12, L42, D59) cut later tool calls
   from 2.2 s to 0.58 s but cost two restores on the first call (4.3 s), because the gateway
   runs `server/discover` on a throwaway session (A27); break-even at the third tool call of
   a gateway session. A runtime session that outlives one chat (idle timeout up to 8 h, E11)
   costs nothing while idle, and a session id reused shortly after its timeout is penalized
   (502s and 7 to 15 s restores in the first minute, A36), so a client should start a new id
   once the old one is known to have expired.
3. Bursts are fine on V2 (flat to 20 at once) and V1 drains its pool at about 11 (E8, L41).
4. A JWT authorizer costs 0.12 s per request, every request (E9, L43, A34).
5. VPC mode could not be created on V2 in the default VPC (A35); it needs NAT or endpoints.
6. Restored instances repeat user-space random state, including Node's `crypto` (A29);
   the `prime.py` reseed watcher is needed and correct. Clients built before the snapshot
   carry the build's credentials for an hour, then refresh per microVM without failure
   (E14, E15, A30), so priming is safe.
7. For 20 to 35 s after a version is READY, and for the first sessions after an idle hour,
   first-request work inside a restored instance is ten times slower (A31, E7).

The W experiments (a real call before the snapshot, keep-alive pings, a session opened at
page load, capacity providers) were not run and wait for Sam.

## Isolation for the experiments

- The Mac mini has AWS SSO but not the browser harness (`~/.config/guppi/test-session.json`,
  guppi-gpt with Playwright). The experiments do not need it. Do not try to rerun the
  `/p/hr/` Connect benchmark there unless Sam has copied the session file over.
- Use dedicated test runtimes, not the four live HR runtimes behind Connect, and invoke them
  directly with `InvokeAgentRuntime` (boto3 `bedrock-agentcore`). That keeps `/p/hr/` stable
  and costs no Connect messages. Name them so they are easy to find and delete, and delete
  them when done.
- `platformVersion`: CLI 2.34.42 and botocore 1.43.87 do not expose it. CloudFormation's
  `AWS::BedrockAgentCore::Runtime` accepts `PlatformVersion` and updates it in place, and
  Cloud Control reads it back (`aws cloudcontrol get-resource --type-name
  AWS::BedrockAgentCore::Runtime --identifier <runtime id>`). A newer boto3 may take
  `platformVersion` on create and update; check before building on it. The AWS docs say CDK
  and CloudFormation cannot set it, which is out of date.
- A V2 create or update takes minutes (the snapshot build). The container must answer
  `/ping` healthy within 120 s. V2 caps container environment variables at 2.5 KB.
- On this laptop the auto mode classifier blocked `scripts/deploy.sh` (and `cdk deploy` with
  `--require-approval never`) even with Sam's approval in chat; Sam ran the deploys with `!`.
  Experiments on separate test runtimes may not need the HR stack at all. If a stack deploy
  is needed and is blocked, hand Sam a one-line `!` command and continue other work.

## What is deployed now

- The four runtimes behind Connect (`hr_super_agent_tools`, `_profile`, `_travel`, `_pay`)
  run on V2 with priming (`agent/src/hr_agent/prime.py`, on through `ENV HR_PRIME=1` in
  `agent/Dockerfile`). Versions: tools 28, sub-agents 23, deployed 21:54 UTC.
- TRACES from both HR gateways and the four runtimes go to one X-Ray delivery destination,
  so `aws/spans` holds AgentCore's own `Gateway.*`, `Runtime.Invoke`, `Identity.*` and
  `Policy.*` spans (db53b19).
- Transaction Search indexing stays at 1 percent (GuppiGpt stack); every span still reaches
  `aws/spans`.
- Commits of the day on main: db53b19, 470ba07, 5f85653, bf2785b (V2, priming), 7006127
  (records L32, L33, A25), f0faae4 (V2 timelines), 805fabd (this file and the V2 setting), and the rollback list commit after it. The
  `KEPT_COMMITS` list in `scripts/obo-rollback.sh` holds each code commit; keep
  `scripts/obo-rollback.sh --check` and `uv run -- pytest` green. New code goes in new
  files where possible: edits next to the OBO changes in `agents/server.py`,
  `tools/server.py`, `tools/identity.py`, `sub_agents.py`, `hr_tools.py` and
  `tests/conftest.py` break the rollback replay.

## What the measurements say

Medians of first words, same harness and questions (`docs/latency-timelines-2026-10-04-v2.md`):

| Path | V1 | V2 | V2 primed |
| --- | --- | --- | --- |
| Change my address, first | 5.90 s | 8.90 s | 8.59 s |
| Profile after Clarify | 6.63 s | 9.25 s | 8.62 s |
| Pay, first | 8.62 s | 16.69 s | 13.46 s |
| Buddy passes, first | 6.88 s | 7.32 s | 7.18 s |
| PTO, follow-ups, chat start | same | same | same |

- The cost is the restore on a session's first request. From the runtime's receipt to the
  container: sub-agent 838 ms on V1, 1,870 ms on V2, 2,057 ms primed; tools runtime 613 ms,
  2,052 ms, 2,087 ms. Later requests on a session are about 0.2 s on both.
- Every new session restores a fresh instance. The tools gateway opens a new runtime session
  per tool call because gateway MCP sessions are off (A23), so Profile pays one restore per
  tool call and Pay two.
- Priming cut our own first-request work (MCP client start 310 ms to 42 ms, the tools
  server's `tools/call` 490 ms to 321 ms) but not the restore.
- CloudTrail names the snapshot build `snapstart-build-DEFAULT` and V2 sessions
  `AgentCore-MicroVM-<id>-DEFAULT`: AWS calls the mechanism SnapStart.
- The runtime calls Identity `GetWorkloadAccessTokenForJWT` once per delivered request on
  V1 and V2 (A24), despite a release note about caching.
- On V2 Dynatrace lost most of our own spans (none for Pay); the exporter likely does not
  flush before a restored session ends. AgentCore's spans in `aws/spans` are complete.
- On V2 the containers make no IMDS calls, every restored instance reports hostname
  `localhost` and PID 1, `time.monotonic()` does not advance across a restore, and the
  tools runtime receives platform MCP pings on `127.0.0.1:8000/mcp`.

## Where everything is

- Reports: `docs/latency-timelines-2026-10-04.md` (V1, with tables and evidence files),
  `docs/latency-timelines-2026-10-04-v2.md` (V1, V2, V2 primed), and their `-evidence.md`
  and `-evidence.json` files with every request, trace, span and session id.
- Records: `docs/latency-log.md` L29 to L33; `docs/aws-feedback.md` A21 to A25, TC9, TC10,
  C19, C20; `docs/decision-log.md` D55 to D57.
- Scripts: `connect/scripts/latency/` (harness, analysis, review page builders; see its
  README). The runtimes' own `InvokeAgentRuntime` records are in
  `/aws/vendedlogs/bedrock-agentcore/<runtime name>`; their `timeUnixNano` is the receipt,
  `event_timestamp` the completion.
- The review page (private Artifact): https://claude.ai/artifact/GgBVLV4xTBZyLCR5Rz4D8L.

## Measurement method that worked

- Split each request three ways: caller to runtime receipt (gateway log against the
  runtime's `timeUnixNano`), receipt to container (runtime record against the container's
  first span or log line), container work (our spans). The runtime's and the container's
  clocks can differ by about 0.1 s; `clockcheck.py` checks it.
- Count sessions and restores from the runtime records (`session_id`) and CloudTrail
  (`AgentCore-MicroVM-<id>`), not from log streams.
- Use wall clock times in the container on V2; monotonic time is frozen across a restore.

## Work waiting after the cold start study

- MCP sessions on the tools gateway (`protocolConfiguration.mcp.sessionConfiguration`,
  May 2026): one tools runtime session per gateway session instead of per call. Not yet
  deployed; measure with the same harness.
- A runtime session id per employee and domain instead of per contact (`hr.js` in the
  designer), so a session outlives one chat.
- A span flush at the end of each request on V2 (Dynatrace exporter).
- The issuer's keys in the tools verifier: `PyJWKClient` caches them for 300 s, so every
  restored instance fetches them again.
- Decisions still with Sam: D52 (PolicyFlow without tools), the rest of D56, warm-ups, the
  Touchpoint widget sample.
