# Exact incremental correction ranking

On the same Tsez training order, seed 3,000 sentences then apply the next 100
annotations individually. Five development probes exclude all seed/stream
source sentences. Each trace includes predictions before feedback, after
feedback, and every probe after each correction. No held-out test data is used.

| Measurement | Full sorting | Incremental sorting |
|---|---:|---:|
| Total correction time | 7.4378 s | 0.04784 s |
| Median correction | 73.962 ms | 0.493 ms |
| p95 correction | 76.795 ms | 0.929 ms |
| Rule ranking time | 7.4171 s | 0.02922 s |
| Ranking passes | 100 | 80 |

These are single-run diagnostics, not replicated timing estimates. Total
correction time improved approximately 155× on this prefix. Predictions,
candidate scores/order/evidence, and versions match exactly across all 705
trace rows. SHA256:
`b35560c319dd72ca456161ef4990d6fb1ce4011d35f5dba4f6e220f8a88f0a07`.
Both checkpoints reproduce their final state and probe predictions.

Appending evidence can only increase a rule's support. Therefore the next top
K must come from the previous top K plus rules whose support changed. Sorting
that union by the original complete ordering is exact. Repeated observations
with no support change need no ranking. Revisions reset derived state and replay
authoritative annotations, so support decreases are handled by reconstruction.
No ranking work moves into prediction; checkpoint schema and public API remain
unchanged. New derived state stores the last top K and pending changed rules.

Raw measurements: `tsez-corrections-baseline.json` and
`tsez-corrections-incremental.json`. Local traces are under ignored
`runs/gloss-engine-online-{baseline,incremental}/tsez-trace.jsonl`.

Reproduce with distinct output paths:

```sh
.venv/bin/python tools/profile_gloss_online.py \
  --train data/glossing/tsez/ddo-train-track1-uncovered \
  --dev data/glossing/tsez/ddo-dev-track1-uncovered \
  --output reports/gloss/performance/NEW.json \
  --trace runs/NEW/tsez-trace.jsonl \
  --reference-trace runs/gloss-engine-online-baseline/tsez-trace.jsonl
```

Tests compare the selected rules against exhaustive sorting after randomized
updates and a revision at bounds 1, 3, 17, and 512. Existing tests cover complete
bulk/sequential state equality, checkpoint reconstruction, and read-only probes.

Full Lezgi and Tsez development artifacts also match the prior indexed-engine
artifacts in all three modes and after reload. Their new reports are
`lezgi-incremental.json` and `tsez-full-incremental.json`.
