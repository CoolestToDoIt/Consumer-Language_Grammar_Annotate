# Worker B product features: understanding and ordered checklist

## Starting point

Branch: `feat/worker-b-teaching-review`, created from clean main commit
`a9281397919d9589315c8e43277ad725d81c0755` on 2026-10-24. Remote main matched that
commit when work started. New notes live in this folder; older Worker B notes
remain at their existing paths and are indexed in the parent README.

The application helps a person review source words, teach aligned glosses, and
reopen saved work. It is not fluent sentence translation. The current learner
already supplies deterministic word candidates/evidence and safe corrections;
the previous milestone supplies reproducible evaluation and restartable runs.

## Assignment and boundaries

- Feature 2: real-text teaching CLI. Submit sentences, inspect alternatives,
  confirm/correct complete word-aligned answers, and see updated predictions.
- Feature 6: efficient review. Find unknown/ambiguous items, search, inspect
  annotation history, resolve stale/conflicting corrections safely, and provide
  uncertainty estimates only when a separate calibration has been validated.
- Feature 4: isolated internal-stem-edit experiment. The user explicitly answered
  **“Keep Feature 4 deferred.”** It is outside this implementation pass; no
  experimental branch or learner change will be started.

Worker A owns project persistence, the web UI, contextual modeling, and release
packaging. No project API implementation exists in this checkout. The plan
allows B to develop against a fixture adapter while A builds storage. B will
publish a small typed backend contract and runnable fixture-backed teaching flow;
it will not silently introduce a competing production workspace format.

Existing engine behavior, checkpoint schemas, historical reports and held-out
language boundaries remain fixed. Gitksan stays reserved. Raw model scores must
not be displayed as calibrated confidence percentages.

## Ordered checklist

- [x] Read the feature plan, current state, prior experiment proposal, and relevant
      reader/learner/CLI/session code; inspect branches and working tree.
- [x] Create a fresh feature branch from main before editing files.
- [x] Separate new progress notes from the earlier milestone.
- [x] Establish the existing test baseline and define user-flow/safety fixtures.
- [x] Define the project adapter contract, prediction/annotation records, revision
      conflicts and idempotent correction semantics; document the handoff to A.
- [x] Implement teaching commands and interactive flow against a fixture adapter:
      submit, predict/evidence, confirm, correct, save/reopen and export.
- [x] Implement deterministic review ordering, Unicode search, annotation history,
      and safe stale/conflicting-answer handling through that contract.
- [x] Implement separate frozen-model calibration and held-out validation; require
      sufficient evidence and invalidate calibration after a model change.
- [ ] Verify complete teaching/review/reopen flows and error recovery without
      third-party dependencies; preserve all existing regressions.
- [ ] Run bounded Lezgi/Tsez review/calibration checks, record data membership,
      label budgets and honest outcomes, and leave historical results untouched.
- [x] Resolve Feature 4 scope: keep it deferred at the user's explicit request;
      retain the default learner and do not start the experiment.
- [ ] Record final commands, tests, remaining A integration needs and per-feature
      status; keep all work on feature/experimental branches for review.

## Design decisions to verify before implementation

Prediction inputs contain only ID and NFC-normalized source words. A saved first
prediction is immutable and precedes its answer. Confirming requires a complete,
current prediction; correcting must supply one nonempty gloss per word. Existing
IDs cannot silently change source text. Revisions use the version the person
actually reviewed, so another correction cannot be overwritten accidentally.

Uncertainty calibration uses explicit labeled calibration data and disjoint
validation sources with a frozen model, not only the errors selected for review.
Unknown-first/ambiguity ordering remains clearly labeled as a heuristic whenever
validated calibration is unavailable or stale. Data supplied for calibration is
reported as additional supervision and never becomes a hidden learner input.
