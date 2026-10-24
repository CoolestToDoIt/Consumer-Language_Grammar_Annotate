# Self-contained comparison with the original engine

`tools/compare_gloss_engines.py` loads the engine from a trusted local Git
revision without switching branches or modifying the working tree. It adapts
records to that revision's dataclass and falls back to successive corrections
when the reference predates `fit`. It compares complete candidate outputs in
all three modes plus authoritative record order/version, lexicon counts,
paradigms, every rule hypothesis/support set, and ordered selected rules.

For optional online updates it compares each input before feedback, after
feedback, and all probes after every update. Only public examples reach
prediction. Results contain resolved reference commit/source hashes, current
source identity, corpus hashes, selected IDs, and a digest of matched records.
No ignored baseline prediction artifacts are required. Existing profiling tools
and tests separately cover schema-1 checkpoint/reload equivalence.

Compared against original shared base
`524163c64150cf06773c0afcc1a28ea4d797774c`:

| Workload | Matching prediction records | Complete evidence matches |
|---|---:|---|
| Lezgi 500 seeds, 100 updates, 30 probes, all modes | 9,690 | After seed and every update |
| Tsez 500 seeds, 100 updates, 30 probes, all modes | 9,690 | After seed and every update |
| Lezgi all 634 seeds and all 88 nonoverlapping dev sentences | 264 | After seed |

These runs establish output/state equivalence, not a new timing comparison.
Reports are `{lezgi,tsez}-original-revision-comparison.json` and
`lezgi-full-original-revision-comparison.json`.

```sh
python3 tools/compare_gloss_engines.py \
  --reference-ref 524163c \
  --train data/glossing/lezgi/lez-train-track1-uncovered \
  --dev data/glossing/lezgi/lez-dev-track1-uncovered \
  --limit-train 500 --limit-dev 30 --online-updates 100 \
  --output reports/gloss/performance/NEW-comparison.json --timeout 120
```

Use fresh output paths. The bounded prefix avoids repeating the original
unbounded full Tsez sorting workload. A missing revision, insufficient training
records, deadline failure, or first mismatch produces a nonzero exit and a
report identifying the incomplete stage.
