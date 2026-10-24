# Worker B: completed backend handoff

## Status

**Worker B's assigned milestone is complete.** All checklist items in update 01
are checked. The implementation adds reproducible evaluation, accurate feedback
budgets, and resumable source-only gloss sessions. Both bounded development
matrices completed, and the final code passed **63 tests** with no skips.

The existing branch name is `feat/gloss-online-evalulation`; its spelling was
preserved. Shared starting commit: `524163c64150cf06773c0afcc1a28ea4d797774c`.
Worker A's bulk-fit interface was already included through `83e70a0`.

Local Worker B implementation commits:

- `ab72592`: experiment manifests, metrics, gloss resume/checkpoint infrastructure,
  CLI controls, and initial integration tests.
- `293ef56`: bounded Windows file-lock retry and normalized source fingerprints.
- `ded160c752e2fe87c70fbed5fa358c1f68bfc304`: final immutable checkpoint archives
  and atomic manifests, plus the final regression tests.

The completed matrices record `ded160c` and the normalized SHA-256 fingerprints
of the core Python implementation. Reports and final notes are a separate handoff
change after those experiments. No push or merge to the shared branch was performed.

## Files delivered

| File | Purpose |
|---|---|
| `decipher/gloss_evaluate.py` | Frozen selections and provenance, duplicate accounting, real candidate metrics, sentence/word label budgets, separate first/probe/retention/recall scores, AUC ranges, latency, and experiment orchestration |
| `decipher/gloss_checkpoint.py` | Standard-library adapter, immutable complete archives, atomic/checksummed manifests, and restore validation |
| `decipher/gloss_app.py` | Bulk training and the `stream`, `resume`, and `report` options |
| `decipher/online.py` | Request/arrival events, model-call timing, optional source/feedback validation, and full UTF-8 event export; existing neural save/load retained |
| `tests/test_gloss_stream.py` | 18 integration tests, including all 18 model/delay/policy combinations and exact restart comparisons |
| `reports/gloss/online/` | Both complete matrices, compact manifest/verification indexes, and the real restart check |
| `plans/updates_b/` | Ordered checklist and plain-language explanations of each development step |

Worker A's engine and tests, shared README/CURRENT, corpus manifests, existing
baselines, synthetic/neural algorithms, dependencies, and English/Turkish reports
were not edited. Gitksan labels were neither fetched nor evaluated.

## What passed

- Full suite: **63 passing tests** = 45 starting tests + 18 new Worker B tests.
  All seven optional neural tests executed successfully.
- Every fixture model/delay/policy run resumed through two interruptions and
  matched uninterrupted predictions, candidate scores/order, model versions,
  answer order, pending state, fixed probes, and final learned state.
- Both real matrices: **18 complete runs each, 36 total**. All saved logs, probe
  snapshots, exported models and reconstructed metrics agree with their checkpoints.
- A real Lezgi CLI run stopped at 37 stream inputs, with 17 stream labels arrived
  and 20 pending. After resume it reached 100 inputs, with 80 labels arrived,
  20 pending, and model version 90. All 158 original events stayed exactly intact.
  Its history, probes and final model match the uninterrupted delay-20 rule run,
  excluding only timestamps and measured durations.
- The CLI stream/resume/report check also ran with `-S`, which disables third-party
  package loading. Glossing needs only the standard library.
- Final Lezgi/Tsez offline checksum verification and `git diff --check` passed.

Validation evidence:

- [Lezgi manifest index](../../reports/gloss/online/lezgi-prefix-v3/manifest-index.json)
  and [18-run verification](../../reports/gloss/online/lezgi-prefix-v3/verification.json).
- [Tsez manifest index](../../reports/gloss/online/tsez-prefix-v3/manifest-index.json)
  and [18-run verification](../../reports/gloss/online/tsez-prefix-v3/verification.json).
- [Real-corpus restart verification](../../reports/gloss/online/resume-verification.json).
- [Readable results and interpretation](2026-10-24-06-development-matrix-results.md).

## Run checks on this Windows checkout

Run from the repository root. The UTF-8 setting handles language characters in
the existing fixtures and is inherited by subprocesses.

```powershell
$env:PYTHONUTF8='1'
.venv/Scripts/python.exe -m unittest discover -s tests -v
.venv/Scripts/python.exe tools/fetch_corpora.py --collection glossing --corpus lezgi --corpus tsez --verify-only
.venv/Scripts/python.exe -S -m decipher.app gloss --help
```

