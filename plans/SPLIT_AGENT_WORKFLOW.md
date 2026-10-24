# Two-person / two-agent development workflow

## Objective for the next milestone

Make source-only real-language glossing fast enough for larger development corpora, and make its online correction experiments reproducible and resumable. Split model implementation from experiment infrastructure so both people can work on separate branches with minimal conflicts.

This is the next implementation milestone, not a claim that the entire overview roadmap will be completed by these two branches. Keep the current model semantics and existing held-out results fixed during this milestone. Neural improvements, broader grammar families, calibration, and cross-language initialization follow after integration.

Suggested assignments:
- **Worker A: this developer/agent — gloss engine and performance.** Branch: `feat/gloss-engine`.
- **Worker B: the other developer/agent — online evaluation and resume.** Branch: `feat/gloss-online-evaluation`.
- **Integrator: Worker A**, with Worker B reviewing evaluation behavior. The roles can be swapped before work starts; file ownership should remain the same.

## 0. Establish the shared starting point

The working tree currently includes modified and untracked implementation files. Branching from the current HEAD alone will omit some of the tested checkpoint.

1. Review `git status --short` and create a shared checkpoint commit containing the intended source, tests, plans, dependency configuration, source/checksum manifests, and compact reports. Do not include downloaded corpora, `.venv`, fitted models, or full `runs/` artifacts.
2. Run the existing test suite in the neural-enabled environment. The expected checkpoint is **35 passing tests**. Without PyTorch, explicitly report skipped neural tests instead of claiming the full check passed.
3. Share the checkpoint commit SHA through the team's normal repository workflow. Both people branch from exactly that SHA. Record it in each branch's progress note and experiment metadata.
4. Each person uses a separate checkout/clone and local virtual environment. Reproduce corpora using the pinned fetch script rather than copying untracked data into Git.

Commands for the respective checkouts, after replacing `COMMON_BASE_SHA` with the shared commit:

```sh
# Worker A's checkout
 git switch -c feat/gloss-engine COMMON_BASE_SHA

# Worker B's separate checkout
 git switch -c feat/gloss-online-evaluation COMMON_BASE_SHA

# In each checkout
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[neural]'
.venv/bin/python tools/fetch_corpora.py --collection glossing
.venv/bin/python -m unittest discover -s tests -v
```

This document only plans the workflow. It does not create branches, commit existing changes, or push anything.

## Ownership

| Area / paths | Owner | Boundary |
|---|---|---|
| `decipher/gloss.py` | A | Learner, reader compatibility, rule preparation, bulk training, save/load performance |
| `tests/test_gloss.py` | A | Existing learner/reader regression tests |
| New `tests/test_gloss_performance.py`, `tools/profile_gloss.py` | A | Meaningful performance/equivalence checks and profiling |
| `decipher/gloss_evaluate.py` | B | Metrics, sampling, experiment manifests, offline/online orchestration |
| `decipher/gloss_app.py` | B | Wire bulk training and resume/report options into the existing gloss CLI |
| `decipher/online.py` | B | Event semantics, ordering, revisions; preserve neural session compatibility |
| New `decipher/gloss_checkpoint.py`, `tests/test_gloss_stream.py` | B | Gloss-specific session restore and integration tests; names may change within this ownership |
| `reports/gloss/performance/`, `plans/updates/*-engine.md` | A | Profiling and engine handoff notes |
| `reports/gloss/online/`, `plans/updates/*-evaluation.md` | B | Compact evaluation summaries and evaluation handoff notes |
| `README.md`, `plans/CURRENT.md`, shared CLI entry point `decipher/app.py` | Integrator only | Integrate documentation after both branches; the gloss subcommand already exists |
| `decipher/corpus.py`, existing neural/synthetic code, `pyproject.toml`, corpus source manifests | Frozen unless coordinated | Avoid unrelated refactors, schema changes, or dependency churn |

Do not independently edit the other worker's files. Request the change in a handoff note or small interface proposal. If an essential shared change is needed, land a small shared commit and have both branches incorporate it before continuing.

## Shared contract

Preserve existing interfaces during parallel development:

```python
# Public model input; no gloss, translation, or gold segmentation attached.
TextExample(id: str, tokens: tuple[str, ...])

GlossLearner(mode="rules", max_rules=512, paradigm_window=32)
learner.correct(example, glosses) -> bool
learner.predict(example) -> list[dict]
learner.save(path)
GlossLearner.load(path) -> GlossLearner
```

`correct` returns whether an authoritative annotation changed. Identical feedback is idempotent; revising an existing ID removes superseded evidence; changing the source under an existing ID is rejected.

`predict` returns one record per word with the existing `gloss`, `candidates`, and `known_form` fields. Candidate records retain `gloss`, `score`, and `kind`; explanatory evidence may be additive. Unsupported predictions use `None`. Scores remain explicitly uncalibrated. Prediction must not mutate model state or prepare a deferred cache.

