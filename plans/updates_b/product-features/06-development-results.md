# Development results: calibration and efficient review

## What was measured

Both bounded checks completed using real `.dproj` workspaces. Each starts from
the existing rule model with **110 unique training sentences**, then fits
uncertainty calibration on the next **100 unique training-file sources** and
validates on unique development sources. Whole-source duplicates are removed
before selection; the first annotation is kept and exclusions/conflicts are logged.

Context was explicitly disabled for this controlled measurement so the frozen
word-gloss baseline condition stays comparable with the earlier prefix results.
Normal user projects retain A's configured context support. Calibration never
changed the learner, and full before/after candidate records match exactly.

## Supervision budgets

| Language | Learner training | Calibration fitting | Calibration validation |
|---|---:|---:|---:|
| Lezgi | 110 sentences / 1,115 word labels | 100 / 916 | 85 / 935 |
| Tsez | 110 sentences / 1,175 word labels | 100 / 1,088 | 445 / 4,761 |

Calibration and validation labels are additional supervision. They are not
counted as labels used to teach vocabulary or morphology, and do not enter the
learner's annotations. The three selections are disjoint by whole NFC source.
Every record ID/order, source hash, original file checksum and configuration is
saved. Gitksan was not accessed.

## Calibration outcome

| Language | Frozen word-gloss accuracy | Estimate coverage | Held-out ECE | Brier score | Constant-prior Brier | Gate |
|---|---:|---:|---:|---:|---:|---|
| Lezgi | 59.57% | 100% | 0.025968 | 0.063041 | 0.242034 | Validated |
| Tsez | 41.59% | 100% | 0.019659 | 0.085437 | 0.243017 | Validated |

Lower ECE and Brier are better. Both artifacts passed the thresholds declared
before these runs. This validates correctness estimates for the supplied frozen
development samples. It does not improve the underlying gloss predictions or
establish calibration for arbitrary languages or future model revisions.

The unchanged word-gloss accuracy is the same as the earlier immediate-feedback
110-sentence prefix condition. A major contributor to good correctness calibration
is recognizing unsupported outputs: an unknown gloss cannot exactly match a
nonempty target. A low calibration error is not evidence that unknown meanings
have been learned.

## Which items were presented first

The following compares the first **10 sentence reviews** in each order. A sentence
review requires a label for every word, so the word annotation cost is also shown.

| Language | Order | Word labels reviewed | Incorrect words found | Errors per reviewed word |
|---|---|---:|---:|---:|
| Lezgi | Upstream source order | 140 | 49 | 35.00% |
| Lezgi | Unknown/ambiguity priority | 61 | 42 | 68.85% |
| Lezgi | Calibrated priority | 61 | 42 | 68.85% |
| Tsez | Upstream source order | 111 | 59 | 53.15% |
| Tsez | Unknown/ambiguity priority | 87 | 81 | 93.10% |
| Tsez | Calibrated priority | 87 | 81 | 93.10% |

Priority concentrated mistakes into fewer word annotations. On Lezgi it found
fewer total errors per ten sentences, but used substantially fewer word labels.
On Tsez it found more errors with fewer word labels. These are different cost
comparisons; the report does not hide them behind one “efficiency” percentage.

The heuristic and calibrated order selected the same first ten items in both
languages. These runs therefore do **not** demonstrate extra ranking benefit
from calibration at that budget. They establish supported correctness estimates
and a useful unknown-first review order. No corrections were applied while
measuring the review queues, so this is error concentration, not a measured
active-learning gain.

## Reproducibility and integrity

Measurements record implementation commit `e1fad21`. A later shell text-parsing
fix does not change the learner or calibrator. Verification against the final
code reconstructed:

- original full validation candidates from reopened workspaces;
- word metrics from saved predictions and separate private scoring records;
- calibration Brier/ECE and reliability bins;
- review order and word-annotation costs;
- source memberships, checksums, model identities and the absence of validation
  labels from authoritative learner annotations.

The production CLI smoke run taught anchors and a plural form, correctly predicted
`mirum` as `bird-PL` before confirmation, retained that original prediction, kept
an unreviewed sentence containing an apostrophe literal, and reopened/restored its
backup with identical model and teaching metadata. It ran with third-party package
loading disabled.

The final **129-test suite** passes, including all seven neural tests and A's
workspace/web tests. New and modified runtime files also parse with Python 3.10
grammar; execution was on the local recorded Python 3.13 runtime, so this is not
a claim of a separate Python 3.10 runtime test.

## Artifacts

- [Lezgi summary](../../../reports/product/review-calibration/lezgi-v1/summary.md)
  and [detailed results](../../../reports/product/review-calibration/lezgi-v1/results.json).
- [Tsez summary](../../../reports/product/review-calibration/tsez-v1/summary.md)
  and [detailed results](../../../reports/product/review-calibration/tsez-v1/results.json).
- [Reconstruction and real CLI verification](../../../reports/product/review-calibration/verification.json).

Raw workspaces, calibration artifacts, prediction logs and private scoring files
remain under ignored `runs/product-review-{lezgi,tsez}-v1`. The synthetic real-CLI
smoke workspace and backup are under `runs/product-teaching-smoke`.

Historical reports are unchanged. Feature 4 remains deferred, and no language-level
significance, unrestricted translation or external user-trial claim is made.
