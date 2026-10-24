# Online adaptation results

Development-only online comparisons. Shared source examples, seed labels, stream order, probe set and answer-delay schedule. All-label feedback is the main matched-supervision condition; corrections-only feedback may produce different label exposure and is reported separately. Pending labels are not drained.

| Task | Mode | Seed | Delay | Policy | Final probes | First guesses | AUC | Labels arrived |
|---|---|---:|---:|---|---:|---:|---:|---:|
| tr_imst-ud-train | affix | 7 | 0 | all | 55.0% | 17.5% | 0.550 | 40 |
| tr_imst-ud-train | frozen | 7 | 0 | all | 0.0% | 0.0% | 0.000 | 40 |
| tr_imst-ud-train | memory | 7 | 0 | all | 0.0% | 0.0% | 0.000 | 40 |
| tr_imst-ud-train | parameters | 7 | 0 | all | 0.0% | 0.0% | 0.000 | 40 |
| tr_imst-ud-train | replay | 7 | 0 | all | 0.0% | 0.0% | 0.000 | 40 |
| tr_imst-ud-train | hybrid | 7 | 0 | all | 0.0% | 0.0% | 0.000 | 40 |

No pretrained weights or cross-language initialization. Every neural condition starts from identical seed-specific parameters. Replay sees more training-example presentations per optimizer step; optimizer-step and presentation counts are reported, so these are equal-label comparisons, not equal-compute claims. Exact memory recall and retention are distinct from disjoint probe accuracy. Frozen-mode and tiny-data negative results are reported without selecting the best test outcome. Full state and event logs live in the corresponding local run directories.
