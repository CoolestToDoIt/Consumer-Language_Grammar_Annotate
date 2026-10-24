# Teaching/review API and safety fixtures

## Why an adapter is needed

Worker A owns the real language workspace. The CLI and review logic should call
that workspace instead of maintaining a second production project format. The
interfaces below define B's requirements; they are a proposal for A to implement,
not a claim that A has already approved an API.

The development backend is explicitly named a **fixture**. It lets the complete
teaching flow run and reopen during tests and demonstrations. Its files identify
themselves as fixture projects. Production workspace loading is an injected adapter
and is not silently replaced by this test backend.

## Small interface

`ProjectStore.create(path, name, language, mode)` and `ProjectStore.open(path)`
return a project adapter. The adapter provides:

| Method/property | Meaning |
|---|---|
| `project_id`, `name`, `language`, `model_version` | Stable identity and current model revision |
| `submit(TextExample)` / `examples()` | Register/list public source sentences, with no gold attached |
| `predict(TextExample)` | Read-only word predictions with full candidates/evidence |
| `remember_prediction(record)` / `prediction(id)` | Store/retrieve immutable before-answer predictions |
| `annotation(id)` / `history(id)` | Latest verified annotation and all actual annotation revisions |
| `correct(...)` | Atomically check expected annotation revision and operation ID, then apply the correction |
| `model_identity()` / `training_sources()` | Bind calibration to the exact model and exclude its training sources |
| `save()` / `export(path)` | A-owned persistence boundary |

Correction requests include a prediction ID, one label per word, the annotation
revision reviewed, an idempotency operation ID, a reason and an explicit replacement
choice. Repeating an identical operation does not teach twice; reusing its ID for
a different request is an error. Replacing a different existing annotation requires
an explicit replacement choice and reason. Confirmation also rejects a prediction
from an older model version.

## Fixtures to establish before implementation

- Teach `tal mir` → `tree bird`, then `talum` → `tree-PL`; inspect `mirum`
  before teaching it. Confirm that only grounded affix transfer changes it.
- Unknown predictions cannot be confirmed as complete answers.
- Misalignment, empty labels, changed source under an existing ID, stale revisions,
  reused operation IDs and implicit conflicting replacements leave evidence intact.
- Two clients reviewing the same revision cannot silently replace each other.
- Reopen/export preserve prediction records and revision history, not just the
  latest dictionary. Failed writes preserve the last complete saved fixture.
- Search handles Unicode normalization and case; review puts unsupported items
  first without calling heuristic scores confidence.
- Calibration fitting and validation use disjoint whole sources, exclude learner
  training sources, and never correct the model. Too little data, failed validation,
  and changed model identity disable confidence estimates.

## Baseline

All **83 existing tests pass**, including the optional neural tests. New tests
will enforce these fixtures while the production workspace integration remains
owned by A. No default learner or old experiment format needs changing.
