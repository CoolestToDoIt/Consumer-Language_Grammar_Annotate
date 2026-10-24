# Combined gloss integration validation

Fresh runs used core implementation commit `ad602cb` on local branch
`integration/gloss-workstreams`, combining Worker A and Worker B with the
partial-manifest-write cleanup fix. **83 tests pass**, including optional neural
tests. Lezgi/Tsez pinned dataset checksums pass offline verification.

Both 18-run prefix matrices completed: memory/analogy/rules × delays 0/5/20 ×
all-label/correction-only feedback, ten support and 100 stream sentences. No
pending labels were drained. All non-timing metrics match Worker B's historical
matrices exactly, excluding source-dependent manifest hashes and output locations.
Frozen IDs/source hashes, scoring hashes and exclusion accounting also match.

| Immediate all-label final probe word accuracy | Memory | Analogy | Rules |
|---|---:|---:|---:|
| Lezgi | 57.01% | 58.50% | 59.57% |
| Tsez | 30.69% | 35.35% | 41.59% |

[Verification](verification.json) records checks for all 36 runs: checksummed
checkpoint loading, exact exported events/requests/feedback, metrics reconstruction,
exported model state, and complete probe/retention/recall candidates replayed at
each saved history boundary. These are integrity/equivalence checks, not new
model improvements or independent statistical replications.

[Real-corpus resume verification](resume-verification.json) used the CLI with
site packages disabled. A Lezgi rule run stopped at 37 inputs with 17 stream
answers arrived and 20 pending. It resumed to 100 inputs, 80 answers arrived,
20 pending, and model version 90. All 158 original events stayed intact. Its
complete history (excluding timestamps/latencies), learned state, all snapshots,
and reconstructed report match the uninterrupted run.

Raw integrated matrices are local under ignored
`runs/gloss-integration-20261024-{lezgi,tsez}-prefix-v1`; the restart is under
`runs/gloss-integration-20261024-resume-v1`. The local audit script is
`runs/gloss-integration-20261024/verify.py`. Historical reports remain unchanged.
Fresh matrix commands use the options in Worker B's handoff with these new
output paths and no `--report-dir`; this folder keeps compact verification only.

These remain ordered development prefixes. Unseen-word and sentence accuracy
are limited; correction-only and all-label exposure happened to match on these
prefixes. Gitksan and corpus test labels were not evaluated. No main merge,
integration publication, or internal-stem-edit experiment has been performed.
