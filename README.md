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

## Corpus attribution

Format: [Universal Dependencies CoNLL-U](https://universaldependencies.org/format.html). Sources: [English EWT](https://github.com/UniversalDependencies/UD_English-EWT/tree/r2.15) and [Turkish IMST](https://github.com/UniversalDependencies/UD_Turkish-IMST/tree/r2.15). English annotations use CC BY-SA 4.0; the upstream README describes underlying text rights. Turkish IMST uses CC BY-NC-SA 4.0. Downloads include the original README and license files, and remain excluded from version control alongside fitted models. Consult those source terms before redistributing data or trained artifacts.
