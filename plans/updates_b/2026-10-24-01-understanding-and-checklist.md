# Worker B: evaluation and resumable gloss experiments

Working branch: `feat/gloss-online-evalulation` (existing branch spelling).
Shared baseline: `524163c64150cf06773c0afcc1a28ea4d797774c`.
Starting HEAD: `24a5a386a04dcaf98f84d1d4aa029f20e81b110c`, which already includes
Worker A's `83e70a0` bulk-fit API and engine handoff. The starting tree was clean.

## Understanding and scope

The research objective is correction transfer to unseen examples, with arbitrary
lexical meanings grounded by teacher answers. This milestone evaluates word-aligned,
source-only real-language glossing, not unrestricted translation. Worker B owns
evaluation, manifests, online event infrastructure, gloss session checkpoints,
gloss CLI wiring, stream integration tests, and compact online reports. Engine,
synthetic/neural algorithms, shared README/CURRENT, and previous baseline reports
stay with their assigned owners. Gitksan remains reserved and unevaluated.

Predictions must precede their answers; due older answers arrive before the next
prediction. Support/stream/probes must be disjoint by normalized whole source.
Historical predictions, candidate ordering, answer arrival order, model versions,
and authoritative annotations must survive restart. Separate stream first guesses,
held-out transfer, and retention. Count sentences and word annotations, and report
requested, arrived, revised, and pending answers independently of teacher decisions.

## Ordered checklist

- [x] Read roadmap, current direction, split ownership, engine handoff, code/tests.
- [x] Establish baseline tests and restore checksum-pinned Lezgi/Tsez inputs.
- [x] Implement frozen selections/provenance and reconstructable metrics/budgets.
- [x] Implement atomic validated gloss checkpoints and CLI interruption/resume.
- [x] Verify delays/policies, revisions, disjointness, read-only probes, invalid
      artifacts, metric reconstruction, and uninterrupted/resumed equality.
- [ ] Run Lezgi then Tsez bounded 18-condition development matrices.
- [ ] Run combined regressions and CLI/integrity checks; publish compact reports
      and exact reproduction/handoff commands.

## Initial environment findings

The local `.venv` uses Windows Store Python 3.13.2 and includes PyTorch. Its
interpreter requires sandbox escalation to launch. Initial 45-test baseline had
43 passes and two Windows cp1252 encoding errors (a combining Unicode fixture and
an arrow printed by the existing stream command). Rerunning with `PYTHONUTF8=1`
passed all 45 tests, including the neural tests. No source change was needed for
those baseline errors.
Lezgi/Tsez were absent and have now been fetched through the pinned source manifest;
all their file checksums verified. No Gitksan data was fetched or inspected.

## How to run the baseline on this Windows machine

```powershell
$env:PYTHONUTF8='1'
.venv/Scripts/python.exe -m unittest discover -s tests -v
.venv/Scripts/python.exe tools/fetch_corpora.py --collection glossing --corpus lezgi --corpus tsez --verify-only
```

The first environment setting tells Python to read and write Unicode consistently.
It avoids failures when language examples contain combining accents or characters
that Windows' default encoding cannot represent.

## Update location

At the user's request, all Worker B development notes now live in `plans/updates_b`.
Later notes will explain each major implementation step, the files involved, how
it was checked, and any remaining limitations in plain language.
