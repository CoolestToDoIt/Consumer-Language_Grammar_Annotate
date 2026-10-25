# 06 · Making the review workflow intuitive (current UI)

## Why
The Japandi pass (05) read like a presentation and looked generic, so it was reverted to
the Realm UI from 04. That UI had the right features, but the core flow was hard to read:
- the sentence appeared twice, once as a headline and once as a grid of 14 cards;
- every word carried a status label, so the few words that needed checking didn't stand out;
- there were six filter chips with jargon names, and the save button sat below the fold;
- the sidebar and Home both listed each language twice.

Same rule as before: no server, API or engine changes.

## What changed
- **Revert:** `decipher/ui.html` was restored to the Realm version, rebuilt from the
  session transcript and checked against it. The bundled fonts, the `/fonts/` route, the font
  package data and the font licence note were removed.
- **Review is interlinear text**, the layout linguists already use. Each word sits directly
  above its gloss in reading order, and the edit box sizes itself to the gloss. A thin coloured
  underline shows what the suggestion is based on. Only guesses and new words get a label
  ("guess · check", "new word"), and an edited word says "edited".
- **It says what needs you:** "7 words to check · 7 look right", plus **Next to check**. Review
  now starts on the first word that needs checking, not on word 1.
- **One menu replaces the six filter chips:** To review, quickest first, with guesses, with new
  words, already reviewed, everything. The links on the Overview page still pick the right set.
- **Pinned action bar:** overall progress, keyboard hints, Skip and Save & next stay
  visible at the bottom while you scroll.
- **Leipzig small caps:** outside the edit boxes, grammatical tags print in small capitals
  (in dog-PL-ERG, the PL and ERG). This covers Up next, the inspector, the change summary, Vocabulary
  and the Overview preview. It's the convention linguists expect, and it makes the product look
  like a linguistics tool rather than a generic dashboard.
- **Inspector:** leads with the suggested gloss, its tags in plain words
  ("perfective + converb") and why it was suggested. Next come saved-elsewhere options,
  other options (only when they differ from the suggestion), other sentences that use the
  word, and related forms.
- **Overview "Up next"** is interlinear too, with a count of words to check.
- **Sidebar:** the duplicate "Needs you" list is gone. Each language shows its waiting count,
  and Review is the first page under it ("Review · 60 waiting").
- **Home:** one card, **Pick up where you left off**, is the only primary button (Enter opens it).
  It sits next to **How right the model is**, then one list of languages with progress and a
  Review button each. The demo is a text link.
- **Fixes:**
  - collapsing the sidebar, or any screen narrower than 860px, used to blank the whole page
    (a bug already in the Realm version);
  - tables now scroll sideways on phones;
  - light-mode grey text and the orange labels now pass WCAG AA (grey 4.7–5.2:1, orange text
    5.0:1).

## Files
`decipher/ui.html`, `decipher/gloss_web.py` (font route removed), `pyproject.toml`, `NOTICE.md`,
`README.md`, `tests/test_language_view.py` (page assertion), `decipher/fonts/` (deleted).

## How it was checked
- 24 unit tests pass.
- A scripted run in headless Chrome checked:
  - focus starts on the first word to check;
  - Saved elsewhere › Use, then Next to check;
  - Tab fills the whole-line box with all 14 of 14 words;
  - Enter saves, and the summary reports "1 sentence updated · One → one";
  - search keeps focus, and the queue menu switches sets;
  - Review, Overview and Home each have one primary button;
  - Enter on Home opens Review, and the Performance chart renders.
- Screenshots at 1440px in light and dark, and at 500px.
- At a true 375px width, Home, Review, Overview, Grammar and Performance were measured in both
  themes; nothing pushes the page wider than the screen.

## Hardest part
Getting the Realm version back. `ui.html` had never been committed, the Japandi pass
overwrote it with one write, and the only file backup was from the earlier Stora round. The
fix was to replay the session transcript: the last full write of the Realm file, then the
three scripted edits made after it. The result was checked line-for-line against the last
time that file was read before the overwrite.

Close second: the "blank page" bug. When the sidebar is hidden, the grid still has three
columns, so the main area dropped into the zero-width sidebar slot and was clipped to nothing.
At first it looked like a screenshot-timing problem in the test setup.
