# Exact indexed spelling analogy

Worker A follow-up on `feat/gloss-engine`, based on commit `24a5a38`. This changes candidate search cost without changing the gloss learner, dataset, labels, model configuration, similarity function, or tie-breaking rule.

## Change

The learner now builds a trigram-to-known-forms index when each new surface form is released through `correct` or `fit`. For an unseen query, overlap counts come from those postings. Only known forms with positive overlap need comparison: every such form has a higher Jaccard score than any zero-overlap form. If no form overlaps, the lexicographically first known form preserves the old all-zero tie behavior.

Jaccard is computed as `intersection / (query_size + known_size - intersection)`, exactly matching the old set-union denominator. Shared trigrams are counted once because both the word grams and posting memberships are sets. Candidate ranking uses the same float score and lexical tie-break. The index is prepared during correction/training, not mutated during prediction.

## Same-data comparison

| Dataset | Previous analogy pass | Indexed pass | Speedup | Previous process peak RSS | Indexed peak RSS |
|---|---:|---:|---:|---:|---:|
| Lezgi, full development | 0.2657 s | 0.0215 s | 12.4× | 34.0 MiB | 36.7 MiB |
| Tsez, full development | 7.7850 s | 0.4619 s | 16.9× | 177.7 MiB | 190.6 MiB |

Measurements are sequential single-run diagnostics on Python 3.12.4 / macOS 14.5 / arm64, without overlapping benchmark/test jobs. Process peak RSS includes training, original and reloaded models, and verification; it is not an isolated model allocation. No statistical timing interval is claimed.

The extra index trades some training work and memory for much faster analogy inference. Full Tsez training measured 0.839 s versus the earlier 0.789 s, and reload 0.857 s versus 0.829 s. Only inference speed is the improvement claimed in this patch.

## Output and checkpoint compatibility

- Full prediction/candidate artifacts for **all three modes** match exactly on full Lezgi and full Tsez development data, including glosses, scores, ordering, and evidence. Both models also match their complete artifacts after checkpoint reload.
- Lezgi output SHA-256: `f02d95f3db048b4c772a4e4c3215879b481659983fcd080692737eae5ff1e927`.
- Tsez output SHA-256: `02a931fc9a5960a0349bf056002dedd7032d4b73741aa1c3e1457c7baab0e3d0`.
- The public constructor, `fit`, `correct`, `predict`, `save/load`, and candidate output fields are unchanged.
- Checkpoint schema remains version 1. The postings are derived from authoritative corrected records on reload, not stored in an incompatible file format.
- Existing baseline reports remain unchanged. New raw candidates are local under ignored `runs/gloss-engine-indexed/`.

## Verification

50 tests pass in the neural-enabled environment (previous 45 plus five index tests). New tests compare against the exhaustive old Jaccard search using a fixed randomized Unicode vocabulary and hundreds of unseen queries; cover zero-overlap ties, identical trigram sets, revisions, duplicate updates, appended fitting and reload; check that unrelated forms are not scanned; and prove unknown queries do not mutate postings or other learned state.

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m unittest discover -s tests -p test_gloss_performance.py -v
```

## Reproduction and handoff

Use fresh output paths; the profiler will not overwrite reference artifacts.

```sh
.venv/bin/python tools/profile_gloss.py \
  --train data/glossing/tsez/ddo-train-track1-uncovered \
  --dev data/glossing/tsez/ddo-dev-track1-uncovered \
  --strategy bulk --timeout 120 \
  --output reports/gloss/performance/tsez-index-rerun.json \
  --predictions runs/gloss-index-rerun/tsez.jsonl \
  --reference-predictions runs/gloss-engine-optimized/tsez-full-predictions.jsonl
```

Worker B needs no interface or session changes for this optimization; incorporate the engine commit through the existing branch workflow. The index is internal. This patch touches only Worker A-owned engine/tests/performance notes and artifacts. No evaluator, CLI, session, source manifest, neural module, or shared README/CURRENT file is changed. Gitksan remains reserved and was not accessed.
