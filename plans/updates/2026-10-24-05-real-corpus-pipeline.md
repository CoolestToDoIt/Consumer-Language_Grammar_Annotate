# Real-corpus pipeline

## Direction

Continue the long-term language-learning plan. Remove presentation-specific artifacts and temporary delivery tooling. Keep useful synthetic tests and measured reports as regression evidence.

The synthetic learner scored 100% on its regular held-out combinations, but its fixed three-word meaning schema does not fit real text. A separate corpus model now learns vocabulary, POS labels, feature bundles, contextual evidence, and lemma edits from released annotations. It does not import the synthetic concept inventory.

## Implemented

- Streaming CoNLL-U and aligned JSONL readers with Unicode normalization, sentence boundaries, label validation, missing-label handling, and multiword/empty-node treatment.
- Public token-only model inputs separated from private annotations.
- Incremental corpus learner with lexical counts, context and word-shape evidence, reusable suffix-based lemma edits, arbitrary learned label inventories, idempotent corrections, authoritative annotation revisions, and compressed checkpoints.
- Corpus train/evaluate/analyze/correct commands. Existing synthetic commands remain available independently.
- English EWT and Turkish IMST UD 2.15 corpora using upstream splits; source URLs, licenses, and per-file checksums in data/corpora/SOURCES.json. Downloads and fitted models remain local and ignored by version control.
- Frozen evaluation removes exact training-source overlaps, records denominators, and reports lemma/POS/features, joint token, out-of-vocabulary, nonpunctuation, sentence exact accuracy, feature F1, timing and error samples.

## Development results (not final test scores)

English: affix model 95.8% lemma / 91.8% POS / 88.0% joint token; lexicon baseline 80.2% joint. Excluded 68 overlapping source sentences.

Turkish: affix model 87.7% lemma / 87.6% POS / 78.2% joint token; lexicon baseline 62.9% joint. No training-source overlaps.

These use all annotated training tokens, not a tiny seed dictionary. The task is morphological analysis, not English translation. Unknown-root semantics still require bilingual anchors. Corpus word segmentation is supplied; raw-text whitespace tokenization is only a convenience.

## Next work

Complete regression coverage, run the unchanged model on untouched official test splits, document real-corpus commands and licenses, and verify correction/resume on real inputs. Then prioritize contextual disambiguation and unseen-word morphology based on error reports, followed by a separately scored bilingual gloss/translation track with semantic anchors. Keep real-data claims separate from synthetic demonstrations.
