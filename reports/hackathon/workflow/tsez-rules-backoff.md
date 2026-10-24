# Workflow metrics: Tsez

Model `rules`, guess_unknown=False, normalize_unknown=True. Teaching replay over 3547 training sentences / 37396 words in corpus order, starting from zero annotations; review triage on 4761 development words with no training-source overlap.

## Teaching session (prediction before each correction)

| Metric | Value |
|---|---:|
| Suggestions accepted as-is | 71.1% |
| Fixed by picking a listed candidate | 8.1% |
| Typed from scratch | 20.8% |
| Gloss characters the user did not type | 74.1% |
| Sentences needing zero edits | 10.0% |
| Precision when a suggestion is shown | 81.7% |
| Words left blank ("I don't know") | 13.0% |
| Words with a wrong suggestion | 16.0% |
| Teach-once reuse (same word, same answer as taught) | 90.0% |
| Accuracy on never-seen word forms | 39.3% |
| Sentences until rolling-50 acceptance ≥50% / 60% / 70% | 201 / 374 / 503 |
| Predict latency per sentence p50 / p95 | 0.08 / 0.24 ms |
| Apply-correction latency p50 / p95 | 0.47 / 0.75 ms |

Acceptance by 50-sentence window:

| Sentences taught | Accepted | Typed from scratch |
|---:|---:|---:|
| 50 | 17.2% | 81.7% |
| 100 | 39.6% | 56.0% |
| 150 | 47.1% | 48.4% |
| 200 | 49.2% | 46.6% |
| 250 | 54.2% | 38.3% |
| 300 | 55.6% | 39.9% |
| 350 | 57.3% | 35.4% |
| 400 | 61.6% | 31.8% |
| 450 | 65.5% | 28.7% |
| 500 | 68.8% | 24.5% |
| 550 | 67.5% | 27.2% |
| 600 | 65.8% | 26.4% |
| 650 | 70.6% | 23.0% |
| 700 | 65.7% | 27.2% |
| 750 | 63.5% | 26.5% |
| 800 | 67.6% | 23.2% |
| 850 | 68.9% | 23.1% |
| 900 | 71.3% | 20.6% |
| 950 | 72.2% | 19.7% |
| 1000 | 68.7% | 22.8% |
| 1050 | 66.3% | 24.6% |
| 1100 | 71.1% | 18.7% |
| 1150 | 71.9% | 21.5% |
| 1200 | 70.8% | 20.7% |
| 1250 | 70.6% | 21.4% |
| 1300 | 71.8% | 18.6% |
| 1350 | 70.8% | 20.9% |
| 1400 | 74.7% | 19.6% |
| 1450 | 70.6% | 19.8% |
| 1500 | 70.3% | 18.7% |
| 1550 | 69.6% | 22.5% |
| 1600 | 74.2% | 17.8% |
| 1650 | 77.3% | 15.9% |
| 1700 | 74.2% | 17.4% |
| 1750 | 75.2% | 16.7% |
| 1800 | 75.0% | 17.0% |
| 1850 | 77.5% | 14.5% |
| 1900 | 72.1% | 18.2% |
| 1950 | 74.5% | 17.2% |
| 2000 | 72.4% | 20.5% |
| 2050 | 76.3% | 13.5% |
| 2100 | 77.3% | 13.7% |
| 2150 | 75.3% | 16.8% |
| 2200 | 80.7% | 12.8% |
| 2250 | 74.1% | 16.2% |
| 2300 | 76.3% | 14.0% |
| 2350 | 77.8% | 14.4% |
| 2400 | 76.7% | 14.3% |
| 2450 | 76.4% | 15.0% |
| 2500 | 75.1% | 14.4% |
| 2550 | 71.8% | 16.1% |
| 2600 | 76.1% | 14.2% |
| 2650 | 76.6% | 14.8% |
| 2700 | 79.4% | 13.3% |
| 2750 | 77.2% | 13.8% |
| 2800 | 80.1% | 13.2% |
| 2850 | 77.9% | 13.7% |
| 2900 | 78.3% | 14.6% |
| 2950 | 77.0% | 14.4% |
| 3000 | 75.6% | 12.5% |
| 3050 | 78.0% | 12.1% |
| 3100 | 80.0% | 10.9% |
| 3150 | 77.8% | 12.2% |
| 3200 | 77.2% | 12.3% |
| 3250 | 78.6% | 12.4% |
| 3300 | 81.3% | 11.9% |
| 3350 | 76.2% | 15.2% |
| 3400 | 75.9% | 12.5% |
| 3450 | 79.6% | 11.9% |
| 3500 | 79.7% | 13.9% |
| 3547 | 79.4% | 12.8% |

## Review triage (frozen fully-taught model, unseen dev sentences)

Dev word accuracy 76.9%; 1099 wrong words.

| Words reviewed | Errors found (review order) | Errors found (random order) |
|---:|---:|---:|
| 10% | 36.9% | 9.5% |
| 20% | 47.9% | 21.3% |
| 30% | 69.7% | 31.4% |
| 50% | 86.7% | 50.0% |

Unflagged words (known form, single candidate): 48.7% of words at 93.7% accuracy. Flagged words hold 86.7% of all errors.

Simulated user: an answer counts as accepted only on an exact gloss match. "Picked" means the gold gloss was among the top five listed candidates. Rates are empirical on this development language and are not calibrated probabilities. Gitksan is not used.
