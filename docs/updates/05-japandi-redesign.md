# 05 · Japandi redesign (reverted)

> **Reverted.** Feedback: it read like a presentation and looked like a generic design. The
> Realm-based UI from 04 was restored (fonts, font route and licence note removed) and improved
> in 06 instead. A copy of the Japandi files was kept outside the repo during the revert.

Visual and layout pass only. No business logic, API calls, data fetching or state handling
changed; the one server addition is a read-only route for the bundled fonts.

## In scope
Home, Review and Model performance. The other pages share the same styles and pick up the
new look without their own layout pass.

## What changed
- **Tokens, defined once** at the top of `decipher/ui.html`: paper, ink, stone, line, accent and
  moss in light and dark; type scale; spacing 4–128; 4px radius; 400ms ease-out motion.
  Colours appear nowhere else in the file.
- **Contrast fixes** (WCAG AA, checked by calculation):

  | Token | Problem | Fix |
  |---|---|---|
  | stone text, light | 3.3:1 | `#6F695E` for text (4.8:1); `#8A8478` kept for hairlines and glyphs |
  | accent, dark | 1.9:1 | `#8AA7BA` (6.9:1) |
  | moss, dark | 3.5:1 | `#9AA383` (6.6:1) |

- **Fonts:** Newsreader (headlines, figures) and Instrument Sans (body), bundled in
  `decipher/fonts/` under the SIL Open Font License and served by a new `/fonts/` route that
  only returns the packaged files. Google Fonts was not used: the app is offline-only and its
  security policy blocks outside resources.
- **Everywhere:** no shadows, gradients or filled cards. Hairlines and space separate content,
  and sections sit 128px apart. One filled button per screen; everything else is a text link.
  Status is shape plus label: ● known, ◆ pattern, ○ guess, – not taught, ✓ reviewed.
  Language tiles became serif initials in a hairline box. Pages fade and rise 8px over 400ms,
  and motion is off when the system asks for reduced motion.
- **Home:** the headline is the five-second message, "Every correction teaches it the grammar.",
  with one button (Continue reviewing …) and the model's 53% set off to the right. Fig. 1 Needs
  you, Fig. 2 Model, Fig. 3 Languages.
- **Review:** the sentence as a serif headline; each word is source above an underline-only
  gloss field, then status; text-tab filters; the inspector is a hairline-ruled right margin;
  Save and next is the only button; Skip, Previous, Next and Use are links.
- **Model performance:** a 128px figure, Fig. labels, a thin single-line chart with no fill that
  bleeds off the right edge, hairline tables.
- **Mobile:** below 760px the sidebar becomes a Menu overlay, the grid stacks, and secondary
  table columns hide.

## Files
`decipher/ui.html`, `decipher/fonts/` (6 font files, 2 licences), `decipher/gloss_web.py`
(font route), `pyproject.toml` (package data), `NOTICE.md`, `tests/test_language_view.py`.

## How it was checked
- 24 unit tests pass.
- Review, Home and Model performance were screenshotted at 1440px and a true 375px, light and dark.
- A script measured that nothing extends past 375px.
- A scripted run confirmed the Review flow still works (Use, Tab fill, save, change note,
  search focus, tabs) and that each screen has at most one filled button.

## Hardest part
Testing the 375px layout. Headless Chrome will not make a viewport narrower than 500px, so the
first "375px" screenshots were a 500px page cropped, which made working layouts look broken and
hid real ones. The fix was a throwaway test harness that loads the real page inside a 375px
iframe and measures every element's right edge. That found the actual bugs:
- grid rows whose flex class overrode the grid;
- inline column placements that never collapsed on mobile;
- a seven-column table with headers that could not wrap.
