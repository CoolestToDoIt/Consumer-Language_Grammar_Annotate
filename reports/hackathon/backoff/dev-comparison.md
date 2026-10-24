# Unseen-form normalization backoff (development data)

| Language | Model | Word exact | OOV word | Grounded OOV | Sentence exact | Top 5 | Precision when suggesting |
|---|---|---:|---:|---:|---:|---:|---:|
| Lezgi | rules | 72.2% | 15.8% | 27.7% | 11.4% | 77.0% | 84.7% |
| Lezgi | rules+backoff | 73.1% | 19.8% | 35.3% | 11.4% | 77.6% | 84.8% |
| Lezgi | rules+guess | 73.2% | 20.3% | 36.1% | 11.4% | 78.0% | 73.2% |
| Lezgi | rules+backoff+guess | 73.3% | 20.7% | 37.0% | 11.4% | 77.8% | 73.3% |
| Tsez | rules | 75.1% | 35.2% | 38.6% | 11.0% | 84.0% | 83.1% |
| Tsez | rules+backoff | 76.9% | 44.6% | 48.4% | 13.5% | 85.9% | 82.7% |
| Tsez | rules+guess | 76.9% | 44.5% | 48.4% | 12.8% | 85.8% | 76.9% |
| Tsez | rules+backoff+guess | 77.4% | 47.2% | 51.4% | 13.9% | 86.4% | 77.4% |

Backoff only changes unseen forms: it strips edge punctuation (keeping apostrophe letters) and casefolds, reuses glosses of taught forms with the same key, then retries affix rules. "guess" is the existing provisional analogy fallback. Development data only; the default engine is unchanged.
