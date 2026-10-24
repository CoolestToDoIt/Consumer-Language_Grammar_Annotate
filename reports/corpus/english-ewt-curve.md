# Real-corpus acquisition curve

Development-only acquisition curve for supervised morphological analysis.

Original training sentence order; complete sentence annotations released at each budget; all input words are observable, but no development annotations are taught; exact source overlaps with the complete training split excluded. Recall is scored separately on the first 25 released sentences.

| Sentence labels | Token labels | Lexicon joint | Affix joint | Affix OOV joint |
|---:|---:|---:|---:|---:|
| 0 | 0 | 0.0% | 0.0% | 0.0% |
| 25 | 554 | 38.0% | 52.2% | 26.3% |
| 100 | 2311 | 51.7% | 67.2% | 37.6% |
| 500 | 11595 | 60.9% | 74.8% | 44.0% |
| 1000 | 21857 | 65.4% | 79.1% | 48.8% |
| 12544 | 204444 | 80.2% | 88.0% | 52.8% |

Evaluated 1933 fixed development sentences. Evaluation limit: none. These are corpus-order prefix budgets, not randomized replicated learning curves. No claims about small-data translation follow from these scores.
