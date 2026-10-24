# Real-corpus morphology and fixed baseline validation

Completed on 2026-10-24. Consolidates original updates 05–06.

## Delivered pipeline

Added a separate supervised real-text analysis track, without importing the
synthetic noun/role inventory. Streaming CoNLL-U and aligned JSONL readers handle
Unicode NFC, sentence boundaries, label alignment, absent labels, multiword
ranges and empty nodes. Public examples contain only source tokens; annotations
remain private to correction and scoring.

The incremental learner combines lexical counts, observable context, word shape,
suffix patterns and reusable lemma edits. Vocabulary, POS labels and feature
bundles come from the corpus. Commands support train, frozen evaluate, acquisition
curves, batch/raw-word analyze, correct and compressed checkpoint reload.
Identical corrections are idempotent; revisions replace authoritative annotations
and rebuild counts. Exact corrected sentences may return verified recall, which
is explicitly separate from unseen prediction.

English EWT and Turkish IMST use UD 2.15 upstream splits, pinned URLs, licenses and
checksums in [SOURCES.json](../../data/corpora/SOURCES.json). Downloads and fitted
models stay local and ignored. Temporary presentation/delivery artifacts were
removed; useful synthetic tests and reports remain regression evidence.

## Development and held-out results

Frozen evaluation excludes exact training-source overlaps and records denominators,
lemma/POS/features, joint token accuracy, OOV and nonpunctuation accuracy, sentence
exact accuracy, feature F1, timing and error samples. Joint accuracy requires the
exact lemma, POS and complete morphological feature bundle.

| Filtered upstream test split | Training annotated tokens | Scored test tokens | Lexicon joint | Affix joint | Affix lemma | Affix POS | OOV joint |
|---|---:|---:|---:|---:|---:|---:|---:|
| English EWT | 204,444 | 24,929 | 80.0% | 88.6% | 95.8% | 92.3% | 56.3% |
| Turkish IMST | 37,442 | 10,032 | 64.9% | 78.5% | 87.7% | 88.0% | 44.7% |

English test evaluation excluded 94 overlapping source sentences; Turkish excluded
none. Segmentation is supplied and punctuation is included, so these are filtered
upstream results, not unfiltered official scores. Preserve these test reports as
fixed baselines; further model choices use development data only.

Development affix joint accuracy was 88.0% English and 78.2% Turkish, versus 80.2%
and 62.9% lexicon baselines. English excluded 68 development overlaps. Upstream-order
acquisition curves improved from 52.2% at 554 token labels to 88.0% at 204,444 for
English, and 35.5% at 358 labels to 78.2% at 37,442 for Turkish. These are prefix
budgets, not shuffled replications; training recall is scored separately.

## Validation and interpretation

23 tests passed at this milestone, including parsing/alignment, Unicode, missing
labels, unseen morphology, answer isolation, nonmutating prediction, overlap and
budget handling, duplicates/revisions, authoritative recall and CLI reload.
Corpus checksums passed. Typed-sentence inference and a manual correction/reload
on a temporary copy of the full English model passed without modifying scored
models. Reports are in [reports/corpus](../../reports/corpus); commands are in the
[README](../../README.md).

This is morphological analysis, not English translation. It uses substantial
supervision, supplied word segmentation and learned corpus labels. Unknown meanings
still need semantic anchors; novel forms, context ambiguity and complete-sentence
accuracy remain limitations. The next milestone added neural comparisons and a
separately scored source-only gloss track.
