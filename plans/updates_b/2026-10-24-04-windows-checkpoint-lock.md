# Worker B: handling a Windows checkpoint file lock

## What happened

The first Lezgi matrix attempt completed five conditions, then Windows refused to
replace a checkpoint ZIP in the OneDrive-backed workspace (`WinError 5: Access is
denied`). The command exited with an error instead of pretending the matrix was
complete. The partial run remains under
`runs/gloss-online-worker-b-20261024-lezgi-prefix-v1` for inspection.

This was an operating-system file lock during the final atomic replacement. It
was not a model prediction failure or a corpus checksum mismatch. The previous
checkpoint remains the recovery point when replacement fails.

## Change

`decipher/gloss_checkpoint.py` now retries only a permission/file-sharing error
while replacing the completed ZIP. It makes at most six attempts, waiting a total
of at most 1.55 seconds. Other errors still fail immediately. If the lock persists,
the run still reports failure and retains the old complete checkpoint.

A new test simulates two temporary sharing errors and verifies that the third
replacement succeeds and restores the same session. The existing interrupted-save
test still checks that a permanent failure leaves the previous checkpoint usable.

Source fingerprints now normalize LF/CRLF line endings before hashing. This lets
the same Python revision checked out on different systems pass the code-identity
check despite Git's Windows line-ending conversion; changes to code still reject
continuation.

## Next check

Run the combined regression suite again, then start the bounded matrices in fresh
`v2` run directories. The `v1` attempt is incomplete and will not be presented as
a completed development matrix.

The combined verification is complete: **62 tests passed** (45 existing and 17
Worker B tests), including neural resume compatibility. The retry fix is ready
for the fresh corpus runs. No corpus settings or learner semantics changed.
