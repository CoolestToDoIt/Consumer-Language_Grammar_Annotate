# Worker B: reproducible experiments and restart support

## What this step does

An experiment must remember exactly what it saw and when it learned each answer.
Saving only its final dictionary cannot reproduce the first guesses or continue a
delayed-feedback run. This step adds the experiment's full history and selections
alongside the learner checkpoint.

## Files being developed

- `decipher/gloss_evaluate.py`: freezes the support examples, incoming stream, and
  development probes. It removes repeated whole sentences before online selection,
  keeps the first annotation, and records excluded IDs and conflicting answers.
  It counts requested and arrived labels in both sentences and words, and separates
  first guesses, unseen probes, support retention, and current training recall.
- `decipher/online.py`: records when feedback is requested as well as when it
  arrives. It measures the actual model calls and exports the full event history.
  The existing neural checkpoint methods are preserved.
- `decipher/gloss_checkpoint.py`: adapts the existing gloss learner to online
  sessions and bundles its model, pending answers, original events, remaining
  stream, private scoring answers, and configuration into one checksummed ZIP.
  The completed ZIP replaces the previous checkpoint in one operation.
- `decipher/gloss_app.py`: adds stream limits, checkpoint intervals, compact report
  output, and dedicated `resume` and `report` commands. Offline training/evaluation
  now use Worker A's equivalent bulk-fitting interface.

## Why the measurements are different

The previous streaming evaluator kept only its best guess and called that its
top-five result. The new history retains every candidate returned by the learner,
so top-five scoring checks actual alternatives. It also distinguishes a teacher's
decision to offer an answer from the answer actually arriving after a delay.

Learning curves use arrived annotations. Their normalized area is reported with
the actual budget range; a run that receives fewer answers does not silently get
the same denominator as another run. Pending labels remain queued at the end.

## Restart checks

The restore path checks archive contents and checksums, validates event order,
replays the feedback history privately, and checks the restored model against it.
Continuation also checks implementation fingerprints and original dataset hashes.
No PyTorch import is needed for gloss checkpoints. Original predictions are retained.

## Verification status

The starting 45 tests pass with `PYTHONUTF8=1`. New stream integration tests and
CLI checks are the next step; these implementation changes are not yet claimed as
verified. Corpus matrices will run only after the fixture checks pass.
