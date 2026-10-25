**Note: Full research history (experiments, evaluation, and the complete commit log): [https://github.com/CoolestToDoIt/Unknown-Language-Translation]
**
# Decipher Lab · Local pilot edition

A small, offline workbench for human-reviewed **word-level gloss annotation**, scoped to the local product in [the commercial plan](plans/COMMERCIAL_USAGE_AND_OPPORTUNITIES.md). It learns from aligned examples and corrections; it does not produce fluent sentence translations.

## Run

Python 3.10+; no runtime dependencies, API keys, database, downloads, or model weights.

```sh
python3 -m decipher
```

Open **http://127.0.0.1:8765**. Stop with Ctrl+C. Projects are saved under `~/.decipher/projects`.

To keep work in a chosen folder:

```sh
python3 -m decipher --workspace-dir ./language-projects --port 8765
```

Optional installation provides the `decipher` command:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
decipher
```

Installation may fetch the setuptools build dependency. Running directly from this checkout works offline. The server always binds to `127.0.0.1`; run one server/operator per workspace directory. This is a local pilot build, not a hosted team service.

## Full fictional runthrough

See [the hands-on pilot walkthrough](examples/pilot/README.md) for sample files, realistic reviewer decisions, deliberate model mistakes, exports, and backup recovery. Generate practice and completed projects with:

```sh
python3 tools/run_walkthrough.py
python3 -m decipher --workspace-dir ./demo-run/projects
```

The script records actual suggestions and verifies recovery. It uses invented data and leaves the practice project unreviewed for you to explore.

## First session

The left sidebar lists your **Languages** with how many sentences are waiting, each expanding into its pages (Review first). Every language is one project file with a name, an optional ISO 639-3 code (saved as `und`, "undetermined", when left blank), and an optional description.

- **Overview:** progress, the next sentence up, "Things to know" with next steps, recent activity, waiting words by suggestion type, and top patterns.
- **Review:** the main work session. One sentence at a time as interlinear text: each word directly above its editable gloss, in reading order. A coloured underline shows what each suggestion is based on (known word, learned pattern, closest-spelling guess, or not taught yet); only guesses and new words are labelled, and the bar above the sentence says how many words need checking, with **Next to check** to jump between them. Review starts on the first word that needs you. A menu picks which sentences to work through (to review, quickest first, with guesses, with new words, already reviewed, everything), and search is in the top bar. Save & next stays pinned at the bottom with overall progress. The inspector on the right shows why a word got its suggestion, its candidates, every other sentence that uses it, glosses already saved for it elsewhere (one click to reuse), and related forms of the same meaning. After each save, a summary shows new patterns learned and which waiting sentences got different suggestions. Enter saves and moves on; Alt+←/→ moves between sentences; "Type the whole gloss line instead" accepts a whole line at once (Tab fills it with the current suggestions). Glosses shown outside the edit boxes print grammatical tags in small capitals, following the Leipzig Glossing Rules.
- **Help with tags:** hover any grammatical tag to see what it means (standard Leipzig abbreviations plus common additions; unknown tags are shown as written, never guessed). The word panel reads the gloss being typed in plain words, e.g. `dog-PL-ERG` reads "dog + plural + ergative". **How to write a gloss**, under the sentence in Review, explains the convention with an example from the language and lists the tags it uses; Grammar lists them all.
- **Unusual glosses:** a saved gloss that differs from how the same word is otherwise consistently glossed (for example *one* saved once as `Online` but eight times as `one`) is often a slip. Overview lists how many there are and **Check them** opens Review on just those, with the word marked "unusual · check". Fix it, or choose **Keep as is**; kept glosses are remembered in the project file and not flagged again.
- **Grammar:** endings, prefixes and swaps learned from reviewed glosses (for example `-um` = PL), each backed by at least two meanings, with taught examples, and every tag used in the language with its meaning.
- **Vocabulary:** every taught meaning with the word forms it has been seen in.
- **Import**, **Backups & export**, and **Settings** (language details, data-ownership notes, suggestion settings, deletion).

Home leads with one card, **Pick up where you left off** (Enter opens it), next to a **How right the model is** card, then one list of languages, each with its progress, a Review button and whether consent is recorded. Consent is the data-ownership note in Settings; the language header shows the same status, and Import reminds you before community data comes in if it is missing. The **On this computer** badge in the top bar is a reminder that Decipher works offline: it runs on this computer only and uploads nothing. The light/dark switch is at the bottom of the icon rail; on small screens the sidebar is hidden and the rail remains.

**Model performance** (the chart icon in the rail, and summarised on Home) is a workspace-level page, separate from the review workflow. It replays each language's saved glosses in order and scores the suggestion Decipher would have made just before each sentence was taught: how often it matched exactly, how often no typing was needed, how often each suggestion label (known word, pattern, guess) was right, teach-once reuse, and a learning curve per language. It measures only this workspace's own data; imported glosses are replayed too, and scoring is exact-match.

The **Pilot report** on the same page gives what a pilot needs to report:
- **Time saved (estimate):** glosses that needed no typing (right as suggested, or picked from the options), times an adjustable number of seconds to type one gloss by hand. During a pilot, time a sample of sentences with and without suggestions to measure it directly.
- **Errors caught:** glosses corrected after their first save, and unusual glosses still waiting to be checked, with a link into Review for each language.
- **Permission & data:** which languages have consent recorded.

**Download CSV** exports one row per language.

### English from Universal Dependencies

`tools/make_english_corpus.py` converts UD English (CoNLL-U) into a gloss TSV, building Leipzig-style glosses from UD lemmas and features (`birds` → `bird-PL`, `chased` → `chase-PST`, `running` → `run-PROG`, `me` → `1SG.ACC`). The corpus is CC BY-SA 4.0 and is not bundled; download it from [UD_English-EWT](https://github.com/UniversalDependencies/UD_English-EWT/tree/r2.15) and keep the output outside version control:

```sh
python3 tools/make_english_corpus.py --glossed en_ewt-ud-train.conllu --review en_ewt-ud-dev.conllu --output runs/english/english-ewt.tsv
```

1. Choose **Demo language** to explore seven invented examples, or **Add language**. The demo contains no community corpus.
2. Under **Settings**, record ownership, permitted uses, consent, provenance, retention, and annotation conventions before importing real data.
3. Preview a UTF-8 corpus and inspect sentence counts, supplied labels, and alignment. Confirm to import. Supplied glosses count as authoritative annotations; import only labels you intend to trust.
4. Review sentences. Edit every draft and save the reviewed glosses. Choose the **Reviewed** filter to revise earlier work. Suggestions are evidence, not probabilities, and a known word in an unreviewed sentence still needs review.
5. Download a ZIP backup regularly. JSONL/TSV exports contain source sentences and accepted labels; unreviewed sentences have null/empty labels. Download revision history separately, or use ZIP for the complete project, policy, and revision history.

The sentence list shows up to 400 matches; use search to narrow it. Predictions are still computed in memory for the full project; this edition targets small pilot corpora rather than large archives. Grammar patterns only appear when glosses follow the lowercase-meaning, UPPERCASE-tag, hyphen-separated convention, and tags that start with the same letters (such as PRS and PST) may not show up as a pattern.

## Input formats

- **Text:** one whitespace-segmented sentence per line; no labels.
- **TSV:** source words, a tab, and one gloss per source word. A row without a tab is unreviewed. A tab followed by empty/misaligned glosses is rejected.
- **SIGMORPHON:** `\t` source and optional `\g` gloss tiers, with blank lines between sentences. Translation and gold segmentation tiers are discarded.

```text
tal mir<TAB>tree bird
talum<TAB>tree-PL
mirum
```

Replace `<TAB>` with a real tab. Word segmentation is preserved exactly as supplied after whitespace splitting and NFC normalization; this edition does not automatically segment morphemes. Custom labels can be entered, but rule grounding retains the upstream assumption that lowercase labels carry lexical meaning and uppercase labels represent grammatical tags. An empty project needs a human-provided semantic anchor before useful suggestions are possible.

Imports are capped at 25 MiB; the entire saved project, including revisions, also has a 25 MiB limit so every accepted workspace can be restored through the backup path. Split larger corpora across projects. Duplicate detection compares normalized-BOM-stripped file content, not semantic sentence equivalence.

## Recovery, privacy, and pilot operations

- [Data handling](docs/DATA_HANDLING.md): ownership, access, retention, deletion, and backup responsibilities.
- [Operations](docs/OPERATIONS.md): clean installation, backup recovery, compatibility, upgrades, support, and verification.
- [Provenance](NOTICE.md): upstream revision and redistribution status.
- [Pilot checklist](docs/PILOT.md): user validation and release gates that software alone cannot complete.

No research benchmarks, externally sourced language corpora, synthetic experiments, neural training, billing, accounts, remote storage, or collaboration services are included. No accuracy or time-saving claims are made for a customer's language.

## Verify

```sh
python3 -m unittest discover -s tests -v
```

Tests cover the import → prediction → correction → reopen → export/restore workflow, language isolation, exact-neighbor disambiguation, project policies, clean-workspace restore, stale revisions, interrupted writes, malformed input, and browser request protections.
