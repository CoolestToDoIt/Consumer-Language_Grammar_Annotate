# Feature 4 handoff and commands

## What is done

Worker A's published main checkpoint `eaab130` was already an ancestor of the
integrated Worker B branch. Fetching and merging `origin/main` reported already
up to date. Feature 4 then ran on **`experiment/gloss-internal-edits`**, starting
from `bc0a5df`; no experimental work was put on local main or the product branch.

The [ordered checklist](01-plan-and-frozen-protocol.md) is complete. The new
experimental overlay, tests, bounded comparison runner, independent artifact
auditor and reproducible development reports are delivered. All 146 combined
tests pass without skips; both full language runs and artifact audits pass.

The outcome is **reject default adoption**, for the reasons in
[results and error analysis](03-results-and-decision.md). This completes Feature 4
as assigned. There is no remaining Worker B implementation step for this
experiment. The code is isolated and the default model stays at the evaluated
baseline. Any future model iteration should have a new frozen protocol and
separate result paths.

## Files to review

| File | Purpose |
|---|---|
| `decipher/gloss_internal.py` | Explicitly prepared internal-edit overlay, stale-state guard and checkpoint reconstruction |
| `tests/test_gloss_internal.py` | Eleven linguistic/state/grounding/equivalence fixtures |
| `tests/test_internal_experiment.py` | Six timeout, memory, scoring and decision-gate fixtures |
| `tools/evaluate_internal_edits.py` | Frozen full-data comparison, persisted regression record and adoption decision |
| `tools/verify_internal_edits.py` | Independent saved-artifact scoring, membership and full-candidate replay |
| `reports/gloss/internal-edits/` | Compact versioned results, audits, regression record and decision |
| `runs/internal-edits-v1/{lezgi,tsez}/` | Ignored full manifests, candidate logs, private scoring, rule tables and base checkpoints |

The original learner, product CLI/UI, persistence and online evaluator files have
no experimental changes. Existing schema-1 base checkpoints reconstruct the
overlay; no experimental schema migration is needed. Candidate scores remain
uncalibrated, so the existing product confidence calibration is not transferable
to this experiment.

## Run a fresh reproduction

From the repository root in PowerShell, using the existing `.venv`. The following
uses **v2 paths** so the delivered v1 evidence remains intact. Choose another
unused suffix if those paths already exist. Corpus files must already be present
and match the pinned checksums; the experiment performs no downloads.

```powershell
$env:PYTHONUTF8='1'
.venv/Scripts/python.exe tools/evaluate_internal_edits.py tests --output reports/gloss/internal-edits/regressions-v2.json
.venv/Scripts/python.exe -X utf8 -S tools/evaluate_internal_edits.py compare --language lezgi --run-dir runs/internal-edits-v2/lezgi --report-dir reports/gloss/internal-edits/lezgi-v2 --timeout 120
.venv/Scripts/python.exe -X utf8 -S tools/evaluate_internal_edits.py compare --language tsez --run-dir runs/internal-edits-v2/tsez --report-dir reports/gloss/internal-edits/tsez-v2 --timeout 120
.venv/Scripts/python.exe -X utf8 -S tools/verify_internal_edits.py --run-dir runs/internal-edits-v2/lezgi --output reports/gloss/internal-edits/lezgi-v2/verification.json
.venv/Scripts/python.exe -X utf8 -S tools/verify_internal_edits.py --run-dir runs/internal-edits-v2/tsez --output reports/gloss/internal-edits/tsez-v2/verification.json
.venv/Scripts/python.exe -X utf8 -S tools/evaluate_internal_edits.py decide --reports reports/gloss/internal-edits/lezgi-v2/results.json reports/gloss/internal-edits/tsez-v2/results.json --tests reports/gloss/internal-edits/regressions-v2.json --output reports/gloss/internal-edits/decision-v2.json
```

Run each command only after the preceding command succeeds. The regression
command intentionally enables installed packages so all seven optional PyTorch
tests run; `-S` on the corpus commands shows that the gloss experiment itself
uses only the standard library. Without PyTorch, neural tests skip and the strict
adoption screen records an incomplete regression requirement.

Only `compare` has the frozen 120-second child deadline; tests and independent
artifact audits are separate checks. A timed-out/failed comparison remains marked
incomplete, preserves its last phase and cannot qualify for adoption. The tools
refuse to replace nonempty experiment directories or existing audit/decision/test
outputs. A rejected adoption decision still exits successfully because applying
the decision is a completed operation.

To re-audit delivered v1 artifacts, use the verifier with the v1 run directory and
a fresh output path, for example `reports/gloss/internal-edits/lezgi-v1/recheck.json`.
No original corpus files or new model corrections are needed for that audit.

## Git and integration

Protocol checkpoint: `9afb8b8`. Evaluated implementation checkpoint: `4eb8632`.
The compact result and handoff commit is `32bb612`. At the initial handoff,
changes were local on the experiment branch. The user subsequently authorized
pushing both completed Worker B branches and merging them into main; see
[the publication note](05-publication-and-main-integration.md).

Publishing the experimental code and reports preserves the research record.
It does not select the overlay in the application: the rejected adoption decision
and existing default learner remain in effect.
