# Worker B product-feature handoff

## Completion status

**Features 2 and 6 are implemented and verified.** The user explicitly kept
Feature 4 deferred; it was not started. The checklist in update 01 is complete
for this authorized scope. All work is collected on
`feat/worker-b-teaching-review` for review, not developed on main.

The teaching CLI now uses A's real `.dproj` workspace by default. It supports
source submission, full candidates/evidence, confirmation, aligned corrections,
safe replacement, revision history, save/reopen, backup export, search and review
priority. Validated frozen-model calibration is available; stale or unsupported
estimates are disabled. First predictions remain immutable.

## Branches and source checkpoints

The umbrella branch started from main `a928139`. Feature 2's early verified
adapter/fixture checkpoint is retained on `feat/real-text-teaching-cli` at
`8261882`. Dependent review work is on `feat/efficient-review`; the umbrella branch
collects that work and its later production integration.

Important local source checkpoints:

- `8261882`: typed project contract, teaching CLI, safety fixtures and tests.
- `b152ac7`: review/search/conflict diagnostics, frozen calibration and its driver.
- `80feecb`: merge A's newly published `eaab130` into the feature branch, retaining
  both web and teaching commands.
- `e1fad21`: real workspace adapter, atomic revision/write guards, production
  integration tests, and the implementation measured in the corpus checks.
- `dd54772`: literal source/gloss apostrophes, replacement reasons and native paths
  in the teaching shell, plus its regression test.

The individual teaching branch is an earlier dependency checkpoint; use the
umbrella branch for the complete production flow. No stem-edit experimental branch
was created. Publication/merging into main remains a separate review step.

## What was tested

**129 tests passed, none skipped.** This includes the original 83 tests, A's six
new project/web tests, and B's 40 tests: 14 teaching, seven review, nine calibration,
and ten production workspace integration tests. All seven optional neural tests ran.

Checks cover prediction-before-answer behavior, immutable history, malformed input,
source-ID reuse, Unicode, apostrophes, stale revisions, retries, explicit replacements,
read-only review/calibration, CLI/web stale writers in both directions, failed
atomic saves, reopen, export/restore and malformed audit metadata. CLI tests and
the real smoke flow also run with `-S`, without third-party site packages.

Both bounded Lezgi/Tsez checks passed calibration gates and reconstructed saved
scores/candidates/costs exactly. See [results and limits](06-development-results.md).
Final offline corpus checksum verification and `git diff --check` passed.

## Start a real project

From the repository root, choose a fresh path:

```powershell
.venv/Scripts/python.exe -X utf8 -S -m decipher.app gloss teach init --project runs/my-language.dproj --name "My language" --language Demo
.venv/Scripts/python.exe -X utf8 -S -m decipher.app gloss teach shell --project runs/my-language.dproj
```

Inside the shell:

```text
submit anchors tal mir
predict anchors
correct tree bird
submit plural talum
predict plural
correct tree-PL
submit probe mirum
predict probe
confirm
review 10
search bird
history probe
export runs/my-language-backup.zip
quit
```

Reopen with the same shell command. Each successful change is saved. Source and
gloss words are whitespace segmented; source text and apostrophes are literal.
Use simple sentence IDs without spaces for interactive `submit` commands.
`replace REASON :: WORD-GLOSSES` replaces a different verified answer after a
new prediction. `reload` reopens newer saved work after a stale-client conflict.
`gloss teach --help` lists all one-shot commands and `COMMAND --help` shows options.

A project imported/created through A's UI can be opened with the same CLI:

```powershell
.venv/Scripts/python.exe -X utf8 -S -m decipher.app gloss teach review --project PATH_TO_PROJECT.dproj --limit 10
.venv/Scripts/python.exe -X utf8 -S -m decipher.app gloss teach search --project PATH_TO_PROJECT.dproj --query bird --history
```

The actual smoke project is available locally at
`runs/product-teaching-smoke/demo.dproj`, with its backup and restored copy beside it.
The fixture backend is optional test infrastructure; normal commands do not need it.

## Fit and use calibration

Supply separate complete labeled source/gloss files. Training-source overlaps,
duplicates and alignment exclusions are reported, and fitting/validation sets must
remain nonempty and disjoint. These labels are additional supervision.

```powershell
.venv/Scripts/python.exe -X utf8 -S -m decipher.app gloss teach calibrate --project PATH_TO_PROJECT.dproj --fit PATH_TO_CALIBRATION_TIERS --validation PATH_TO_VALIDATION_TIERS --output runs/my-calibration.json
.venv/Scripts/python.exe -X utf8 -S -m decipher.app gloss teach review --project PATH_TO_PROJECT.dproj --calibration runs/my-calibration.json --limit 10
```

Passing the declared gate enables empirical estimates of **top word-gloss
correctness** for that exact model and development population. It does not make
raw rule scores probabilities. Changed model evidence, context settings or engine
identity make the artifact stale. Insufficient/failed artifacts produce no estimates;
review uses clearly uncalibrated priorities instead. Calibration artifacts are
explicit separate JSON files; preserve them separately if needed with a backup.

## Reproduce the development checks

The following are the exact completed commands. Change both output paths to a new
suffix when rerunning; existing artifacts are protected from overwrite.

```powershell
.venv/Scripts/python.exe -X utf8 -S tools/evaluate_review_calibration.py --language lezgi --run-dir runs/product-review-lezgi-v1 --report-dir reports/product/review-calibration/lezgi-v1
.venv/Scripts/python.exe -X utf8 -S tools/evaluate_review_calibration.py --language tsez --run-dir runs/product-review-tsez-v1 --report-dir reports/product/review-calibration/tsez-v1
```

Defaults are 110 learner-training sentences, 100 calibration-fitting sentences,
the unique development set, and a comparison of the first ten sentence reviews.
The tool verifies pinned corpus checksums and uses real workspaces with context
explicitly off to preserve the frozen baseline condition. It never accesses Gitksan.

Run the test suite on this Windows environment with UTF-8 enabled:

```powershell
$env:PYTHONUTF8='1'
.venv/Scripts/python.exe -m unittest discover -s tests -v
.venv/Scripts/python.exe tools/fetch_corpora.py --collection glossing --corpus lezgi --corpus tsez --verify-only
```

## Integration details for A/reviewers

`teaching.py` defines the injected project/store contract; `workspace.py` binds it
to `project.py`. The optional `teaching` field inside the existing schema-1 `.dproj`
contains immutable predictions, retry receipts and revision reasons. Existing
annotation/corpus records retain A's format, and old projects need no migration.
Export/restore carries that metadata in the existing project ZIP.

The shared API additions are `submit`, optional `expected_revision` and deferred
`persist=False` for an atomic correction-plus-audit save. Normal existing callers
retain their original persistence behavior. The shared save method checks the
opened file identity under an exclusive writer lock. A stale CLI/browser must
reload instead of overwriting newer work. The browser sends its displayed revision
and returns conflict status for stale updates. A lock left after an interrupted
writer is reported and needs explicit recovery; it is not stolen automatically.

`review.py` and `review_calibration.py` are reusable through the same adapter for
future UI widgets. This pass exposes review/search/history through the CLI and
adds the minimal web revision guard; it does not redesign A's UI or claim an
external user trial. Release packaging and that trial remain A-owned work.

No historical reports, corpus manifests, dependencies, reserved-language results,
or default stem-learning behavior were changed. The controlled measurements do
not establish an active-learning gain or unrestricted translation. There is no
remaining B implementation blocker for the authorized Features 2 and 6.
