# Gloss-engine performance and equivalence

Worker A branch: `feat/gloss-engine`. Shared base: `524163c64150cf06773c0afcc1a28ea4d797774c`. Engine/API commit: `83e70a0`.

This change preserves the learner and corpus semantics. It removes redundant global rule ranking during bulk ingestion and version-1 checkpoint reconstruction. Online `correct()` still prepares inference immediately. No evaluator, CLI, event/session, source-manifest, neural, or shared README files were changed.

## Same-hardware comparisons

| Dataset | Training sentences | Sequential training | Bulk training | Speedup | Old reload | New reload | Reload speedup | Ranking passes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Lezgi, full | 634 | 0.6353 s | 0.0343 s | 18.5× | 0.6389 s | 0.0358 s | 17.9× | 634 → 1 |
| Tsez, prefix | 500 | 1.5942 s | 0.0813 s | 19.6× | 1.6183 s | 0.0862 s | 18.8× | 500 → 1 |

These are single-run diagnostic measurements, not repeated timing distributions or statistical confidence intervals. Both comparisons used the same interpreter, machine, dataset hashes, selected IDs, bounds (512 rules / 32 paradigm window), prediction modes, and profiling script. Comparisons ran sequentially without overlapping test/profiling jobs.

Measured environment: Python 3.12.4, macOS 14.5, arm64. The baseline loaded the unmodified shared-base engine; reports include engine source SHA-256 to identify optimized working-tree code measured before its commit.

## Exact output checks

The saved artifacts cover every predicted development word, all candidate glosses, scores, ordering, evidence, IDs, and source tokens for **memory, analogy, and rules**. Lezgi used the full nonoverlapping development set; Tsez prefix used the first 30 nonoverlapping development sentences. The optimized run compares decoded JSON records against the original artifact, rather than merely comparing accuracy. Reloaded models are checked against every saved candidate record as well.

| Dataset | Identical baseline/optimized candidate-output SHA-256 |
|---|---|
| Lezgi | `f02d95f3db048b4c772a4e4c3215879b481659983fcd080692737eae5ff1e927` |
| Tsez prefix | `c184f2b3a6d381db15820d181384918f1acd56633e7f93f9daaf1d165d2da038` |

Full candidate artifacts remain local under ignored `runs/gloss-engine-baseline/` and `runs/gloss-engine-optimized/`. Compact JSON reports here contain their hashes. Existing `reports/gloss/lezgi-dev.*` and corpus test reports were left unchanged.

## Bounded full Tsez engine run

Completed within the 120-second deadline: 3,547 training sentences / 37,396 annotated words, and 445 development sentences / 4,761 words. No alignment exclusions or source overlaps occurred in this run.

- Bulk training: 0.789 s, including 0.650 s ingestion/induction and 0.116 s ranking (one pass).
- Checkpoint save: 0.172 s; reload: 0.829 s. Reloaded candidate outputs match exactly.
- Process peak RSS: 186,351,616 bytes (177.7 MiB). This is a process lifetime peak including both original and reloaded models, not an isolated per-model allocation.
- Final evidence hypotheses: 77,448; prepared rules: 512.

There is no full-size pre-change Tsez timing or candidate artifact: the earlier evaluation was interrupted. Do not infer an exact full-size speedup or claim full-size old/new output equivalence. The exact old/new comparison is the declared 500-sentence prefix.

The remaining dominant profile phase is spelling analogy: 7.785 s per complete development pass, versus 0.091 s for rule prediction. The profile repeats prediction after checkpoint reload for verification; that extra pass is validation overhead. Production evaluation/report generation belongs to Worker B, not this profiler.

## Interface and behavior

`GlossLearner.fit(records)` consumes an iterable of `GlossExample` records in order and returns `self`. It appends to existing state and preserves duplicate/revision semantics and the version counter. It prepares rule state before returning. If a record/iterator fails, the successful prefix stays applied and prepared before the exception propagates. It is not a concurrent training/inference API.

Existing `correct`, `predict`, constructor, `save`, `load`, diagnostic attributes, rule bounds/ranking, lexical grouping and schema-version-1 files remain compatible. `load` now rebuilds counts through bulk fitting and restores the stored version, which may differ from the number of authoritative records after revisions.

## Validation

45 tests pass in the neural-enabled virtual environment (35 existing + 10 new engine tests). New coverage checks all modes and bounded rankings; full learned-state/candidate equality; duplicate/revised feedback; appending and empty batches; interrupted/invalid input with prepared partial state; immediate post-fit corrections; handcrafted legacy files and duplicate-ID rejection; and save/load/read-only prediction.

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m unittest discover -s tests -p test_gloss_performance.py -v
```

The test suite asserts ranking-pass counts instead of brittle wall-clock thresholds. Both measured bulk-training comparisons exceed the 5× profiling target.

## Reproduction

Use fresh output paths: the profiler refuses to overwrite baseline files. The original baseline can be recaptured in a separate checkout at the shared base with this profiling script copied in; keep the baseline engine unchanged. Running `--strategy sequential` on the optimized branch still measures per-record training, but its checkpoint loader is already optimized and does not reproduce the old reload implementation.

```sh
.venv/bin/python tools/profile_gloss.py \
  --train data/glossing/lezgi/lez-train-track1-uncovered \
  --dev data/glossing/lezgi/lez-dev-track1-uncovered \
  --strategy bulk --timeout 120 \
  --output reports/gloss/performance/lezgi-bulk-rerun.json \
  --predictions runs/gloss-engine-rerun/lezgi.jsonl \
  --reference-predictions runs/gloss-engine-baseline/lezgi-predictions.jsonl
```

For a Tsez prefix comparison, use the Tsez training/development paths and `--limit-train 500 --limit-dev 30`. For the full run omit those limits. `--cprofile runs/NAME.prof` optionally captures instrumented training call statistics; do not directly compare its inflated timing to uninstrumented runs.

## Worker B handoff

Cherry-pick engine commit `83e70a0` once available in your checkout, or merge the local `feat/gloss-engine` branch through the agreed workflow. Change offline evaluator/CLI training loops to `model.fit(training)`. Keep online updates on `correct`. No event, checkpoint-wrapper, or metric API changes are required by this patch. This branch has not been pushed by Worker A.

Worker B owns source-only production evaluation, online resume, manifests, metric reconstruction and the bounded development matrix. Gitksan remains unevaluated; its dev/test labels were not accessed by this work.
