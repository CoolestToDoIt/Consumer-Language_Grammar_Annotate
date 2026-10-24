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

1. Choose **Try a disposable demo** to explore seven invented examples, or create a project for your language. The demo contains no community corpus.
2. Record ownership, permitted uses, consent, provenance, retention, and annotation conventions in **Data ownership & conventions** before importing real data.
3. Preview a UTF-8 corpus and inspect sentence counts, supplied labels, and alignment. Confirm to import. Supplied glosses count as authoritative annotations; import only labels you intend to trust.
4. Review the queue. Edit every draft and save the reviewed glosses. Enable **Show reviewed sentences** to revise earlier work. Candidate evidence is an uncalibrated score, not a probability. Known-form evidence alone does not mean the current sentence is reviewed.
5. Download a ZIP backup regularly. JSONL/TSV exports contain source sentences and accepted labels; unreviewed sentences have null/empty labels. Download revision history separately, or use ZIP for the complete project, policy, and revision history.

Search and 20-sentence pages keep the visible queue manageable. Predictions are still computed in memory for the full project; this edition targets small pilot corpora rather than large archives.

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
