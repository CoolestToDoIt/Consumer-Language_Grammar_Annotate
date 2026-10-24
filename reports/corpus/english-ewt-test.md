# Real-corpus analysis

Supervised word lemmatization, POS and morphological feature prediction; not translation.

Split: test. Training: 12,544 sentences / 204,444 annotated tokens. Excluded exact training-source overlaps: 94.

| Model | Lemma | POS | Feature bundle | Joint token | OOV joint | Nonpunctuation joint | Sentence exact |
|---|---:|---:|---:|---:|---:|---:|---:|
| lexicon | 95.1% | 85.8% | 87.3% | 80.0% | 13.9% | 77.4% | 16.2% |
| affix | 95.8% | 92.3% | 92.6% | 88.6% | 56.3% | 87.1% | 35.7% |

Frozen model; evaluation receives tokens only; exact NFC token-sequence overlaps with training are excluded; supplied syntactic-word segmentation; punctuation included with nonpunctuation scores reported separately.

The lexicon baseline memorizes the most frequent analysis per form and falls back to an unchanged lemma plus the global majority POS/feature bundle for unknown forms. The affix learner uses learned suffix distributions, observable neighboring words, word shape, and reusable lemma edits. Neither model receives evaluation annotations or gold POS as an input.

Corpus labels, lemmas and word segmentation are supplied supervision. These results measure morphological analysis, not discovery of arbitrary meanings or English translation. Large training corpora are not comparable to the small synthetic seed condition. Individual error samples, metric denominators, feature F1, file hashes, and timing diagnostics are in the companion JSON report.
