# Source-only gloss online development results

Source-only real glossing; prediction before correction; fixed disjoint development probes.

| Mode | Delay | Policy | Inputs | Labels arrived (sentences / words) | Pending | First word | Final probe word | Sentence AUC |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| memory | 0 | all | 100 | 100 / 1085 | 0 | 21.84% | 30.69% | 21.16% |
| memory | 0 | corrections | 100 | 100 / 1085 | 0 | 21.84% | 30.69% | 21.16% |
| memory | 5 | all | 100 | 95 / 1012 | 5 | 20.92% | 29.51% | 20.48% |
| memory | 5 | corrections | 100 | 95 / 1012 | 5 | 20.92% | 29.51% | 20.48% |
| memory | 20 | all | 100 | 80 / 853 | 20 | 17.51% | 28.12% | 19.01% |
| memory | 20 | corrections | 100 | 80 / 853 | 20 | 17.51% | 28.12% | 19.01% |
| analogy | 0 | all | 100 | 100 / 1085 | 0 | 27.93% | 35.35% | 25.45% |
| analogy | 0 | corrections | 100 | 100 / 1085 | 0 | 27.93% | 35.35% | 25.45% |
| analogy | 5 | all | 100 | 95 / 1012 | 5 | 27.28% | 34.01% | 24.62% |
| analogy | 5 | corrections | 100 | 95 / 1012 | 5 | 27.28% | 34.01% | 24.62% |
| analogy | 20 | all | 100 | 80 / 853 | 20 | 23.04% | 32.68% | 23.35% |
| analogy | 20 | corrections | 100 | 80 / 853 | 20 | 23.04% | 32.68% | 23.35% |
| rules | 0 | all | 100 | 100 / 1085 | 0 | 27.83% | 41.59% | 28.15% |
| rules | 0 | corrections | 100 | 100 / 1085 | 0 | 27.83% | 41.59% | 28.15% |
| rules | 5 | all | 100 | 95 / 1012 | 5 | 26.36% | 40.64% | 27.16% |
| rules | 5 | corrections | 100 | 95 / 1012 | 5 | 26.36% | 40.64% | 27.16% |
| rules | 20 | all | 100 | 80 / 853 | 20 | 21.47% | 38.16% | 25.20% |
| rules | 20 | corrections | 100 | 80 / 853 | 20 | 21.47% | 38.16% | 25.20% |

These are prefix development experiments in upstream order, not full-corpus or final-language results. Whole-source duplicates are removed before selection; the first annotation is kept and conflicts are counted. Fixed development probes exclude every aligned training source, not just the selected prefix.

All-label runs share supervision schedules. Correction-only runs request labels according to their own saved errors, so their answer exposure can differ. Compare both processed inputs and arrived sentence/word labels. Support labels are reported separately and excluded from the curve x-axis. AUC is trapezoidal over the recorded probe snapshots and normalized over each run's declared arrived-answer range; different ranges require care in comparisons.

First predictions, held-out transfer, fixed support retention and current training recall are separate measurements. Full top-five candidates are saved. Scores are uncalibrated. Pending labels are not drained. Latency reports give median/p95 model-call milliseconds; checkpoint, report and probe costs are excluded. No language-level significance or unrestricted translation claim is made.
