# Internal-edit experiment: tsez

Status: **complete**.

| System | Word exact | OOV | Grounded OOV | Coverage | Sentence exact |
|---|---:|---:|---:|---:|---:|
| baseline | 75.089% | 35.237% | 38.614% | 90.401% | 11.011% |
| experimental | 75.005% | 34.806% | 37.995% | 90.338% | 11.011% |

Rules: {'algorithm_id': 'grounded-internal-stem-overlay-v1', 'base_version': 3547, 'total_rule_budget': 512, 'paradigm_window': 32, 'base_hypotheses': 77448, 'internal_hypotheses': 12474, 'selected_rules': 512, 'selected_internal_rules': 40, 'baseline_rules_displaced': 40}. Time seconds: {'parsing_seconds': 0.054689800017513335, 'base_fit_seconds': 0.8723951999563724, 'overlay_prepare_seconds': 0.16221930005121976, 'baseline_prediction_seconds': 0.046483400044962764, 'experimental_prediction_seconds': 0.13272969995159656, 'scoring_and_analysis_seconds': 0.167759699979797, 'base_checkpoint_save_seconds': 0.19285800005309284, 'checkpoint_load_and_prepare_seconds': 1.060052499989979, 'reconstruction_verification_seconds': 0.10717220010701567}.
Process peak: 185724928 bytes (177.12 MiB).
Correctness transitions: {'both_correct': 3568, 'candidate_records_changed': 115, 'top_gloss_changed': 14, 'newly_covered': 3, 'lost_coverage': 6, 'known_form_errors_unchanged': 585, 'both_wrong': 1183, 'baseline_correct_only': 7, 'experimental_correct_only': 3}.

Both systems use the same full pinned training/development records and one 512-rule budget. Duplicate-source weighting is retained and disclosed. These are development results, not unrestricted translation or language-level significance. Scores remain uncalibrated. The default learner and production CLI/checkpoint schemas are unchanged. A separate two-language decision report applies the preregistered adoption gates.
