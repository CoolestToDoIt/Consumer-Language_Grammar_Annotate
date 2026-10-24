# Current development direction

Two-person implementation plan: [split-agent workflow](SPLIT_AGENT_WORKFLOW.md). The plan assigns engine/performance work and evaluation/resume work to separate branches; implementation has not resumed as part of writing it.

Work is paused at a tested checkpoint at the user's request. Latest status and exact resume steps: [tested stopping point](updates/2026-10-24-08-tested-stopping-point.md).

Completed tracks:
- Synthetic grammar learning with correction transfer, delayed feedback and checkpoints.
- Supervised real-corpus morphology, with held-out joint scores of 88.6% English / 78.5% Turkish on filtered upstream splits.
- Optional attention/GRU adaptation and replay with deterministic CPU resume tests. Small pilot runs did not beat symbolic learners.
- Source-only real-language glossing with a first Lezgi development result of 72.2% exact word glosses, versus 68.6% memory and 69.9% spelling analogy.

35 regression tests pass in the neural-enabled .venv. No full-plan completion or unrestricted translation claim is made.

Next action is to profile and finish the larger Tsez development run; then run real-gloss online correction comparisons. Keep Gitksan reserved for a final fresh-language evaluation and use development data for model changes. The [original research roadmap](overview/Language_Decipherment_Build_Plan.md) still contains unfinished experiments and optional extensions.
