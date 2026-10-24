# Running and maintaining a pilot

## Supported shape

Python 3.10+ with the standard library; the implementation is verified in Python 3.12. There are no runtime dependencies. Optional pip packaging uses setuptools 68+. Use a local browser with modern JavaScript, File, TextDecoder, fetch, and localStorage support. A graphical browser review must be performed on the intended pilot machines.

One operator and one running server per workspace directory. Keep the server on loopback; do not put it behind a public proxy or use a network share for project files. Tabs send an explicit project identifier to avoid accidental cross-project edits. Annotation revision checks and disk digests reject stale edits. Queue pages limit rendered cards, while all model predictions still run locally in memory.

## Backups and clean-install recovery

1. Download a ZIP backup before upgrades and at the cadence agreed with the data steward. Keep it outside the active workspace in approved storage.
2. Start a fresh installation with an empty directory: `python3 -m decipher --workspace-dir ./recovery-check --port 8766`.
3. Use **Restore a workspace**, enter a new name, and select the ZIP. Restore is available even when no projects exist. It never overwrites a same-named project.
4. Compare sentence/reviewed counts, several accepted glosses, project policy, and revision history. Export JSONL and compare it with the original project's export.
5. Close and reopen the recovered project. Keep the original backup until recovery is verified.

ZIPs contain exactly one `.dproj` JSON document, with no executable model serialization. Unexpected members, unsupported schemas, malformed state, and project members over 25 MiB are rejected. ZIP upload cap is 27 MiB. Backup contents are sensitive if the original corpus is sensitive.

## Writes, conflicts, and crashes

Writes use a per-project exclusive lock, fsync, and atomic file replacement. A failure before replacement preserves the last saved document. Refresh/reopen after a write conflict and review the latest revision before saving. Failed requests are reloaded from disk on subsequent requests rather than silently committing partial in-memory imports.

A process crash can leave `<project>.dproj.lock` or an unnamed temporary file beside a project. Stop every server using that directory, copy the entire directory for recovery, and confirm no writer remains before manually removing a stale lock. Never remove an active writer's lock. Reopen the `.dproj`; if it cannot be opened, restore the most recent verified ZIP into a new name. Do not substitute temporary files without examining them. Atomic replacement is not a guarantee against disk failure or power loss; keep independent backups.

## Upgrade and compatibility policy

Release 0.1.0 reads/writes project schema 1 and does not automatically migrate data. Upstream schema-1 projects with the retained model configuration are accepted. Policy metadata is optional for earlier projects and retained in new backups. Unknown schema versions are rejected rather than rewritten. Test upgrade and restore against copies before replacing a working pilot installation. Retain the prior release alongside its pre-upgrade backup for rollback; do not open future-schema files in an older version.

For packaged distribution, build a wheel with `python3 -m pip wheel --no-deps . --wheel-dir dist`, install it into a clean virtual environment, and run `decipher --version`, `decipher --help`, and the backup recovery workflow. No wheel, corpora, or personal project state should be checked into this source repository.

## Support and verification

This repository supplies software, not a support SLA or payment contract. Name a pilot maintainer, supported OS/browser combinations, support channel, response expectations, release cadence, and maintenance owner in the pilot agreement. Report failures with the release version and a redacted reproduction; never attach private corpora by default. Check Python security updates and rebuild/test releases before distribution.

Run `python3 -m unittest discover -s tests -v` after changes. Automated tests exercise application endpoints in-process and storage recovery. Before distribution, additionally test keyboard-only navigation, browser downloads/uploads, large representative permissioned corpora, clean-machine setup, and the institution's security/privacy requirements. No independent security assessment or customer trial is claimed.
