# Worker B: reliable checkpoints in a synced Windows folder

## Why the format changed

The bounded retry prevented some transient file locks but the second Lezgi attempt
still stopped while replacing a ZIP. Six memory conditions completed; this second
attempt remains an incomplete `v2` run. It is not used as the final result.

Repeatedly replacing a large ZIP is unreliable in this OneDrive-backed workspace.
The split plan explicitly allows an atomic manifest pointing to complete,
checksummed component files. This step adopts that option instead of depending on
the lock disappearing quickly.

## How saving now works

1. Save a complete session ZIP under a new unique name in `checkpoints/`.
2. Record its relative filename and SHA-256 checksum in a small manifest.
3. Atomically replace `checkpoint.json` with that manifest, after the ZIP is complete.

The model, original predictions, pending answers, scoring data and configuration
remain together inside each ZIP. Old ZIPs are immutable and stay available as
recovery points. A failure before the manifest replacement leaves the previous
manifest pointing to its previous complete archive. A later run may leave an
unreferenced ZIP after an interrupted save; it is harmless and is retained locally.

The reader checks the manifest and archive checksum, checks the archive's internal
component checksums, and performs the existing event/model/experiment validation.
It rejects missing archives and references outside the local `checkpoints/`
directory. It also accepts a standalone session ZIP for inspection.

## What changes for the user

Use `--checkpoint PATH/TO/checkpoint.json` with `gloss resume` and `gloss report`.
Keep that manifest and its sibling `checkpoints/` folder together when copying a
run. Old generations are intentionally not deleted automatically.

## Checks added

Tests cover complete/checksummed archive references, missing archives, changed
checksums, an escaping path, unsupported manifest versions, successful standalone
ZIP loading, transient manifest locks, and a persistent lock that leaves the old
manifest usable. Periodic and final saves also avoid writing a duplicate final
generation when a checkpoint was just saved at that input boundary.

The combined suite will be rerun before the fresh `v3` development matrices.

Verification completed: **63 tests passed** (45 existing and 18 Worker B tests),
including the complete interrupted/resumed matrix and neural checkpoint tests.
`git diff --check` passes. Fresh corpus runs can now use the manifest format.
