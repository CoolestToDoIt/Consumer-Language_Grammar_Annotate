# Tested integration stopping point

Paused at the user's request to find a stopping point. No process or experiment
is left running. Work is on local `integration/gloss-workstreams`.

## Completed and checked

- Combined Worker A with `origin/feat/gloss-online-evalulation` at `c5c81e0`
  without conflicts; merge commit `6713c3f`.
- Fixed and regression-tested temporary manifest cleanup after partial writes;
  implementation commit `ad602cb`.
- **83 tests pass**, including optional neural and standard-library CLI checks.
- All 36 fresh Lezgi/Tsez prefix runs complete. Checkpoint, exported model/log,
  metric reconstruction, frozen selections and complete saved snapshot candidates
  verified. Non-timing metrics match Worker B's historical matrices exactly.
- A real standard-library-only Lezgi interruption/resume matches uninterrupted
  history, complete model state, all probe snapshots and reconstructed metrics;
  all 158 pre-interruption events are preserved exactly.
- Updated shared README/CURRENT with actual commands and limitations.

Evidence: `reports/gloss/online/integration-20261024/summary.md`. Raw artifacts
remain under ignored `runs/gloss-integration-20261024-*` directories. Existing
Worker B reports, reserved Gitksan labels and corpus test results are untouched.

## Branch state

Worker A's tested engine was pushed with user approval to
`origin/feat/gloss-engine` at `22e0203`. The combined integration and later status
documentation are local. Main is unchanged; no combined branch has been pushed.
The user deferred the internal-stem-edit experiment until combined integration.
It is only a proposal; no experimental model was implemented.

## Resume here

```sh
git switch integration/gloss-workstreams
git status --short --branch
git log -3 --oneline
```

Read this note and `plans/CURRENT.md`, then review the combined diff against main
and the compact verification reports. The next decision is approval to publish
the tested integration and merge it into main. Do not perform that important
action without approval. Re-run the suite if code changes:

```sh
.venv/bin/python -m unittest discover -s tests -v
python3 tools/fetch_corpora.py --collection glossing --corpus lezgi --corpus tsez --verify-only
```

Core fingerprints intentionally reject continuing old-revision sessions on new
code; use the recorded revision for those sessions. Keep a checkpoint manifest
and its sibling `checkpoints/` directory together. The complete overview plan is
still unfinished; structural expansion, calibration and cross-language studies
remain later work after integration and a separately approved scope.
