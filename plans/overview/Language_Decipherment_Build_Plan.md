# Interactive Language Decipherment Build Plan

Build and evaluate a learner that starts with a small set of translated examples, guesses the meanings of unfamiliar words and sentences, and improves when a teacher supplies the correct answer. The main research question is whether a correction improves predictions on other unseen examples that use the same linguistic structure.

This plan assumes one developer, text input, an English or structured meaning output, and roughly 10 to 12 weeks of part time work. The first prototype should run on a laptop. These are planning assumptions and proposed settings, not measured performance claims.

### The first deliverable

Create a command line program with a simulated teacher. It accepts a short invented sentence, returns its best interpretation and alternatives, receives a correction immediately or later, and saves an updated learner. A repeatable evaluator measures its first predictions before any correction is revealed.

### What counts as success

The learner should transfer a correction to new combinations, require fewer corrections than strong simple baselines, and preserve previously learned meanings. A later experiment should show whether the same approach helps with at least one real language held out from development.

### Boundaries of the first version

Use typed text with known word boundaries. Start with vocabulary, inflection, and short sentence structure. Handwriting recognition, speech, missing word boundaries, unrestricted conversation, and archaeological decipherment are separate extensions. A successful synthetic experiment supports a limited learning claim, not universal language decipherment.

### The central information constraint

Patterns can reveal recurring units and structure, but arbitrary word meanings need an anchor. If the learner has never received any evidence connecting a new root to a concept, it cannot reliably name that concept. Teacher translations supply those anchors. Familiar roots and grammatical rules can then support predictions about unfamiliar combinations.

### Deliverables

- A versioned data generator and manifests identifying every split.

- Memorization, analogy, rule learning, and neural comparison models.

- An event based correction engine with immediate and delayed feedback.

- Reproducible experiments, plots, checkpoints, and an error report.

- A small interactive demonstration after the evaluator works.

## Research Questions and Experimental Claims

### Questions to answer

Q1. Does one correction help predict new words that contain the same affix or follow the same rule?

Q2. Does the learner infer sentence roles and tense when familiar words appear in unfamiliar combinations?

Q3. How does starting with 10, 25, or 100 labeled examples change the number of later corrections needed?

Q4. How much do feedback delay, irregular forms, ambiguity, and missing boundaries reduce performance?

Q5. Do rules learned across several languages make adaptation to a genuinely held out language faster?

Q6. Can a learner starting fresh acquire contrasting root and grammar systems without defaulting to the structures most familiar to its designer or prior training?

### Separate three forms of novelty

An unseen combination contains familiar parts in a new arrangement, such as a known noun with a known plural suffix. An unseen form expresses a meaning already grounded elsewhere, such as a new spelling or inflection. An unseen concept has no established meaning connection. Score these separately; performance on combinations does not establish discovery of ungrounded concepts.

### Proposed hypotheses

H1. A model that learns reusable morphology will outperform an exact dictionary on held out root and affix combinations after equal feedback.

H2. Combining episodic memory with incremental parameter updates will improve adaptation while reducing forgetting relative to updates without replay.

H3. An initialization trained across artificial languages may improve adaptation on held out language rules. This is an optional later hypothesis, not a requirement for the first working system.

### Important comparisons

Compare a learner with its parameters frozen, a learner whose memory alone changes, a learner whose parameters alone change, and one where both change. This identifies whether gains come from retrieval, rule revision, or neural training.

### A concrete transfer test

Teach tal = TREE, mir = BIRD, and talum = TREE plus PLURAL. Before revealing mirum, ask the model to predict its meaning. After one correction involving another plural example, evaluate a fresh set of roots combined with that suffix. Track the changed predictions. Do not put the corrected item itself in the transfer score.

### Claims to avoid

Do not describe a remapped English cipher as a structurally unknown language. Do not call success on a previously translated item generalization. Do not claim that a multilingual pretrained model began with only the few examples shown to it. Report prior training separately from target language supervision.

## Data Generator and Learning Curriculum

### Controlled meaning representation

Represent meanings with typed records, for example {predicate: SEE, agent: BIRD, patient: TREE, tense: PAST, agent_number: PLURAL}. Use a canonical serialization with fixed field names and ordering. Keep the concept inventory explicit. The simulator can render an English explanation for people, but the scorer compares structured meanings.

