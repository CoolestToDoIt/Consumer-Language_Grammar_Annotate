# Decipher Lab

Learn reusable language structure from corrected examples. The project has two independent tracks: a controlled synthetic grammar learner and a real-corpus morphology learner. Both run locally with Python 3.10+ and the standard library. Corpus acquisition requires a one-time download; training and prediction run offline.

## Real text

The corpus learner predicts each word's lemma, part of speech, and morphological feature bundle from its form and observable context. Vocabulary and label inventories come from annotations; there is no fixed noun/verb list or three-word sentence limit. This is a real-language analysis task, not yet an English translation system.

English EWT and Turkish IMST datasets are configured at UD release **2.15**, with upstream train/dev/test splits, checksums and license metadata in [SOURCES.json](data/corpora/SOURCES.json).

```sh
# Explicit one-time download, then offline integrity verification.
python3 tools/fetch_corpora.py
python3 tools/fetch_corpora.py --verify-only

# Fit an English model and report frozen development accuracy.
python3 -m decipher.app corpus evaluate \
  --train data/corpora/english-ewt/en_ewt-ud-train.conllu \
  --eval data/corpora/english-ewt/en_ewt-ud-dev.conllu \
  --split dev --output reports/corpus/english-ewt-dev.json \
  --save-model models/english-ewt.json.gz

# Analyze explicitly segmented words.
python3 -m decipher.app corpus analyze \
  --model models/english-ewt.json.gz --text 'The birds chased the cats .'
```

`--text` splits on whitespace. For a corpus with contractions, multiword tokens, or different segmentation, provide CoNLL-U or JSONL through `--input`. CoNLL-U analysis uses supplied syntactic words: multiword-token range rows and empty-node rows are excluded. No gold lemma, POS, morphology, dependency heads or dependency labels are given to the predictor.

```sh
python3 -m decipher.app corpus train \
  --train path/to/train.conllu --model models/custom.json.gz
python3 -m decipher.app corpus analyze \
  --model models/custom.json.gz --input path/to/public.jsonl --output predictions.jsonl
python3 -m decipher.app corpus correct \
  --model models/custom.json.gz --annotations path/to/corrections.jsonl
```

Annotations can be CoNLL-U or one JSON object per sentence:

```json
{"id":"lesson-1","tokens":["birds","fly"],"analyses":[{"lemma":"bird","upos":"NOUN","feats":["Number=Plur"]},{"lemma":"fly","upos":"VERB","feats":["Tense=Pres"]}]}
```

Public prediction JSONL requires only `id` and `tokens`. Annotation arrays align one to one with tokens; feature names and POS labels may be corpus-specific. UTF-8 input is normalized to NFC. Missing labels are represented by `null` and omitted from their metric denominators. Corrections with an existing ID replace that sentence's annotations and rebuild counts to remove superseded evidence. Repeating the same correction does nothing. Analysis of an exactly corrected full sentence returns its latest verified annotation and marks the output as `verified_recall`; that is recall, not unseen accuracy. Reusing an ID with different source tokens is rejected. Compressed JSON checkpoints preserve authoritative corrections and reconstruct all learned counts, without executable serialization.

## Measuring real-corpus accuracy

Use `corpus evaluate --split test` with an untouched test file for a final report. The model is frozen throughout evaluation. Exact NFC token-sequence overlaps with training are excluded and counted. Reports contain file hashes, limits, annotated-token counts, lemma/POS/feature-bundle accuracy, joint accuracy, OOV accuracy, nonpunctuation accuracy, sentence exact accuracy, feature micro F1, diagnostics and error samples. A metric with no annotated denominator is `null`, not zero or a perfect score. `--limit-train` and `--limit-eval` support explicitly reported smoke runs.

The `lexicon` baseline memorizes the majority analysis for each observed form, then uses an unchanged lemma and the corpus-majority label bundle on unfamiliar forms. The `affix` model also learns suffix and lemma-edit patterns, word-shape evidence and neighboring-word associations. Optional `--models memory lexicon affix` includes a strict memory model that returns unknown on unseen forms. All models receive identical training annotations. There is no pretrained model or external dictionary.

