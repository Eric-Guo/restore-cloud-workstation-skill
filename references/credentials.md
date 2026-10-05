# Credential recovery

## Discover a private backup without exposing it

Use the user's authorized storage connector to locate the requested backup by metadata. Verify owner, purpose, time, size, checksum, and current access. Resolve duplicates. Keep backup names, IDs, account identifiers, authentication endpoints, and all contents in the private deployment records, never this repository.

Fetch raw bytes only for the requested recovery. Do not convert credential files to document text, print them, include them in model context, or put secrets in arguments, logs, shell history, or deliverables. Use a fresh owned directory with mode 0700 and files 0600. Inspect metadata only; never `source`, `eval`, or execute an environment file.

Downloading a backup and enabling its credentials are distinct actions. Obtain the required current approval before configuring persistent access on a replacement machine. Identify the account, destination, and scope without quoting the secret. The user enters passwords or passphrases through a secure handoff or interactive terminal, never chat. New recipients, OAuth scopes, or access expansion require a separate review.

If a backup or connector is missing, report the affected component and continue public-source preparation. Do not create replacement tokens automatically.

## Optional GitHub access

Public source clone/build does not require restoring GitHub authentication. Restore it only for needed private access or an authorized push. Use a reviewed helper or a user-operated official sign-in; do not expose tokens or alter global Git credential configuration.

A credential-archive restore helper should:

- Decrypt through the user's interactive GnuPG prompt into fresh private staging.
- Reject absolute/traversing paths, duplicate or conflicting members, symlinks, hardlinks, sparse files, and special entries before extraction.
- Publish atomically into a new destination without overwriting existing configuration.
- Keep directories 0700 and files 0600. Retain the original encrypted archive.
- Verify account access using a process-local configuration directory with unrelated inherited token variables removed. Record only non-secret account/status metadata.

Review any downloaded helper and its provenance before execution. Offline-test a new helper with synthetic archives, not the user's real credentials. Successful decryption is not proof of authentication. Never read credential payloads into the conversation or run a token-printing command. Required credential entry, configuration, and consent remain with the user or an approved secure flow.

## Private OpenCode launcher example

`../scripts/private_launcher_template.py` is an example for a reviewed Linux ELF binary, not a generic shell launcher. Configure its absolute binary path, exact SHA-256, private runtime root, and one `TOKEN_NAME` that matches the selected application's verified source. The default `APPLICATION_BEARER_KEY` is a placeholder, not a universal OpenCode variable.

The example reads `ROOT/credentials.env`, allowing only a single literal assignment to that configured name. It rejects duplicate keys, extra assignments, shell expansions, and malformed values. It does not execute the file. Preserve the parser's narrow allowlist; do not replace it with shell sourcing.

Use owned private runtime directories and a 0600 credential file. Keep a versioned executable in an owned directory that is not group/world-writable. Never update a deployed binary in place. The launcher hashes an open file and executes that descriptor on Linux, protecting against a path replacement between verification and launch. It does not protect against a same-inode write by the owning user; prevent concurrent deployment changes.

The environment allowlist preserves selected proxy, CA, locale, and application settings. Review these against the actual application before extending it. Configure authentication service destinations privately and verify that they are the intended recipients. This public example contains no endpoint defaults or permission to send credentials.

Compile configured copies without executing, and run the synthetic tests. Only after approval and the appropriate secure credential handoff may a deployed wrapper load its private credential file. A `--version` success is only launch compatibility. Credential-free file-client status queries must not use the credential-loading wrapper.