**One agreed addition, implemented by A:**

```python
learner.fit(records: Iterable[GlossExample]) -> GlossLearner
```

Bulk fitting must produce the same observable predictions, candidate ordering/scores, authoritative records, and version as calling `correct` in the same order. It prepares all inference state before returning. Duplicates and revisions keep their existing semantics. It is valid to defer redundant rule sorting during bulk ingestion; it is not valid to move that work into prediction.

B can implement against the existing per-record loop while A works. Switch to `fit` in B's evaluator and train command after A's interface commit is available. Do not add duplicate model-training logic to B's branch.

The evaluator currently reads `model.lexicon`, `model.paradigms`, and `model._rules()` for diagnostics. A preserves those until integration. Replacing those accesses with a public diagnostics interface is a separate coordinated change, not a reason to create competing APIs now.

## Worker A: engine and performance

### A1. Capture a reproducible baseline

- Profile representative prefixes of Tsez training and the completed Lezgi run. The interrupted Tsez stack was inside full rule sorting called from every correction.
- Separate parsing, ingestion/rule induction, rule ranking, prediction, checkpoint save, and checkpoint reload time. Record corpus hashes, token/sentence counts, configuration, machine/runtime, and peak memory with units.
- Save local per-word Lezgi baseline predictions before changing the engine. Keep the existing `reports/gloss/lezgi-dev.*` reports unchanged.
- Do not repeat an unbounded full Tsez run merely to establish the already-observed bottleneck. Use a measured prefix and a bounded full-run attempt after the fix.

### A2. Add equivalent bulk fitting

- Avoid repeated global ranking while bulk ingesting; prepare the final rule cache once at the bulk boundary.
- Keep immediate `correct` behavior ready for the next prediction, including annotation revisions.
- Use the bulk path during checkpoint reconstruction where equivalence holds. Preserve loading of existing schema-version-1 gloss checkpoints.
- Keep the same rule bounds, ranking/tie behavior, lexical grouping heuristic, data membership, and label exposure. Any accuracy-changing algorithm change belongs in a later experiment.

### A3. Validate and hand off

Acceptance:
- Unit coverage for bulk versus sequential fitting, including duplicate IDs, revisions, all three modes, and save/load.
- Per-word predictions/candidate ordering match the unchanged Lezgi baseline; matching only the aggregate percentage is insufficient.
- Probe prediction leaves all learned/cache state unchanged.
- A measured speedup on the same corpus prefix and hardware. Target at least 5× bulk-training speedup; report the measured result even if the target is missed. Do not turn a machine-specific timing into a brittle universal unit-test assertion.
- Document the runtime/memory of a bounded full Tsez attempt and the remaining bottleneck if one persists.

Hand off the branch commit SHA, API confirmation, exact validation commands, baseline hashes, profiling report, and any limitations. Let B own production evaluation/report generation; use a profiling script or direct model calls on A's branch.

## Worker B: evaluation and resumable experiments

### B1. Work independently on small fixtures

- Add a reusable experiment manifest: dataset hashes, IDs/order of support/stream/probes, model configuration, revision/schema identifiers, feedback policy, delays, source commit, and environment.
- Preserve the public-input/private-answer boundary. Do not retain translation/segmentation tiers in learner inputs.
- Fix or disclose whole-source duplicates within/across support, stream and probes. Freeze the selected IDs/order so resumed and uninterrupted runs use exactly the same inputs.
- Record both sentence and word annotation budgets. Distinguish teacher decisions, answers requested, answers actually arrived, revisions, pending answers, and processed inputs.
- Keep stream first predictions, held-out probe transfer, and training recall as separate measurements.
- The current streaming metrics receive only the top prediction. Preserve full candidates before reporting top-5 accuracy, or omit that metric for the stream; do not present top-1 copies as top-5 evaluation.

### B2. Add real gloss-session resume

- Restore the gloss model through A's existing `save/load` contract and restore sources, step, pending feedback, processed revisions, original events, remaining stream identity/order, and experiment configuration.
- A gloss-specific checkpoint wrapper is preferable to replacing the neural-only `OnlineSession.save/load` behavior. Standard-library gloss commands must not acquire a mandatory PyTorch dependency.
- Write a complete checkpoint atomically, or use an atomic manifest that references complete, checksummed component files. Reject incompatible/corrupted/incomplete artifacts before applying further answers.
- Run delays 0/5/20 and both all-label and correction-only policies on tiny fixtures before corpus runs.
- Preserve historical predictions exactly. Resume comparisons should ignore newly generated wall-clock timestamps and measured latencies, but must match prediction contents, model versions, answer order, pending state, and final authoritative model state.

### B3. Run the development matrix after A's performance patch