### Generate artificial languages

Start with 30 noun roots, 12 verbs, 4 attributes, singular and plural, and present and past tense. Sample short forms from a small sound inventory while preventing accidental collisions in the initial task. Randomize the root to concept mapping per language so spelling cannot reveal the English answer.

Choose word order, plural and tense placement, adjective position, and whether grammatical features are separate words or attached pieces. Begin with regular concatenation. Add prefixes, suffixes, zero marking, agreement, exceptions, and ambiguous forms in later difficulty levels. Record the hidden grammar for scoring and diagnosis; never expose it to the learner. Sample it once per language and hold it fixed within that episode, including its context rules and exceptions. Balance structural choices rather than letting one grammar pattern dominate the dataset.

### Curriculum stages

- Stage A: regular word morphology with isolated word meanings.

- Stage B: sentences of 3 to 8 words with compositional meanings.

- Stage C: exceptions, ambiguous words, and changes of word order.

- Stage D: held out grammar families and optional missing word boundaries.

The simple -um example is only a sanity check. Vary the forms and structural choices across the benchmark so one hand coded plural rule cannot solve it.

### Proposed data sizes

For development, generate 30 training languages, 10 validation languages, and 20 final test languages. Use 25 seed translations and a stream of 300 examples per test language. Keep all seed sizes identical within a comparison. Begin with five languages and shorter streams for debugging before running the full set.

### Split before sampling examples

Keep complete language identities separate across training, validation, and final testing. Within each language, reserve particular root and affix combinations and meaning structures for probes. Ensure probe primitives have been grounded if the test is intended to measure composition. Maintain a separate challenge for ungrounded roots and label its limitations.

### Real language extension

Use the SIGMORPHON 2023 interlinear glossing task as a candidate source [3, 4]. Select two development languages and one final language after checking licensing, available examples, and morphology. Start with word and grammatical gloss prediction. Glossing is a tractable subproblem; it is not full free form translation. Document the selected languages and data counts before the final run.

## Learning Each Language Without Inherited Grammar Assumptions

### The assumption to test

When starting a new language from scratch, the learner must infer its roots, morphology, and grammar from that language's evidence. It must not presume that the new language follows Romance language conventions or whichever patterns dominated earlier training. After learning begins, assume that the language is mostly internally consistent. Stable grammatical rules can include context dependent constructions and regular exceptions.

This is a question about bias across languages. It does not require the grammar of one language to keep changing during an episode. Sample a grammar once per language and keep it fixed throughout its support examples, stream, and probes. Introduce grammar change only as a separately labeled future experiment.

### A clean start for each new language

In the strict from scratch condition, create a fresh learner for every language. Reset weights, optimizer, root dictionary, rule counts, inferred segmentation, memory, replay buffer, pending feedback, and any fitted normalization or calibration. Give it only generic input processing, the declared meaning inventory, the same broad hypothesis space, and that language's permitted seed translations.

Within the language, preserve these learned states across corrections. Do not reset its grammar for every new word. Record a state fingerprint before each episode and test that no examples or fitted language specific parameters survive from the preceding episode.

### Separate prior knowledge from a clean start

Cross language pretraining and meta learning are separate experimental conditions. They may transfer useful learning strategies, but they also transfer preferences. Never label those conditions as learning entirely from scratch. Run the fresh initialization condition alongside them to quantify both positive transfer and harmful inherited assumptions.

### Broaden the structural possibilities

Balance synthetic languages across different word orders, head and modifier directions, grammatical particles, prefixes, suffixes, and marking on nouns or verbs. Extend beyond concatenated roots and suffixes with internal changes, reduplication, or templatic patterns. Include case marking that can disambiguate roles under varied word order. These are selected structural contrasts, not complete simulations of real language families.

The hypothesis space must actually express the tested rule. A suffix only learner failing on internal vowel changes reveals an architectural restriction, not simply a lack of examples. Report restricted and expanded hypothesis spaces separately. Use equal initial weights among the implemented alternatives in the rule learner; no implementation is completely free of inductive bias.

### Tests for inherited assumptions

Create paired languages with similar surface forms but conflicting, internally consistent meanings or grammar. For example, make the same marker plural in one language and past tense in another, or reverse agent and patient order. Compare performance after equal seed evidence. Shuffle opaque root forms so English or Romance looking strings cannot supply the answer.

