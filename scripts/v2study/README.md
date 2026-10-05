# Runtime V2 cold start study: fixtures

The plan is `docs/runtime-v2-experiments.md`; results are recorded in `docs/latency-log.md`,
`docs/aws-feedback.md` and `docs/decision-log.md`, with raw lines under
`docs/runtime-v2-evidence/`. Everything here is isolated from the HR stack: its own ECR
repository (`hr-v2-study`), execution role (`hr-v2-study-runtime`), vended log group
(`/aws/vendedlogs/bedrock-agentcore/hr-v2-study`) and runtimes named `hr_v2_*`.

- `setup.sh` creates the repository, the role and the log delivery destination;
  `setup.sh teardown` removes them once the runtimes are gone.
- `images/python`, `images/node`, `images/go`: the probe servers. Build and push with
  `docker build -t <repo>:<tag> images/python` (arguments `PAD_MB`, `NOPYC`). Tags used:
  `py`, `py-nopyc`, `py-pad500`, `py-pad1500`, `node`, `go`.
- `create.py`: create, update, list and delete test runtimes (needs boto3 1.43.95 or newer
  for `platformVersion`; `uv run --no-project --with 'boto3>=1.43.95' python ...`).
- `invoke.py`: send new sessions, follow-ups and bursts with `InvokeAgentRuntime`, one JSON
  line per request.
- `collect.py`: join the lines with the runtime's own records and print the tables.

The probe answers one JSON document: wall and monotonic clocks at start and at the request,
page faults and RSS from `/proc`, `boot_id`, hostname, PID, random draws, and the time the
handler's own work took. A restore shows as a wall clock far ahead of the monotonic clock.
