# 02 · Model performance measured on your own data

## Why
We wanted to show how right the model is, but the earlier hackathon numbers came from
research datasets. Showing those inside someone's own language would suggest they describe
that language, and the product README makes no accuracy claims about customer data.

## What changed
- **`LanguageProject.performance()`** replays a project's saved glosses in the order they were
  saved. For each sentence's first annotation it records the suggestion a fresh model,
  taught only the earlier annotations, would have made. It reports: right as-is, picked from
  candidates (no typing), accuracy by suggestion label (known word, pattern, guess, not
  taught), teach-once reuse, and a learning curve. Later revisions are applied but not scored.
- **`GET /api/performance`** returns this for every language in the workspace.
- **UI placement:** a workspace-level Model performance page, plus a short Model summary on
  Home. It sits outside the review workflow on purpose: linguists don't need it while
  glossing, but it shows how right the model is.

## Files
`decipher/project.py`, `decipher/gloss_web.py`, `tests/test_performance.py` (5 tests).

## How it was checked
Unit tests with hand-computed expectations, and end-to-end runs on the demo workspace
(English rises from 32% to 72% accepted as-is across 400 sentences; replay takes about 70 ms).

## Hardest part
Making the number honest. Imported glosses are replayed too (in file order), which is fair
but needs saying; scoring is exact-match, so acceptable alternative glosses count as wrong; and
revisions must not be scored or they would reward the model for repeating a correction it was
just given. The page states all three in plain words.
