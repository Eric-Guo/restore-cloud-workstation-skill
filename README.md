# Restore Cloud Workstation

Public reference skill for recovering a cloud Linux workstation and an optional OpenCode workspace-sharing runtime. It covers scoped tool recovery, font provenance, private launchers, and manual offline database/queue backup and restore.

**This is an example, not a ready-to-run deployment or a complete disaster-recovery system.** Configure and review every environment-specific binding before use. The private working configuration is maintained separately; neither version should overwrite or synchronize private configuration into this repository.

## Layout

- `SKILL.md`: agent-facing recovery workflow.
- `references/`: credential, runtime, font, and backup procedures.
- `scripts/private_launcher_template.py`: literal credential parser and hash-bound Linux ELF launcher.
- `scripts/start_sharing_template.py`: configurable foreground owner launcher.
- `scripts/runtime_snapshot.py`: offline SQLite/queue snapshot and quarantined restore.
- `scripts/test_*.py`: isolated synthetic tests, with no live account, model, database, or queue access.

No credentials, account endpoints, private backup links, machine configuration, font packages, runtime databases, or compiled OpenCode binaries are included. Official font projects are linked in the font guide; this repository does not distribute their fonts.

## Use as a skill

Clone this repository into a new directory, then review `SKILL.md` and the references. Use your agent client's supported local-skill installation workflow to import this directory. Installation procedures differ by client; cloning alone does not register it in every client. Never place credential or runtime files inside the skill directory.

For example prompts:

- “Recover the tools needed for this task after the cloud workstation reset.”
- “Prepare an offline backup of the stopped helper runtime after work.”
- “Restore this verified backup into a new private directory, without starting it.”

The scripts require Linux and Python 3.11 or later. The snapshot helper uses only Python's standard library. Actual font installation needs Fontconfig; interactive encryption needs GnuPG. A compatible, separately built OpenCode binary is needed only for real runtime use.

## Configure before real use

The launcher templates intentionally contain invalid placeholder paths and hashes. Prepare a private copy outside this repository and set its canonical paths, full source revision, exact executable/wrapper checksums, and version. Set the credential parser's `TOKEN_NAME` to the single bearer-key name verified in your application's source. The literal placeholder in the example is not a working authentication configuration.

The sharing CLI and queue layout are specific to the implementation identified in [runtime compatibility](references/runtime.md). They are not claimed to work with every upstream OpenCode version. Verify your revision before adapting these scripts. This repository does not include related build or helper skills; follow the selected application's own build instructions when those skills are unavailable.

A snapshot requires the owner to have exited in its actual execution environment and all submissions/writers to remain stopped. A command-line assertion cannot establish that remotely. Snapshot output is sensitive plaintext. Follow the encryption and user-operated upload procedure in [backup and restore](references/backup.md).

## Offline tests

From this directory:

```sh
python3 -m unittest discover -s scripts -p 'test_*.py' -v
```

Tests use temporary synthetic fixtures and fake binaries. They do not demonstrate real SSO, model access, cross-execution persistence, or production disaster recovery.

## Publication boundary

This public source contains reusable examples only. Keep local deployment copies, all backup archives, authentication files, runtime logs/data, personal font manifests and backup locations out of Git. `.gitignore` is a convenience, not a data-loss-prevention guarantee; review the full staged diff and file inventory before every publication.

No license grant is included in this repository. Font projects retain their own licenses, which must be checked and preserved when obtaining fonts.
