# Lezgi review/calibration development check

Frozen-model development correctness calibration and review ordering using production .dproj workspaces

Mode: rules. Calibration status: **validated**. Learner version: 110.

| Label purpose | Sentences | Word labels |
|---|---:|---:|
| learner_training | 110 | 1115 |
| calibration_fit | 100 | 916 |
| calibration_validation | 85 | 935 |

Frozen validation word accuracy: 59.57%.
Estimate coverage: 100.00%; held-out ECE: 0.025967981494639546; Brier: 0.06304123447386258; constant-prior Brier: 0.24203354276315822.

| Review order | Sentence reviews | Word annotations | Incorrect words found | Error fraction |
|---|---:|---:|---:|---:|
| upstream_order | 10 | 140 | 49 | 35.00% |
| unknown_ambiguity_order | 10 | 61 | 42 | 68.85% |
| validated_calibration_or_fallback | 10 | 61 | 42 | 68.85% |

The learner received only its declared training labels. Calibration fitting and validation remained disjoint and frozen; all validation candidates and model identity are unchanged. Reopen and calibration reload checks passed. A failed calibration supplies no confidence estimates; the last row then uses the documented heuristic fallback.

This is an ordered prefix development diagnostic. Equal sentence review budgets can cost different numbers of word annotations. It measures where errors concentrate before teaching, not subsequent learning or unrestricted translation. Raw artifacts stay in the specified local run directory; the workspace uses A's production format. Gitksan and the deferred stem-edit experiment are untouched.
