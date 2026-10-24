# Feature 4: approved internal-stem-edit experiment

## Authorization and starting point

The user has now explicitly requested Feature 4 after bringing in Worker A's main
changes. This supersedes the earlier deferral; those earlier notes remain historical.
`git fetch origin` found main at A's `eaab130`, already included in the Worker B
product branch. `git merge --ff-only origin/main` confirmed it was up to date.

Experiment branch: `experiment/gloss-internal-edits`, created from integrated
product checkpoint `bc0a5df`. The production branch and main are not experimental
work branches. Starting suite: 129 tests, with verification running before changes.

The objective is to decide whether internal spelling changes improve prediction
of unfamiliar forms whose meanings already have teacher-provided anchors. It is
not a promise that the experiment will win, and not approval to change defaults.

## Ordered checklist

- [x] Fetch/check A's main changes and create the separate experiment branch.
- [x] Read the existing proposal, current learner/reader and evaluation interfaces.
- [x] Freeze the model, data, budget and decision criteria below before corpus runs.
- [x] Verify the full starting regression suite and define the targeted fixtures.
- [x] Implement an explicitly prepared, version-checked inference overlay in a new
      module, preserving the base model and its schema-1 checkpoints.
- [x] Test replacement/insertion/deletion, competing tags, Unicode, grounding,
      duplicates/revisions, stale-overlay rejection, read-only prediction,
      checkpoint reconstruction, and exact baseline equivalence without internal evidence.
- [x] Build a Windows-compatible isolated comparison runner with a hard 120-second
      child-process deadline and memory measurement with explicit units.
- [x] Run full pinned Lezgi and Tsez training/development comparisons with the same
      examples and 512 total rule slots; record candidates and private scoring separately.
- [x] Reconstruct scores and changed-word/grounded-error diagnostics from artifacts;
      report runtime, memory, regressions and incomplete runs honestly.
- [x] Apply the frozen adopt/reject criteria, run combined regressions, and document
      results, commands and limitations in this folder. Do not promote the default model.

## Frozen model condition

The base is the current `GlossLearner(mode='rules', max_rules=512,
paradigm_window=32, contextual=False)`. Existing prefix/suffix hypotheses and
new internal hypotheses compete for **512 total slots**, not 512 each. All
authoritative training annotations and their original order are identical.

Within each existing bounded lexical paradigm, infer one changed middle block
with at least one unchanged Unicode codepoint on each side. Reuse the existing
prefix/suffix gloss transformations and lexical-key grounding rule. Include both
directions. Rank the union by descending distinct-lexeme support, ascending edit
complexity, then the existing six-field rule tuple (internal uses the source-side
name `internal`). No minimum-support tuning or extra unreported rule pool.

When several edit positions recover the same anchor under one rule, count that
anchor once. Distinct hypotheses retain separate baseline-style votes. Known-form
candidates remain exactly the base model's candidates. The overlay is explicitly
prepared after teaching and rejects an outdated base version/configuration;
prediction never prepares a deferred cache. Checkpoints save only the unchanged
base model; the overlay is deterministically reconstructed after load.

Internal spelling decompositions are surface hypotheses, not gold morpheme
segmentations. Repeated characters may permit more than one edit location. Inputs
are NFC-normalized by the existing reader; spans are codepoints, not phonemes.
Scores remain uncalibrated. No contextual model, neural training or new root meanings.

## Frozen data and reporting

Use the checksum-pinned full Lezgi and Tsez training/development files. Keep the
offline baseline's duplicate-record weighting; disclose within-split duplicates
and source conflicts rather than silently changing historical membership. Exclude
exact training-source overlaps from development. Do not inspect Gitksan or any
corpus test labels. Settings are fixed before outcomes; no development-result
tuning of edit bounds, ranking or budgets.

Run each language in a fresh subprocess with a hard **120-second** wall deadline.
Report parsing, base fitting, overlay preparation, prediction and verification
times separately. Peak RSS/working-set bytes describe the process containing
both base and overlay and its artifacts, not isolated per-component allocations.

Report word/OOV/grounded-OOV/nonpunctuation/sentence accuracy, coverage and top-five
results; raw correct/incorrect transitions; known-form output equality; hypothesis
counts/budget displacement; and grounded failures classified by absent root
recovery, missing grammatical output or ranking. Gold is private scoring data only.
Save full artifacts under ignored runs/ and compact reports in a new experiment
directory; historical reports and production evaluation/session code stay fixed.

## Predeclared decision criteria

Recommend an adoption review only if both full runs finish and all correctness
tests pass, and all of the following hold:

- Overall word accuracy drops by no more than **0.5 percentage points** on either
  language; known-form candidate equality is exact.
- Mean grounded-OOV accuracy gain is at least **1 percentage point**, with neither
  language losing more than **0.5 points** on that metric.
- Each overlay prediction pass is at most **2× baseline time or adds at most
  0.25 seconds** (the absolute allowance avoids unstable tiny-denominator ratios).
- Measured process peak is at most **512 MiB** and the 120-second deadline holds.

Otherwise reject default adoption and retain the frozen baseline. These are
declared engineering/research screening criteria, not statistical significance
tests. Passing would still require a separate approval before any default-model
change. A negative result is a complete, useful Feature 4 outcome.

## Starting verification and concrete fixtures

All 129 starting tests pass, including the optional neural tests. Fixtures are
defined before the overlay: `man/men` transferring to grounded `tal/tel`; reverse
transfer from an observed plural; middle insertion/deletion; repeated deletion
positions recovering one anchor; competing plural/dual tags; accented Unicode;
unanchored roots; pure edge morphology with full candidate equivalence; and
duplicate/revised annotations followed by explicit preparation and save/load.

## Completion

Feature 4 is complete as an isolated experiment. All 146 combined tests passed
without skips. Both full corpus runs and independent artifact/checkpoint audits
passed. The frozen decision is **reject default adoption**: Lezgi accuracy did not
improve and Tsez grounded-OOV accuracy fell by 0.619 percentage points. See
[results](03-results-and-decision.md) and [handoff](04-handoff-and-commands.md).
The default learner remains the frozen baseline.
