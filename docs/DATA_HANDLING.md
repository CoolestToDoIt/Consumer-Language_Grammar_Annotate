# Local pilot data handling

The application reads only the files selected for import or restore and the configured workspace directory. It makes no external network requests, sends no telemetry, and uses no third-party AI service. Browser assets are embedded locally. Project choice is stored in the browser's localStorage as a project identifier; corpus contents are stored in `.dproj` files on disk, not localStorage.

The operator and data steward determine ownership, consent, permitted uses, attribution, access, retention, and deletion. Record those decisions in each project's policy fields. These are descriptive records, not an enforcement or consent-verification system. Do not import a community corpus or share trained resources without appropriate permission. Source text and glosses remain within the selected local workspace unless you export or otherwise copy them.

Each project holds source tokens, corpus names and hashes, accepted gloss revisions and timestamps, model configuration, and project policy. Earlier accepted glosses remain in revision history after correction. The learner is reconstructed from the latest accepted labels. A ZIP backup includes the complete project; JSONL/TSV are interoperable annotation exports rather than full recovery backups.

There is no application login, role control, encryption at rest, or protection from other programs running as your OS user. Use a private OS account, protected directory, device encryption, and institution-approved backup storage when required. Project writes use private temporary files; the default workspace directory is created with owner-only permissions where supported. Existing directory permissions are not changed. Localhost binding and browser-origin checks reduce exposure but are not a security certification.

The application retains files until the operator deletes them. **Delete project** requires the exact project name and removes its active `.dproj` file. It does not erase exported ZIPs, browser downloads, OS backups, filesystem snapshots, or securely wipe storage blocks. Apply the agreed retention policy to every copy. Delete any disposable demo through the same project control. Clear the browser's site storage if the remembered project identifier also needs removal.

The pilot operator owns installation, backups, access decisions, incident handling, user support, and any rights-clearance process. Agree on those responsibilities before using real data.
