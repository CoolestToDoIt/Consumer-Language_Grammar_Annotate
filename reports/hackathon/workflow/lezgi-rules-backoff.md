# Workflow metrics: Lezgi

Model `rules`, guess_unknown=False, normalize_unknown=True. Teaching replay over 634 training sentences / 6250 words in corpus order, starting from zero annotations; review triage on 992 development words with no training-source overlap.

## Teaching session (prediction before each correction)

| Metric | Value |
|---|---:|
| Suggestions accepted as-is | 66.3% |
| Fixed by picking a listed candidate | 6.0% |
| Typed from scratch | 27.7% |
| Gloss characters the user did not type | 58.5% |
| Sentences needing zero edits | 11.2% |
| Precision when a suggestion is shown | 83.6% |
| Words left blank ("I don't know") | 20.6% |
| Words with a wrong suggestion | 13.1% |
| Teach-once reuse (same word, same answer as taught) | 93.0% |
| Accuracy on never-seen word forms | 14.1% |
| Sentences until rolling-50 acceptance ≥50% / 60% / 70% | 72 / 125 / 221 |
| Predict latency per sentence p50 / p95 | 0.07 / 0.22 ms |
| Apply-correction latency p50 / p95 | 0.18 / 0.48 ms |

Acceptance by 50-sentence window:

| Sentences taught | Accepted | Typed from scratch |
|---:|---:|---:|
| 50 | 39.6% | 58.6% |
| 100 | 50.4% | 47.0% |
| 150 | 65.7% | 30.5% |
| 200 | 66.5% | 26.8% |
| 250 | 68.9% | 25.6% |
| 300 | 66.9% | 27.2% |
| 350 | 66.7% | 26.2% |
| 400 | 71.8% | 21.4% |
| 450 | 71.6% | 19.9% |
| 500 | 72.2% | 20.6% |
| 550 | 74.5% | 18.8% |
| 600 | 79.1% | 12.7% |
| 634 | 74.7% | 18.2% |

## Review triage (frozen fully-taught model, unseen dev sentences)

Dev word accuracy 73.1%; 267 wrong words.

| Words reviewed | Errors found (review order) | Errors found (random order) |
|---:|---:|---:|
| 10% | 37.1% | 11.6% |
| 20% | 62.2% | 21.0% |
| 30% | 82.8% | 30.7% |
| 50% | 88.8% | 50.2% |

Unflagged words (known form, single candidate): 57.7% of words at 94.2% accuracy. Flagged words hold 87.6% of all errors.

Simulated user: an answer counts as accepted only on an exact gloss match. "Picked" means the gold gloss was among the top five listed candidates. Rates are empirical on this development language and are not calibrated probabilities. Gitksan is not used.
