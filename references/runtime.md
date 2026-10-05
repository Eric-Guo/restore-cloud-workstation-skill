# Runtime recovery and acceptance

## Compatibility scope

The optional workspace-sharing example follows the public [Eric-Guo/opencode source at f414fef393310de92b2d6f0c0d34da334313db01](https://github.com/Eric-Guo/opencode/tree/f414fef393310de92b2d6f0c0d34da334313db01), particularly:

- [`owner.ts`](https://github.com/Eric-Guo/opencode/blob/f414fef393310de92b2d6f0c0d34da334313db01/packages/cli/src/services/workspace-sharing/owner.ts)
- [`files.ts`](https://github.com/Eric-Guo/opencode/blob/f414fef393310de92b2d6f0c0d34da334313db01/packages/cli/src/services/workspace-sharing/files.ts)

This is a protocol reference, not a required deployment pin or a claim of compatibility with unrelated OpenCode releases. Verify the chosen revision's CLI, migrations, storage layout, and credential handling before using the examples. The database example is `opencode.db`; the queue contains `requests`, `replies`, `tasks`, and `outputs` JSON directories, schema-version-1 task records, and a live `worker.lock/owner.json`.

## Preserve a surviving owner

Inspect current launchers and source/help. Credential wrappers and owner launchers can bind different binary paths, hashes, and versions; verify every binding. Keep rollback copies. An existing permitted non-model query that succeeds is reason to reuse the owner, not restart it.

A missing local PID, failed localhost request, stale timestamp, or SQLite lock experiment does not prove that an owner in a different execution namespace is dead. Never signal a foreign recorded PID, clear ownership metadata, steal ownership after a TTL, or open a second server on the database based on those observations. Inspect the owning terminal or report the blocker.

Preserve existing databases and history. If a clean runtime is needed, agree on that change and choose a separate location. Use the canonical task workspace; broad filesystem visibility is not authorization to send unrelated data to a model.

## Configure the foreground launcher

`../scripts/start_sharing_template.py` takes only reviewed non-secret bindings:

- `ROOT`: new or existing private runtime directory.
- `WORKSPACE`: canonical authorized task directory.
- `WRAPPER`: reviewed Python wrapper implementing `environment` and `read_credentials`.
- `BINARY`, `SOURCE_SHA`, `VERSION`, and `HASHES`: verified build and wrapper bindings.

The example reads `credentials.env` beside the wrapper through that reviewed parser. Place the private wrapper accordingly or explicitly adapt that binding; do not copy a token into the launcher. Preserve needed default agents, tools, permission checks, plugins, and allowed proxy/CA settings. Do not add disabling flags or auto-confirmation to make recovery appear successful.

Install a configured private copy outside the repository, with mode 0700, preserving any existing launcher. Compile without executing and run fake-wrapper/binary tests first. The launcher starts one foreground owner on loopback with a dynamically assigned port, `ROOT/opencode.db`, and `ROOT/spool`. It contains no daemon, timer, model test, automatic migration, upload, or startup registration. Existing owner/recovery markers or a restore-review marker block startup.

Keep the actual owner terminal open and wait for its readiness signal. A child PID, `nohup`, or successful launch call does not demonstrate persistence after an execution closes. Do not impose an arbitrary test timeout on the normal owner. Stop normally in that terminal after authorized work.

For status/result/history, use current supported credential-free file-client commands in an isolated HOME/XDG environment. Do not invent a ping/task-list command or switch to another transport to bypass an access denial.

## Layered acceptance

When a real working recovery is requested and authorized:

1. Verify provenance, full source revision, target platform, version, executable hash, and launcher syntax/mode.
2. Verify actual account authentication through the normal application flow without displaying credentials. Detect silent authentication failure; version output alone proves little.
3. Check owner readiness and a non-model query from an independent execution. Corroborate the owner's build, not just the client binary's version.
4. Only if model invocation is in scope, submit one harmless bounded task to the user-selected configured model. Record a stable request ID before submitting; do not use model self-report as identity evidence.
5. Query that same ID to a terminal state and retrieve the expected result/history. Check recorded model/session, start count, exit status, tool calls, and ongoing owner readiness where exposed. Mark unavailable fields unverified.

Queued, running, and cancelling are unfinished. If an outcome is uncertain, preserve the ID and payload and query the original task. Do not generate a new ID and replay a potentially charged request.

For restored data, follow [backup and restore](backup.md). Treat the old launcher as an inert reference; bind a fresh reviewed launcher to the rebuilt artifact and new root. Offline tests do not exercise live credentials, production data, real SSO/model calls, or the current owner.
