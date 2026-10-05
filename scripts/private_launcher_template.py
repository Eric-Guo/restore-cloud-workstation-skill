#!/usr/bin/python3
"""Non-secret template. Configure reviewed paths/hash; never embed credentials."""

import hashlib
import os
from pathlib import Path
import re
import shlex
import stat
import sys

# Configure these non-secret values for the verified build and new private root.
BINARY = Path("/REPLACE_WITH_VERIFIED_BINARY")
BINARY_SHA256 = "REPLACE_WITH_64_HEX_SHA256"
ROOT = Path("/REPLACE_WITH_PRIVATE_RUNTIME")
TOKEN_NAME = "APPLICATION_BEARER_KEY"
PARENT_KEYS = frozenset({
    "PATH", "SHELL", "TERM", "COLORTERM", "LANG", "LC_ALL", "TZ",
    "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
    "http_proxy", "https_proxy", "all_proxy", "no_proxy",
    "NODE_EXTRA_CA_CERTS", "NODE_USE_ENV_PROXY", "SSL_CERT_FILE", "SSL_CERT_DIR",
    "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE",
    "OPENCODE_CONFIG_CONTENT", "OPENCODE_CONFIG_PROJECT_DISABLE",
    "OPENCODE_DISABLE_MODELS_FETCH", "OPENCODE_DISABLE_AUTOUPDATE",
    "OPENCODE_FILEWATCHER_DISABLE", "OPENCODE_ENABLE_OPENTELEMETRY",
})


class ConfigurationError(Exception):
    pass


def parse_environment(raw):
    if len(raw) > 65536:
        raise ConfigurationError("Credential file is too large")
    try:
        lines = raw.decode("utf-8-sig").splitlines()
    except UnicodeError:
        raise ConfigurationError("Credential file must be UTF-8") from None
    result = {}
    for number, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"(?:export[ \t]+)?([A-Za-z_][A-Za-z_0-9]*)[ \t]*=[ \t]*(.*)", line)
        if not match or match[1] != TOKEN_NAME or match[1] in result:
            raise ConfigurationError(f"Unsupported or duplicate credential assignment on line {number}")
        try:
            value = shlex.split(match[2], comments=True, posix=True)
        except ValueError:
            raise ConfigurationError(f"Invalid credential quoting on line {number}") from None
        if len(value) != 1 or not re.fullmatch(r"[A-Za-z0-9._~+/-]+=*", value[0]):
            raise ConfigurationError(f"Invalid bearer credential format on line {number}")
        result[match[1]] = value[0]
    if TOKEN_NAME not in result:
        raise ConfigurationError("Required SSO credential is missing")
    return result


def read_credentials(path):
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
        with os.fdopen(descriptor, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
                raise ConfigurationError("Credential file must be an owned regular file with mode 0600")
            return parse_environment(stream.read(65537))
    except OSError:
        raise ConfigurationError("Cannot safely open the private credential file") from None


def environment(parent, credentials, root=ROOT):
    result = {name: value for name, value in parent.items() if name in PARENT_KEYS}
    result.setdefault("PATH", "/usr/local/bin:/usr/bin:/bin")
    result.update({
        "HOME": str(root / "home"),
        "XDG_CONFIG_HOME": str(root / "config"),
        "XDG_DATA_HOME": str(root / "data"),
        "XDG_STATE_HOME": str(root / "state"),
        "XDG_CACHE_HOME": str(root / "cache"),
        "XDG_RUNTIME_DIR": str(root / "run"),
        "TMPDIR": str(root / "tmp"),
        "TMP": str(root / "tmp"),
        "TEMP": str(root / "tmp"),
        "PWD": os.getcwd(),
    })
    result.update(credentials)
    return result


def main():
    os.umask(0o077)
    try:
        for name in ("", "home", "config", "data", "state", "cache", "run", "tmp"):
            info = (ROOT / name).lstat()
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
                raise ConfigurationError("Runtime directories must be owned private directories with mode 0700")
        if not BINARY.is_absolute() or not ROOT.is_absolute() or not re.fullmatch(r"[0-9a-f]{64}", BINARY_SHA256):
            raise ConfigurationError("Configure verified absolute paths and binary SHA-256 first")
        parent_info = BINARY.parent.lstat()
        if not stat.S_ISDIR(parent_info.st_mode) or parent_info.st_uid != os.getuid() or parent_info.st_mode & 0o022:
            raise ConfigurationError("Binary directory must be owned and not group/world-writable")
        descriptor = os.open(BINARY, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
        with os.fdopen(descriptor, "rb") as stream:
            binary_info = os.fstat(stream.fileno())
            if not stat.S_ISREG(binary_info.st_mode):
                raise ConfigurationError("Binary must be a regular file")
            if binary_info.st_uid != os.getuid() or binary_info.st_mode & 0o022 or not binary_info.st_mode & stat.S_IXUSR:
                raise ConfigurationError("Binary must be owned, executable and not group/world-writable")
            if stream.read(4) != b"\x7fELF":
                raise ConfigurationError("Binary must be the verified Linux ELF artifact")
            stream.seek(0)
            digest = hashlib.sha256()
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
            actual_hash = digest.hexdigest()
            if actual_hash != BINARY_SHA256:
                raise ConfigurationError("Configured binary checksum does not match")
            configured = environment(os.environ, read_credentials(ROOT / "credentials.env"), ROOT)
            # Linux fd-based exec binds credential delivery to the exact file hashed.
            # Keep it open until exec; a concurrent path replacement is not executed.
            os.execve(stream.fileno(), [str(BINARY), *sys.argv[1:]], configured)
    except (ConfigurationError, OSError) as error:
        message = str(error) if isinstance(error, ConfigurationError) else "Unable to start the configured binary"
        print("OpenCode private runtime: " + message, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
