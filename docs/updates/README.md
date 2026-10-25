# Update log

One file per change set, newest last. Each says what changed, which files, how it
was checked, and what was hardest. None of these change how suggestions are
computed: the gloss engine (`decipher/gloss.py`) is untouched throughout.

Who it's for: field linguists and documentation teams, university research groups, and
community language programs and archives. The pilot measures hours saved and errors caught.

| # | Update | Status |
|---|---|---|
| 01 | [Languages as first-class, Grammar and Vocabulary views](01-language-model-and-knowledge-views.md) | Done |
| 02 | [Model performance measured on your own data](02-model-performance-replay.md) | Done |
| 03 | [English corpus from Universal Dependencies](03-english-corpus.md) | Done |
| 04 | [UI iterations: Stora, then Realm](04-ui-iterations-stora-realm.md) | Base of the current UI |
| 05 | [Japandi redesign](05-japandi-redesign.md) | Reverted (felt like a presentation) |
| 06 | [Making the review workflow intuitive](06-intuitive-review-workflow.md) | Done |
| 07 | [Pilot measures, consent and tag help (current UI)](07-pilot-measures-consent-and-tag-help.md) | Done |

Run the app with the demo workspace (English, Tsez and Velari loaded):

```sh
.venv/bin/python -m decipher --workspace-dir runs/demo/workspace
```

`runs/` and `data/` are git-ignored, so the demo workspace and downloaded corpora stay local.
