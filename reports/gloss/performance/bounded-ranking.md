# Exact bounded rule selection

The selected top K now uses `heapq.nsmallest` when the candidate union exceeds
four times K, retaining full sorting for small unions. Both use the identical
total ordering: descending support, ascending edit complexity, then rule tuple.
This changes computation only, with no approximation or model setting change.

An isolated five-run check on the same full Tsez evidence (77,448 rules, K=512)
measured median full sorting at 91.68 ms and bounded selection at 37.28 ms.
End-to-end full Tsez fitting measured 0.809 s, including 0.0624 s in ranking,
versus the preceding affix-indexed run's 0.895 s and 0.1699 s. Reload measured
0.919 s versus 0.942 s. These small single-run end-to-end differences are noisy;
the isolated measurement avoids ingestion costs but is not a multi-machine
benchmark.

Lezgi and Tsez complete development predictions match the prior artifacts in
all three modes, with full checkpoint reconstruction equivalence. The entire
705-row Tsez correction trace also matches the original baseline. Ranking
time on that stream is 0.0353 s, essentially the preceding 0.0355 s, because
small candidate unions continue to use sorting.

Reports: `lezgi-bounded-ranking.json`, `tsez-bounded-ranking.json`, and
`tsez-corrections-bounded-ranking.json`. Raw candidate and trace artifacts remain
under ignored `runs/gloss-engine-bounded-ranking/` and
`runs/gloss-engine-online-bounded/`.

Regression coverage compares against exhaustive sorting after every randomized
correction/revision and explicitly checks empty pools, fewer than K rules, and
pool sizes immediately below/at/above the selection strategy boundary.
