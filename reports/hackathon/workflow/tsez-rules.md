# Workflow metrics: Tsez

Model `rules`, guess_unknown=False, normalize_unknown=False. Teaching replay over 3547 training sentences / 37396 words in corpus order, starting from zero annotations; review triage on 4761 development words with no training-source overlap.

## Teaching session (prediction before each correction)

| Metric | Value |
|---|---:|
| Suggestions accepted as-is | 68.4% |
| Fixed by picking a listed candidate | 8.0% |
| Typed from scratch | 23.6% |
| Gloss characters the user did not type | 71.4% |
| Sentences needing zero edits | 8.0% |
| Precision when a suggestion is shown | 81.8% |
| Words left blank ("I don't know") | 16.4% |
| Words with a wrong suggestion | 15.2% |
| Teach-once reuse (same word, same answer as taught) | 90.0% |
| Accuracy on never-seen word forms | 30.3% |
| Sentences until rolling-50 acceptance ≥50% / 60% / 70% | 221 / 408 / 955 |
| Predict latency per sentence p50 / p95 | 0.08 / 0.21 ms |
| Apply-correction latency p50 / p95 | 0.44 / 0.65 ms |

Acceptance by 50-sentence window:

| Sentences taught | Accepted | Typed from scratch |
|---:|---:|---:|
| 50 | 12.5% | 86.5% |
| 100 | 36.0% | 61.4% |
| 150 | 43.5% | 51.0% |
| 200 | 45.7% | 49.5% |
| 250 | 51.3% | 40.6% |
| 300 | 51.7% | 44.0% |
| 350 | 54.6% | 38.8% |
| 400 | 58.3% | 35.0% |
| 450 | 61.7% | 32.4% |
| 500 | 65.4% | 28.1% |
| 550 | 63.6% | 31.3% |
| 600 | 60.6% | 31.2% |
| 650 | 67.7% | 26.2% |
| 700 | 61.7% | 30.8% |
| 750 | 61.0% | 29.4% |
| 800 | 65.2% | 26.0% |
| 850 | 65.8% | 25.9% |
| 900 | 66.8% | 24.7% |
| 950 | 69.1% | 22.7% |
| 1000 | 65.9% | 26.5% |
| 1050 | 64.5% | 26.9% |
| 1100 | 68.7% | 21.5% |
| 1150 | 68.5% | 24.8% |
| 1200 | 67.9% | 23.3% |
| 1250 | 67.8% | 24.5% |
| 1300 | 67.9% | 23.0% |
| 1350 | 67.4% | 24.1% |
| 1400 | 73.5% | 21.0% |
| 1450 | 67.7% | 22.3% |
| 1500 | 66.6% | 21.8% |
| 1550 | 69.0% | 23.2% |
| 1600 | 71.9% | 20.1% |
| 1650 | 75.2% | 18.4% |
| 1700 | 70.6% | 20.2% |
| 1750 | 72.3% | 20.0% |
| 1800 | 74.1% | 17.7% |
| 1850 | 73.7% | 18.0% |
| 1900 | 69.9% | 20.4% |
| 1950 | 73.0% | 18.1% |
| 2000 | 68.9% | 24.2% |
| 2050 | 74.6% | 15.6% |
| 2100 | 75.5% | 15.5% |
| 2150 | 73.8% | 18.1% |
| 2200 | 78.1% | 14.5% |
| 2250 | 72.6% | 17.7% |
| 2300 | 73.5% | 16.8% |
| 2350 | 75.0% | 17.1% |
| 2400 | 75.0% | 16.6% |
| 2450 | 74.3% | 16.4% |
| 2500 | 73.6% | 15.9% |
| 2550 | 68.3% | 20.0% |
| 2600 | 75.2% | 15.8% |
| 2650 | 74.1% | 17.0% |
| 2700 | 78.0% | 15.1% |
| 2750 | 74.1% | 17.1% |
| 2800 | 78.9% | 14.6% |
| 2850 | 75.8% | 16.0% |
| 2900 | 75.8% | 17.5% |
| 2950 | 73.8% | 17.7% |
| 3000 | 73.7% | 15.0% |
| 3050 | 74.9% | 15.5% |
| 3100 | 78.3% | 13.0% |
| 3150 | 75.6% | 14.8% |
| 3200 | 74.7% | 14.4% |
| 3250 | 75.9% | 15.1% |
| 3300 | 79.6% | 13.5% |
| 3350 | 73.1% | 18.5% |
| 3400 | 72.8% | 16.0% |
| 3450 | 77.5% | 14.1% |
| 3500 | 78.0% | 15.4% |
| 3547 | 77.1% | 15.3% |

## Review triage (frozen fully-taught model, unseen dev sentences)

Dev word accuracy 75.1%; 1186 wrong words.

| Words reviewed | Errors found (review order) | Errors found (random order) |
|---:|---:|---:|
| 10% | 39.4% | 9.9% |
| 20% | 51.7% | 21.7% |
| 30% | 71.9% | 31.5% |
| 50% | 87.7% | 49.7% |

Unflagged words (known form, single candidate): 48.7% of words at 93.7% accuracy. Flagged words hold 87.7% of all errors.

Simulated user: an answer counts as accepted only on an exact gloss match. "Picked" means the gold gloss was among the top five listed candidates. Rates are empirical on this development language and are not calibrated probabilities. Gitksan is not used.
