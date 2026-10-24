# Tested stopping point

Work paused at the user's request. No further experiments are running.

## Completed this batch

- Optional byte-level attention/GRU model: 64-dimensional embeddings, 128 hidden units, 405,443 parameters, Adam updates, clipping, reservoir replay, and CPU/accelerator selection.
- Frozen, memory-only, parameter-only, replay, and hybrid adaptation modes with matched input/label schedules.
- Prediction-before-feedback sessions with delays, revisions, immutable historical predictions, separate prediction/feedback logs, and full optimizer/replay/RNG/session checkpoints.
- Neural CLI for synthetic/corpus development benchmarks and generic supervised source/target JSONL training/prediction. Installed PyTorch only in the project .venv and recorded its versioned dependencies.
- Neural correctness tests verify actual fitting without memory, permitted adaptation modes, RNG isolation, duplicate/revised feedback, read-only prediction, delayed arrival, and exact CPU checkpoint continuation.
- Source-only interlinear gloss reader, memory/analogy/rule learners, CLI, annotation revisions, compressed checkpoints, offline metrics, and online delayed-feedback experiments.
- Gloss reader discards sentence translations, gold segmentation, and POS tiers. Prefix/suffix rules transfer only through an already grounded lexical anchor; unsupported root meanings remain unknown.
- Commit/checksum-pinned SIGMORPHON data_v2 training/development files and licenses for Lezgi, Tsez, and reserved Gitksan. Raw downloads remain ignored; source metadata is versioned.

## Verified results

All 35 tests pass in the neural-enabled .venv. The 23 previous tests remain included.

Small neural pilots: two synthetic languages and one Turkish morphology stream, one model seed, five adaptation modes. All neural modes scored zero exact-match disjoint probes at these label budgets. The network can fit a corrected pair with repeated updates, but no tiny-data transfer advantage was demonstrated. Symbolic models remain selected. Results: reports/neural/synthetic-pilot and reports/neural/corpus-pilot. These are pilot results, not a full multi-seed E2 study or equal-compute comparison.

Lezgi source-only development glossing:
- Memory: 68.6% exact word gloss accuracy.
- Spelling analogy: 69.9%.
- Rules: 72.2%; unseen-word accuracy 15.8%.
- 634 training sentences / 6,250 word glosses. Full denominators, alignment exclusions, OOV and sentence scores are in reports/gloss/lezgi-dev.json.

The larger Tsez development evaluation was interrupted because runtime exceeded the intended stopping point. No result is claimed for it. Gitksan has not been evaluated, and its final test data has not been downloaded or inspected.

## Resume here

1. Profile the larger gloss evaluation. Bulk training currently prepares/sorts rule hypotheses repeatedly; avoid redundant work while preserving read-only inference and online correction behavior. Re-run Tsez development evaluation after profiling, without changing the fixed Lezgi result silently.
2. Add a real-gloss online development run using existing `gloss stream` with delays 0/5/20 and both all-label/correction-only policies; compare against its fixed probes and record actual annotation budgets.
3. Complete broader synthetic grammar-family tests and the full replicated neural comparison if development evidence justifies the compute. Calibration, statistical confidence intervals, equal-compute controls, cross-language initialization, and genuinely held-out grammar experiments remain unfinished.
4. Freeze gloss settings before running the reserved fresh-language Gitksan check. Preserve existing corpus test reports as baselines; do not tune on test scores.

The overview roadmap is not finished. Current work supports synthetic grammar learning, real morphology, and a first real lexical/grammatical glossing experiment; unrestricted translation remains unfinished.
