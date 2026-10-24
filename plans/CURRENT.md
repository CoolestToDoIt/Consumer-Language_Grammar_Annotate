# Current development direction

Work is paused at the user's requested stopping point on local branch
`integration/gloss-workstreams`. Latest status and exact resume steps:
[combined integration checkpoint](updates/2026-10-24-24-tested-integration-checkpoint.md).

Worker A and Worker B are combined locally. **83 tests pass**, including the
optional neural tests. All 36 fresh Lezgi/Tsez prefix matrix runs completed;
checkpoint, exported-log, model, metric and complete snapshot-candidate checks
pass. Their non-timing metrics match Worker B's historical matrices. A real
Lezgi run interrupted at 37 inputs resumed to 100 with all 158 original events
preserved, matching the uninterrupted run. [Integrated validation](../reports/gloss/online/integration-20261024/summary.md).

`main` is unchanged. Worker A's tested engine was published to
`origin/feat/gloss-engine` at `22e0203`. Worker B's published branch preserves
the spelling `feat/gloss-online-evalulation`. The combined integration branch
has not been published or merged into main. Its small checkpoint cleanup fix
is committed at `ad602cb`; the stopping-point documentation follows it.

Completed tracks:
- Synthetic grammar learning with correction transfer, delayed feedback and checkpoints.
- Supervised real-corpus morphology, with held-out joint scores of 88.6% English / 78.5% Turkish on filtered upstream splits.
- Optional attention/GRU adaptation and replay with deterministic CPU resume tests. Small pilot runs did not beat symbolic learners.
- Source-only real-language glossing with a first Lezgi development result of 72.2% exact word glosses, versus 68.6% memory and 69.9% spelling analogy.
- Equivalent bulk loading, indexed analogy/rule inference, and incremental rule ranking, validated against the original engine. [Performance evidence](../reports/gloss/performance/README.md).
- Reproducible source-only gloss evaluation, accurate annotation budgets, atomic session checkpoints, and interrupted/resumed experiments. [Worker B handoff](updates_b/2026-10-24-07-handoff-and-commands.md).

Next: review the combined diff and validation, then obtain approval before
merging into main. Core-code fingerprints intentionally reject continuation of
old-revision sessions on changed code; resume them with their recorded revision.
Keep checkpoint manifests with their sibling `checkpoints/` directory.

The internal-stem-edit proposal is deferred by the user until combined
integration; no experimental implementation exists. Keep Gitksan reserved and
use development data for model changes. The [original research roadmap](overview/Language_Decipherment_Build_Plan.md)
still has unfinished structural, calibration, and cross-language experiments.
This milestone does not complete the full plan or establish unrestricted translation.
