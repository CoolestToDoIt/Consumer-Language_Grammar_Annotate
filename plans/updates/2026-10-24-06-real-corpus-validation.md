# Real-corpus validation checkpoint

## Completed

The product now has a working real-corpus analysis track alongside the synthetic grammar learner. Removed temporary presentation artifacts and delivery tooling, and replaced their documentation with development-focused notes. The long-term research plan remains intact.

Real-corpus commands support training, frozen evaluation, development acquisition curves, batch/raw-word analysis, incremental corrections, annotation revisions, and compressed checkpoint reload. Exact corrected sentences can return verified memory, clearly identified as recall. Generic inference learns its vocabulary and label inventories from the corpus rather than importing synthetic nouns or roles.

## Final baseline results

Using UD 2.15 upstream training and test files, after excluding exact training-source overlaps:

| Corpus | Training annotated tokens | Test tokens scored | Lexicon joint | Affix joint | Affix lemma | Affix POS | OOV joint |
|---|---:|---:|---:|---:|---:|---:|---:|
| English EWT | 204,444 | 24,929 | 80.0% | 88.6% | 95.8% | 92.3% | 56.3% |
| Turkish IMST | 37,442 | 10,032 | 64.9% | 78.5% | 87.7% | 88.0% | 44.7% |

Joint requires an exact lemma, POS, and complete morphological feature bundle. English excluded 94 overlapping source sentences; Turkish excluded none. These are filtered upstream test results, not an unfiltered official benchmark score. Word segmentation is supplied and punctuation is included; nonpunctuation and sentence exact results are reported separately.

Development curves use fixed complete development sets, no annotation leakage, and upstream training order. English improves from 52.2% at 554 token labels to 88.0% at 204,444. Turkish improves from 35.5% at 358 labels to 78.2% at 37,442. Recall on released training examples is separate from unseen performance. These are prefix-budget measurements, not shuffled replications.

## Verification

- 23 regression tests pass, including corpus parsing/alignment, Unicode, absent labels, unseen morphology, private-answer isolation, nonmutating inference, overlap exclusion, learning budgets, duplicate corrections, revisions, authoritative exact-sentence recall, and CLI train/analyze/correct/reload.
- Verified corpus checksums against the pinned source manifest.
- Ran saved-model inference on a typed natural-language sentence.
- Applied a new manual correction to a temporary copy of the full English model, reloaded it, and verified that the corrected sentence recalls the authoritative answer. Scored model files were not modified by this check.
- Downloaded corpora and fitted models remain local and ignored by version control; upstream documentation and licenses are stored with the downloads. Reproduction commands are in README.md.

## Interpretation and next work

This validates a supervised real-text morphology pipeline, not an English translator. Unknown-word semantics require bilingual anchors. The system still makes substantial errors on novel forms, contextual ambiguity, and complete sentences. It uses far more target-language labels than the synthetic seed condition.

Next priorities:
1. Improve contextual disambiguation and unknown-form analysis using development data only; preserve the current test reports as a fixed baseline.
2. Add a separately scored bilingual/interlinear-gloss track with explicit semantic anchors, data licensing, and established splits. Do not score morphology as translation.
3. Add randomized corpus acquisition runs and correction-budget comparisons, including delayed real-corpus feedback.
4. Profile larger corpora and add incremental-count reversal if annotation-revision rebuild time becomes limiting.