Results are in [reports/corpus](reports/corpus). Held-out test joint accuracy is **88.6% on English** and **78.5% on Turkish**, compared with lexicon baselines of 80.0% and 64.9%. These use hundreds of thousands or tens of thousands of labeled tokens, respectively, and must not be described as learning from a handful of anchors. Joint accuracy requires an exact match of lemma, POS, and the complete feature bundle. Sentence-level accuracy is substantially lower. OOV performance remains a key limitation.

To measure acquisition at annotation budgets without revealing development answers:

```sh
python3 -m decipher.app corpus curve \
  --train data/corpora/english-ewt/en_ewt-ud-train.conllu \
  --eval data/corpora/english-ewt/en_ewt-ud-dev.conllu \
  --budgets 25 100 500 1000 --output reports/corpus/english-ewt-curve.json
```

The command includes zero labels and the full training split, reports both sentence and token answer counts, and keeps training recall separate from unseen development accuracy. Training uses upstream corpus order, so these are prefix-budget curves rather than shuffled replications. English joint development accuracy rises from 52.2% at 554 token labels to 88.0% at 204,444; Turkish rises from 35.5% at 358 to 78.2% at 37,442. Full development sets are scored at each budget without teaching those annotations.

## Controlled grammar learning

```sh
python3 -m decipher.app demo
python3 -m decipher.app walkthrough
python3 -m decipher.app evaluate
python3 -m decipher.app evaluate --delay 3
python3 -m decipher.app stress
```

The synthetic learner receives eleven root anchors and considers six role orders with prefix, suffix or particle marking. `teach` shows a prediction, releases a correction, and displays the same fixed probe sources before and after. `predict SOURCE TEXT` and `answer AGENT VERB PATIENT TENSE AGENT_NUMBER PATIENT_NUMBER` support custom interactions. Other commands: `next`, `correct`, `roots`, `status`, `rules`, `probe`, `save`, `load`, `new A/B/C`, `quit`.

A new preset resets learned state. Delayed feedback reaches the learner at its due input step, and recorded first guesses never change. Checkpoints reject incompatible dataset identities. Probe scoring excludes any sources explicitly taught by the user. Candidate agreement is not calibrated confidence.

The regular synthetic benchmark reaches 100% held-out accuracy after nine support sentences. Its limited grammar and weak copying baselines make it a correctness/transfer check, not evidence of real-language translation. [Synthetic reports](reports/immediate/summary.md) and the real-corpus reports are intentionally separate.

## Tests and development

```sh
python3 -m unittest discover -s tests -v
```

[Progress notes](plans/updates) track completed work and next steps. The [long-term build plan](plans/overview/Language_Decipherment_Build_Plan.md) remains the research roadmap. Priorities are unseen-word morphology, contextual disambiguation, corpus learning curves, and a separately evaluated bilingual gloss/translation track. Arbitrary word meanings require semantic anchors; unannotated text alone does not establish English meanings.

The combined gloss integration checkpoint passes **83 tests** in the neural-enabled
`.venv`; without optional PyTorch the neural tests are skipped. Its current
branch and resume instructions are in [plans/CURRENT.md](plans/CURRENT.md).

## Corpus attribution

