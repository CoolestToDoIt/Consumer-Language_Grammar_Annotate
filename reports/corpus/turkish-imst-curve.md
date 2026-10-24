# Real-corpus acquisition curve

Development-only acquisition curve for supervised morphological analysis.

Original training sentence order; complete sentence annotations released at each budget; all input words are observable, but no development annotations are taught; exact source overlaps with the complete training split excluded. Recall is scored separately on the first 25 released sentences.

| Sentence labels | Token labels | Lexicon joint | Affix joint | Affix OOV joint |
|---:|---:|---:|---:|---:|
| 0 | 0 | 0.0% | 0.0% | 0.0% |
| 25 | 358 | 27.1% | 35.5% | 13.4% |
| 100 | 1162 | 33.5% | 46.0% | 20.9% |
| 500 | 5761 | 44.7% | 60.6% | 32.0% |
| 1000 | 12546 | 51.8% | 68.6% | 38.7% |
| 3435 | 37442 | 62.9% | 78.2% | 46.8% |

Evaluated 1100 fixed development sentences. Evaluation limit: none. These are corpus-order prefix budgets, not randomized replicated learning curves. No claims about small-data translation follow from these scores.
