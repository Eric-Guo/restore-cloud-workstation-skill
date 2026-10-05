# Manual offline runtime backup and restore

## Scope and sensitive-data boundary

Run a backup only when the user requests it, for example after finishing work. Do not schedule, automatically start, or perform a live backup during skill authoring/testing.

Retain the helper's session/history database and queue requests, replies, task states, and outputs, plus a reviewed non-secret startup launcher and provenance/checksum manifest. Rebuild OpenCode from the recorded revision rather than backing up its binary. Exclude source checkouts, dependencies, build caches, logs, fonts, credential files, unrelated configuration, and live ownership/recovery metadata. Credential and font recovery remain separate workflows.

Database and queue payloads may themselves contain tokens, prompts, private code, or sensitive information. A filename allowlist is not redaction. Never print rows or queue contents, put them in model context, or include them in this repository. Assume snapshots contain highly sensitive credentials unless a separately reviewed export establishes otherwise; the helper does not implement such an export.

Snapshot output is sensitive plaintext. Encrypt locally through the user's interactive GnuPG prompt or an approved secure handoff. Never ask for, generate, save, or pass a passphrase through chat, arguments, environment variables, history, or logs. The user must perform upload of potentially credential-bearing archives even when encrypted. Ordinary permission to upload private deliverables does not authorize transmitting credentials. Never publish backups or expand storage sharing.

## Establish a consistent stopped boundary

1. Identify the owner in its actual execution environment and all submitting clients. Shared files do not prove shared PID/network namespaces or reliable cross-execution SQLite locking.
2. Arrange for no further submissions and wait for known queued/running/cancelling work to finish. Use status interfaces verified in the selected source; do not invent a public pause, ping, task-list, or quiesce command. An active count of zero does not freeze future submissions.
3. Stop the foreground owner normally in its owning terminal and confirm its exit and lock release there. Stop all other database writers. Never signal a foreign recorded PID, kill to force a snapshot, remove an owner/recovery lock, or delete WAL/SHM/journal files. Missing local processes, failed localhost requests, stale timestamps, and quiet files are insufficient evidence.
4. Keep every writer and submission stopped for the entire snapshot. Do not copy a hot database alone. A separately designed online system would need an application-level boundary spanning both SQLite and the independent file queue; SQLite's backup API alone does not create that boundary.
5. Treat refused owner/recovery markers, unknown layout, sidecars, and nonterminal tasks as blockers. Interrupted-owner leftovers need supported recovery first; preserve them.

The helper supports the files-v1 layout documented in [runtime compatibility](runtime.md). If your revision differs, review and adapt the explicit allowlist and tests before use. It never discovers or stops a foreign process for you.

## Create, encrypt, and deliver

Use `../scripts/runtime_snapshot.py` only after the stopped/frozen boundary has been independently confirmed. It performs an offline SQLite backup, validates database integrity/schema metadata, copies bounded queue files without displaying payloads, and detects changed source files. It publishes a new mode-0600 uncompressed ZIP into an existing private directory. It does not encrypt, upload, read a separate credential file, or stop/start an owner.

Prepare a new private staging directory outside the runtime with space for the copied database plus archive. Set the following variables from the reviewed current deployment, keeping private values outside the repository. The source revision is a full SHA; the checksum refers to the verified current binary. These variables are placeholders, not runnable deployment defaults:

```sh
umask 077
python3 "$SKILL_DIR/scripts/runtime_snapshot.py" create \
  --root "$RUNTIME_ROOT" --launcher "$LAUNCHER" \
  --output "$PRIVATE_STAGING/runtime.zip" \
  --source-sha "$FULL_SOURCE_SHA" --binary-sha256 "$BINARY_SHA256" \
  --version "$VERSION" --workspace "$CANONICAL_WORKSPACE" \
  --owner-stopped-in-owning-terminal

gpg --no-options --no-symkey-cache --symmetric --cipher-algo AES256 \
  --output "$PRIVATE_STAGING/runtime.zip.gpg" "$PRIVATE_STAGING/runtime.zip"
sha256sum "$PRIVATE_STAGING/runtime.zip.gpg"
```