Format: [Universal Dependencies CoNLL-U](https://universaldependencies.org/format.html). Sources: [English EWT](https://github.com/UniversalDependencies/UD_English-EWT/tree/r2.15) and [Turkish IMST](https://github.com/UniversalDependencies/UD_Turkish-IMST/tree/r2.15). English annotations use CC BY-SA 4.0; the upstream README describes underlying text rights. Turkish IMST uses CC BY-NC-SA 4.0. Downloads include the original README and license files, and remain excluded from version control alongside fitted models. Consult those source terms before redistributing data or trained artifacts.

## Source-only interlinear glossing

This track learns lexical gloss anchors and reusable affix substitutions from aligned source/gloss examples. Translation and gold-segmentation tiers are discarded at ingestion. Input is the whitespace-segmented source sentence; output is one interlinear gloss per word. It is not unrestricted sentence translation.

```sh
python3 tools/fetch_corpora.py --collection glossing --corpus lezgi --corpus tsez
python3 -m decipher.app gloss evaluate \
  --train data/glossing/lezgi/lez-train-track1-uncovered \
  --eval data/glossing/lezgi/lez-dev-track1-uncovered \
  --output reports/gloss/lezgi-dev.json
python3 -m decipher.app gloss train \
  --train data/glossing/lezgi/lez-train-track1-uncovered --model models/lezgi-gloss.json.gz
python3 -m decipher.app gloss predict --model models/lezgi-gloss.json.gz --text 'SOURCE WORDS'
```

The source-only Lezgi development experiment scores 72.2% exact word glosses, versus 68.6% memory and 69.9% spelling analogy. Unseen-word accuracy is 15.8%, so vocabulary grounding remains a substantial limitation. These are development results, not a final held-out-language result. See [gloss reports](reports/gloss).

The word-gloss learner considers both prefix and suffix edits and reuses only meanings grounded in corrected examples. Its explicit linguistic assumption is the Leipzig-style convention of lowercase lexical gloss labels versus uppercase grammatical tags. Scores are uncalibrated, not probabilities. Misaligned source/gloss records are excluded with counts in reports. Exact source overlap with training is excluded from evaluation.

### Local language workspace

Install the package and start the local browser interface:

```sh
python3 -m pip install -e .
python3 -m decipher.app gloss web
```

Open the printed `127.0.0.1` URL, create a project with a language ID, and
import a UTF-8 corpus. Plain text has one source sentence per line; TSV has
source words and optional tab-separated gloss words; SIGMORPHON uses its `\t`
and `\g` tiers. Supplied glosses become the project's initial authoritative
annotations. Rows without glosses enter the editable review queue. The
invented [demo TSV](examples/gloss-demo.tsv) is only a workflow fixture, not
real language data.

Projects are independent `.dproj` files in `~/.decipher/projects` by default.
The file stores a corpus content hash, model configuration, source sentences,
annotation revisions and a versioned model checkpoint rebuilt from those
annotations. The interface supports project reopen, portable ZIP backup, and
restore as a separately named project. To use another project directory run:

```sh
python3 -m decipher.app gloss web --workspace-dir ./language-projects --port 8765
```

The server binds only to loopback. Imports are capped at 25 MiB. The workspace
model enables exact adjacent-word context to rerank ambiguous known forms;
contextual scoring is disabled by default for the existing CLI models and
historical evaluations. This simple exact-neighbor method cannot resolve an
ambiguity unless the relevant source form and neighboring form were seen
together in corrections; its evidence scores are not calibrated probabilities.

The configured data is the deduplicated `data_v2` release of [SIGMORPHON 2023 glossing](https://github.com/sigmorphon/2023glossingST), pinned to a commit and checksums in [glossing SOURCES.json](data/glossing/SOURCES.json). Original licenses are downloaded locally (CC BY-NC 4.0). This source-only condition does not use the supplied sentence translation and is not directly comparable to the official shared-task conditions or the original pre-deduplication results. Lezgi and Tsez are development languages; Gitksan remains reserved for final fresh-language evaluation.

`gloss stream --train FILE --dev FILE --run-dir runs/NAME` runs prediction-before-correction with fixed development probes, memory/analogy/rule comparisons, and delays 0/5/20. `--policies all corrections` adds correction-only feedback; exposure counts and pending answers are recorded separately.

Both development languages have complete 18-run prefix matrices (three models,
three delays, two feedback policies), with ten support and 100 stream sentences.
Immediate all-label final probe word accuracy is 57.01% / 58.50% / 59.57% for
Lezgi memory / analogy / rules and 30.69% / 35.35% / 41.59% for Tsez. These small
prefix results use less supervision than the full-training baseline above.
See [historical online results](reports/gloss/online/README.md) and
[combined validation](reports/gloss/online/integration-20261024/summary.md).

To interrupt and resume one fresh rule-learning experiment:

```sh
python3 -m decipher.app gloss stream \
  --train data/glossing/lezgi/lez-train-track1-uncovered \
  --dev data/glossing/lezgi/lez-dev-track1-uncovered \
  --run-dir runs/gloss-resume-example --support 10 --stream 100 \
  --modes rules --delays 20 --policies all --probe-every 25 \
  --checkpoint-every 25 --max-inputs 37
python3 -m decipher.app gloss resume \
  --checkpoint runs/gloss-resume-example/rules-delay-20-all/checkpoint.json
python3 -m decipher.app gloss report \
  --checkpoint runs/gloss-resume-example/rules-delay-20-all/checkpoint.json \
  --output runs/gloss-resume-example/reconstructed.json
```

Use fresh run/report paths. `--max-inputs` is an additional budget per invocation;
stopping does not drain pending answers or rewrite historical predictions.
Keep each checkpoint manifest with its sibling `checkpoints/` folder. Resume
requires the recorded core implementation and unchanged original dataset paths;
cross-machine path remapping is not implemented. A single-run resume updates its
metrics, while an earlier matrix-level summary remains the original snapshot.
Gloss commands need only the standard library. Engine model checkpoints remain
schema 1 and reconstruct prepared inference state when loaded.

## Optional neural adaptation

The byte-level model has a bidirectional GRU encoder, attention, and an autoregressive decoder. No pretrained weights or future-data vocabulary is used. The standard-library learners remain available without PyTorch. Install the optional neural dependency into a local environment:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[neural]'
.venv/bin/python -m unittest discover -s tests -v
```

The local experiments were run with PyTorch 2.14.1; pinned installed neural dependencies are in [configs/neural-environment.txt](configs/neural-environment.txt). Deterministic CPU restart is regression-tested within this runtime; cross-version/device bitwise identity is not claimed. See the [PyTorch reproducibility notes](https://docs.pytorch.org/docs/2.14/notes/randomness.html).

```sh
.venv/bin/python -m decipher.app neural benchmark \
  --presets A B --stream 20 --probes 10 \
  --run-dir runs/neural-example --report-dir reports/neural/example
```

Modes: `frozen` updates neither parameters nor prediction memory; `memory` returns verified exact matches but freezes parameters; `parameters` trains on the new answer alone; `replay` trains with previous corrections; `hybrid` adds verified prediction memory to replay. Defaults are 64 embedding dimensions, 128 hidden units, Adam at 0.0003, two clipped updates per correction, up to fifteen replay examples, and a reservoir of at most 2,000 examples.

The [synthetic pilot](reports/neural/synthetic-pilot/summary.md) and [real-morphology pilot](reports/neural/corpus-pilot/summary.md) show zero exact-match probe accuracy for these small neural runs. The symbolic systems remain the preferred models. These pilots use one model seed, small streams, and equal teacher exposure; replay consumes more example presentations, so no equal-compute or statistically significant neural advantage is claimed. This negative result is distinct from verifying that the network can fit a corrected pair when repeatedly trained.

`neural corpus-benchmark --train FILE --dev FILE --run-dir DIR --report-dir DIR` applies the same online protocol to lemma/POS/features targets. `neural fit --pairs FILE --run-dir DIR` accepts JSONL records with `id`, `source`, and `target`, records each prediction before feedback, and saves the optimizer, replay reservoir/RNG, authoritative corrections, pending feedback, and original events in `session.pt`. `--resume FILE` continues a compatible session; revisions rebuild from the original initialization. `neural predict --session FILE --source TEXT` inspects a saved model. Full runs remain local under ignored `runs/`; compact result summaries are kept under `reports/`.
