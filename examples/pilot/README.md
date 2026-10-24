# A fictional annotator's first session

Maya is a fictional language-program annotator reviewing a new field session. All language forms, people, labels, institutions, and permissions in this example are invented. The word pairs exercise the software; they do not represent a real language or performance evaluation.

## Prepare and open the walkthrough

From the repository root:

```sh
python3 tools/run_walkthrough.py
python3 -m decipher --workspace-dir ./demo-run/projects
```

The first command creates new files under `demo-run` and runs the real browser application's endpoints in-process. It preserves a practice project before review, completes a separate copy, exports annotations and history, and verifies restore into a fresh workspace. It refuses to overwrite an existing walkthrough. For another run, use `--output-dir ./demo-run-2` and start the app with that directory's `projects` folder.

Open **http://127.0.0.1:8765**. Choose **01 Maya - review practice**, then click **Open**. This contains nine supplied reviewed anchors and five unreviewed sentences. The other project, **02 Maya - completed session**, shows the final result.

## Hands-on review

1. Read **Data ownership & conventions**. The project records fictional provenance and defines `PL` and `PST`. In a real pilot, the actual data steward must supply the permission and policy information.
2. The review queue contains five sentences. Search for `velum`. The model suggests `flower-PL bird` for `velum mir`: it has seen `vel → flower`, plus two examples of the plural suffix. Review both fields and click **Save reviewed glosses**. The sentence leaves the default queue.
3. Search for `noka`. The initial model draft is `see flower`; `noka` is unfamiliar. Maya's invented notes say it means `water`. Replace the first field with `water`, keep `flower`, and save. This creates a new semantic anchor rather than accepting an unsupported guess.
4. Clear the search. Review and save `zalen tal → PST-see tree`, `mirum vor → bird-PL go`, and `vel tal → flower tree`. Known words still require sentence review.
5. Enable **Show reviewed sentences**, search for `noka`, change `flower` to `blossom`, and save the revision. This is Maya's sentence-specific terminology decision; other sentences are not silently rewritten. Revision 1 remains in history and revision 2 becomes authoritative for this sentence.
6. Clear the search. The project summary should report **14 sentences · 14 reviewed**. Download revision history: it contains 15 entries, including both versions of `noka vel`.
7. Preview [03-misaligned-example.tsv](03-misaligned-example.tsv). It has two source words but only one label. The app rejects it without importing partial data.
8. Preview [02-new-session.txt](02-new-session.txt) again. It is marked as already imported, and the add button is disabled.
9. Export JSONL and TSV, then **Download backup**. The annotation exports preserve accepted labels; the ZIP additionally preserves policy and full history.
10. In **Restore a workspace**, choose the downloaded ZIP and a new project name. Open the restored project and check counts, `water blossom`, policy, and history. Restore never overwrites the original.

Drafts can change as you teach the model. The initial outputs above were recorded before any of the five new sentences were corrected. The generated `demo-run/WALKTHROUGH.md` captures the actual outputs of each automated run.

## Start from a completely empty project

Create a new project, record its policy, preview and import [01-reviewed-seed.tsv](01-reviewed-seed.tsv), then preview and import [02-new-session.txt](02-new-session.txt). That reproduces the practice project's starting point. Supplied seed labels are treated as authoritative; the new session has no supplied labels.

[reviewer-decisions.json](reviewer-decisions.json) contains the fictional reviewer's initial answers. It is used by the walkthrough script, not ingested as hidden model evidence. The model sees these answers only when the script submits a correction, just as the browser would.

## Files produced

- `projects/`: untouched practice project plus completed project, ready for the browser.
- `WALKTHROUGH.md`: actual prediction table and ten-step transcript.
- `annotations.jsonl`, `annotations.tsv`: completed accepted annotations.
- `revision-history.json`: all 15 accepted revisions.
- `practice-backup.zip`, `completed-backup.zip`: before/after full project backups.
- `recovery-check/`: separately recovered completed project; its annotation export, policy, and revision count are checked against the original.

The script uses the same project, import, correction, and restore code as the browser, but does not automate browser clicks or verify visual layout.
