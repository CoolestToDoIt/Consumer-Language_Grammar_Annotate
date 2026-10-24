# Synthetic grammar learning and correction foundations

Completed on 2026-10-24. Consolidates original updates 01–04.

## Delivered behavior

Implemented deterministic synthetic languages, exact memory, character-trigram
copying, and symbolic grammar learning. Presets use distinct roots and markers;
the learner considers contrasting grammars rather than one fixed suffix rule.
Corrections transfer to held-out combinations, arrive immediately or after a
declared delay, and persist across checkpoints.

The interactive CLI supports typed predictions, validated manual corrections,
fixed before/after probes, readable grammar hypotheses, and correction persistence.
Versioned dataset manifests identify episodes and splits. Grounding and split
checks prevent hidden answers from reaching public prediction inputs. Atomic
checkpoints reject incompatible episode/schema identities.

Prediction/feedback logs retain historical first guesses. Evaluation records
answer counts, model-call latency, per-support-lesson probes, normalized learning
AUC, and matched immediate/delayed schedules. Marker-reversal tests check that
contrary evidence changes learned rules rather than preserving an inherited
marker interpretation. Fresh episodes isolate learned state.

## Evidence and limits

The regular synthetic rule learner reaches 100% held-out probe accuracy after
nine support sentences. That saturation motivated measuring early acquisition
separately. Copying baselines cannot construct new held-out meanings, so this
comparison demonstrates correctness and transfer on the implemented grammar;
it does not establish real-language translation or a strong general benchmark.

The checkpoint had 13 tests covering transfer, contrasting grammars, state
isolation, held-out evaluation, delayed feedback, resume, dataset/schema identity,
invalid-answer rejection, and CLI persistence. These remain part of the later
combined suite. See [synthetic reports](../../reports/immediate/summary.md).

## What followed and what remains

The fixed three-word meaning schema was insufficient for real text. The next
milestone introduced a separate corpus model with learned vocabularies and label
inventories; see [real-corpus morphology](2026-10-24-02-real-corpus-morphology.md).
Broader grammar families, structural holdouts, calibration and replicated studies
remain research work in the [overview](../overview/Language_Decipherment_Build_Plan.md).