If corpora are absent in another checkout, run the fetch command without
`--verify-only` for the same two `--corpus` choices. Do not include Gitksan.
This machine's Windows Store interpreter required sandbox escalation to launch.
The installed neural tests emit a missing-NumPy warning, but all pass; no
dependency changes were needed.

## Exact completed matrix commands

These commands produced the final `v3` runs. For a rerun, change `v3` in both
output paths to a fresh suffix: existing experiments/reports are protected from
accidental overwrite. The default model list is memory, analogy and rules.

```powershell
.venv/Scripts/python.exe -X utf8 -m decipher.app gloss stream --train data/glossing/lezgi/lez-train-track1-uncovered --dev data/glossing/lezgi/lez-dev-track1-uncovered --run-dir runs/gloss-online-worker-b-20261024-lezgi-prefix-v3 --report-dir reports/gloss/online/lezgi-prefix-v3 --support 10 --stream 100 --delays 0 5 20 --policies all corrections --probe-every 25 --checkpoint-every 25

.venv/Scripts/python.exe -X utf8 -m decipher.app gloss stream --train data/glossing/tsez/ddo-train-track1-uncovered --dev data/glossing/tsez/ddo-dev-track1-uncovered --run-dir runs/gloss-online-worker-b-20261024-tsez-prefix-v3 --report-dir reports/gloss/online/tsez-prefix-v3 --support 10 --stream 100 --delays 0 5 20 --policies all corrections --probe-every 25 --checkpoint-every 25
```

## Try interruption and resume

The following uses a new example directory. `--max-inputs` is an additional input
budget for each invocation; stopping does not drain queued answers.

```powershell
.venv/Scripts/python.exe -X utf8 -S -m decipher.app gloss stream --train data/glossing/lezgi/lez-train-track1-uncovered --dev data/glossing/lezgi/lez-dev-track1-uncovered --run-dir runs/gloss-resume-demo --support 10 --stream 100 --modes rules --delays 20 --policies all --probe-every 25 --checkpoint-every 25 --max-inputs 37

.venv/Scripts/python.exe -X utf8 -S -m decipher.app gloss resume --checkpoint runs/gloss-resume-demo/rules-delay-20-all/checkpoint.json

.venv/Scripts/python.exe -X utf8 -S -m decipher.app gloss report --checkpoint runs/gloss-resume-demo/rules-delay-20-all/checkpoint.json --output runs/gloss-resume-demo/reconstructed.json
```

The actual verified restart used the same options under
`runs/gloss-online-worker-b-20261024-resume-smoke`. Its final reports are retained
locally. The completed matrix artifacts remain in their separate `v3` directories.

## Checkpoint and reporting details

Each `checkpoint.json` points to a uniquely named complete ZIP in its sibling
`checkpoints/` folder and records its checksum. Keep both together. The archive
contains the existing schema-1 gloss model, session/event history, remaining stream
and configuration, private scoring data and fixed probe predictions. Component
checksums, source/order/configuration checks, and a private history replay are
validated before continuation. Historical scores always use the saved predictions;
validation replay does not replace them.

Reports separately expose support and stream sentence/word budgets, teacher
decisions, requested/arrived/revised/superseded/pending answers, and processed
inputs. Probe curves are sampled at inputs 0/25/50/75/100. Sentence and word AUC
each declare their own arrived-answer range. Training recall and fixed support
retention are not counted as unseen accuracy. Full word candidates are retained.

## Limits and integration notes

- The experiment is a deterministic upstream-order prefix, not the full training
  corpus, a replicated language study, or unrestricted translation. Unseen-word
  accuracy and exact sentence accuracy remain substantial limitations.
- Correction-only exposure can depend on the model. In these real prefixes every
  sentence required a correction, so the two policies had identical exposure.
- Continuation intentionally rejects changed core code or changed original input
  files. Original dataset paths recorded in the manifest must remain accessible;
  cross-machine path remapping is not implemented.
- Resume operates on one run. Its `metrics.json` and a fresh `gloss report` reflect
  the resumed state. A previously written matrix-level summary remains a snapshot
  of its original invocation; it is not automatically rebuilt by single-run resume.
- Checkpoint validation replays history and can take longer than an individual
  model call. Reported model latency excludes this work and file I/O. Old immutable
  archive generations are kept locally, including harmless unreferenced generations
  after a failed manifest replacement.
- Lezgi `v1` and `v2` are incomplete file-lock diagnostics. Only `v3` is the final
  matrix. The final format completed both languages without replacement failures.
- The integrator still owns the shared README/CURRENT update and normal branch
  integration. There is no remaining Worker B implementation blocker.
