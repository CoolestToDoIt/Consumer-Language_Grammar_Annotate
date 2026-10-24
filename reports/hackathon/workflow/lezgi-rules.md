# Workflow metrics: Lezgi

Model `rules`, guess_unknown=False, normalize_unknown=False. Teaching replay over 634 training sentences / 6250 words in corpus order, starting from zero annotations; review triage on 992 development words with no training-source overlap.

## Teaching session (prediction before each correction)

| Metric | Value |
|---|---:|
| Suggestions accepted as-is | 64.9% |
| Fixed by picking a listed candidate | 5.8% |
| Typed from scratch | 29.3% |
| Gloss characters the user did not type | 56.8% |
| Sentences needing zero edits | 9.3% |
| Precision when a suggestion is shown | 83.8% |
| Words left blank ("I don't know") | 22.6% |
| Words with a wrong suggestion | 12.5% |
| Teach-once reuse (same word, same answer as taught) | 93.0% |
| Accuracy on never-seen word forms | 9.2% |
| Sentences until rolling-50 acceptance ≥50% / 60% / 70% | 103 / 135 / 387 |
| Predict latency per sentence p50 / p95 | 0.06 / 0.20 ms |
| Apply-correction latency p50 / p95 | 0.19 / 0.49 ms |

Acceptance by 50-sentence window:

| Sentences taught | Accepted | Typed from scratch |
|---:|---:|---:|
| 50 | 38.5% | 59.7% |
| 100 | 48.5% | 49.4% |
| 150 | 64.6% | 32.4% |
| 200 | 65.5% | 27.9% |
| 250 | 67.2% | 27.3% |
| 300 | 65.6% | 28.4% |
| 350 | 65.2% | 27.7% |
| 400 | 69.9% | 23.2% |
| 450 | 70.2% | 21.5% |
| 500 | 69.4% | 23.3% |
| 550 | 73.2% | 20.2% |
| 600 | 78.4% | 13.5% |
| 634 | 73.6% | 19.3% |

## Review triage (frozen fully-taught model, unseen dev sentences)

Dev word accuracy 72.2%; 276 wrong words.

| Words reviewed | Errors found (review order) | Errors found (random order) |
|---:|---:|---:|
| 10% | 35.9% | 11.2% |
| 20% | 63.0% | 20.3% |
| 30% | 83.3% | 30.1% |
| 50% | 89.1% | 48.9% |

Unflagged words (known form, single candidate): 57.7% of words at 94.2% accuracy. Flagged words hold 88.0% of all errors.

Simulated user: an answer counts as accepted only on an exact gloss match. "Picked" means the gold gloss was among the top five listed candidates. Rates are empirical on this development language and are not calibrated probabilities. Gitksan is not used.
