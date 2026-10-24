# Real-corpus results

The evaluated task predicts lemma, universal POS, and the complete morphological feature bundle for every supplied word token. It is separate from the synthetic sentence-meaning task and does not measure translation.

The algorithm (`count-affix-v1`) was held unchanged between development and final test evaluation. Training used the complete upstream UD 2.15 training split, without pretrained weights, external dictionaries, development labels, or test labels. Exact NFC token-sequence matches to training were excluded before scoring. Other sentences in the original upstream evaluation splits were kept in their original order; these are filtered upstream splits, not unfiltered official benchmark scores.

| Corpus | Training tokens | Test tokens scored | Lexicon joint | Affix joint | Affix lemma | Affix POS | OOV joint |
|---|---:|---:|---:|---:|---:|---:|---:|
| English EWT | 204,444 | 24,929 | 80.0% | 88.6% | 95.8% | 92.3% | 56.3% |
| Turkish IMST | 37,442 | 10,032 | 64.9% | 78.5% | 87.7% | 88.0% | 44.7% |

Joint requires all three outputs to match. Punctuation is included here; individual reports also show nonpunctuation and full-sentence exact scores. Unknown-form tokens are counted using exact observed surface forms. Dataset size and supervision differ greatly from the synthetic learner's eleven anchors; compare the two tracks only within their own protocols.

- [English test report](english-ewt-test.md) and [raw counts/errors](english-ewt-test.json)
- [Turkish test report](turkish-imst-test.md) and [raw counts/errors](turkish-imst-test.json)
- [English development acquisition curve](english-ewt-curve.md)
- [Turkish development acquisition curve](turkish-imst-curve.md)

The lexicon baseline returns the most frequent known analysis, or an unchanged lemma plus the corpus-majority POS/features. The affix model adds learned suffix, word-shape and observable context evidence, and reusable lemma edits. Source words and neighboring surface words are the only inputs at prediction time. Word segmentation is supplied, not learned.

Errors remain substantial on unseen forms and complete sentences. For example, a lemma can be correct while verbal mood/voice is wrong. The next improvements should be evaluated on development data; these test results are a fixed baseline for this version, not a tuning set.

Source definitions, upstream URLs, original licenses and file checksums are in [SOURCES.json](../../data/corpora/SOURCES.json). English EWT annotations are CC BY-SA 4.0 with underlying-text rights described upstream; Turkish IMST is CC BY-NC-SA 4.0. Raw downloads and fitted checkpoints remain local and excluded from version control.