Report results per structural group, their macro average, and the worst group. Hold entire structural families out of cross language training. Measure how many corrections overturn an incorrect initial rule and whether it keeps returning after contrary evidence. Choose settings on validation languages with a minimum group performance requirement; specify that threshold before final testing.

## Baselines and Recommended Model

### Build simple baselines first

B0 is an exact translation memory with an unknown output for unseen inputs. B1 retrieves the nearest corrected example using character n gram similarity and copies its meaning; this provides a simple spelling analogy baseline. B2 is a probabilistic morphology and grammar learner. All receive exactly the same seed examples and teacher answers.

For B2, enumerate plausible splits of word forms and candidate prefix, suffix, or standalone markers. Count associations between recurring pieces and semantic features across corrected examples. Maintain weighted hypotheses for marker meanings and sentence order. Use a complexity penalty to discourage inventing a separate rule for every word. Return the highest scoring consistent parse and several alternatives. Use bounded beam search and cap hypothesis counts.

The purpose of B2 is to test whether explicit reusable structure is sufficient. It is a serious candidate for the final small data system, rather than only a weak baseline.

### Neural comparison model

Build a small character encoder and autoregressive decoder in PyTorch. Proposed starting settings are 64 dimensional character embeddings, a bidirectional GRU with 128 hidden units per direction, attention, and a 128 unit decoder that emits the canonical meaning sequence. Cap the initial vocabulary to generator characters plus required semantic symbols. Use teacher forcing and token cross entropy for training.

These are initial engineering choices. Tune hidden size, learning rate, and update count on validation languages. Record the actual parameter count and memory use. Do not assume a small neural network can infer reliable rules from 25 examples without useful priors or prior training.

### Adaptation paths

Run the neural model from random initialization as a control. Then train an initialization across training languages, with each language receiving a fresh random lexicon and grammar sample. Adapt on new languages with a separate support set. Begin with ordinary multitask training plus fine tuning; episodic meta learning is optional if that baseline is insufficient. Related work studies meta learning for compositional generalization [5].

### Memory and hybrid prediction

Store every teacher verified example in an episodic memory. Exact matches return the corrected meaning. For unseen inputs, compare the rule learner and neural predictions. Initially evaluate them separately. Add a combined ranking model only after their individual errors are understood; select combination weights on validation data.

### Confidence

Keep top candidate interpretations. Neural probabilities and rule scores are not automatically calibrated confidence. Fit any calibration on validation data, report coverage and error, and retain uncertainty when several interpretations remain plausible.

## Correction Loop and Persistent State

### Event ordering

Each input receives an example_id and a prediction record containing candidates, model version, and timestamp. Save the prediction before the teacher response can be accessed. A feedback event contains that example_id, the correct structured meaning, and its arrival step. The learner never receives hidden gold values through its input object.

At a step, process feedback already due, predict the new example, record its score using the evaluator private answer, then process any zero delay answer. Queue later answers. At the end, explicitly report whether pending answers were drained; draining must not change historical prediction scores.

### Feedback schedules

Use immediate feedback as the main experiment. Then test delays of 5 and 20 input events using exactly the same examples and arrival schedule for every model. In the main controlled condition, provide answers for all stream items, including correct guesses. Also test the requested correction policy: reveal a label only when the saved top prediction is wrong. That policy itself supplies correctness information and can create different feedback exposure across models, so report answer counts and teacher decisions separately.

### Updating the learner

First, write the teacher verified pair into memory. Update the rule counts and hypothesis weights. For neural adaptation, start with 1 to 5 optimizer steps per arriving answer using the corrected example plus a replay batch of 15 earlier corrected examples. Start with Adam at 0.0003 and gradient norm clipping at 1.0. Tune these settings on validation languages only.

Use a reservoir of up to 2,000 replay examples, stratified or audited for rare features where possible. Store memory separately from the replay sample. Limit update time and save a recoverable checkpoint. Full retraining from every past example is a comparison condition, not the default interaction loop.

### Correction handling

Treat duplicate feedback as idempotent. An amended teacher answer should supersede the earlier annotation with a revision record. If exact reversal of earlier gradient updates is unavailable, rebuild from a checkpoint and the authoritative event log. Report unresolved or contradictory annotations instead of silently accumulating incompatible labels.

