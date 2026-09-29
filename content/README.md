# Synthetic HR policy corpus

The documents in `hr/` are invented for the HR Super Agent MVP (decision D5). They describe a
fictional airline employer and contain no real company policy. `scripts/seed-content.sh`
syncs `content/hr/` to `docs/hr/` in the content bucket; `scripts/ingest.sh` indexes it.
