# Current development direction

The user approved bringing the tested integration into `main`. Main now
contains integration checkpoint `7b95de1`; the accompanying status update is
being published with it. [Main integration update](updates/2026-10-24-25-main-integration.md).
The [tested stopping note](updates/2026-10-24-24-tested-integration-checkpoint.md)
preserves the validation and earlier branch state.

Worker A and Worker B are combined on main. **83 tests pass**, including the
optional neural tests. All 36 fresh Lezgi/Tsez prefix matrix runs completed;
checkpoint, exported-log, model, metric and complete snapshot-candidate checks
pass. Their non-timing metrics match Worker B's historical matrices. A real
Lezgi run interrupted at 37 inputs resumed to 100 with all 158 original events
preserved, matching the uninterrupted run. [Integrated validation](../reports/gloss/online/integration-20261024/summary.md).

Worker A's tested engine was published to
`origin/feat/gloss-engine` at `22e0203`. Worker B's published branch preserves
the spelling `feat/gloss-online-evalulation`. Main was fast-forwarded from
`24a5a38` to the tested combined checkpoint without conflicts. Its small
checkpoint cleanup fix is committed at `ad602cb`.

Completed tracks:
- Synthetic grammar learning with correction transfer, delayed feedback and checkpoints.
- Supervised real-corpus morphology, with held-out joint scores of 88.6% English / 78.5% Turkish on filtered upstream splits.
- Optional attention/GRU adaptation and replay with deterministic CPU resume tests. Small pilot runs did not beat symbolic learners.
- Source-only real-language glossing with a first Lezgi development result of 72.2% exact word glosses, versus 68.6% memory and 69.9% spelling analogy.
- Equivalent bulk loading, indexed analogy/rule inference, and incremental rule ranking, validated against the original engine. [Performance evidence](../reports/gloss/performance/README.md).
- Reproducible source-only gloss evaluation, accurate annotation budgets, atomic session checkpoints, and interrupted/resumed experiments. [Worker B handoff](updates_b/2026-10-24-07-handoff-and-commands.md).

Next: choose the next research milestone separately; publication does not start
the deferred internal-stem-edit experiment. Core-code fingerprints intentionally reject continuation of
old-revision sessions on changed code; resume them with their recorded revision.
Keep checkpoint manifests with their sibling `checkpoints/` directory.

The internal-stem-edit proposal is deferred by the user until combined
integration; no experimental implementation exists. Keep Gitksan reserved and
use development data for model changes. The [original research roadmap](overview/Language_Decipherment_Build_Plan.md)
still has unfinished structural, calibration, and cross-language experiments.
This milestone does not complete the full plan or establish unrestricted translation.
