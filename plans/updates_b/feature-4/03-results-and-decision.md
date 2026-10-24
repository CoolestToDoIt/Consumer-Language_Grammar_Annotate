# Feature 4 results and decision

## Decision

**Reject default adoption of this internal-edit overlay.** The experiment is
complete, including its negative result. Keep the existing learner for the
application. No defaults or production checkpoint formats were changed.

The settings and decision gates were committed at `9afb8b8`, before either corpus
run. The tested and evaluated implementation is `4eb8632`. No settings, data
membership or acceptance thresholds were adjusted after seeing the outcomes.

The [machine-readable decision](../../../reports/gloss/internal-edits/decision.json)
fails two preregistered gates:

- Mean grounded unseen-word gain is **-0.309 percentage points**, below the
  required +1 point.
- Tsez grounded unseen-word accuracy drops **0.619 points**, beyond the allowed
  0.5-point loss.

The overall accuracy, technical correctness, time and memory gates pass. Passing
those gates alone does not justify adopting a model that misses its transfer goal.

## Data used

Both systems use source words only and identical full pinned annotations. There
were no alignment exclusions or exact train/development source overlaps in these
runs. Within-split repeated sentences retain the historical offline weighting.

| Language | Training sentences / word labels | Development sentences / words | Unseen words | Grounded unseen words |
|---|---:|---:|---:|---:|
| Lezgi | 634 / 6,250 | 88 / 992 | 222 | 119 |
| Tsez | 3,547 / 37,396 | 445 / 4,761 | 928 | 808 |

Training has 107 repeated whole sources in Lezgi and 14 in Tsez, with one
conflicting annotation in each. Development has three repeated sources in Lezgi
and none in Tsez. Both systems retain them equally. The full-record development
denominators therefore differ from the earlier unique-source online experiments.
All selected files and licenses match `data/glossing/SOURCES.json`. No reserved
Gitksan annotations or corpus test labels were inspected or evaluated.

"Unseen" means the exact source word was absent from training. "Grounded unseen"
additionally means its private gold lexical key already occurs in the trained
lexical paradigms. That label is used only for scoring, never as model input.

## Accuracy and coverage

Each cell shows baseline -> experiment. These are percentages, not relative gains.

| Metric | Lezgi | Tsez |
|---|---:|---:|
| Word exact | 72.177 -> 72.177 | 75.089 -> 75.005 |
| Unseen word exact | 15.766 -> 15.766 | 35.237 -> 34.806 |
| Grounded unseen exact | 27.731 -> 27.731 | 38.614 -> 37.995 |
| Nonpunctuation word exact | 61.268 -> 61.268 | 75.037 -> 74.953 |
| Top five exact | 77.016 -> 77.016 | 83.953 -> 83.995 |
| Coverage | 85.181 -> 85.282 | 90.401 -> 90.338 |
| Sentence exact | 11.364 -> 11.364 | 11.011 -> 11.011 |

Coverage means the model returned a gloss, even if it was wrong. Top five means
the correct gloss was among the returned candidates, even if it ranked below the
first choice. Neither should be described as first-choice accuracy.

Lezgi remains **716/992** correct, including **33/119** grounded unseen words.
Thirty word candidate records change, but only three first-choice glosses change;
all three were wrong before and after. Two words gain a prediction and one loses
it. The extra covered word does not improve accuracy.

Tsez changes from **3,575/4,761** to **3,571/4,761** correct. Three words improve
and seven regress, for a net loss of four. Grounded unseen accuracy changes from
**312/808** to **307/808**: two gains and seven losses in that subset. The third
overall improvement is a grammatical label outside that lexical subset. There
are 115 changed candidate records, 14 changed first choices, three newly covered
words and six words that lose coverage. Known-form full candidates are identical
for all **770 Lezgi** and **3,833 Tsez** known-word occurrences.

## What the changes tell us

The same 512 slots now contain 96 internal rules in Lezgi and 40 in Tsez,
displacing exactly that many selected baseline rules. Before selection, Lezgi has
3,048 baseline and 656 internal hypotheses; Tsez has 77,448 and 12,474.

