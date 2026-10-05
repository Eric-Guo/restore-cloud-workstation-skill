#!/usr/bin/python3
"""Reviewed foreground owner template. Configure non-secret bindings before use."""

from contextlib import ExitStack
import hashlib
import os
from pathlib import Path
import re
import stat
import sys

ROOT = Path("/REPLACE_WITH_PRIVATE_SHARING_ROOT")
WORKSPACE = Path("/REPLACE_WITH_CANONICAL_WORKSPACE")
WRAPPER = Path("/REPLACE_WITH_REVIEWED_PRIVATE_WRAPPER")
BINARY = Path("/REPLACE_WITH_VERIFIED_BINARY")
VERSION = "REPLACE_WITH_VERIFIED_VERSION"
SOURCE_SHA = "REPLACE_WITH_40_HEX_SOURCE_SHA"
HASHES = {
    WRAPPER: "REPLACE_WITH_WRAPPER_64_HEX_SHA256",
    BINARY: "REPLACE_WITH_BINARY_64_HEX_SHA256",
}


class StartupError(Exception):
    pass


def verify_file(file, expected):
    parent = file.parent.lstat()
    if not stat.S_ISDIR(parent.st_mode) or parent.st_uid != os.getuid() or parent.st_mode & 0o022:
        raise StartupError("Runtime file parent is not an owned protected directory")
    descriptor = os.open(file, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    stream = os.fdopen(descriptor, "rb")
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o022:
            raise StartupError("A required runtime file is not an owned, protected regular file")
        if hashlib.file_digest(stream, "sha256").hexdigest() != expected:
            raise StartupError("A verified runtime file changed; review it before restarting")
        stream.seek(0)
        return stream
    except BaseException:
        stream.close()
        raise


def private_directory(directory):
    try:
        directory.mkdir(mode=0o700)
    except FileExistsError:
        pass
    info = directory.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise StartupError("Runtime directories must be owned private directories with mode 0700")


def main():
    if sys.argv[1:] == ["--help"]:
        print("Usage: start-sharing")
        print("Starts the pinned foreground owner; Ctrl+C stops it. Storage is reused on restart.")
        print("Version: " + VERSION)
        print("Workspace: " + str(WORKSPACE))
        print("Database: " + str(ROOT / "opencode.db"))
        print("Shared queue: " + str(ROOT / "spool"))
        return 0
    if sys.argv[1:]:
        raise StartupError("Unexpected arguments; use start-sharing without arguments")
    os.umask(0o077)
    if not re.fullmatch(r"[0-9a-f]{40}", SOURCE_SHA) or any(
        not re.fullmatch(r"[0-9a-f]{64}", h) for h in HASHES.values()
    ):
        raise StartupError("Configure the verified full source revision and checksums first")
    if any(not p.is_absolute() or p.resolve() != p for p in (ROOT, WORKSPACE, WRAPPER, BINARY)):
        raise StartupError("Configure canonical absolute paths without symlinks")
    if os.path.lexists(ROOT / "RESTORE_REVIEW_REQUIRED"):
        raise StartupError("Restored database/queue needs review before startup")
    if any(os.path.lexists(ROOT / "spool" / x) for x in ("worker.lock", ".owner", ".recover")):
        raise StartupError("Existing or unknown owner/recovery marker; use the owning terminal")
    if WORKSPACE.resolve(strict=True) != WORKSPACE or not WORKSPACE.is_dir():
        raise StartupError("The configured workspace is unavailable or is not canonical")
    for name in ("", "home", "config", "data", "state", "cache", "run", "tmp"):
        private_directory(ROOT / name)
    private_directory(ROOT / "config" / "opencode")
    with ExitStack() as opened:
        verified = {file: opened.enter_context(verify_file(file, expected))
                    for file, expected in HASHES.items()}
        source = {"__name__": "workspace_sharing_bootstrap", "__file__": str(WRAPPER)}
        # Use exactly the wrapper bytes and binary inode checked above, even if paths are replaced.
        exec(compile(verified[WRAPPER].read(), str(WRAPPER), "exec"), source)
        # The reviewed parser reads its existing private file only in this user-started process.
        # Credential values remain in memory and are never printed, copied or persisted here.
        configured = source["environment"](
            os.environ,
            source["read_credentials"](WRAPPER.parent / "credentials.env"),
            root=ROOT,
        )
        configured.update({
            "OPENCODE_DB": str(ROOT / "opencode.db"),
            "OPENCODE_CONFIG_DIR": str(ROOT / "config" / "opencode"),
        })
        os.chdir(WORKSPACE)
        configured["PWD"] = str(WORKSPACE)
        print("Starting OpenCode " + VERSION, flush=True)
        print("Workspace: " + str(WORKSPACE), flush=True)
        print("Database: " + str(ROOT / "opencode.db"), flush=True)
        print("Shared queue: " + str(ROOT / "spool"), flush=True)
        print("Keep this terminal open. Wait for 'workspace sharing ready'; Ctrl+C stops the owner.", flush=True)
        binary = verified[BINARY]
        # Script fixtures need an inherited descriptor for their interpreter; ELF binaries do not.
        if binary.read(4) != b"\x7fELF":
            os.set_inheritable(binary.fileno(), True)
        binary.seek(0)
        os.execve(binary.fileno(), [
            str(BINARY), "serve", "--hostname", "127.0.0.1", "--port", "0",
            "--workspace-sharing", str(ROOT / "spool"),
        ], configured)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except StartupError as error:
        print("OpenCode sharing: " + str(error), file=sys.stderr)
        sys.exit(2)
    except Exception:
        print("OpenCode sharing could not start safely. Check the existing private runtime and storage permissions.", file=sys.stderr)
        sys.exit(2)
