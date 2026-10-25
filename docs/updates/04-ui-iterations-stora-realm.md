# 04 · UI iterations: Stora, then Realm

The Realm version is the base of the current interface: 05 replaced it, was reverted, and
06 builds on it.

## What changed across these iterations
- The page moved out of a Python string into `decipher/ui.html` (served by `gloss_web.py`).
- A home screen of languages, and per-language pages: Overview, Review, Grammar, Vocabulary,
  Import, Backups & export, Settings.
- **Review became a work session:** an inspector for the focused word (why it got its
  suggestion, candidates, every other sentence that uses it, related forms), "Saved elsewhere
  as …" with one-click reuse, a summary after each save of new patterns learned and which
  waiting sentences changed, a whole-line gloss input (Tab fills suggestions), filters, search
  and keyboard movement. All of this carries into 06.

## How it was checked
Headless-Chrome screenshots in both themes and scripted interaction runs (save, filters,
search, import through the real file input, settings, demo).

## Hardest part
Showing what a correction changed. The page snapshots every waiting sentence's suggestions
before a save, reloads, and diffs them. That is what lets the UI say "teaching One → one
updated *One of the Wesley boys wrote the hymn*" without any new server code.
