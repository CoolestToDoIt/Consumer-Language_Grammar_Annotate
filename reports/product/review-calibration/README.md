# Worker B product review and calibration checks

Two bounded development runs used real `.dproj` workspaces with the frozen rule
condition (context off): 110 training sentences, then 100 separate calibration
sentences, followed by unique development validation. The learner never received
the calibration/validation answers. Source memberships and additional label budgets
are recorded in each JSON report.

| Language | Frozen word accuracy | Estimate coverage | ECE | Brier | Constant-prior Brier |
|---|---:|---:|---:|---:|---:|
| Lezgi | 59.57% | 100% | 0.025968 | 0.063041 | 0.242034 |
| Tsez | 41.59% | 100% | 0.019659 | 0.085437 | 0.243017 |

Both calibrators pass the predeclared gate for these development samples. Model
predictions stay unchanged. Unknown outputs being certainly wrong contribute to
good correctness calibration; this does not establish better language understanding.

- [Lezgi summary](lezgi-v1/summary.md) and [full report](lezgi-v1/results.json).
- [Tsez summary](tsez-v1/summary.md) and [full report](tsez-v1/results.json).
- [Saved-artifact reconstruction and real CLI verification](verification.json).
- [Plain-language interpretation](../../../plans/updates_b/product-features/06-development-results.md).
- [Implementation and commands](../../../plans/updates_b/product-features/07-handoff-and-commands.md).

Unknown-first review concentrates errors into fewer word annotations in these
prefixes. Equal sentence budgets have different word costs, which are reported.
Calibrated and heuristic ordering select the same first ten items here; no extra
ranking benefit or subsequent learning gain is claimed. A changed model invalidates
its calibration. The default project context setting is retained outside this
explicitly frozen evaluation. Gitksan and the stem-edit experiment remain untouched.

Raw project, calibration, prediction and private scoring artifacts remain under
ignored `runs/product-review-{lezgi,tsez}-v1`. Historical baseline reports are unchanged.
