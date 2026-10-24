# Feature 4 implementation and verification

## What was built

`decipher/gloss_internal.py` adds `InternalGlossOverlay`, an experimental layer
around a fitted, authoritative `GlossLearner`. Nothing routes the product into it
automatically. Worker A's workspace/UI and the existing teaching/review CLI keep
their established behavior.

The layer learns spelling changes inside a word, such as `man` to `men`, from
forms with teacher-provided meanings. It can then transfer that pattern from an
observed `tal` meaning `tree` to unfamiliar `tel`, suggesting `tree-PL`. It cannot
invent a root meaning: reversing a rule must recover an observed source word,
and changing its gloss must preserve that word's learned lexical key.

Middle insertion and deletion work the same way. Both directions are learned.
An internal change must leave at least one source character on each side. The
existing prefix/suffix and new internal hypotheses share one 512-rule budget,
ranked by the same support, edit cost and deterministic tie order. Different
positions that recover the same anchor under one rule vote only once.

## State and restart behavior

- Construction and `prepare()` explicitly prepare the overlay. Prediction and
  recovery inspection only read prepared indexes; they do not train or rank rules.
- A changed base version or configuration makes the old overlay reject prediction.
  The caller must finish teaching and explicitly prepare it again.
- Duplicate feedback does nothing. Revised feedback removes the old annotation's
  evidence through the authoritative learner, then preparation rebuilds the layer.
- Known words return the base model's complete candidate records unchanged.
- Saving uses the existing schema-1 base checkpoint. `from_checkpoint()` loads
  that base and reconstructs the overlay, avoiding a second authoritative format.
- This experiment only supports rules mode with contextual prediction disabled.
  Its scores are ranking weights, not calibrated probabilities.

## Tests before corpus outcomes

The 129 existing tests passed before changes. The 17 new tests pass:

- Eleven model tests cover replacement, insertion, deletion, competing tags,
  Unicode, unsupported roots, known-word equality, duplicate/revised feedback,
  stale state, read-only prediction/RNG, schema-1 reconstruction, and full
  baseline-candidate equality when there is no internal evidence.
- An exhaustive reference checks indexed anchor recovery and the shared budget.
- Six runner tests check actual subprocess timeout and exit status, memory units,
  private-score reconstruction, every adoption gate, and tiny timing allowances.

Focused command: `.venv/Scripts/python.exe -X utf8 -S -m unittest
tests.test_gloss_internal tests.test_internal_experiment -v`.

## How the corpus runner works

`tools/evaluate_internal_edits.py compare` starts a fresh, standard-library-only
child for one language. The parent imposes a 120-second execution timeout and
records the last completed phase if it expires. Process creation and cleanup can
add platform overhead to the parent's elapsed time. This follows Python's
[subprocess timeout behavior](https://docs.python.org/3/library/subprocess.html).

Before fitting, the child checks the frozen base learner source and all pinned
files for that language, including its license. Both systems receive identical
full training records and development words. Exact whole-source train/dev
overlaps are excluded; within-split duplicates and conflicting annotations retain
the offline baseline's weighting and are counted explicitly.

Each phase is timed separately. On Windows, memory uses the documented
[PeakWorkingSetSize byte count](https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-process_memory_counters).
It measures the lifetime process peak, including base, overlay, prediction arrays
and checkpoint reconstruction, rather than pretending to isolate each component.

Raw local artifacts include membership, selected rules, source-only predictions,
private gold and changed-word diagnostics, scoring context, and a base checkpoint.
Compact versioned reports include hashes, exact metric counts, runtime/memory,
known-word equality, gains/losses and grounded-error categories. Every full
candidate record and selected rule is checked again after checkpoint loading.

`tests` writes a regression record tied to source fingerprints. `decide` applies
the criteria committed in the protocol before any corpus outcomes. Even a
passing result only recommends a separate adoption review; it changes no default.

Corpus results and the final combined regression record are pending at this
implementation checkpoint. See the following results/handoff notes when present.
