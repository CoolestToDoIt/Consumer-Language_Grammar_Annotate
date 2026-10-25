# 01 · Languages as first-class, Grammar and Vocabulary views

## Why
A project only had a free-text `language_id` label, and nothing showed what the
model had learned about a language. Users could not tell what "Language ID" meant.

## What changed
- **Language details:** optional `description` on a project; a blank code is saved as
  `und` (ISO 639 "undetermined"). Name, code and description are editable without
  changing the project file or ID. Old `.dproj` files still open.
- **`LanguageProject.knowledge()`:** a read-only summary built from the model:
  - vocabulary grouped by meaning (the lowercase parts of a Leipzig-style gloss);
  - grammar-only words (glossed only with tags);
  - learned endings, prefixes and swaps (e.g. `-um` = PL, `-a → -ni` = PRS → FUT),
    each with how many meanings support it and taught examples.
- **`queue()`** now includes the saved glosses of reviewed sentences, so the editor shows
  what was verified rather than a fresh prediction.
- **API:** `GET /api/knowledge`, `POST /api/language`; `POST /api/projects` accepts an
  optional code and description; project listings include counts for the home screen.

## Files
`decipher/project.py`, `decipher/gloss_web.py`, `tests/test_language_view.py` (6 tests).

## How it was checked
Unit tests, plus manual runs on Velari (invented) and real Tsez: Tsez surfaces the noun-class
prefixes `b-` (III), `y-` (II), `r-` (IV) and endings such as `-n` (TOP) and `-ä` (ERG).

## Hardest part
Turning the engine's raw affix rules into patterns a linguist would recognise. The engine
learns many edits that are technically valid but meaningless to show: one-off whole-word
edits, punctuation stuck to words (`-in.`), and edits split mid-tag (`see-PRS → see-PST`
learned as `RS → ST`). The filter now requires at least two meanings, no punctuation in the
affix, and that the gloss edit lines up with a real tag boundary in a taught example. One
known gap remains: tags that start with the same letters (PRS and PST) may not appear as a
pattern, because the engine itself learns them misaligned.
