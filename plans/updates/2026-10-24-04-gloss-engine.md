# Scalable gloss engine, input integrity and equivalence

Completed on 2026-10-24. Consolidates original updates 09–21. Worker A developed
`feat/gloss-engine` from shared base `524163c`; the tested branch was published
with user approval at `22e0203`. It is now included in main through the
[integrated release](2026-10-24-05-integrated-gloss-release.md).

## Stable contract and delivered changes

`GlossLearner.fit(records) -> self` applies records in order and prepares inference
at the batch boundary. It preserves sequential duplicate/revision/version behavior,
appends to existing state, and leaves a successful prefix ready if an iterable or
annotation fails. `correct` remains ready for the next prediction immediately.
Schema-1 load rebuilds through bulk fitting and restores the stored version.
Derived indices are reconstructed, not serialized separately or prepared lazily
by prediction. Concurrent training/inference is not supported.

Engine work preserved the hypothesis space, rule bounds, complete ranking key,
lexical grouping heuristic and valid candidate outputs:

- A trigram postings index computes the exact prior Jaccard analogy, including
  deterministic ties and zero-overlap fallback, without scanning unrelated forms.
- Incremental ranking reconsiders the previous top K plus rules whose support
  grew; unchanged support skips sorting. Revisions reset/reconstruct derived state.
- A source-affix index skips impossible inverse edits and restores original rule
  order before voting, retaining floating-score order and explanatory evidence.
  Lookups use learned affix lengths rather than slicing every query length.
- Large pools use exact heap-based top-K selection; small pools still sort.
- Forward/reverse source and target edits reuse matched spans, preserving every
  induced hypothesis, support set and insertion order.
- Observed lexical gloss keys are parsed once per reconstruction in a learner-local
  lookup. Prediction does not add entries; revisions remove superseded labels.

## Measurements and tradeoffs

| Diagnostic | Before | After |
|---|---:|---:|
| Full Lezgi bulk fit | 0.6353 s sequential | 0.0343 s |
| Tsez 500-sentence bulk fit | 1.5942 s sequential | 0.0813 s |
| Full Tsez analogy development pass | 7.785 s | 0.462 s |
| 100 Tsez corrections, incremental-ranking stage | 7.44 s | 0.048 s |
| Full Tsez rule development pass | 90.21 ms | 50.02 ms |
| Isolated 512-rule selection from 77,448 hypotheses, median of five | 91.68 ms | 37.28 ms |
| Full Tsez fit, shared-edit stage | 0.794 s | 0.533 s |
| Full Tsez fit, prepared keys, six alternating fits | 0.502 s median | 0.478 s median |

These describe individual stages, not one combined replicated benchmark. Most
are single-run timings; no statistical speedup or full original-engine Tsez
training-time comparison is claimed. Detailed commands, hashes, timings and
runtime provenance remain in [the performance reports](../../reports/gloss/performance/README.md).

Trigram indexing raised full Tsez process peak RSS from 177.7 to 190.6 MiB in that
comparison, including original and reloaded models. Preparing affix indices raised
the 100-correction total from 47.84 to 53.89 ms while improving inference. Gloss-key
preparation added 86,919 bytes across 9,391 labels to an identity-deduplicated Python
object-graph estimate; that excludes allocator/process overhead and is not RSS.

Full Tsez diagnostics completed on 3,547 training sentences / 37,396 words and
445 development sentences / 4,761 words. Starting from ten support sentences,
3,537 individual corrections took 2.006 s total: median 0.584 ms, p95 0.848 ms,
maximum 27.266 ms, with 24,764 trace rows and equivalent checkpoint reconstruction.
Lezgi's matching 624 corrections took 0.174 s, p95 0.598 ms. These are performance
diagnostics, separate from production online accuracy claims.

## Input integrity and persistence

A malformed correction such as `('valid', 42)` previously inserted a record/counts
before raising, without incrementing version. Validation now precedes mutation:
string ID, immutable nonempty tuple of nonempty whitespace-free word strings,
aligned labels, and positive integer bounds. A bare string/bytes label sequence
cannot silently become per-character labels. Invalid batches retain only their
valid prefix. Schema-1 loading rejects malformed arrays/metadata, duplicate IDs
and versions smaller than authoritative record counts; valid legacy files work.

The reader accepts exact `\t` / `\g` tiers followed by whitespace or end of line;
metadata such as `\translation` / `\glossary` cannot enter source/label fields.
Space and tab delimiters remain supported; complete real-corpus membership is
unchanged. Tests inject partial engine-checkpoint writes and rename failures,
verify old bytes and live state remain intact, remove temporary files, and prove
later save/reload recovery.

## Equivalence and handoff

The engine milestone ended with 64 tests. Coverage includes complete bulk/online
state equality, tight top-K bounds, randomized Unicode analogy/filter oracles,
full original induction evidence/order, frequent duplicate/revision histories,
read-only inference, fresh-learner isolation, legacy checkpoints, invalid inputs,
and CLI transfer with site packages disabled.

Full Lezgi/Tsez candidates match saved outputs in all three modes and after reload.
The original 705-row online trace matches exactly. The portable
`tools/compare_gloss_engines.py` loads a trusted local Git revision without switching
branches: against `524163c`, both languages match 9,690 candidate records in a
500-seed/100-update/30-probe workload, plus complete learned evidence after every
update. Full Lezgi offline outputs also match. See [portable equivalence evidence](../../reports/gloss/performance/git-reference-equivalence.md).

Key commits: bulk API `83e70a0`, analogy `7128624`, incremental ranking `7f3ead8`,
affix index `50beecf`, bounded selection `73375d5`, validation `2aa309a`, shared
edits `1f411c5`, exact tiers `c7cac7f`, gloss keys `cb824ba`, checkpoint-failure
checks `33115de`, and portable checks/published handoff `22e0203`.

Worker A left evaluator/session/CLI ownership to Worker B during parallel work.
B consumed `fit` for bulk loading and retained `correct` for arriving answers.
Their branches were combined and revalidated in the release milestone. Existing
baseline reports and reserved Gitksan labels were not altered by engine tuning.
