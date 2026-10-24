# Source-only gloss online development results

Source-only real glossing; prediction before correction; fixed disjoint development probes.

| Mode | Delay | Policy | Inputs | Labels arrived (sentences / words) | Pending | First word | Final probe word | Sentence AUC |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| memory | 0 | all | 100 | 100 / 1009 | 0 | 42.91% | 57.01% | 49.06% |
| memory | 0 | corrections | 100 | 100 / 1009 | 0 | 42.91% | 57.01% | 49.06% |
| memory | 5 | all | 100 | 95 / 967 | 5 | 41.33% | 57.01% | 49.44% |
| memory | 5 | corrections | 100 | 95 / 967 | 5 | 41.33% | 57.01% | 49.44% |
| memory | 20 | all | 100 | 80 / 836 | 20 | 36.37% | 55.83% | 47.47% |
| memory | 20 | corrections | 100 | 80 / 836 | 20 | 36.37% | 55.83% | 47.47% |
| analogy | 0 | all | 100 | 100 / 1009 | 0 | 44.20% | 58.50% | 50.95% |
| analogy | 0 | corrections | 100 | 100 / 1009 | 0 | 44.20% | 58.50% | 50.95% |
| analogy | 5 | all | 100 | 95 / 967 | 5 | 42.81% | 58.61% | 51.33% |
| analogy | 5 | corrections | 100 | 95 / 967 | 5 | 42.81% | 58.61% | 51.33% |
| analogy | 20 | all | 100 | 80 / 836 | 20 | 37.46% | 57.65% | 49.46% |
| analogy | 20 | corrections | 100 | 80 / 836 | 20 | 37.46% | 57.65% | 49.46% |
| rules | 0 | all | 100 | 100 / 1009 | 0 | 45.09% | 59.57% | 50.43% |
| rules | 0 | corrections | 100 | 100 / 1009 | 0 | 45.09% | 59.57% | 50.43% |
| rules | 5 | all | 100 | 95 / 967 | 5 | 43.31% | 59.57% | 50.84% |
| rules | 5 | corrections | 100 | 95 / 967 | 5 | 43.31% | 59.57% | 50.84% |
| rules | 20 | all | 100 | 80 / 836 | 20 | 37.96% | 57.97% | 48.57% |
| rules | 20 | corrections | 100 | 80 / 836 | 20 | 37.96% | 57.97% | 48.57% |

These are prefix development experiments in upstream order, not full-corpus or final-language results. Whole-source duplicates are removed before selection; the first annotation is kept and conflicts are counted. Fixed development probes exclude every aligned training source, not just the selected prefix.

All-label runs share supervision schedules. Correction-only runs request labels according to their own saved errors, so their answer exposure can differ. Compare both processed inputs and arrived sentence/word labels. Support labels are reported separately and excluded from the curve x-axis. AUC is trapezoidal over the recorded probe snapshots and normalized over each run's declared arrived-answer range; different ranges require care in comparisons.

First predictions, held-out transfer, fixed support retention and current training recall are separate measurements. Full top-five candidates are saved. Scores are uncalibrated. Pending labels are not drained. Latency reports give median/p95 model-call milliseconds; checkpoint, report and probe costs are excluded. No language-level significance or unrestricted translation claim is made.
