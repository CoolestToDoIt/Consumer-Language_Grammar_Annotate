# Source-only real-language glossing

Word-aligned, source-only interlinear gloss prediction; no translations or gold segmentation as input.

Training sentences: 3547; words: 37396. Split: dev. Excluded sentence-source overlaps: 0.

| Model | Word exact | OOV word | Grounded lexical OOV | Nonpunctuation word | Sentence exact | Top 5 |
|---|---:|---:|---:|---:|---:|---:|
| memory | 68.2% | 0.0% | 0.0% | 68.2% | 6.3% | 76.1% |
| analogy | 71.3% | 15.9% | 17.1% | 71.3% | 8.1% | 79.2% |
| rules | 75.1% | 35.2% | 38.6% | 75.0% | 11.0% | 84.0% |

Inputs contain only whitespace-delimited source words. Translation, morphological-segmentation and POS tiers are discarded by the reader. This is a stricter source-only variant of shared-task track 1, not a directly comparable official shared-task score. The pinned data_v2 split differs from the original 2023 release.

Rules learn prefix/suffix substitutions within a teacher-grounded lexical paradigm and transfer them to another grounded form. The lexical-paradigm heuristic uses lowercase lexical gloss labels and uppercase grammar conventions; this is a declared linguistic assumption. Rule scores are uncalibrated. Unsupported roots remain unknown. Grounded-OOV diagnostics use lexical labels privately in the scorer; they are never a model input. All denominators and alignment exclusions are in JSON.
