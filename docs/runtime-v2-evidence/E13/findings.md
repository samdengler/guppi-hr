# E13. What a restored instance keeps: findings

Read by the main session from every probe answer of E1 to E12 (5 October 2026, 00:52 to
02:06 UTC); the per-runtime telemetry tables are in each experiment's `results.md`.

## Hypothesis

Every restored instance of one version reports hostname `localhost`, PID 1, the same
`boot_id`, a monotonic clock frozen at the snapshot, and the same first draw from the
language's default random generator; `os.urandom` differs. The snapshot's age grows over
the study.

## What the answers show

- Hostname `localhost` and PID 1 on every V2 answer (all runtimes, all languages). On V1 the
  hostname is a container id and PID is also 1.
- Two `boot_id` values per V2 runtime version, not one: each version runs from two snapshots
  taken 1 to 2 s apart, and the same two `boot_id` values appear on every V2 runtime in the
  account (two other values on every V1 runtime), so the guest kernel is booted once and
  shared (A32). The two snapshots restore at different speeds (0.1 to 0.3 s apart).
- The monotonic clock is frozen across the restore: `mono_since_start_s` on a new session's
  first request reads about 66.5 s or about 77.3 s on every V2 runtime (the age of the
  process at the snapshot, one value per snapshot) whatever the wall clock says. Within a
  session it advances normally (E11: by the wait between requests). On V1 it reads 3 to 6 s
  while the wall clock says up to 318 s: pool instances are paused, not snapshotted.
- The wall clock jumps forward at the restore: `wall_since_start_s` on a first request grew
  from about 2 minutes right after READY to over an hour at the end of the study. The snapshot
  age made no difference to the restore time (E8: 323 to 1013 s; E7: 30 minutes).
- User-space random state repeats across restored instances; the kernel's does not (A29). Per
  75 answers of one version: Python `random` 6 distinct values, `os.urandom` and `uuid4` 75;
  Go `math/rand` 29 distinct, `crypto/rand` 75; Node `Math.random` 6 and `crypto.randomBytes`
  and `crypto.randomUUID` also 6; `/proc/sys/kernel/random/uuid` 75 everywhere. The
  `first_random` drawn at start has 2 distinct values per V2 runtime (one per snapshot) and 25
  per 25 V1 sessions.
- Memory and CPUs as the guest sees them: `MemTotal` 8 GB and 2 CPUs on every runtime, V1 and
  V2, whatever the image or knobs. V2's elastic memory is invisible from inside.
- Environment variable count and the session header are as sent; the runtime adds its own
  variables (the probe counts 13 to 20).

## Conclusion

The hypothesis holds, with two corrections: a version has two snapshots, not one, and in Node
the repeated state includes the cryptographic generator. For the HR agents this confirms the
restore watcher in `agent/src/hr_agent/prime.py` (reseed `random` when the wall clock jumps
ahead of the monotonic clock) is needed, that OpenTelemetry id generators drawing from
`random` would repeat without it, and that anything derived from a user-space generator
before the first request (tokens, nonces, ids) must be drawn from the kernel instead.
