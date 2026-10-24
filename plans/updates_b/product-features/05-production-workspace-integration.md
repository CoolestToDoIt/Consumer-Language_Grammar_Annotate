# Binding teaching and review to the real workspace

## New information during implementation

Worker A published commit `eaab130` while B was developing against the allowed
fixture adapter. It supplies `decipher/project.py`, the local web app and contextual
model support. That published main was merged into B's feature branch at `80feecb`.
The shared CLI conflict was resolved by retaining both `gloss web` and `gloss teach`.
Local main and the published main were not modified by that feature-branch merge.

## Actual integration

`decipher/workspace.py` adapts A's `LanguageProject` to the teaching/review contract.
The default CLI now opens real `.dproj` projects; `--backend fixture` remains an
explicit test/demo option. An existing UI-created or imported workspace opens in
the CLI without migration. Its original corpus identities and annotation history
stay in A's format.

Immutable prediction records, correction retry receipts and human revision reasons
are stored in an optional `teaching` metadata field inside the same `.dproj` file.
They therefore travel through A's existing export/restore path. No competing
production project file or sidecar was introduced.

## Small shared API additions

Inspection showed that A's first API saved corrections immediately and did not
detect stale clients. B needs to save the correction and its audit information
together and prevent a CLI/browser client from overwriting newer work.

- `LanguageProject.submit` registers public manual source sentences.
- `correct(..., expected_revision=..., persist=False)` checks the reviewed
  annotation revision and allows one final save after the audit metadata is added.
  Existing callers retain their normal save behavior.
- `save()` uses an exclusive writer lock and checks the file identity from open
  before replacing it. Failed writes clean up temporary files and retain the last
  complete project. A stale writer must reopen instead of silently overwriting.
- The web form sends its displayed revision. Stale annotation/file writes return
  HTTP 409 so the user can refresh. The page layout and project format are retained.
- Calibration identity includes A's contextual setting as well as model evidence
  and settings, so artifacts cannot be reused across different prediction behavior.

These are targeted storage/API safety additions needed by B's teaching/review
flow. A's model extension is preserved; B has not started the deferred internal
stem-edit experiment or changed the default learner for that experiment.

## Integration fixtures

New tests exercise real workspace teaching/transfer, confirmation, imported history,
save/reopen, export/restore with retry IDs and predictions, CLI/web stale-client
conflicts in both directions, failed combined saves, malformed metadata and the
default standard-library CLI. The existing A project/web tests also run against
the additive API. Combined verification follows these targeted checks.

Verification completed: all **128 tests passed**, including the ten new production
adapter tests, all six A project/web tests and the optional neural checks. The
bounded corpus driver now uses real `.dproj` workspaces as well. It explicitly
disables context in that controlled evaluation to retain the frozen word-gloss
baseline condition; normal projects retain A's contextual configuration.

## Real project commands

```powershell
.venv/Scripts/python.exe -X utf8 -S -m decipher.app gloss teach init --project runs/my-language.dproj --name "My language" --language Demo
.venv/Scripts/python.exe -X utf8 -S -m decipher.app gloss teach shell --project runs/my-language.dproj
.venv/Scripts/python.exe -X utf8 -S -m decipher.app gloss teach review --project runs/my-language.dproj --limit 10
.venv/Scripts/python.exe -X utf8 -S -m decipher.app gloss teach export --project runs/my-language.dproj --output runs/my-language-backup.zip
```

Opening the same `.dproj` file through A's UI uses the same authoritative annotations.
The fixture backend is no longer needed for the actual teaching/review path.