### Checkpoint contents

Save parameters, optimizer state, character and semantic vocabularies, rule hypotheses, verified memory, replay sampling state, pending feedback, random generator states, configuration, and processed event IDs. A restart must reproduce the remaining event sequence.

### User interaction

The initial CLI displays input, predicted meaning, alternatives, and uncertainty. The teacher enters the corrected meaning or confirms the answer. After an update, display the changed interpretation and a small set of new rule related examples. Avoid presenting a generated explanation as evidence of the actual internal rule.

## Evaluation Without Answer Leakage

### Three evaluation tracks

Track 1 measures streaming first predictions. Score each example once before its answer arrives. Preserve the original prediction even if the example is later corrected.

Track 2 measures transfer. At fixed answer budgets of 0, 10, 25, 50, 100, and 200, evaluate a frozen snapshot on unseen combinations whose parts have already been grounded. Never reveal probe labels, update parameters, or add probe inputs to learner memory. Probe results cannot influence decisions during a final test run.

Track 3 measures retention. Reevaluate an earlier labeled set after subsequent updates. These are explicitly retention scores, not unseen performance.

### Primary metric

Use the area under the held out compositional accuracy curve against teacher answer count, computed with trapezoidal integration and normalized by the answer budget range. Higher values indicate stronger predictions with less supervision. Report the curve and its raw points, since a single number can hide learning behavior.

### Supporting metrics

- Exact structured meaning accuracy and token accuracy for diagnostic use.

- Slot precision, recall, and F1 for predicate, roles, tense, and number.

- Accuracy broken down by composition, unseen form, ungrounded concept, and irregularity.

- Transfer gain on fresh rule related examples after a correction or matched correction batch.

- Retention drop from the best earlier checkpoint, in percentage points.

- Teacher labels used, teacher decisions required, update latency, prediction latency, and peak memory.

- Top k accuracy and confidence error; measure calibration only where probabilities are defined.

### Fair comparisons

Use identical language instances, seed examples, stream order, and feedback events in the main experiment. Compare both equal label budgets and equal compute budgets. A slower model given many more training steps should not receive an unexplained advantage.

Treat language as the main unit of replication. Run three random model seeds per test language and summarize within language before paired comparisons. Bootstrap paired differences across languages for 95 percent confidence intervals. Do not treat thousands of sentences from one language as independent language level evidence.

### Leakage checks

Keep gold answers and generator grammar in evaluator owned structures. Assert that support, stream, and probe IDs do not overlap in prohibited ways. Check duplicates after normalization. Hold out entire grammar families for a separate transfer experiment. For real data, group related paradigms or documents where possible and disclose remaining overlap.

Do not expose English translations or gold segmentation as model input when they contain the target answer. Some glossing tracks provide additional information; choose a track explicitly. A pretrained multilingual model is a separate condition because target language exposure may be unknown.

## Experiment Matrix and Decision Rules

### Run experiments in increasing cost order

E0 checks event ordering and scoring on tiny deterministic examples. No learning result is trusted until an intentionally answer leaking learner is rejected by the harness.

E1 compares dictionary, nearest neighbor, and rule learning on regular artificial morphology. Run all three seed sizes. Inspect whether rules transfer to new roots.

E2 adds sentence composition and compares the neural model, memory only adaptation, parameter only adaptation, and parameters plus replay. Keep architecture and initial checkpoint fixed for neural ablations.

E3 evaluates immediate and delayed feedback. Repeat with the correction only policy. Plot outcomes by processed examples, supplied labels, and teacher decisions so delay and feedback selection remain visible.

E4 adds exceptions, ambiguity, paired languages with conflicting grammar, and held out structural families. Run strict fresh starts separately from shared initialization and report results by structural group. Change one difficulty at a time before combining them. Measure whether confidence falls when the language violates learned assumptions.

E5 tests cross language initialization on final held out languages. Compare against random initialization and the rule learner under equal target supervision. Report source training size and compute separately.

E6 evaluates real language glossing. Use the same prediction before correction protocol and fixed target label budget. Compare against an exact dictionary and a suitable task baseline. Report qualitative errors and which parts of the synthetic approach transferred.

### Proposed acceptance criteria

