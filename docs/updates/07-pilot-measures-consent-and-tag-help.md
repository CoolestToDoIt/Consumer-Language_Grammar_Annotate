# 07 · Pilot measures, consent and tag help

## Why
The pitch names three groups of users: field linguists and documentation teams, university
research groups, and community language programs and archives. It also names the reasons
they'd pick Decipher (offline, so it fits consent rules; it learns from their corrections)
and a pilot that measures hours saved and errors caught. The UI didn't show any of that:
- tags like ERG or 3SG were unexplained for people new to glossing;
- "offline" and consent were invisible;
- nothing measured time saved or errors caught.

## What changed
**1. Help with grammatical tags (for people new to glossing)**
- **Hover any tag** in a gloss to see its meaning, e.g. PL: plural (more than one).
  - The dictionary covers the Leipzig Glossing Rules standard abbreviations plus common
    additions, including the Tsez localization series, and builds person, class and
    numbered tags (3SG, IISG, GEN1, NPRS).
  - Tags it doesn't know are shown as written, never guessed.
- **The word panel reads the gloss as you type**: `dog-PL-ERG` reads "dog + plural + ergative".
- **How to write a gloss** in Review explains the convention, gives a worked example from the
  language itself, and lists the tags that language uses. Grammar lists all of them.

**2. Offline and consent made visible**
- **On this computer** badge in the top bar of every page. Its tooltip says Decipher works
  offline and uploads nothing. This was verified: the app makes no outgoing requests, the
  server only answers on 127.0.0.1, and the page's security policy only allows its own address.
- **Consent recorded / Consent not recorded** shows on each language on Home and in each
  language's header (linking to Settings).
- **Import** warns before a file is added if consent isn't recorded.

**3. Pilot report (Model performance page)**
- **Time saved (estimate):** glosses that needed no typing × an adjustable seconds-per-gloss
  (default 5 s, typing only). The page says it's an estimate and how to measure it in the pilot.
- **Errors caught:** glosses corrected after their first save (from revision history), plus
  unusual glosses still waiting to be checked, with a "Check …" link into Review per language.
- **Permission & data:** how many languages have consent recorded, per language.
- **Download CSV:** one row per language with every number above and which policy fields are
  recorded.

**4. Unusual-gloss check (the "errors caught" loop in the workflow)**
- A saved gloss is flagged when it differs from how the same word is otherwise consistently
  glossed. Example: English *One* saved as `Online` once, against `one` eight times. That
  was a wrong guess accepted with Enter.
- Overview shows "N saved glosses look unusual". **Check them** opens Review on just those
  sentences; the word is marked "unusual · check", and the panel explains why and offers
  **Use** the usual gloss or **Keep as is**.
- Kept glosses are stored in the project file, so they aren't flagged again.

**Server additions** (small and backward compatible):
- `summary()` now lists which policy fields are filled in (`policy_recorded`; names only,
  not text).
- `performance()` now counts revisions.
- New `unusual_glosses()` and `keep_gloss()`, with endpoints `GET /api/checks` and
  `POST /api/checks/keep`.
- New optional `kept_glosses` list in `.dproj`; older files open unchanged.

## Not done
- **Per-sentence time tracking:** the pilot can time a sample by hand.
- **FLEx / Toolbox / ELAN import:** the biggest remaining gap for field linguists.

## Files
`decipher/project.py`, `decipher/gloss_web.py`, `decipher/ui.html`, `README.md`,
`tests/test_pilot.py` (new, 6 tests), `tests/test_language_view.py`.

## How it was checked
- 30 unit tests pass.
- A scripted run in headless Chrome checked the pilot report, the CSV download, the
  "Check English" link, Use + save on a flagged gloss, Keep as is, the server's counts, the
  live reading, tag tooltips, the gloss help and consent badges after saving a policy.
- Screenshots at 1440px in light and dark, and at 500px.
- No page is wider than the screen at 375px in either theme.
- New text colours pass WCAG AA; the tightest is the orange heading on the unusual-gloss box,
  at 4.5:1.

## Hardest part
Making "errors caught" mean something without crying wolf. The first rule flagged any rare
gloss of a word, which also caught real ambiguity. English *'s* is POSS 20 times and be-3SG
17 times, and once correctly "us" in *let's*; *had* is both have-PST and have-PTCP. The rule
now needs the word to be otherwise consistent: its usual gloss covers at least three quarters
of its uses, and the odd one out appears at most twice and in at most a fifth of uses. On
the demo data that took English from 14 flags to 5; those 5 include the real slip
(One → Online) and a capitalisation inconsistency (People-PL). Real ambiguity still slips
through sometimes, which is why **Keep as is** had to be remembered in the project file.
