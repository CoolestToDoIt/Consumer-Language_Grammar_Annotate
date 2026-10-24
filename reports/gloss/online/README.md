# Source-only gloss online development experiments

Both final prefix matrices completed at implementation commit
`ded160c752e2fe87c70fbed5fa358c1f68bfc304`: three models, delays 0/5/20, and
all-label/correction-only feedback, for **36 complete runs**. All 36 checkpoints
passed exact log/metric/model reconstruction. The separate real Lezgi restart
matched its uninterrupted comparison.

| Language | Support / stream sentences | Probe sentences / words | Final immediate all-label memory / analogy / rules word accuracy |
|---|---:|---:|---:|
| Lezgi | 10 / 100 | 85 / 935 | 57.01% / 58.50% / 59.57% |
| Tsez | 10 / 100 | 445 / 4,761 | 30.69% / 35.35% / 41.59% |

- [Lezgi summary](lezgi-prefix-v3/summary.md), [metrics](lezgi-prefix-v3/results.json),
  [manifest index](lezgi-prefix-v3/manifest-index.json), [verification](lezgi-prefix-v3/verification.json).
- [Tsez summary](tsez-prefix-v3/summary.md), [metrics](tsez-prefix-v3/results.json),
  [manifest index](tsez-prefix-v3/manifest-index.json), [verification](tsez-prefix-v3/verification.json).
- [Real-corpus resume verification](resume-verification.json).
- [Interpretation and limits](../../../plans/updates_b/2026-10-24-06-development-matrix-results.md).
- [Commands and implementation handoff](../../../plans/updates_b/2026-10-24-07-handoff-and-commands.md).

Whole-source duplicates are removed before online selection; the first annotation
is retained and conflicts/exclusions are recorded. These are ordered prefix
development results, not replacements for the prior full-training baseline.
Pending answers are not drained. First guesses, disjoint probes, support retention
and training recall are measured separately. AUC reports include budget ranges;
latencies are model-call times, excluding checkpoint/probe/report work.

Unseen-word and sentence exact scores remain low. In these prefixes all stream
sentences needed a correction, so correction-only and all-label exposure happened
to match. No statistical language-level or unrestricted translation claim is made.
Gitksan remains reserved. Source/licensing metadata is pinned in
[SOURCES.json](../../../data/glossing/SOURCES.json).

Full local artifacts are under ignored
`runs/gloss-online-worker-b-20261024-{lezgi,tsez}-prefix-v3`. A checkpoint manifest
and its sibling `checkpoints/` directory must stay together. Earlier Lezgi `v1`/`v2`
attempts were interrupted by Windows ZIP replacement locks and are diagnostic only.
