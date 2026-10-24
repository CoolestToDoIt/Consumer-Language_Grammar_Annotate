# Source-only real-language glossing

Word-aligned, source-only interlinear gloss prediction; no translations or gold segmentation as input.

Training sentences: 634; words: 6250. Split: dev. Excluded sentence-source overlaps: 0.

| Model | Word exact | OOV word | Grounded lexical OOV | Nonpunctuation word | Sentence exact | Top 5 |
|---|---:|---:|---:|---:|---:|---:|
| memory | 68.6% | 0.0% | 0.0% | 56.3% | 6.8% | 72.5% |
| analogy | 69.9% | 5.4% | 10.1% | 58.0% | 6.8% | 73.7% |
| rules | 72.2% | 15.8% | 27.7% | 61.3% | 11.4% | 77.0% |

Inputs contain only whitespace-delimited source words. Translation, morphological-segmentation and POS tiers are discarded by the reader. This is a stricter source-only variant of shared-task track 1, not a directly comparable official shared-task score. The pinned data_v2 split differs from the original 2023 release.

Rules learn prefix/suffix substitutions within a teacher-grounded lexical paradigm and transfer them to another grounded form. The lexical-paradigm heuristic uses lowercase lexical gloss labels and uppercase grammar conventions; this is a declared linguistic assumption. Rule scores are uncalibrated. Unsupported roots remain unknown. Grounded-OOV diagnostics use lexical labels privately in the scorer; they are never a model input. All denominators and alignment exclusions are in JSON.