- Incorporate A's API/performance commit and switch offline training to `fit`.
- Start with Lezgi, then Tsez: memory / analogy / rules × delays 0/5/20 × all-label / correction-only = **18 runs per language**, 36 if both complete.
- Use fixed development probes and a declared prefix budget initially (for example, 10 support + 100 stream sentences). Mark this as a prefix experiment, not a full-corpus result.
- All-label runs have matched supervision schedules. Correction-only runs can have model-dependent answer exposure; compare them by processed inputs and actual arrived labels and state that limitation.
- Report raw accuracy-versus-arrived-answer points, normalized AUC with its budget range, OOV/nonpunctuation/sentence metrics, retention, median/p95 latency, and pending-answer status. Never drain pending labels and rewrite historical scores.
- Save full artifacts under unique ignored `runs/` paths; keep compact summaries under the B-owned report directory. Preserve the previous baseline reports.

Acceptance:
- Tests for delayed arrival, idempotence, revision supersession, nonmutating probes, disjoint selections, invalid checkpoint rejection, and interrupted-versus-uninterrupted resume.
- Metrics can be reconstructed from immutable prediction/feedback logs and the private scoring data.
- The full existing neural-enabled suite still passes; no regression to the 35-test starting checkpoint.
- At least a bounded Lezgi end-to-end matrix completes with reproducible manifests; report incomplete Tsez work explicitly rather than filling in expected results.

## Coordination and integration order

1. **Shared start:** checkpoint SHA and the contract above are agreed before implementation. Each worker writes a separate progress note with ownership, current task, test command/results, and blockers.
2. **Parallel work:** A profiles/optimizes the engine; B builds fixtures, metrics, manifests and resume support against the unchanged API. B does not need to wait for full Tsez training.
3. **First review:** review and integrate A's minimal performance/API patch. It should not contain evaluator or shared README edits.
4. **Refresh B:** B merges the integrated engine changes into the private feature branch, or rebases if the branch has not been shared with others. Do not rewrite a branch other people are using. B switches evaluator/CLI training to `fit` and runs the bounded matrix.
5. **Second review:** integrate B's evaluator/resume work. Run all tests plus the documented CLI smoke run on the combined branch. Check behavior, not just resolution of merge conflicts.
6. **Integration checkpoint:** integrator updates README and CURRENT once, links both workers' notes/reports, and records what was measured, incomplete, and intentionally unchanged.

Keep commits focused: A baseline/profile → bulk-fit optimization → equivalence tests; B manifest/metrics → resume → integration tests → development reports. Avoid formatting unrelated files during this split.

Suggested final checks:

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python tools/fetch_corpora.py --collection glossing --verify-only
.venv/bin/python -m decipher.app gloss --help
```

The actual corpus matrix and resume commands should be documented by B after their CLI options exist; do not invent runnable flags before implementation.

## Guardrails and later work

- **Gitksan stays reserved.** Do not inspect/evaluate its dev/test labels during this milestone. Existing files can remain cached. Freeze settings and decide on final evaluation separately.
- Keep existing English/Turkish corpus test results fixed; use development data for changes.
- Do not claim unrestricted translation, calibrated confidence, equal-compute neural comparisons, or language-level statistical significance from these runs.
- Do not split one small stream across processes that share a mutable learner. Each language/run gets an isolated learner and output directory; parallelism is across independent runs only, after memory profiling.
- Prefer symbolic learning based on current evidence. Neural pilots showed no exact-match benefit; larger replicated neural training requires a separate, bounded experiment plan.
- After this milestone, parallelize again: one worker can expand grammar/OOV modeling while the other adds calibration/statistical analysis. Cross-language initialization and final held-out-language evaluation follow only when their prerequisites and protocols are ready.

## Copyable task briefs

**Worker A:** “Read plans/CURRENT.md and plans/SPLIT_AGENT_WORKFLOW.md. On feat/gloss-engine, profile the repeated gloss-rule ranking bottleneck, implement equivalent bulk fit and faster checkpoint reconstruction in decipher/gloss.py, and prove unchanged per-word predictions and read-only inference. Own the engine tests and profiling artifacts only. Preserve the agreed contract and existing reports. Do not run Gitksan or edit evaluation/CLI/shared documentation files. Hand off your commit SHA, measurements, test results, and limitations.”

**Worker B:** “Read plans/CURRENT.md and plans/SPLIT_AGENT_WORKFLOW.md. On feat/gloss-online-evaluation, build reproducible manifests, correct annotation-budget/stream metrics, and resumable gloss sessions. Own the evaluator, gloss CLI, session infrastructure and new stream tests. Work against the existing learner API until A's fit interface lands, then integrate it and run bounded Lezgi/Tsez development comparisons. Preserve historical predictions and neural checkpoint compatibility. Do not edit decipher/gloss.py, inspect Gitksan labels, or overwrite existing baselines. Hand off your commit SHA, run manifests, commands, test results, and limitations.”
