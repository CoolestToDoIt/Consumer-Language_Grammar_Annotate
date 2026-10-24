# Combined gloss integration — in progress

The user deferred the internal-edit experiment until combined integration.
The model hypothesis space and default settings remain frozen.

## Combined branches

Fetched Worker B's published branch, whose preserved spelling is
`feat/gloss-online-evalulation`, at `c5c81e0`. Its handoff is under
`plans/updates_b/2026-10-24-07-handoff-and-commands.md`. The earlier fetches used
the expected spelling and therefore did not find this ref.

Created local `integration/gloss-workstreams` and merged it with the current
Worker A branch at merge commit `6713c3f`. There were no conflicts. Main and
both published feature branches remain unchanged. The initial combined suite
passed 82 tests.

## Integration fix and checks

Reproduced a partial session-manifest write leaving an orphan `.tmp` pointer
file. The previous complete checkpoint stayed valid. Extended the existing
cleanup guard to include manifest creation/write, with a regression injecting
a real partial write. It also verifies old-pointer preservation, successful
restore, and later save recovery. All **83 tests now pass**, including optional
neural tests and standard-library CLI checks.

Pinned Lezgi/Tsez corpus checksums pass offline verification. The combined
`gloss stream` CLI loads with `python -S`, without site packages.

## Next

Commit the fix before generating new manifests, then run fresh integrated
Lezgi/Tsez prefix matrices at the same 10 support/100 stream settings, 18 runs
each. Independently check saved artifacts and an interrupted/resumed real run.
Keep Worker B's historical reports untouched and preserve their original source
provenance. Core implementation fingerprints intentionally prevent continuing
an old-revision session on changed code; do not bypass that check.

After combined validation, update shared README/CURRENT with actual commands,
results and limitations. Present the concrete integrated diff and checks for
approval before merging into main. No experimental morphology work is included.
