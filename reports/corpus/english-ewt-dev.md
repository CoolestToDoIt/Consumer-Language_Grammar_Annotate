# Real-corpus analysis

Supervised word lemmatization, POS and morphological feature prediction; not translation.

Split: dev. Training: 12,544 sentences / 204,444 annotated tokens. Excluded exact training-source overlaps: 68.

| Model | Lemma | POS | Feature bundle | Joint token | OOV joint | Nonpunctuation joint | Sentence exact |
|---|---:|---:|---:|---:|---:|---:|---:|
| lexicon | 95.3% | 85.8% | 87.0% | 80.2% | 14.1% | 77.7% | 15.8% |
| affix | 95.8% | 91.8% | 92.1% | 88.0% | 52.8% | 86.4% | 32.8% |

Frozen model; evaluation receives tokens only; exact NFC token-sequence overlaps with training are excluded; supplied syntactic-word segmentation; punctuation included with nonpunctuation scores reported separately.

The lexicon baseline memorizes the most frequent analysis per form and falls back to an unchanged lemma plus the global majority POS/feature bundle for unknown forms. The affix learner uses learned suffix distributions, observable neighboring words, word shape, and reusable lemma edits. Neither model receives evaluation annotations or gold POS as an input.

Corpus labels, lemmas and word segmentation are supplied supervision. These results measure morphological analysis, not discovery of arbitrary meanings or English translation. Large training corpora are not comparable to the small synthetic seed condition. Individual error samples, metric denominators, feature F1, file hashes, and timing diagnostics are in the companion JSON report.
