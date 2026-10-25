# 03 · English corpus from Universal Dependencies

## Why
A language everyone can read makes the demo easier to follow: judges can check that
`-s` really means plural.

## What changed
`tools/make_english_corpus.py` converts UD English (CoNLL-U) into the gloss TSV format,
building Leipzig-style glosses from UD lemmas and features:
`birds → bird-PL`, `chased → chase-PST`, `running → run-PROG`, `me → 1SG.ACC`, `not → NEG`.
Punctuation is dropped. The first file's sentences are written with glosses (imported as
reviewed); a second file's sentences are written without glosses for review.

With no hints, the Grammar view finds `-s` (PL), `-ing` (PROG), `-s` (3SG), `-ed` (PST and
PTCP), `take → taken` and `do → done`.

## Files
`tools/make_english_corpus.py`, a converter test in `tests/test_performance.py`, README section.
The UD data (CC BY-SA 4.0) is not bundled; the converted file lives in git-ignored `runs/`.

## Hardest part
Mapping UD features onto glosses the pattern learner can use. The learner treats any gloss
part with a lowercase letter as meaning and all-caps parts as grammar, so all-caps names
like "US" were being filed as grammar words; they are now lowercased. Pronouns became
person/number tags (`3PL`, `1SG.ACC`) so they show up as grammar-only words rather than
cluttering the vocabulary.
