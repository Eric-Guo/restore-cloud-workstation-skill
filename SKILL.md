---
name: restore-cloud-workstation
description: Recover task-needed tools, fonts, and an optional OpenCode workspace-sharing runtime on a cloud Linux computer after reset or lost files. Prepare user-requested manual offline database and queue backups or restore into a fresh private directory. Use for cloud workstation recovery, 云电脑恢复, or helper data recovery; not routine builds, the user's local computer, automatic backups, or a complete disaster-recovery guarantee.
---

# Restore a cloud workstation

This public skill is a configurable reference. Private deployments are maintained separately. A request to review or edit the skill uses offline fixtures only and does not authorize a live backup, credential activation, service restart, or model request.

## 1. Establish what survived

- Confirm the intended cloud Linux environment is ready. Do not switch to the user's local computer without their request.
- Check task-relevant paths, ownership/mode, source revision, executable hashes, tool versions, and non-secret authentication status. Do not dump environment variables, process arguments, credential files, database contents, or unrestricted logs.
- Shared files do not prove shared PID or network namespaces. A changed hostname does not establish why files disappeared or that browser/plugin sessions were lost. Check those separately when needed.
- Classify each needed component as present and verified, missing, or unknown. Preserve dirty work, local commits, existing binaries, databases, queues, and ownership metadata. Never restart an active owner just to test recovery.

## 2. Choose the smallest recovery path

Use a working tool as-is and recover only missing layers. Read the relevant reference:

- [Credentials](references/credentials.md): private configuration and optional GitHub access.
- [Runtime](references/runtime.md): compatible build, private wrapper, foreground owner, and acceptance gates.
- [Fonts](references/fonts.md): official sources, private cache verification, and explicit substitutions.
- [Backup](references/backup.md): requested end-of-work offline snapshot, encryption, and fresh-directory restore.

Verify the source repository, requested revision, workspace, and model with the current user task. This example does not pick an account, live authentication endpoint, or deployment configuration for the user. Companion build/helper skills are optional; use the current application source and build instructions when unavailable.

## 3. Recover source and required tools

1. Pin the user's full commit SHA. If they supplied a branch instead, resolve its full SHA once and keep it fixed throughout this recovery.
2. Inspect working state before changing it. Use a fresh clone or detached build worktree and separate output directory. Do not reset, clean, implicitly stash, or overwrite dirty/untracked work.
3. Read the selected revision's repository instructions, package-manager pin, and builder. Use official tool sources and pinned versions under the applicable authorization. Tune resource limits locally rather than changing project defaults.
4. Build and verify the target platform/version/artifact hash. Retain the old runnable artifact until the replacement passes. Compiled binaries are rebuildable and excluded from the runtime data backup.
5. Switch a launcher only within an authorized recovery or upgrade, with verified bindings and a rollback copy. Do not start or restart a live service incidentally.

## 4. Back up only on request

When the user requests a backup after work, follow the offline procedure. Keep a reviewed non-secret startup launcher and provenance/checksum manifest with the database and queue. Do not schedule backups or run one merely because this skill was installed or edited.

The owner must exit orderly in its actual terminal, and submissions and every writer must remain stopped. Never remove locks, recovery markers, WAL/SHM files, or ownership metadata to force a snapshot. Treat database/queue contents as potentially credential-bearing. Encrypt locally and require user-operated upload when they may contain highly sensitive credentials.

Restore into a new private directory, quarantine the old queue, and require compatibility and credential-enablement review before startup. No automatic task replay, migration, upload, or deletion of previous backups.

## 5. Report the requested level accurately

Distinguish source/tools recovered, binary verified, private launcher configured, credentials pending or authenticated, owner ready or stopped, and real model acceptance tested or not run. A version command is not an authentication test.

For backups, distinguish local snapshot, encryption, off-machine delivery, and verification. For restores, distinguish database integrity, queue quarantine, compatibility review, and authorized startup. For fonts, distinguish a verified package from installed and actually selected families/styles, with substitutes and gaps stated.

Keep stable task IDs when resolving uncertain model outcomes. Do not replay a potentially charged request under a new ID. When an operation is denied or needs permission, stop that step rather than switching routes to bypass it. Continue independent authorized work and request the smallest missing decision. Stop when the requested scope passes or needs user input; do not add autorun or unrelated recovery.
