# Real-corpus analysis

Supervised word lemmatization, POS and morphological feature prediction; not translation.

Split: dev. Training: 3,435 sentences / 37,442 annotated tokens. Excluded exact training-source overlaps: 0.

| Model | Lemma | POS | Feature bundle | Joint token | OOV joint | Nonpunctuation joint | Sentence exact |
|---|---:|---:|---:|---:|---:|---:|---:|
| lexicon | 73.8% | 64.8% | 65.8% | 62.9% | 0.0% | 54.3% | 7.1% |
| affix | 87.7% | 87.6% | 82.9% | 78.2% | 46.8% | 73.1% | 21.4% |

Frozen model; evaluation receives tokens only; exact NFC token-sequence overlaps with training are excluded; supplied syntactic-word segmentation; punctuation included with nonpunctuation scores reported separately.

The lexicon baseline memorizes the most frequent analysis per form and falls back to an unchanged lemma plus the global majority POS/feature bundle for unknown forms. The affix learner uses learned suffix distributions, observable neighboring words, word shape, and reusable lemma edits. Neither model receives evaluation annotations or gold POS as an input.

Corpus labels, lemmas and word segmentation are supplied supervision. These results measure morphological analysis, not discovery of arbitrary meanings or English translation. Large training corpora are not comparable to the small synthetic seed condition. Individual error samples, metric denominators, feature F1, file hashes, and timing diagnostics are in the companion JSON report.
