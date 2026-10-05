# AgentCore Runtime V2 cold start: experiment plan, 4 October 2026

Written from `docs/runtime-v2-research.md` and `docs/handoff-runtime-v2.md` on the evening of
4 October 2026, on Sam's Mac mini while he travels. Sam asked for a comprehensive set of
experiments on dedicated test runtimes, run in parallel by sub-agents without a review of
the plan. Results go to `docs/latency-log.md` (L34 on), AWS findings to
`docs/aws-feedback.md` (A26 on) and choices to `docs/decision-log.md` (D58 on). Everything
here is isolated from the four HR runtimes behind Connect: separate runtimes, a separate
ECR repository, a separate execution role, direct `InvokeAgentRuntime` calls, and no
Connect messages.

## What the study has to answer

The research puts a new V2 session's first request at about 2 s on the runtime's own records
(receipt to completion), against 0.6 to 0.8 s on V1, and says the gap is the per-session
restore from the snapshot. The experiments separate that time into parts the agent
controls (image, working set, language, imports, priming, protocol, auth mode, network mode)
and parts the platform owns (placement, snapshot cache warmth, bursts), and measure how many
restores a workload pays (idle timeout, session reuse, gateway MCP sessions). Each
experiment names a hypothesis from the research so a result either confirms or refutes
something written down.

## Rules in force

- No warm-up calls. Nothing before the snapshot makes a network call, and no request is sent
  only to warm a session or a client. The experiments marked "waiting for Sam" need one and
  are not run.
- Test runtimes are named `hr_v2_<experiment>_<variant>`, tagged `hr-v2-study=2026-10-04`,
  and deleted at the end of the study with their ECR repository, role, log deliveries,
  gateways and Cognito pool. The four HR runtimes are not touched.
- Every runtime gets `APPLICATION_LOGS` delivered to
  `/aws/vendedlogs/bedrock-agentcore/hr-v2-study`, so the runtime's own
  `InvokeAgentRuntime` records (`timeUnixNano` receipt, `event_timestamp` completion,
  `session_id`) are available for every request, as they were for the HR runtimes.
- No Lambda, no stack deploy, nothing in the request path of `/p/hr/`.

## Shared fixtures

Everything lives in `scripts/v2study/`.

### Test servers

One Python image, one Node image and one Go image, each a minimal server with the same
contract: `GET /ping` answers `{"status":"Healthy"}`; the request handler answers one JSON
document with in-guest telemetry and does no outbound call unless asked. The Python image
serves three protocols chosen by `MODE`:

| Mode | Port | Framework | Request |
| --- | --- | --- | --- |
| `http` | 8080 | FastAPI 0.141 on uvicorn 0.52, as the HR agents | `POST /invocations` |
| `mcp` | 8000 | `mcp` 1.29 FastMCP, stateless streamable HTTP, as the HR tools server | `initialize`, then `tools/call` of `probe` |
| `a2a` | 9000 | `a2a-sdk` 0.3.26 on Starlette, as the HR sub-agents | `message/send` |

The Node image (Node 24, `http` module) and the Go image (Go 1.25 `net/http`, static binary
on a distroless base) serve `http` only.

Telemetry in every answer: wall clock and monotonic clock at process start and at the
request; `/proc/uptime`; `/proc/self/stat` minor and major faults and RSS before and after
the handler's work; hostname, PID, `/proc/sys/kernel/random/boot_id`; the first value drawn
from the language's default random generator after start (to see whether restored instances
repeat it) and one from the kernel (`os.urandom`); the environment variable count; a count of
requests this process has served; and the time the handler's own work took. A restore is
visible as a wall clock far ahead of the monotonic clock. The runtime's record gives the
receipt and the completion, so three segments come out of every request: receipt to
handler start (the restore plus delivery), handler work, handler end to completion.

Knobs, all environment variables read at process start unless noted (V2 caps the block at
2.5 KB):

| Knob | Values | Effect |
| --- | --- | --- |
| `IMPORTS` | `none`, `heavy` | `heavy` imports boto3, botocore, strands, opentelemetry, pydantic and mcp at start, before `/ping` |
| `LAZY_IMPORTS` | `0`, `1` | with `heavy`, do the imports inside the first request instead of at start |
| `PRIME` | `none`, `clients`, `routes` | `clients` builds boto3 Bedrock, DynamoDB and STS clients at start (service models parsed, no network); `routes` also runs one request through the app with Starlette's `TestClient` |
| `TOUCH_MB` | integer | allocate and write this many MB at start and keep them, never read on request (snapshot size without a working set effect) |
| `TOUCH_ON_REQUEST_MB` | integer | allocate and write this many MB at start, then read every page on the first request (snapshot pages faulted in on restore) |
| `OUTBOUND` | `0`, `1` | the handler calls `sts:GetCallerIdentity` and times it (credentials, DNS, TLS from a restored instance) |
| `PAD_MB` (build argument) | integer | a file of random bytes of this size in the image, never read |
| `PYC` (build argument) | `1`, `0` | `1` compiles bytecode into the image; `0` ships no `.pyc` and sets `PYTHONDONTWRITEBYTECODE` |