The following are project targets chosen before final testing, not expected results. Revise them only during development and record the change.

- On regular synthetic composition, achieve at least 80 percent exact accuracy after 100 teacher answers, with at least a 10 percentage point gain over exact memory on unseen combinations.

- Beat the strongest simple baseline on the primary accuracy curve with a positive paired difference whose 95 percent confidence interval excludes zero. If the rule learner is strongest, it can become the selected system.

- Limit retention loss to 5 percentage points after the main stream, subject to the same evaluation set and feedback budget.

- Target median interactive prediction below 1 second and median correction update below 3 seconds on the measured machine. Report tail latency and actual hardware; these are usability targets.

### Stop or change direction

If corrected examples improve but new combinations do not, investigate memorization and representation. If synthetic performance is strong but real glossing fails, report the restricted result and simplify the real task. If neural training adds no benefit over rules, use rules and memory. If every method fails on a task with ungrounded meanings, revisit what information is available before increasing model size.

## Implementation Structure and Verification

### Suggested repository

Use src/language_lab/ with generator.py for grammars and data, schemas.py for typed records, teacher.py for answer scheduling, stream.py for event ordering, memory.py for verified examples, and checkpoints.py for persistence. Put models in models/dictionary.py, analogy.py, rules.py, and neural.py. Separate evaluate.py, metrics.py, and cli.py. Keep tests/, configs/, scripts/, and reports/ at the repository root.

Generated datasets belong under data/generated/ with a manifest; raw real language data remains separate from derived splits. Every run writes config.json, environment.txt, metrics.json, predictions.jsonl, feedback.jsonl, manifest.json, and checkpoint files under a unique runs/ directory. Save large results outside Git and version their checksums and locations.

### Core interfaces

predict(input, context) returns candidate meanings, scores, and model_version. observe_feedback(example_id, correct_meaning, revision) returns an updated version and update statistics. save_checkpoint(path) and load_checkpoint(path) preserve the full learner state. Evaluator methods receive the gold label separately from model calls.

Use JSONL events with schema_version, language_id, example_id, event_type, input_text, arrival_step, feedback_revision, and optional context. Store predictions and gold in separate records with controlled access. Surface only teacher released labels to the learner.

### Required correctness tests

- A hidden gold label never reaches predict or the learner state before its scheduled arrival.

- Delay 0 updates after prediction; delay 5 cannot change the preceding five historical predictions.

- Restarted and uninterrupted runs consume identical events and match predictions within a documented numerical tolerance.

- Duplicate feedback does not update twice; revised feedback rebuilds from authoritative labels.

- Probe evaluation leaves model, memory, optimizer, and random state unchanged.

- Starting a fresh language clears all fitted state, while corrections within a language preserve its learned state.

- The generator keeps one grammar fixed throughout an episode and covers the configured structural alternatives.

- Generator parsing round trips recover the canonical meaning for unambiguous generated examples.

- Split validation rejects duplicated forms, meanings where prohibited, and language identities across partitions.

- An explicit plural rule transfers to a new grounded root in the deterministic sanity task.

### Engineering tools

Use Python, PyTorch, NumPy, pytest, a YAML configuration reader, and Matplotlib for reports. Start with JSONL and local checkpoints. Add SQLite only if annotation management requires it. Freeze package versions after the first successful installation and record the operating system and accelerator.

### Hardware plan

Design the first experiments for CPU and a small memory footprint, especially on an 8 GB laptop. Keep the neural model small, cap replay memory, and run experiments sequentially. On compatible Macs, PyTorch offers an MPS backend; detect availability at runtime and retain a CPU path [6]. Profile before purchasing cloud compute. No cost estimate is justified until a representative run has been timed.

## Milestones and Work Schedule

### Weeks 1 and 2

Write the research specification and data schemas. Implement generator Stage A, canonical meaning parsing, dataset manifests, seed splits, and the simulated teacher. Build the dictionary baseline and event recorder. Finish when immediate and delayed feedback pass ordering tests and the same run can be replayed.

### Weeks 3 and 4

Implement the character analogy and probabilistic rule learners. Add fresh combination probes and retention evaluation. Run E1 across five development languages before scaling. Finish when a correction changes at least one appropriate unseen prediction and all reported scores are computed before answers arrive.

