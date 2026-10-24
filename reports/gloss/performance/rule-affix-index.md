# Prepared source-affix rule index

Inference profiling on full Tsez development found 477,894 calls to `transform`
and 378,096 suffix checks. The original loop checked every selected rule for
each unfamiliar word. Profiling instrumentation captured inference only;
`tools/profile_gloss.py --profile-stage prediction --cprofile PATH` now supports
that separately from the default training profile.

Prepare a mapping from source side and required affix to ranked rules whenever
the selected rules change. Query only learned affix lengths, then restore
original rule order before accumulating votes. This preserves floating-point
addition order and the last supporting rule stored in each candidate. Empty
affixes, prefix/suffix edits, Unicode, and long tokens use the same matching
semantics. No inference cache is created or modified by prediction.

| Full development rule pass | Previous | Indexed |
|---|---:|---:|
| Tsez | 90.21 ms | 50.02 ms |

These are single-run diagnostics including JSONL serialization, about 1.8×
for this pass. Full Lezgi and Tsez candidates match all prior outputs in all
three modes and after checkpoint reload. Their SHA256 values remain
`f02d95f3db048b4c772a4e4c3215879b481659983fcd080692737eae5ff1e927`
and `02a931fc9a5960a0349bf056002dedd7032d4b73741aa1c3e1457c7baab0e3d0`.

Tradeoff: preparing the index adds work after rankings. The same 100-correction
Tsez trace rose from 47.84 ms total to 53.89 ms total; median correction is
0.562 ms and p95 is 1.004 ms. Its complete 705-row trace remains exactly equal
to the original full-sort baseline. Full Tsez training took 0.895 s and reload
0.942 s; process peak RSS was 207,126,528 bytes including both models. Treat
small memory/timing differences as noisy observations rather than precise
allocation or statistical estimates.

Final reports: `tsez-rule-affix-indexed.json`, `lezgi-rule-affix-indexed.json`,
and `tsez-corrections-affix-indexed.json`. `tsez-rule-indexed.json` records the
intermediate variant enumerating all query lengths, replaced by bounded learned
lengths. `tsez-rule-inference-profile.json` instruments the original inference;
`tsez-rules-profile.json` captures original training only. Full binary profiles
and raw predictions remain under ignored `runs/` directories.

54 tests pass. Added an exhaustive affix-filter oracle over randomized Unicode
queries and candidate comparisons against the original full-rule scan after
updates, annotation revisions, and checkpoint reconstruction. The public API,
model settings, checkpoint schema, and accuracy are unchanged.