### Creation, invocation and collection

- `create.py` creates a runtime from a short spec (name, image tag, protocol, platform
  version, environment, lifecycle, authorizer, network), waits for READY, records
  `createdAt`, `READY` time and the version, and attaches the log delivery. It uses boto3
  1.43.108 from a scratch environment, which has `platformVersion`.
- `invoke.py` sends one or more requests with `InvokeAgentRuntime` (SigV4 by default, a
  bearer token with `--jwt`), a fresh session id per new session, the protocol's payload, and
  prints one JSON line per request: client send time, first byte, end, status, the parsed
  telemetry. `--burst N` sends N new sessions at once from threads; `--reuse` sends a
  follow-up on the same session after a wait.
- `collect.py` joins the client lines with the runtime's records by `session_id` and
  `request_id`, pulls the container log stream per session, and writes per-experiment
  tables: median, p10, p90 and n for client latency, receipt to handler start, handler work,
  and the telemetry facts. It also counts CloudTrail `GetWorkloadAccessTokenForJWT` events
  for JWT runtimes.
- Every run's raw lines are kept under `docs/runtime-v2-evidence/` so a table can be rebuilt.

### Sample sizes

A new-session measurement is 25 sessions sent one at a time (one in flight), unless the
experiment says otherwise. The first five after READY are kept apart as "first restores".
Medians are compared; a difference under 0.15 s is reported as none.

## Experiments to run

Each experiment names the runtimes it creates (platform V2 unless stated), the hypothesis
it tests, the procedure and the measurements. "Baseline" is `hr_v2_proto_http_v2`: Python,
`http`, `IMPORTS=none`, no padding, no touch, SigV4, PUBLIC network, default lifecycle.

### E1. Protocol and platform: HTTP, MCP and A2A on V1 and V2

Runtimes: `hr_v2_proto_{http,mcp,a2a}_{v1,v2}` (6).
Hypothesis: V2's new-session cost is a platform floor of about 2 s regardless of protocol,
and V1's warm pool answers in under 1 s; the MCP `initialize` and the A2A `message/send`
pay the same restore as HTTP. Classmethod measured 1.9 s against 0.6 s.
Procedure: 25 new sessions each, then 10 follow-ups on existing sessions.
Measurements: receipt to handler start and client latency per protocol and platform; the
delivery time on an existing session (expected about 0.2 s on both).

### E2. Image size

Runtimes: `hr_v2_image_500`, `hr_v2_image_1500` (`PAD_MB` 500 and 1500; the baseline is 0).
Hypothesis: image size does not move the restore, because the padding is never read and a
snapshot restores pages on demand; AWS's benchmark showed 200 MB and 2 GB images within
0.2 s on V2.
Procedure: 25 new sessions each. Also record create to READY per image size (the snapshot
build time).
Measurements: receipt to handler start against image size; build time.

### E3. Memory touched before the snapshot

Runtimes: `hr_v2_touch_64`, `hr_v2_touch_256` (`TOUCH_MB`), `hr_v2_fault_32`,
`hr_v2_fault_128` (`TOUCH_ON_REQUEST_MB`).
Hypothesis: memory dirtied before the snapshot but never read costs nothing at restore
(pages stay in the snapshot store); the same memory read on the first request costs page
faults, 50 to 200 µs per 4 KB page from a network-backed store, so 128 MB read serially is
about 1.6 to 6 s. This is the single largest knob the research predicts.
Procedure: 25 new sessions each, then 10 follow-ups (the second request reads the same
pages: they should be resident).
Measurements: receipt to handler start, handler work (the read loop), minor and major fault
counts before and after the loop, the fault count on the follow-up.

### E4. Language: Python, Node and Go

