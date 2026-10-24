# Neural adaptation controls and source-only gloss foundations

Completed on 2026-10-24. Consolidates original updates 07–08.

## Neural implementation and experimental controls

Added an optional UTF-8 byte model with a bidirectional GRU encoder, attention and
an autoregressive decoder. A fixed byte vocabulary avoids deriving an inventory
from unreleased answers. Initial settings: 64-dimensional embeddings, 128 hidden
units, 405,443 parameters, Adam at 0.0003, clipping at 1.0, and replay of up to 15
previous corrections from a bounded reservoir. CPU/accelerator selection and
versioned neural dependencies are documented; PyTorch is optional for symbolic
and gloss commands.

Five adaptation conditions separate frozen parameters, memory-only updates,
parameter-only updates, replay and replay plus verified memory. Sessions save
predictions before feedback, apply delayed labels only on arrival, retain original
history, and checkpoint optimizer, replay/RNG, memory, pending feedback and cursor.
Duplicates are idempotent; revisions rebuild from initialization and authoritative
labels. CLI commands cover synthetic/corpus benchmarks and generic supervised
source/target JSONL fitting and prediction.

Correctness tests verify actual fitting without memory, permitted update modes,
RNG isolation, read-only probes and exact deterministic CPU continuation. This
milestone passed 35 tests, retaining the earlier 23. Cross-runtime/device bitwise
identity is not claimed.

## Measured outcome

Small pilots used two synthetic languages and a Turkish morphology stream, one
model seed and all five conditions. Every neural condition scored zero exact-match
disjoint probes at those budgets. Repeated updates can fit a corrected pair, but
no tiny-data transfer advantage was shown; symbolic systems remain selected.
These were pilots, not a full multi-seed study or equal-compute comparison.
See [synthetic pilot](../../reports/neural/synthetic-pilot/summary.md) and
[corpus pilot](../../reports/neural/corpus-pilot/summary.md).

## Source-only interlinear glossing

Added aligned source/gloss ingestion, memory/analogy/prefix-and-suffix rule
learners, annotation revisions, compressed schema-1 checkpoints, offline metrics,
CLI commands and initial delayed-feedback experiments. Sentence translations,
gold segmentation and POS tiers are discarded. Rules transfer only through an
observed lexical anchor; an ungrounded root cannot acquire an English meaning
from spelling patterns alone. The lowercase lexical / uppercase grammatical gloss
convention is an explicit heuristic, and scores are uncalibrated.

Pinned SIGMORPHON data_v2 sources/checksums and licenses identify Lezgi/Tsez for
development and Gitksan as reserved. Raw corpora remain ignored. Lezgi's first
full-training development baseline used 634 sentences / 6,250 word glosses:

| Model | Exact word gloss accuracy |
|---|---:|
| Memory | 68.6% |
| Spelling analogy | 69.9% |
| Rules | 72.2% |

Rule unseen-word accuracy was 15.8%. Full denominators and exclusions are in
[the baseline](../../reports/gloss/lezgi-dev.json). This is word-aligned glossing,
not unrestricted translation or a final fresh-language evaluation.

The first larger Tsez evaluation was interrupted for runtime; no result was
claimed at that point. That bottleneck led to the [engine milestone](2026-10-24-04-gloss-engine.md),
which later completed bounded full-corpus diagnostics. Replicated neural studies,
structural holdouts, calibration, equal-compute controls and cross-language
initialization remain unfinished; reserved-language evaluation needs a frozen
protocol and settings.
