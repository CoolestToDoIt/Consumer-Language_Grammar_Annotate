# Efficient review and honest uncertainty

## What changed

Feature 6 is being built on `feat/efficient-review`, based on the verified
teaching checkpoint `8261882`. The separate `feat/real-text-teaching-cli` branch
preserves Feature 2. The requested umbrella branch will collect both features.

`decipher/review.py` adds read-only review ordering and Unicode-aware search.
Conflicting verified answers for the same complete source are shown first;
unsupported words and unseen forms then receive attention. Reviewed sentences
are normally skipped, except unresolved source conflicts. Ties are stable.
Search can include past annotation revisions and reasons when explicitly requested.

The revision checks and explicit replacement reason from Feature 2 also protect
review corrections. Conflicting source aliases are diagnosed, not silently merged:
some ambiguity can be real and should be reviewed by a person or A's context model.

## What calibrated uncertainty means here

The model's raw scores are not probabilities. A separate calibration artifact
estimates how often the top word gloss is correct for observed groups of candidate
kind, known/unseen form and relative candidate margin. Small groups back off to a
broader supported group; unsupported groups get no estimate. Unknown output has
zero exact-gloss correctness against a nonempty target.

Calibration uses a frozen model, a complete labeled fitting set and a disjoint
validation set. Neither set can contain a whole source used to train the learner.
Correction-only logs are rejected as a calibration policy because selected errors
do not represent all predictions. Calibration and validation labels are additional
supervision and are counted separately; they never update the gloss learner.

The default validation gate requires at least 100 fitting words and 100 scored
validation words, groups of at least 20 words, at least 90% estimate coverage,
ECE at most 0.10, and Brier score no more than 0.005 worse than a constant estimate
from fitting-set accuracy. These are declared development criteria, not a universal
guarantee. Rejected/insufficient artifacts supply no confidence estimates.

ECE measures the gap between estimated and observed correctness in reliability
bins; Brier score measures squared probability error. The calibration background
is [Guo et al., 2017](https://proceedings.mlr.press/v70/guo17a.html). This implementation
uses empirical groups, not that paper's temperature scaling, and reports both
metrics instead of relying on ECE alone.

An artifact is bound to the exact model evidence, ordering, settings, revision and
engine identity. Teaching changes invalidate it immediately. Review then falls
back to explicitly uncalibrated ordering. It does not reuse a stale percentage.
The estimates concern word correctness in the supplied development population,
not whole-sentence probability or language-level statistical significance.

## Commands

```powershell
.venv/Scripts/python.exe -X utf8 -S -m decipher.app gloss teach review --project runs/teaching-demo.fixture.json --backend fixture --limit 10
.venv/Scripts/python.exe -X utf8 -S -m decipher.app gloss teach search --project runs/teaching-demo.fixture.json --backend fixture --query bird --history
.venv/Scripts/python.exe -X utf8 -S -m decipher.app gloss teach calibrate --project runs/teaching-demo.fixture.json --backend fixture --fit PATH_TO_FIT_TIERS --validation PATH_TO_VALIDATION_TIERS --output runs/review-calibration.json
```

`review --calibration runs/review-calibration.json` uses estimates only when the
artifact is validated and current. Calibration file ingestion records duplicate,
overlap and alignment exclusions. Choose fresh artifact paths to preserve history.

## Tests so far

The first six review tests and eight calibration tests passed. Additional tests
now cover the complete calibration CLI flow and malformed validation metadata.
They check read-only behavior, hidden-answer separation, strict source disjointness,
stale calibration, insufficient support, failed validation and real revision safety.
The next step is combined verification and bounded real-development measurements.

Feature 4 remains deferred at the user's explicit request. There is no change to
the default learner or historical experiment schemas.