Runtimes: `hr_v2_lang_node_v2`, `hr_v2_lang_go_v2`, `hr_v2_lang_go_v1`.
Hypothesis: a compiled server touches fewer pages per request, so Go restores faster than
Python by a few hundred ms, but not below the platform floor; Lambda's Rust hello world
still restores in 377 ms. Node sits between. On V1 the language makes no difference on a
warm pool.
Procedure: 25 new sessions each, 10 follow-ups.
Measurements: receipt to handler start, RSS, fault counts, handler work.

### E5. Python import depth and bytecode

Runtimes: `hr_v2_imp_heavy` (`IMPORTS=heavy`), `hr_v2_imp_lazy` (`heavy`,
`LAZY_IMPORTS=1`), `hr_v2_imp_nopyc` (`IMPORTS=none`, `PYC=0`), `hr_v2_imp_heavy_nopyc`.
Hypothesis: imports done before the snapshot cost nothing at restore beyond the pages the
request touches, so `heavy` is within 0.2 s of the baseline; the same imports done in the
first request cost seconds on every new session (the 18.3 s Profile answer of 4 October
before priming); bytecode in the image matters only when imports run after the restore.
Procedure: 25 new sessions each, 10 follow-ups.
Measurements: receipt to handler start, handler work (import time on `lazy`), RSS.

### E6. Priming depth without network calls

Runtimes: `hr_v2_prime_clients`, `hr_v2_prime_routes` (both `IMPORTS=heavy`).
Hypothesis: building boto3 clients and running one request through the app before the
snapshot moves their cost (service model parsing, route compilation, first JSON encode)
out of the first request: handler work falls, receipt to handler start does not. This is the
mechanism behind L33's 490 to 321 ms.
Procedure: 25 new sessions each, compared with `hr_v2_imp_heavy`.
Measurements: handler work, receipt to handler start.

### E7. First restores after a deploy against later restores and after idle

Runtimes: none new. Every runtime's first five sessions after READY are kept apart. The
baseline is updated once (a new environment variable makes a new version and a new
snapshot) and measured again from READY, then left idle and measured after 30 minutes, 2
hours and at the end of the study.
Hypothesis: the first sessions after a deploy are the slowest (snapshot chunks come from S3
or the AZ cache, not the host cache), later sessions are faster as hosts hold the chunks,
and a snapshot idle for hours slows down again. The research calls this the most likely
hidden variable in our measurements.
Measurements: receipt to handler start for sessions 1 to 5, 6 to 25, after each idle gap.

### E8. Bursts of new sessions

Runtimes: `hr_v2_proto_http_v2` and `hr_v2_proto_http_v1` from E1.
Hypothesis: V2 restores in parallel with no pool to drain, so 10 or 20 sessions at once each
take about the single-session time; V1's pool is finite, so a burst past it boots microVMs
and the tail rises to the 7 to 10 s seen after deploys (A21).
Procedure: bursts of 1, 5, 10 and 20 new sessions, three repeats each, one minute apart; the
account's limit is 25 new sessions a second.
Measurements: per-session receipt to handler start and client latency, median and maximum
per burst size; throttling errors.

### E9. Inbound JWT against IAM SigV4

Runtimes: `hr_v2_auth_jwt` (a `customJWTAuthorizer` on a Cognito user pool created for the
study, client credentials grant) against the SigV4 baseline.
Hypothesis: the runtime's `GetWorkloadAccessTokenForJWT` call adds 0.1 to 0.3 s on every
request to a JWT runtime (A24 saw one call per request on V1 and V2), so SigV4 inbound is
cheaper per request and per restore; the release note's 30-minute cache does not show.
Procedure: 25 new sessions with the same bearer token, then 10 follow-ups on one session
with the same token, then 10 with a fresh token.
Measurements: client latency and receipt to handler start against the baseline; CloudTrail
`GetWorkloadAccessTokenForJWT` events per request, per session and per token.

### E10. Network mode

Runtimes: `hr_v2_net_vpc` (the account's default VPC, two subnets, a security group with no
inbound rules) against the PUBLIC baseline.
Hypothesis: the documentation says VPC "may increase session startup times"; the attach of
an elastic network interface per microVM would add hundreds of ms to a restore.
Procedure: 25 new sessions, 10 follow-ups; record create to READY.
Measurements: receipt to handler start; build time; any failure to create or to invoke.

### E11. Idle timeout and session reuse

