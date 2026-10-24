# Resumable gloss evaluation and integrated main release

Completed on 2026-10-24. Consolidates original updates 22–25 and the final
integration decisions. Current released main is `7b07cdf`, including tested
integration checkpoint `7b95de1`. The push to origin succeeded and local/remote
main matched. Main integration is complete; the earlier pending-approval and
local-only stopping states are historical, not current instructions.

## Combined implementation and release history

Worker B's branch preserves the spelling `feat/gloss-online-evalulation`; its
handoff commit is `c5c81e0`. It adds frozen selections/provenance, whole-source
repeat/conflict accounting, separate first/probe/retention/recall metrics,
sentence/word feedback budgets, actual top-five candidates, declared AUC ranges,
model-call timing, and stream/resume/report CLI controls. Session archives are
immutable and checksummed, with an atomic pointer manifest and bounded retries
for transient Windows locks. See [Worker B's handoff](../updates_b/2026-10-24-07-handoff-and-commands.md).

The branches merged without conflicts on `integration/gloss-workstreams` at
`6713c3f`. Review reproduced an orphan temporary pointer after a partial manifest
write: the old checkpoint stayed valid, but cleanup began too late. Commit
`ad602cb` extended cleanup to include creation/write and added a real partial-write
regression with recovery checks. The combined suite then passed **83 tests**,
including optional neural tests and standard-library CLI checks.

The user requested a stopping point, recorded at `7b95de1`, then explicitly
approved pushing the integration into main. Origin/main had no incoming changes
outside the integration history. Main fast-forwarded from `24a5a38`; status-only
commit `7b07cdf` accompanied the successful push. Feature and integration branches
were retained. No implementation changed after the tested checkpoint; the release
and this consolidation only update documentation.

## Fresh integrated evidence

Both 18-run matrices completed on core commit `ad602cb`: three models × delays
0/5/20 × all-label/correction-only feedback, ten support and 100 stream sentences.
All non-timing metrics match Worker B's historical matrices, excluding source-
dependent hashes/output paths. Frozen selected IDs/source hashes, scoring hashes
and exclusions also match. Pending labels were not drained.

| Immediate all-label final probe word accuracy | Memory | Analogy | Rules |
|---|---:|---:|---:|
| Lezgi | 57.01% | 58.50% | 59.57% |
| Tsez | 30.69% | 35.35% | 41.59% |

All 36 checkpoints, exported events/requests/feedback, exported models and metrics
were checked. Every saved probe/retention/recall candidate was replayed at its
history boundary. These are integrity/equivalence checks, not new model gains or
independent statistical replications. [Integrated summary and verification](../../reports/gloss/online/integration-20261024/summary.md).

A real Lezgi rule run, using the CLI with site packages disabled, stopped at 37
inputs with 17 stream answers arrived and 20 pending. It resumed to 100 inputs,
80 arrived answers, 20 pending, and model version 90. All 158 original events stayed
exactly intact. Complete history excluding timestamps/latencies, model state,
snapshots and reconstructed metrics match the uninterrupted run.

Raw matrices remain local under ignored
`runs/gloss-integration-20261024-{lezgi,tsez}-prefix-v1`; the restart is under
`runs/gloss-integration-20261024-resume-v1`. The local audit script is
`runs/gloss-integration-20261024/verify.py`. Compact verification is tracked;
historical reports are unchanged. Pinned Lezgi/Tsez corpus checksums pass.

## Operating and research boundaries

`fit` prepares bulk state; `correct` applies arriving feedback. Derived engine
indices are not independently serialized. Keep session manifests with their sibling
`checkpoints/` folders. Resume requires the recorded core implementation and
unchanged original dataset paths; cross-machine path remapping is not implemented.
A single-run resume updates its metrics but does not rewrite an earlier matrix
summary. Historical first predictions are never replaced by replay scores.

These are upstream-order development prefixes with limited unseen-word and
sentence accuracy. On these prefixes every stream sentence requested correction,
so both feedback policies happened to receive the same exposure. Gitksan remains
reserved; existing corpus test baselines remain fixed. The overview is not finished.

## Resume and next decisions

Start from `main`, inspect the working tree, and read [CURRENT](../CURRENT.md).
No experiment was left running at the stopping point. Re-run code checks when
implementation changes:

```sh
.venv/bin/python -m unittest discover -s tests -v
python3 tools/fetch_corpora.py --collection glossing --corpus lezgi --corpus tsez --verify-only
```

The next research scope needs a separate decision. The user deferred the internal
stem-edit experiment until integration; completion of integration does not itself
authorize it. The proposal below is preserved for review and remains unimplemented.

---

# Deferred proposal — isolated internal stem edit experiment

Status: deferred by the user until combined integration is complete. No
experimental implementation has started. Implementation still requires user
approval; the completed integration did not approve a change in model behavior. The overview roadmap
explicitly calls for broader morphology, including internal changes. This is
a bounded first experiment toward that item, not a claim of full structural
coverage or completion of the overview.

## Scope and isolation

Create `experiment/gloss-internal-edits` from the published engine checkpoint.
Keep `feat/gloss-engine` available for Worker B and do not mix the experiment
into the combined integration or main. Use a separate experimental module and
tests; keep the default learner, CLI, evaluator, neural/generator code, and
schema-1 checkpoint format unchanged.

## Concrete model

Build a derived inference overlay on an existing authoritative `GlossLearner`.
Prepare it explicitly after corrections; prediction must not rebuild or mutate
it. Reject a stale overlay if the underlying learner version has changed.
Reconstruct it deterministically from the base model after checkpoint load.

For pairs within the existing bounded lexical paradigms, identify a single
middle insertion/deletion/replacement with at least one unchanged character
on each side. Infer forward/reverse edits and existing prefix/suffix gloss
edits from the same grounded lexical key. Example: `man` → `men` with a plural
gloss suggests `a` → `e`; a grounded `tal` may then support unseen `tel`.
Applying an inverse internal edit must recover an actually observed anchor;
it cannot assign English meanings to an ungrounded root.

Rank the union of existing and internal hypotheses with the same support,
edit-complexity and deterministic tie ordering, retaining a declared total
budget of 512. Keep known-form lexical predictions unchanged. For unknown
forms, score selected rules using the baseline weighting and grounded-anchor
frequencies, recording internal edits explicitly in candidate evidence.
Deduplicate identical recovered anchors before voting. Scores remain
uncalibrated. No context model, multilingual initialization, or neural training.

## Checks and bounded evaluation

First test internal replacement, insertion/deletion, competing grammatical
tags, Unicode, ungrounded roots, duplicate/revised answers, stale-overlay
rejection, read-only inference and reconstruction from an engine checkpoint.
When there is no internal evidence, require complete baseline candidate
equivalence. Preserve the complete 83-test integrated baseline.

Then run direct, isolated offline comparisons on the pinned full Lezgi and Tsez
training/development splits, with the same source-only inputs and 512-rule
budget. Freeze these initial settings before examining outcomes. Record exact
word/OOV accuracy, coverage, changed predictions, fit/inference time and memory;
report regressions and negative results. Use a 120-second deadline per run.
Do not tune on or inspect Gitksan or corpus test labels. Leave Worker B's
production online matrix, manifests and session-resume implementation alone.

## Decision gate

Deliver experimental code, tests, reproducible development reports and an error
analysis. Do not promote the experiment automatically. Review whether its added
coverage improves grounded-form transfer without an unacceptable accuracy or
latency regression, then obtain approval for any default-model change after
combined integration is available. If it fails, retain the frozen baseline and
record the limitation instead of changing the benchmark or claiming success.
