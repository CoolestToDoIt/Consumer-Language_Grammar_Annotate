# Reuse symmetric edit calculations

Training profiling identified 792,604 edit calculations on full Tsez. Each
paradigm pair previously recalculated target edits for both source sides and
recalculated everything in the reverse direction. Forward/reverse edits share
the same matched span: swapping their removed/appended pieces gives the reverse
edit exactly. Compute admissible source and target edits once per pair, then
combine them in the original directional order. Also hoist the common-prefix
length bound out of its character loop.

| Full fit/reload | Before | Shared edits |
|---|---:|---:|
| Tsez fit | 0.794 s | 0.533 s |
| Tsez ingestion | 0.699 s | 0.434 s |
| Tsez reload | 0.928 s | 0.615 s |
| Lezgi fit | 0.0377 s | 0.0296 s |

Single-run diagnostics, without statistical significance claims. The same
100-correction Tsez stream spent 0.0104 s ingesting annotations versus 0.0176 s
before this change. Its full trace remains exactly equal to the original
full-sort baseline.

Complete Lezgi/Tsez development candidates match prior artifacts in all three
modes and after reload. Reports: `lezgi-shared-edits.json`,
`tsez-shared-edits.json`, `tsez-corrections-shared-edits.json`.
Raw outputs remain in ignored `runs/gloss-engine-shared-edits/` and
`runs/gloss-engine-online-shared-edits/`.

59 tests pass. A separate implementation of the original induction loop checks
every hypothesis, complete lexeme-support sets, and insertion order after each
of 85 annotations (including a revision), at paradigm windows 1, 3, and 32.
This guards hypotheses outside the currently selected 512 as well as predictions.
