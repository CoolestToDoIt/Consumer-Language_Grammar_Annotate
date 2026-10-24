# Worker B: checking the experiment protocol on small examples

## What was checked

The first integration-test pass completed successfully: **15 new tests passed**.
The tests include all 18 combinations of three models, delays 0/5/20, and the two
feedback policies. Each combination runs uninterrupted and also stops after seven
inputs, resumes for three more, then resumes to completion.

For those runs, the original predictions, full alternatives, annotation arrival
order, model versions, pending answers, final learned state, and fixed probe
snapshots match. Timestamps and measured call durations are excluded from equality
because they naturally change between executions.

## Other checks in that pass

- A queued correction can be replaced by a newer revision. Old answers do not
  accumulate conflicting evidence, and the original guess remains in the log.
- Invalid feedback does not replace a valid pending answer.
- Repeated whole sources are removed before online selection, including Unicode
  spelling variants that normalize to the same source. Conflicting labels are counted.
- Top-five scoring can credit a real second candidate when the first is wrong.
  A sixth candidate is not counted as top-five.
- Reports can be reconstructed with prediction and correction calls disabled.
- Probe evaluation does not modify the learner or the online session.
- Truncated archives, missing components, checksum mismatches, incompatible
  schemas, and inconsistent restored state are rejected.
- A simulated failed checkpoint replacement leaves the previous checkpoint usable.
- The CLI can train, predict, interrupt, resume, and rebuild a report with Python's
  third-party package loading disabled. Glossing therefore does not depend on PyTorch.

## Follow-up before corpus experiments

Review identified one additional boundary worth protecting: an invalid source
must not advance the input clock and accidentally release a pending answer.
That guard and a sixteenth test have been added. Restore validation also checks
the declared teacher policy/delay against requests and checks each probe's model
version and annotation state. The full combined suite will verify these additions
before the real development matrices run.

That combined verification has now completed: **61 tests passed** (45 existing
tests plus 16 Worker B tests), including all seven optional neural tests. No
regression was found. The environment emits PyTorch's existing missing-NumPy
warning, but the neural checks complete successfully and gloss commands do not
use NumPy or PyTorch. `git diff --check` also passes.

## Test command

```powershell
$env:PYTHONUTF8='1'
.venv/Scripts/python.exe -m unittest discover -s tests -p test_gloss_stream.py -v
```

This checks experiment correctness, not whether a small fixture establishes strong
real-language performance. Actual Lezgi/Tsez measurements are a separate next step.
