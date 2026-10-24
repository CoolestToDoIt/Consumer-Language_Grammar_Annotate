# Internal-edit experiment: lezgi

Status: **complete**.

| System | Word exact | OOV | Grounded OOV | Coverage | Sentence exact |
|---|---:|---:|---:|---:|---:|
| baseline | 72.177% | 15.766% | 27.731% | 85.181% | 11.364% |
| experimental | 72.177% | 15.766% | 27.731% | 85.282% | 11.364% |

Rules: {'algorithm_id': 'grounded-internal-stem-overlay-v1', 'base_version': 634, 'total_rule_budget': 512, 'paradigm_window': 32, 'base_hypotheses': 3048, 'internal_hypotheses': 656, 'selected_rules': 512, 'selected_internal_rules': 96, 'baseline_rules_displaced': 96}. Time seconds: {'parsing_seconds': 0.012988300062716007, 'base_fit_seconds': 0.04687079996801913, 'overlay_prepare_seconds': 0.008360200095921755, 'baseline_prediction_seconds': 0.010938799940049648, 'experimental_prediction_seconds': 0.015578899998217821, 'scoring_and_analysis_seconds': 0.019079299992881715, 'base_checkpoint_save_seconds': 0.033602199982851744, 'checkpoint_load_and_prepare_seconds': 0.0729128000093624, 'reconstruction_verification_seconds': 0.03246939997188747}.
Process peak: 52387840 bytes (49.96 MiB).
Correctness transitions: {'both_correct': 716, 'candidate_records_changed': 30, 'top_gloss_changed': 3, 'newly_covered': 2, 'lost_coverage': 1, 'known_form_errors_unchanged': 89, 'both_wrong': 276}.

Both systems use the same full pinned training/development records and one 512-rule budget. Duplicate-source weighting is retained and disclosed. These are development results, not unrestricted translation or language-level significance. Scores remain uncalibrated. The default learner and production CLI/checkpoint schemas are unchanged. A separate two-language decision report applies the preregistered adoption gates.
