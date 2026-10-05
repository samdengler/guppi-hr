# AgentCore Runtime V2 cold start: research, 4 October 2026

Two Fable research sub-agents, run from the laptop session on 4 Oct 2026, wrote these
reports (lightly condensed; sources kept). Part 1 covers snapshot restore mechanics (Lambda
SnapStart, Firecracker, language effects). Part 2 covers AgentCore Runtime V2 itself and the
features that change how many restores a workload pays. Inferences are marked. The
experiment plan is built from this file (see `docs/handoff-runtime-v2.md`).

## Main points

- Our measured 2.2 s on a new session's first request is the platform's current V2 floor,
  not an anomaly of our image. An independent test measured a new session on a runtime that
  already had sessions at 1.912 s on V2 against 0.611 s on V1
  (https://dev.classmethod.jp/en/articles/amazon-bedrock-agentcore-runtime-v2-tried/).
  AWS's "about 2 s P75" is a cross-region, client-side cold invoke of an echo agent
  (https://github.com/awslabs/agentcore-samples/pull/2092).
- V2 has no documented pool of pre-restored instances or provisioned capacity; a microVM is
  restored only when an invocation with a new session id arrives. Fewer new sessions is the
  main lever: gateway MCP sessions (restores per gateway session, not per tool call) and a
  long-lived runtime session id per user with a long idle timeout (V2 reclaims idle memory
  after 120 s, so a long idle timeout is cheap).
- Lambda SnapStart (the same family) loads snapshots in 512 KB chunks from a per-host cache,
  a per-AZ cache and S3, and prefetches a recorded working set that builds up over
  invocations; infrequently used snapshots restore slower. Research on Firecracker puts
  page faults on the working set at 40 to 95 percent of post-restore execution. Inference:
  V2 likely has the same cache-warmth effect (first sessions after a deploy slowest), and our
  low volume keeps us on the slow side.
- What the agent controls: everything before `/ping` is in the snapshot; a small first-request
  working set restores faster; a compiled server (Rust, Go) shrinks the working set but not
  the platform floor (Lambda's Rust hello world still restores in 377 ms).
- Python OpenTelemetry id generators draw from `random`, seeded in the snapshot, so restored
  instances emit identical span ids; AWS samples patch the generator to `os.urandom`. Our
  watcher reseeds `random` on a clock jump.
- SDK and IaC: `platformVersion` arrived in botocore/boto3 1.43.95 and AWS CLI 2.36.46;
  CloudFormation has `PlatformVersion`; CDK `CfnRuntime` has a typed prop from aws-cdk-lib
  2.272.0. The devguide's "CloudFormation and CDK do not support it" is stale.
- Per-request Identity call: the March 2026 release note says the runtime caches the
  workload access token for 30 minutes. Inference: the cache is per session, so on V2 every
  restore pays one `GetWorkloadAccessTokenForJWT`. We saw one per request on V1 and V2 (A24),
  which suggests the cache is not working for our JWT setup.

## Part 1: snapshot restore mechanics

### Lambda SnapStart lifecycle

- Init runs at version publish; Lambda snapshots the microVM's memory and disk, encrypts it
  and caches it (https://docs.aws.amazon.com/lambda/latest/dg/snapstart.html). Init plus
  before-snapshot hooks may run up to 130 s or the function timeout. One snapshot per
  published version. Java snapshots unused for 14 days are deleted
  (https://docs.aws.amazon.com/lambda/latest/dg/snapstart-activate.html).
- Storage: 512 KB chunks in S3 (up to hundreds of ms per chunk), a per-AZ L2 cache (single
  digit ms) and a per-host L1 cache (about 1 ms); infrequently invoked functions are evicted
  from L1. Lambda records the chunks each invocation touches and prefetches that working set
  on later restores
  (https://aws.amazon.com/blogs/compute/under-the-hood-how-aws-lambda-snapstart-optimizes-function-startup-latency).
  AWS: "Functions that are invoked infrequently might not experience the same performance
  improvements" (https://docs.aws.amazon.com/lambda/latest/dg/snapstart-best-practices.html).
- USENIX ATC 2023 "On-demand Container Loading in AWS Lambda": per-worker cache median hit
  rate 67 percent, AZ cache 99.9 percent; AZ fetch median 550 µs against 36 ms from S3; the
  same system stores SnapStart memory snapshots (https://arxiv.org/pdf/2305.13162).
  Firecracker itself restores a microVM snapshot in about 4 to 10 ms
  (https://brooker.co.za/blog/2022/11/29/snapstart.html).
- Restore phase: runtime load plus after-restore hooks must finish in 10 s; REPORT shows
  `Restore Duration`; telemetry emits `platform.restoreStart`, `platform.restoreRuntimeDone`,
  `platform.restoreReport` (https://docs.aws.amazon.com/lambda/latest/dg/snapstart-monitoring.html).
- Hooks: Java CRaC `beforeCheckpoint`/`afterRestore`; Python `snapshot_restore_py`
  `@register_before_snapshot`/`@register_after_restore`; .NET `SnapshotRestore`; custom
  runtimes block on `GET /runtime/restore/next`
  (https://docs.aws.amazon.com/lambda/latest/dg/snapstart-runtime-hooks-custom.html).

### What drives restore duration (measured)

- Memory size alone barely moves a trivial restore (Java hello world p50 487 ms at 128 MB,
  475 ms at 10 GB). Touching data captured in the snapshot does: 1,157 ms at 128 MB, 82 ms at
  1,769 MB, 29 ms at 10 GB (https://dev.classmethod.jp/articles/memory-size-is-not-correlate-restore-duration/).
  Inference: page faults are serviced within the CPU share, which scales with memory.
- Restore time tracks resident memory: a 327 MB Rust container restored in 673 to 693 ms, a
  51 MB TypeScript function in 395 ms
  (https://dev.classmethod.jp/en/articles/lambda-snapstart-container-benchmark/).
- Restore has a floor of several hundred ms: Python 3.12 Init 93 ms against Restore 622 ms;
  Rust hello world Init 19 ms against Restore 377 ms
  (https://chariotsolutions.com/blog/post/whats-the-point-of-lambda-snapstart/). It pays off
  when Init takes seconds (Spring Boot 6,334 ms to 182 ms).
- Priming: move heavy work to Init; invoke the handler before the snapshot so its code paths
  and pages are captured (.NET first-request Duration 468 ms to 156 ms)
  (https://aws.amazon.com/blogs/dotnet/blog-improving-snapstart-performance-in-net-lambdas).
- Uniqueness: Lambda reseeds the kernel RNG on restore via VM Generation ID; connections made
  in Init are not guaranteed; credentials come from a container credentials endpoint so they
  do not expire in the snapshot (https://docs.aws.amazon.com/lambda/latest/dg/snapstart-uniqueness.html).

### SnapStart and container images

Lambda supports SnapStart for container images since July 2026. AWS base images for Java,
Python and .NET behave like zip functions; other images need
`LABEL com.amazonaws.lambda.feature.snapstart="Allow"` or the restore protocol
(https://aws.amazon.com/about-aws/whats-new/2026/07/aws-lambda-snapstart-container/,
https://www.infoq.com/news/2026/09/lambda-snapstart-container-image/). AWS gives no number
linking image size to restore time.

### Firecracker snapshot and restore

- A snapshot is a memory file and a vmstate file; restore performance "depends on the memory
  size, vCPU count and emulated devices count". The guest wall clock continues from the
  snapshot; VMGenID lets Linux 5.18+ reseed; vsock connections close on resume
  (https://github.com/firecracker-microvm/firecracker/blob/main/docs/snapshotting/snapshot-support.md).
- Memory is mapped `MAP_PRIVATE` (kernel per-page faults) or served by a userfaultfd handler,
  which lets the host prefetch a working set or pull pages from a chunk store
  (https://github.com/firecracker-microvm/firecracker/blob/main/docs/snapshotting/handling-page-faults-on-snapshot-resume.md).
- REAP (ASPLOS 2021): page faults are 95 percent of post-restore function processing; working
  sets 8 to 99 MB, 97 percent identical across invocations; prefetching the recorded set cut
  cold start 3.7 times (https://arxiv.org/abs/2101.09355). FaaSnap (EuroSys 2022): a hello
  world takes over 200 ms after restore against 4 ms warm; fault cost 13.3 µs disk-backed,
  3.7 µs from page cache. PASS (ATC 2024): faults are 40 to 60 percent of SnapStart execution
  time; a cached snapshot is still about 30 percent slower than warm
  (https://usenix.org/system/files/atc24-pang.pdf). Network-backed faults cost 50 to 200 µs
  per page; a 24 MB working set faulted serially at 200 µs is about 1.2 s (inference).

### Language effects

- A snapshot removes interpreter start, imports and JIT; what remains is faulting in the
  pages one request touches. The useful property becomes "pages touched per request".
- Python: modules, bytecode and a framework heap spread over many pages; one request touches
  the interpreter, event loop, HTTP parsing, JSON and logging. CPU share governs fault service.
- Java and .NET: JIT state is captured, so invoke priming matters most.
- Rust or Go: cold starts are already 10 to 60 ms without snapshots, so a snapshot saves
  little init and still pays the restore floor; a compiled server touches fewer pages per
  request. Rust `ThreadRng` needs a reseed after restore; Go `crypto/rand` reads the kernel.

### Likely components of V2's ~2 s (inference unless cited)

1. Placement and microVM creation for the new session id.
2. Snapshot chunk fetch: per-host cache only if that host restored this version recently;
   otherwise the AZ cache or S3. First sessions after a deploy are likely slowest.
3. Page faults on the working set: plausibly 30 to 80 MB for a Python MCP server's first
   request; the V2 snapshot is trimmed, so file-backed pages also come back on demand.
4. Agent first-request work: reconnects, credentials, DNS, TLS, lazy imports.
5. V1 was 0.6 s because a warm-pool container was already initialized; V2 restores per
   session by design.

### Measurements that separate the components

1. In-guest timeline: wall and monotonic timestamps at startup and at the first request.
2. Page fault counters from `/proc/self/stat` before and after the first request.
3. Working-set sensitivity: the same server with a 0 MB and a 128 MB buffer touched on first
   request.
4. Cache warmth: new-session latency for the first 5 sessions after a deploy, after 50, and
   after 24 hours idle.
5. Language: a minimal Rust MCP server against the Python one.
6. Outbound work timed separately from the MCP `initialize`.
7. Concurrency: 10 new sessions at once against one at a time.

## Part 2: AgentCore Runtime V2

### How V2 works

- `platformVersion` (`V1` or `V2`) is a field on the runtime; omitted on create means V1,
  omitted on update keeps the current value; only `get-agent-runtime` returns it
  (https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-how-it-works.html).
  SDK support: botocore/boto3 1.43.95, AWS CLI 2.36.46. GA 18 Sep 2026.
- One snapshot per runtime version an endpoint points to, taken on the first healthy
  `/ping` (120 s limit); old snapshots are deleted after their sessions end (up to 8 h).
- Each new session restores from the snapshot; hostname `localhost`, PID 1; monotonic time
  frozen across restore; sockets do not survive, client caches do
  (https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-v2-optimize.html).
- Elastic memory: sessions start small, page in on demand; idle memory is reclaimed after
  120 s (https://aws.amazon.com/bedrock/agentcore/pricing/).
- No pre-restored pool or provisioned capacity is documented ("No pre-provisioning
  required", "Scale to zero"). The "committed baseline" coming soon is a pricing commitment.
- Cache warmth after a deploy is not documented. Classmethod measured the first invoke after
  READY at 1.8 to 2.2 s across image sizes.
- AWS's benchmark: 5,000 cold invocations per image size, client in us-west-2 calling
  us-east-1, an echo agent; cold P75 V1 against V2: 200 MB 5.37 s against 1.94 s, 2 GB
  29.72 s against 2.16 s; warm invoke 152 ms
  (https://github.com/awslabs/agentcore-samples/pull/2092).
- Pricing: V1 $0.0895 per vCPU-hour and $0.00945 per GB-hour; V2 $0.1276 and $0.0169, billed
  per second on actual consumption with idle reclaim. Inference: V2 wins for mostly idle
  sessions.

### Knobs and constraints

- `lifecycleConfiguration`: `idleRuntimeSessionTimeout` default 900 s, `maxLifetime` default
  28,800 s, both 60 to 28,800 s on microVMs; a stopped session's id restores a new microVM on
  the next invoke (https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-lifecycle-settings.html).
- `/ping`: set `time_of_last_update` only on a status change. A value initialized at module
  load is the snapshot time on V2 and can make a fresh instance look long idle
  (https://github.com/aws-samples/sample-cloud-native-nanoclaw/pull/46).
- Environment variables: 2.5 KB for containers, 1.5 KB for direct code on V2 (4 KB on V1).
- Protocols and ports: HTTP 8080, MCP 8000 `/mcp`, A2A 9000, AG-UI 8080. Session header:
  `Mcp-Session-Id` for MCP, `X-Amzn-Bedrock-AgentCore-Runtime-Session-Id` otherwise.
- arm64 only; x86 coming soon. VPC "may increase session startup times".
- Snapshot-safe crypto libraries do not reseed after restore on AgentCore; use `os.urandom`
  or `secrets` in the handler.
- CloudFormation `PlatformVersion` exists; CDK typed prop from 2.272.0; Terraform lacks it;
  the AgentCore CLI and starter toolkit do not expose it.

### What practitioners report

- awslabs/loom PR 62: needs `boto3>=1.43.95`; no runtime code changes.
- sample-agent-platform PR 42: OTel id generators (including ADOT's X-Ray one) use Python
  `random`, seeded in the snapshot, so parallel agents emitted identical span ids; fixed by
  an `os.urandom` generator and reseeding `random` per request. PR 43 runs V1 and V2 side by
  side; replays `GetAgentRuntime` into `UpdateAgentRuntime` and strips
  `requireServiceS3Endpoint`.
- sentry-javascript 24728: Node `crypto.randomUUID()` cache and OpenSSL DRBG state are in the
  snapshot, so ids collide across instances for up to an hour after a deploy.
- agentcore-samples: persistent filesystem sample median 5,529 ms V1 against 4,185 ms V2;
  strands-bedrock 9,230 ms against 4,512 ms; credentials captured at startup expired hours
  later (403 `ExpiredTokenException`); an audio resampler built at import was restored
  unusable without an error.
- classmethod (ap-northeast-1): create to READY about 5 s on V1, 188 to 204 s on V2; cold
  start 3.4/5.5/13.6 s on V1 against 2.1/2.2/1.8 s on V2 for 46/335/859 MB images; warm
  invokes 0.15 to 0.21 s on both.

### Paying fewer restores

- Runtime session id reuse: the same id reuses the microVM and resets the idle timer; ids are
  at least 33 characters; the backend owns the user-to-session mapping
  (https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-sessions.html).
  Inference: one long-lived session id per user with a long idle timeout is the main lever.
- Gateway MCP sessions: `protocolConfiguration.mcp.sessionConfiguration.sessionTimeoutInSeconds`
  (default 3,600, 900 to 28,800). "The gateway stores the MCP server target's session ID and
  reuses it on subsequent tool calls"; for Runtime targets, "AgentCore Runtime doesn't need
  to cold-start a new MCP server connection on each request". If the target's microVM stops
  first, calls return a 4xx such as `session not found` and the client must re-initialize
  (https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-sessions.html).
- Gateway HTTP Runtime targets (our agents gateway): the docs do not say how the runtime
  session id is set or propagated.
- AWS's blog tip: start the session when the user engages (opening a chat, typing), not on
  submit.

### Inbound JWT and token caching

- A JWT runtime validates the token, then calls `GetWorkloadAccessTokenForJWT` and passes the
  workload access token to the agent
  (https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-oauth.html).
- Release note (March 2026): tokens cached for their 30-minute validity. Inference: the cache
  is per session, so every V2 restore pays one call. Scope and survival across idle stop are
  undocumented. SigV4 inbound makes no such call.

## Open questions for AWS

1. Does restore latency depend on snapshot cache warmth (first restores after a deploy,
   snapshots idle for hours)?
2. Is any pre-restored pool or provisioned concurrency planned for V2?
3. What does the ~2 s decompose into, measured in-region?
4. Does the platform poll `/ping` on a freshly restored instance, and can a stale
   `time_of_last_update` cause immediate idle termination?
5. Does a restore reseed the kernel CRNG, and is a restore hook planned (as in Lambda)?
6. Is the 120 s idle memory reclaim configurable, and what does the next page-in cost?
7. For gateway HTTP Runtime targets, how is the runtime session id propagated?
8. For gateway MCP sessions with a Runtime target, is a stopped target session re-initialized
   transparently?
9. Is the 30-minute auth token cache per microVM, per runtime or per account, and why do we
   see one `GetWorkloadAccessTokenForJWT` per request?
10. Why does the devguide say CloudFormation and CDK cannot set `platformVersion`?
11. When will the V2 environment variable cap match V1, and when do x86 and larger compute
    arrive?
