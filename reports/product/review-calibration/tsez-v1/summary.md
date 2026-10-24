# Tsez review/calibration development check

Frozen-model development correctness calibration and review ordering using production .dproj workspaces

Mode: rules. Calibration status: **validated**. Learner version: 110.

| Label purpose | Sentences | Word labels |
|---|---:|---:|
| learner_training | 110 | 1175 |
| calibration_fit | 100 | 1088 |
| calibration_validation | 445 | 4761 |

Frozen validation word accuracy: 41.59%.
Estimate coverage: 100.00%; held-out ECE: 0.0196589149820448; Brier: 0.0854374155549043; constant-prior Brier: 0.24301721657950057.

| Review order | Sentence reviews | Word annotations | Incorrect words found | Error fraction |
|---|---:|---:|---:|---:|
| upstream_order | 10 | 111 | 59 | 53.15% |
| unknown_ambiguity_order | 10 | 87 | 81 | 93.10% |
| validated_calibration_or_fallback | 10 | 87 | 81 | 93.10% |

The learner received only its declared training labels. Calibration fitting and validation remained disjoint and frozen; all validation candidates and model identity are unchanged. Reopen and calibration reload checks passed. A failed calibration supplies no confidence estimates; the last row then uses the documented heuristic fallback.

This is an ordered prefix development diagnostic. Equal sentence review budgets can cost different numbers of word annotations. It measures where errors concentrate before teaching, not subsequent learning or unrestricted translation. Raw artifacts stay in the specified local run directory; the workspace uses A's production format. Gitksan and the deferred stem-edit experiment are untouched.