Five of Tsez's seven regressions have a baseline winning-evidence rule that is no
longer selected. Four previously correct words now have no candidate. This is
consistent with competition for the fixed budget. It is not a controlled
attribution of every loss: additional votes can also change ranking, and the
recorded evidence rule is only one contributor to an aggregated score.

Representative private development examples:

- `ik’ixanu,` improves from unknown to `go-PRS-NEG`, using observed `ik’ix,`.
- `boysƛin”,` improves from unknown to `III-do-PST.WIT-QUOT`, using `boys,`.
- `ƛexunanu.` regresses from `remain-PFV.CVB-NEG` to `remain-PST.UNW-NEG`.
- `č’edoł` regresses from `earth-CONT.ESS` to unknown after its supporting edge
  hypothesis loses its selected slot.

All three improvements contain punctuation. An insertion immediately before a
comma or period qualifies as an internal character edit because the punctuation
is an unchanged final character. These gains are therefore not evidence that
the system learned a productive linguistic stem alternation. The frozen rule
definition intentionally stayed unchanged after discovering this limitation.

## Grounded unseen-word failures

The following categories describe the returned top-five candidates. "Lexical key
absent" means no returned candidate has the expected lexical key; it does not
prove the root is absent from all possible anchors or lower-ranked hypotheses.
"Grammar missing" means that key is represented, but the exact target gloss is
not in the returned five. "Ranking" means the target is returned below first.

| Failure category | Lezgi baseline -> experiment | Tsez baseline -> experiment |
|---|---:|---:|
| Expected lexical key absent from returned candidates | 59 -> 60 | 409 -> 410 |
| Exact grammatical output missing from returned candidates | 17 -> 16 | 41 -> 39 |
| Correct gloss returned below first | 10 -> 10 | 46 -> 52 |

Among experimental grounded failures, a selected internal inverse edit reaches
an observed anchor with the expected lexical key for only **6/86 Lezgi** and
**19/501 Tsez** cases. The remaining 80 and 482 cases lack such an internal
recovery. Merely knowing the lexical meaning elsewhere in training is not enough
for this bounded surface-change method to recover the unfamiliar form.

Known-form errors also remain: 89 in Lezgi and 585 in Tsez. This experiment keeps
the base known-form behavior, so it cannot resolve those ambiguities. Worker A's
separate contextual feature is outside this frozen comparison.

## Time, memory and reproducibility

| Measurement | Lezgi | Tsez |
|---|---:|---:|
| Full isolated child run, including reconstruction | 0.964 s | 3.738 s |
| Baseline fit | 0.047 s | 0.872 s |
| Overlay preparation | 0.008 s | 0.162 s |
| Baseline prediction | 0.0109 s | 0.0465 s |
| Overlay prediction | 0.0156 s | 0.1327 s |
| Checkpoint load plus overlay preparation | 0.073 s | 1.060 s |
| Process lifetime peak working set | 49.96 MiB | 177.12 MiB |

Both runs exit normally within their 120-second deadline and 512-MiB memory
allowance. Tsez prediction takes 2.86 times baseline, but adds only 0.086 seconds,
so it passes the predeclared alternative allowance of at most 0.25 added seconds.
These are single-process timing measurements on this Windows machine, not a
stable cross-hardware speed claim. Memory includes base plus overlay, prediction
arrays and restart verification; it is not an isolated overlay memory estimate.

All **146 tests** pass with zero skips. Both runs preserve the base model identity,
known-word candidate records, selected rules and every candidate after save/load.
Independent artifact replay also reconstructs every score, transition, sample and
grounded failure, and checks training/development membership and checksums.

Compact evidence is in [the experiment reports](../../../reports/gloss/internal-edits).
Full local artifacts remain under `runs/internal-edits-v1/`, which Git ignores.
Historical reports were preserved. Reproduction commands and file roles are in
[the handoff](04-handoff-and-commands.md).

This is a bounded development experiment, not a significance test, untouched-test
result, general translation system or demonstration that internal morphology is
unhelpful in general. Its supported conclusion is that **this frozen overlay
should not replace the current default**.