The assertion flag records an operator-confirmed precondition; the script cannot establish remote process death. Do not set it based only on local observations. Verify the installed GnuPG flags and interactive TTY/pinentry before preparing a command. The user enters their passphrase directly at the prompt. Do not use batch/loopback passphrase flags or temporary passphrase files. Use new paths and preserve old backups.

Verify encryption success. Have the user decrypt to another new private file through the same interactive mechanism and compare its plaintext checksum with the snapshot. Prepare a private non-secret receipt containing timestamp, source revision, binary version/hash, format, archive hashes/sizes, and file/task counts. Do not include task bodies, session titles, raw schema SQL, or credentials. This operational receipt does not belong in public Git.

Have the user upload the encrypted archive to their intended private storage. Verify the exact file's metadata, access, size, and any supported matching checksum without opening its payload. When necessary, locally hash downloaded ciphertext without decrypting. A filename or upload-start response is insufficient; label unavailable verification honestly. Keep the previous verified backup.

After verified encryption/delivery, follow the applicable deletion approval before removing the exact plaintext staging created for this backup. Never delete runtime data or another backup. Ordinary file deletion is not guaranteed secure erasure on cloud/SSD storage. Report snapshot, encryption, delivery, and verification separately; a local snapshot is not an off-machine backup.

## Restore into a new private directory

1. Resolve the requested backup from the user's private records. Verify ownership/access, receipt, ciphertext size/hash, and source revision. Download only for authorized restoration and preserve the original. The user decrypts interactively into a new private archive; verify its recorded plaintext hash without reading data into the conversation.
2. Rebuild the recorded revision and independently verify the new artifact. A rebuilt binary hash can differ from the historical hash; record and bind the new one. Do not require reproducible builds without evidence, silently upgrade, or run blind migrations.
3. Create a new destination under an existing owned mode-0700 parent:

```sh
python3 "$SKILL_DIR/scripts/runtime_snapshot.py" restore \
  --archive "$PRIVATE_STAGING/runtime.zip" --sha256 "$PLAINTEXT_SHA256" \
  --destination "$NEW_PRIVATE_RUNTIME"
```

The helper rejects an existing destination, unsupported format/layout, unsafe or duplicate paths, special entries, excess sizes, inconsistent hashes, and database integrity/schema discrepancies. It restores `opencode.db`, leaves the old launcher as an inert mode-0600 reference, and places the old queue under `quarantine/spool`. No owner lock or SQLite sidecar is restored. `RESTORE_REVIEW_REQUIRED` blocks the supplied startup template. Extraction starts no service and executes no task.

4. Review application compatibility and workspace mapping privately. A matching SQLite fingerprint establishes integrity, not compatibility with another application build. Inspect migrations before any approved upgrade. Restoring the database may restore persistent credentials; keep it inactive until the required current credential-enablement approval and secure handoff are complete.
5. Resolve unfinished/indeterminate operations by original stable IDs and available provider evidence. Do not automatically replay, change owner IDs, reset states, or retry charged work with new IDs. Retain quarantine and the original backup. Import terminal history only through a verified supported procedure; do not invent an import/resume command. New execution of uncertain work requires the user's decision.
6. Configure a fresh launcher against the verified binary, wrapper, and new private root. Preserve normal agents, tools, plugins, and permission checks. Remove only the new review marker after compatibility, credential, and queue reviews pass. Start only when authorized, in the foreground with fresh owner metadata. Verify readiness and independent non-model status/history at the requested depth. A live model test has its own scope and authorization.

## Limits and offline tests

The helper has a 1 GiB archive limit (including ZIP overhead) and a 100,000-file limit (including the launcher; manifest is additional), requires owned private regular files without hardlinks, and rejects compressed ZIP payloads and unknown archive entries/extensions. It supports only the reviewed queue layout. Large limits are not promises of performance or crash durability; ensure disk capacity and verify every finished archive off-machine. Before any restored payload is published, the helper places the startup-review marker in the new destination. An interrupted restore therefore remains blocked; preserve and inspect the incomplete destination. Existing runtimes are not overwritten.

There is no automatic rotation, upload, scheduler, online consistency protocol, foreign-process detection, migration, or replay. Increase limits or support a new layout only after source review and synthetic tests. Run `python3 -m unittest discover -s scripts -p 'test_*.py' -v` from the repository root. Never use the production database, credentials, queue, or owner to validate the skill.