Runtimes: `hr_v2_idle_60` (`idleRuntimeSessionTimeout` 60 s, the minimum) and the baseline
(900 s).
Hypothesis: a follow-up within the idle timeout reuses the microVM (about 0.2 s), a
follow-up after the 120 s memory reclaim pays page-ins but no restore, and a follow-up after
the idle timeout restores a new microVM with the same session id and the full first-request
cost. A long idle timeout costs little under V2 pricing because idle memory is reclaimed.
Procedure: on each runtime, five sessions each with a follow-up after 30 s, 75 s, 130 s and
(baseline only) 16 minutes.
Measurements: follow-up receipt to handler start; telemetry showing the same process (PID,
monotonic clock, request count) or a new restore.

### E12. Gateway MCP sessions on against off

Fixtures: two AgentCore gateways with IAM inbound auth, `hr-v2-gw-off` and `hr-v2-gw-on`
(`protocolConfiguration.mcp.sessionConfiguration` on the second), each with
`hr_v2_proto_mcp_v2` as an MCP server runtime target using the gateway's role (SigV4).
Hypothesis: with sessions off every `tools/call` lands on a new runtime session of the
target (A23: 21 calls, 21 sessions), so every tool call pays a restore; with sessions on,
one gateway session maps to one target session, so a conversation pays one restore. This is
the largest lever for Profile and Pay.
Procedure: through each gateway, one MCP client session doing `initialize`, `tools/list`
and five `tools/call`, repeated five times; then a second client session.
Measurements: runtime sessions on the target per gateway session (from the target's
records), per-call latency at the client, first call against later calls.

### E13. What a restored instance keeps

Runtimes: none new; read from every answer in E1 to E12.
Hypothesis: every restored instance of one version reports hostname `localhost`, PID 1, the
same `boot_id`, a monotonic clock frozen at the snapshot, and the same first draw from the
language's default random generator; `os.urandom` differs. The snapshot's age (wall clock
at start against at request) grows over the study.
Measurements: counts of distinct values per field per runtime version.

### E14. Outbound work from a restored instance

Runtimes: `hr_v2_out_sts` (`IMPORTS=heavy`, `PRIME=clients`, `OUTBOUND=1`).
Hypothesis: the first outbound call from a restored instance pays credentials (the
container credentials endpoint), DNS and a TLS handshake, about 0.2 to 0.5 s, and the
follow-up on the same session pays none of it. This is the cost that a warm-up call before
the snapshot would try to remove, measured without making one.
Procedure: 25 new sessions, 10 follow-ups.
Measurements: the timed `sts:GetCallerIdentity` on the first and the second request.

## Experiments waiting for Sam's approval

Not run. Each needs a network call made only to warm something.

- W1. A real call before the snapshot: `PRIME=network`, where the start makes one
  `sts:GetCallerIdentity` and one Bedrock `ListFoundationModels` so credentials, DNS answers
  and TLS session state are in the snapshot. Compared with E14. Risk: credentials captured in
  the snapshot expire (agentcore-samples saw 403 hours later).
- W2. Keep-alive requests on an open session (a `/ping`-like request every 60 s) to hold a
  microVM for a user between turns, compared with E11.
- W3. A session opened when the page loads so the restore overlaps the user's typing (the
  AWS blog's tip), which is a warm-up by another name.
- W4. A capacity provider: the control plane now has `create-capacity-provider` (EC2
  instances the account pays for, with an operating system, instance types and networking)
  and runtimes take `capacityProviderConfiguration`. It may be the pre-restored pool the
  research found no trace of, at EC2 prices. Not created: it costs money while idle and is
  outside the POC's shape.

## Sub-agents and order

1. The session builds the shared fixtures: images pushed to ECR, the role, the log delivery
   destination, `create.py`, `invoke.py`, `collect.py`, and the baseline runtime.
2. Sub-agents run in parallel, each on its own runtimes, each writing raw lines and a
   results file under `docs/runtime-v2-evidence/<experiment>/`:
   group A: E1 and E8 (protocols, platforms, bursts);
   group B: E2, E3 (image size, memory);
   group C: E4 (languages);
   group D: E5, E6, E14 (imports, priming, outbound);
   group E: E9, E10, E11 (auth, network, idle);
   group F: E12 (gateways).
   E7 and E13 are computed by the session from everyone's lines at the end.
3. The session merges the results into the three record files, deletes the fixtures, checks
   `uv run -- pytest`, `cdk synth` and `scripts/obo-rollback.sh --check`, and pushes.

## Open questions for AWS this plan can answer or sharpen

From the research's list: 1 (cache warmth, E7), 3 (the decomposition, E1 and E3), 5
(reseeding, E13), 6 (the 120 s reclaim, E11), 8 (gateway sessions with a Runtime target,
E12) and 9 (the token cache, E9). Questions 2, 4, 7, 10 and 11 need AWS.
