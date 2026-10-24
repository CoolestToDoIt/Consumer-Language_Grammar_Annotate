# Worker B: Lezgi and Tsez development results

## What completed

Both final `v3` matrices completed: **18 runs per language, 36 total**. Each uses
memory, analogy and rules; delays of 0, 5 and 20 inputs; and all-label and
correction-only feedback. Each run starts with a fresh learner, 10 labeled support
sentences, and the next 100 unique training sources in upstream order.

These are bounded prefix experiments. They do not replace the earlier full-training
Lezgi baseline and do not evaluate the reserved Gitksan language. The learner's
algorithm, settings, and English/Turkish results were not changed.

Implementation revision: `ded160c` (`Use immutable gloss archives with atomic
checkpoint manifests`), incorporating Worker A's `83e70a0` engine interface.

## Data actually used

| Language | Support sentences / word labels | Stream sentences / word labels | Fixed probe sentences / words |
|---|---:|---:|---:|
| Lezgi | 10 / 106 | 100 / 1,009 | 85 / 935 |
| Tsez | 10 / 90 | 100 / 1,085 | 445 / 4,761 |

The reader found 107 repeated whole training sources in Lezgi and 14 in Tsez,
including one conflicting annotation in each language. Lezgi also has three
repeated probe sources; Tsez has none. The online selection keeps the first
annotation and excludes later copies before taking the prefix. All excluded IDs
and conflict counts are saved. There were no train/dev whole-source overlaps or
misaligned examples in these inputs. Shared individual words across the sets are
allowed: learning how familiar words combine or inflect is part of the task.

## Results with immediate, all-label feedback

“First guesses” means the original stream predictions before their answers.
“Final probes” means unseen development sources after the stream. OOV means a
source word spelling not yet observed in arrived annotations. AUC summarizes the
probe learning curve over 0–100 arrived stream sentence labels; support labels
are additional and are not included on that x-axis.

| Language | Model | First word accuracy | Final probe word accuracy | Final probe OOV | Sentence-label AUC |
|---|---|---:|---:|---:|---:|
| Lezgi | Memory | 42.91% | 57.01% | 0.00% | 49.06% |
| Lezgi | Analogy | 44.20% | 58.50% | 4.19% | 50.95% |
| Lezgi | Rules | 45.09% | 59.57% | 7.19% | 50.43% |
| Tsez | Memory | 21.84% | 30.69% | 0.00% | 21.16% |
| Tsez | Analogy | 27.93% | 35.35% | 7.38% | 25.45% |
| Tsez | Rules | 27.83% | 41.59% | 17.25% | 28.15% |

Rules have the highest final word score in these two prefixes. Analogy has a
slightly higher learning-curve AUC on Lezgi, so the final endpoint alone does not
identify the best method at every annotation budget. These are single ordered
development prefixes, without language-level uncertainty estimates.

Unseen-word performance remains weak. Exact full-sentence probe accuracy is only
1.18% for all three Lezgi models; in Tsez it is 0% for memory/rules and 0.67% for
analogy. Lezgi's rule model scores 44.81% on nonpunctuation words, below its 59.57%
overall word score. These are word-gloss results, not sentence translation scores.

## Delays, feedback exposure, and retention

All-label runs requested 100 stream answers. Delay 0/5/20 left respectively
0/5/20 pending answers and 100/95/80 arrived answers. Pending answers were not
drained. Every stream sentence had at least one mistaken word in these prefixes,
so correction-only runs also requested all 100 answers and happened to share the
same schedules. The code supports different exposure when models make completely
correct sentence guesses; the fixture tests exercise that case.

For the rule model, final probe word accuracy under delays 0/5/20 was respectively
59.57% / 59.57% / 57.97% on Lezgi and 41.59% / 40.64% / 38.16% on Tsez. Fewer
arrived labels accompany the longer delays. Each run's raw points and actual
sentence/word AUC budget range are in its JSON report.

Fixed support-set word retention fell by 5.66 percentage points from its best
snapshot in Lezgi and 4.44 points in Tsez. This is measured separately from unseen
accuracy. The word-level model can change a familiar form's majority gloss when
later examples provide a competing annotation; retaining all corrections does not
guarantee perfect recall of every originally labeled sentence.

## Measured model-call latency

For immediate all-label runs, median / p95 milliseconds were:

| Language | Model | Prediction | Feedback application |
|---|---|---:|---:|
| Lezgi | Memory | 0.146 / 0.309 | 0.294 / 0.763 |
| Lezgi | Analogy | 2.039 / 4.742 | 0.349 / 0.693 |
| Lezgi | Rules | 0.268 / 0.758 | 0.276 / 0.782 |
| Tsez | Memory | 0.152 / 0.315 | 0.783 / 1.683 |
| Tsez | Analogy | 4.371 / 11.454 | 0.786 / 1.529 |
| Tsez | Rules | 0.726 / 1.817 | 0.807 / 1.749 |

These time only model calls over support and stream inputs. Probe scoring,
checkpoint compression, reporting, startup, and other file I/O are excluded, so
they are not end-to-end CLI runtime estimates. Environment details are recorded
in every manifest. The corpus matrices ran sequentially.

## Where to read the results

- [Lezgi table](../../reports/gloss/online/lezgi-prefix-v3/summary.md) and
  [detailed JSON](../../reports/gloss/online/lezgi-prefix-v3/results.json).
- [Tsez table](../../reports/gloss/online/tsez-prefix-v3/summary.md) and
  [detailed JSON](../../reports/gloss/online/tsez-prefix-v3/results.json).
- Full predictions, private scoring data, fixed probe snapshots, model files and
  checkpoint generations remain in the corresponding ignored `runs/` directories.

The earlier Lezgi `v1` and `v2` attempts are incomplete Windows-lock diagnostics.
Only `v3` is the final completed matrix. All 36 final sessions passed exact
artifact/log/metric/model reconstruction checks. The separate real-corpus restart
also matched the uninterrupted run. Verification indexes are linked in the handoff.
