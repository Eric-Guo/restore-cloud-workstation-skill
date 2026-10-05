#!/usr/bin/env python3
"""Offline tests only: synthetic credentials, fake binary, no subprocess/network."""
import contextlib
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).with_name("private_launcher_template.py")
spec = importlib.util.spec_from_file_location("private_launcher_template", SOURCE)
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.original_umask = os.umask(0o077)
        self.temp = tempfile.TemporaryDirectory(prefix="restore-synthetic-")
        self.root = Path(self.temp.name) / "runtime"
        for name in ("", "home", "config", "data", "state", "cache", "run", "tmp"):
            (self.root / name).mkdir(mode=0o700, parents=True, exist_ok=True)
        self.creds = self.root / "credentials.env"
        self.creds.write_text("APPLICATION_BEARER_KEY=synthetic-not-a-live-token\n")
        self.creds.chmod(0o600)
        self.binary = Path(self.temp.name) / "fake-binary"
        self.binary.write_bytes(b"\x7fELFnot executable; tests mock execve")
        self.binary.chmod(0o700)
        self.hash = hashlib.sha256(self.binary.read_bytes()).hexdigest()

    def tearDown(self):
        self.temp.cleanup()
        os.umask(self.original_umask)

    def test_literal_assignments(self):
        value = launcher.parse_environment(b"# demo\nexport APPLICATION_BEARER_KEY='synthetic.token=' # comment\n")
        self.assertEqual(set(value), {launcher.TOKEN_NAME})
        self.assertEqual(value[launcher.TOKEN_NAME], "synthetic.token=")

    def test_rejects_unknown_duplicate_expansion_malformed_large(self):
        for raw in (
            b"PATH=/tmp", b"APPLICATION_BEARER_KEY=a\nAPPLICATION_BEARER_KEY=b",
            b"APPLICATION_BEARER_KEY=$(touch /tmp/not-created)",
            b"APPLICATION_BEARER_KEY=`id`", b"APPLICATION_BEARER_KEY=$HOME",
            b"APPLICATION_BEARER_KEY=one two", b"APPLICATION_BEARER_KEY='bad",
            b"\xff", b"#" * 65537, b"",
        ):
            with self.subTest(case=raw[:30]):
                with self.assertRaises(launcher.ConfigurationError):
                    launcher.parse_environment(raw)

    def test_private_regular_file_only(self):
        self.assertEqual(set(launcher.read_credentials(self.creds)), {launcher.TOKEN_NAME})
        self.creds.chmod(0o644)
        with self.assertRaises(launcher.ConfigurationError):
            launcher.read_credentials(self.creds)
        self.creds.chmod(0o600)
        link = self.root / "link.env"
        link.symlink_to(self.creds)
        with self.assertRaises(launcher.ConfigurationError):
            launcher.read_credentials(link)

    def test_fifo_rejected_without_blocking(self):
        fifo = self.root / "fifo.env"
        os.mkfifo(fifo, 0o600)
        with self.assertRaises(launcher.ConfigurationError):
            launcher.read_credentials(fifo)
        result, captured, output = self.call_main(BINARY=fifo)
        self.assertEqual(result, 2)
        self.assertEqual(captured, {})
        self.assertIn("regular file", output)

    def test_allowlist_and_private_paths(self):
        env = launcher.environment({"PATH": "/usr/bin", "HTTPS_PROXY": "http://fixture", "NODE_EXTRA_CA_CERTS": "/fixture/ca", "GH_TOKEN": "synthetic", "AWS_SECRET_ACCESS_KEY": "synthetic", "LD_PRELOAD": "/fixture/evil", "HOME": "/untrusted"}, {launcher.TOKEN_NAME: "synthetic"}, self.root)
        self.assertEqual(env["HTTPS_PROXY"], "http://fixture")
        self.assertEqual(env["NODE_EXTRA_CA_CERTS"], "/fixture/ca")
        for key in ("GH_TOKEN", "AWS_SECRET_ACCESS_KEY", "LD_PRELOAD"):
            self.assertNotIn(key, env)
        self.assertEqual(env["HOME"], str(self.root / "home"))

    def call_main(self, **changes):
        captured = {}
        values = {"BINARY": self.binary, "BINARY_SHA256": self.hash, "ROOT": self.root, **changes}
        def fake_exec(path, argv, env):
            captured.update(fd=path, inode=os.fstat(path).st_ino, argv=argv, env=env)
            raise RuntimeError("synthetic exec captured")
        output = io.StringIO()
        with patch.multiple(launcher, **values), patch.dict(os.environ, {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}, clear=True), patch.object(launcher.os, "execve", fake_exec), patch.object(launcher.sys, "argv", ["wrapper", "run", "space argument", "--detach"]), contextlib.redirect_stderr(output):
            try:
                result = launcher.main()
            except RuntimeError as error:
                self.assertEqual(str(error), "synthetic exec captured")
                result = None
        return result, captured, output.getvalue()

    def test_argv_passes_through_without_shell(self):
        result, captured, output = self.call_main()
        self.assertIsNone(result)
        self.assertEqual(captured["argv"], [str(self.binary), "run", "space argument", "--detach"])
        self.assertEqual(captured["env"]["HOME"], str(self.root / "home"))
        self.assertEqual(output, "")

    def test_atomic_binary_replacement_executes_verified_inode(self):
        original_inode = self.binary.stat().st_ino
        original_read = launcher.read_credentials
        def replace_then_read(path):
            replacement = self.binary.with_name("replacement")
            replacement.write_bytes(b"\x7fELFchanged file not matching expected hash")
            replacement.replace(self.binary)
            return original_read(path)
        with patch.object(launcher, "read_credentials", replace_then_read):
            result, captured, output = self.call_main()
        self.assertIsNone(result)
        self.assertEqual(captured["inode"], original_inode)
        self.assertNotEqual(self.binary.stat().st_ino, original_inode)
        self.assertEqual(output, "")

    def test_unsafe_binary_mode_not_executed(self):
        self.binary.chmod(0o777)
        result, captured, output = self.call_main()
        self.assertEqual(result, 2)
        self.assertFalse(captured)
        self.assertIn("not group/world-writable", output)

    def test_non_elf_not_executed(self):
        self.binary.write_bytes(b"#!/bin/sh\necho fixture\n")
        result, captured, output = self.call_main(BINARY_SHA256=hashlib.sha256(self.binary.read_bytes()).hexdigest())
        self.assertEqual(result, 2)
        self.assertFalse(captured)
        self.assertIn("Linux ELF", output)

    def test_hash_mismatch_never_reads_credentials_or_executes(self):
        with patch.object(launcher, "read_credentials", side_effect=AssertionError("must not read")):
            result, captured, output = self.call_main(BINARY_SHA256="0" * 64)
        self.assertEqual(result, 2)
        self.assertEqual(captured, {})
        self.assertIn("checksum", output)
        self.assertNotIn("synthetic-not-a-live-token", output)

    def test_missing_config_and_unsafe_runtime_fail_closed(self):
        self.creds.unlink()
        result, captured, output = self.call_main()
        self.assertEqual(result, 2)
        self.assertFalse(captured)
        (self.root / "home").chmod(0o755)
        result, captured, output = self.call_main()
        self.assertEqual(result, 2)
        self.assertIn("0700", output)
        self.assertFalse(captured)

    def test_compile_only(self):
        compile(SOURCE.read_text(), str(SOURCE), "exec")


if __name__ == "__main__":
    unittest.main(verbosity=2)
