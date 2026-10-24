# Near-complete individual-correction workloads

Start with ten training sentences and individually correct every remaining
training sentence, predicting each input before its label arrives. Predict five
fixed development probes before any updates and after every correction. Probe
sources exclude all support and stream source strings. These are direct-engine
performance diagnostics; they do not replace production online evaluation or
establish an accuracy-versus-supervision claim.

Tsez: 3,537 corrections, 24,764 trace rows, 2.006 seconds total correction time.
Median 0.584 ms, p95 0.848 ms, maximum 27.266 ms. The final model has 3,547
authoritative records, 77,448 rule hypotheses, and 512 prepared rules. Ingestion
took 0.411 seconds and ranking took 1.551 seconds across 3,091 ranking passes.
Process peak RSS was 185,679,872 bytes including original and restored models.
Checkpoint reconstruction preserves authoritative records, ordered rules,
version, and final probe candidates exactly.

Lezgi: 624 corrections from the same ten-sentence seed protocol. See
`lezgi-full-corrections.json` for latency samples, counts and reconstruction
checks. Both reports completed within the declared 120-second deadline.

These are single runs, with no full-size pre-optimization online trace or timing
comparison. The earlier 100-correction trace is the exact old/new online
comparison. The full streams exercise many more incremental rank transitions;
unit tests separately compare selection with exhaustive sorting and induction
with the original complete evidence-building loop.

Reports: `tsez-full-corrections.json`, `lezgi-full-corrections.json`.
Raw traces remain local under ignored `runs/gloss-engine-full-corrections/`.

```sh
.venv/bin/python tools/profile_gloss_online.py \
  --train data/glossing/tsez/ddo-train-track1-uncovered \
  --dev data/glossing/tsez/ddo-dev-track1-uncovered \
  --seed-sentences 10 --updates 3537 --probes 5 --timeout 120 \
  --output reports/gloss/performance/NEW.json \
  --trace runs/NEW/tsez-trace.jsonl
```

For Lezgi use its corpus paths and `--updates 624`. Outputs must be fresh paths.
