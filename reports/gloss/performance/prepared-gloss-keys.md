# Prepared lexical keys for observed glosses

Each observed gloss label is parsed once per reconstruction and stored in a
learner-local lookup. Ingestion reuses that key; rule inference reuses the
already-observed anchor's key while still parsing newly proposed glosses.
Prediction never inserts lookup entries. Revisions clear and reconstruct the
lookup from authoritative annotations, so superseded labels do not survive.

Six alternating full Tsez fits compared the unmodified `c7cac7f` engine loaded
from its Git source against the candidate in the same Python process, with
garbage collection before each fit. Median fitting time was 0.5018 s before
and 0.4777 s after, about 4.8% lower. Raw repetitions and source hashes are in
`tsez-gloss-keys-paired.json`. This is a local repeated diagnostic, not a
multi-machine benchmark or statistical confidence interval.

The reachable Python instance graph measured 66,275,343 bytes before and
66,362,262 after: an 86,919-byte increase across 9,391 cached labels. The method
uses `sys.getsizeof` with object-identity deduplication across model state and
referenced records; it excludes allocator and process overhead. It is not RSS
or a live allocation delta. See `tsez-gloss-keys-memory.json`.

Full Lezgi/Tsez candidates remain identical in all three modes and after reload.
The complete 705-row Tsez correction trace matches the original full-sort
baseline exactly. Reports: `lezgi-gloss-keys.json`, `tsez-gloss-keys.json`, and
`tsez-corrections-gloss-keys.json`; raw candidates/traces remain under ignored
`runs/gloss-engine-gloss-keys/` and `runs/gloss-engine-online-gloss-keys/`.

61 tests pass. Added checks for one parse per distinct observed label, empty
lexical keys for uppercase tags, removal of superseded keys during revision,
and no lookup state in a fresh learner. Existing full-state/reload comparisons
and read-only inference checks cover reconstruction and prediction behavior.