### Weeks 5 and 6

Implement the compact neural model and its update loop. Add memory only, parameters only, and replay conditions. Save restartable checkpoints. Profile memory and latency on the intended machine. Finish when E2 is reproducible and produces learning curves against label count.

### Weeks 7 and 8

Add varied sentence order, non suffix morphology, exceptions, and ambiguity. Audit structural balance and fresh state isolation between languages. Run feedback delay and ablation experiments. Tune only on validation languages. Freeze the primary metric, final configurations, and acceptance targets before accessing final test results.

### Weeks 9 and 10

Run the final synthetic benchmark and paired uncertainty analysis. Select real language data and reproduce a small glossing baseline. Adapt the chosen learner to the same task, preserving the teacher event interface. Record licensing and the precise fields supplied to each model.

### Weeks 11 and 12

Complete the real language pilot, build a simple interactive CLI demonstration, and write the results and limitations. Package a reproducible run command, a small example dataset, and a saved demonstration checkpoint. If time is limited, defer meta learning, missing boundaries, and the graphical interface.

### Minimum version if the schedule is shorter

Deliver the generator, correction engine, dictionary and rule models, transfer probes, and final experiment report. These can test the central idea without neural training. A six week scope should concentrate on this version, with real language glossing described as a follow up rather than presented as completed evidence.

### Final completion checklist

- One documented command regenerates data and verifies splits.

- One documented command runs each selected model with matched feedback.

- Learning curves and transfer scores are reproducible from saved logs.

- A correction can arrive immediately or later without altering historical scores.

- A saved learner resumes correctly and retains earlier knowledge.

- Results identify the strongest baseline and report negative findings.

- A new user can try the example language and see a verified correction affect a fresh example.

## Risks Extensions and Reading

### Risks and responses

Tiny datasets may not support neural learning from scratch. Use explicit linguistic structure and compare against cross language initialization. Morphological resemblance can be misleading, so evaluate irregular forms and confidence. New concepts require grounding; keep them separate from composition in every chart.

A hidden grammar may accidentally make the benchmark too easy. Randomize mappings, vary structural families, and reserve whole families for testing. Real languages include ambiguity and constructions outside the generator; retain multiple valid annotations where available and separate missing annotation from an actual model error.

Repeated online updates may cause forgetting. Compare replay with frozen parameters and measure retention throughout training. Noisy corrections may destabilize rules; test a small annotated noise condition only after the clean teacher experiment is understood.

### Extensions after the main result

Active learning lets the model ask which ambiguous example should be translated next. Compare its benefit under a fixed teacher budget. Missing boundaries require segmentation learning and separate segmentation scores. Grounded learning connects language to pictures or actions. Speech introduces acoustic recognition and must be evaluated independently. Cross language meta learning tests faster adaptation rather than assuming it.

### Sources and how to use them

[1] Luo, Cao, and Barzilay. Neural Decipherment via Minimum Cost Flow From Ugaritic to Linear B. ACL 2019. A related language and historical constraints support vocabulary decipherment. Use this as background for structured priors, not a claim that the proposed online system already exists.

https://aclanthology.org/P19-1303/

[2] Luo and colleagues. Deciphering Undersegmented Ancient Scripts Using Phonetic Prior. TACL 2021. Relevant to later work on word boundaries and sound correspondence.

https://aclanthology.org/2021.tacl-1.5/

[3] Ginn and colleagues. Findings of the SIGMORPHON 2023 Shared Task on Interlinear Glossing. A candidate real language evaluation setting.

https://aclanthology.org/2023.sigmorphon-1.20/

[4] SIGMORPHON 2023 glossing task repository. Inspect dataset documentation, licenses, track definitions, and official splits before selecting languages.

https://github.com/sigmorphon/2023glossingST

[5] Conklin and colleagues. Meta Learning to Compositionally Generalize. ACL 2021. Relevant to the optional training across tasks extension.

https://aclanthology.org/2021.acl-long.258/

[6] PyTorch documentation. MPS backend. Use runtime checks and consult the installed version documentation for accelerator support.

https://docs.pytorch.org/docs/stable/notes/mps.html

All model sizes, schedules, data counts, and acceptance thresholds in this document are proposed project choices. The sources motivate related methods and candidate data; they do not establish the performance of this proposed learner.
