#!/usr/bin/env python3
"""Synthetic fixtures only; no production DB, credential, or queue access."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import patch

SCRIPT = Path(__file__).with_name('runtime_snapshot.py')

class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='snapshot-fixture-')
        self.base = Path(self.temp.name)
        self.script = SCRIPT
        self.root = self.base / 'runtime'
        self.root.mkdir(mode=0o700)
        for g in ('requests','replies','tasks','outputs'):
            (self.root / 'spool' / g).mkdir(parents=True, mode=0o700)
        os.chmod(self.root / 'spool', 0o700)
        db = sqlite3.connect(self.root / 'opencode.db')
        db.execute('CREATE TABLE history (id INTEGER PRIMARY KEY, content TEXT)')
        db.execute("INSERT INTO history VALUES (1, 'synthetic-private-payload')")
        db.execute('PRAGMA user_version=17')
        db.commit(); db.close()
        os.chmod(self.root / 'opencode.db', 0o600)
        self.put('tasks/job1.json', {'version':1,'id':'job1','state':'completed','starts':1,'input':{'message':'synthetic'}})
        self.put('outputs/job1.json', {'stdout':'synthetic-result','stderr':''})
        self.put('requests/req1.json', {'id':'req1','command':{'op':'run','message':'synthetic'}})
        self.put('replies/req1.json', {'id':'req1','state':'completed'})
        self.launcher = self.base / 'start-sharing'
        self.launcher.write_text('# synthetic non-secret launcher\n'); self.launcher.chmod(0o700)
        self.zip = self.base / 'backup.zip'

    def tearDown(self):
        self.temp.cleanup()

    def put(self, rel, data):
        p = self.root / 'spool' / rel
        p.write_text(json.dumps(data)); p.chmod(0o600)

    def run_cli(self, *args, success=True):
        r = subprocess.run([sys.executable, str(self.script), *map(str,args)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0 if success else 2, r.stderr + r.stdout)
        self.assertNotIn('synthetic-private-payload', r.stdout + r.stderr)
        self.assertNotIn('synthetic-result', r.stdout + r.stderr)
        return r

    def backup(self, success=True, assertion=True):
        args = ['create','--root',self.root,'--launcher',self.launcher,'--output',self.zip,
                '--source-sha','a'*40,'--binary-sha256','b'*64,'--version','0.0.0-test','--workspace',self.base]
        if assertion: args += ['--owner-stopped-in-owning-terminal']
        return self.run_cli(*args, success=success)

    def restore(self, path=None, destination=None, success=True, sha=None):
        path = path or self.zip
        return self.run_cli('restore','--archive',path,'--sha256',sha or hashlib.sha256(path.read_bytes()).hexdigest(),
                            '--destination', destination or self.base / 'restored', success=success)

    def test_roundtrip_and_no_overwrite(self):
        self.backup()
        self.assertEqual(stat.S_IMODE(self.zip.stat().st_mode),0o600)
        self.restore()
        out = self.base / 'restored'
        self.assertTrue((out / 'RESTORE_REVIEW_REQUIRED').exists())
        self.assertFalse((out / 'spool').exists())
        self.assertTrue((out / 'quarantine/spool/tasks/job1.json').exists())
        con = sqlite3.connect(out / 'opencode.db')
        self.assertEqual(con.execute('SELECT content FROM history').fetchone(), ('synthetic-private-payload',))
        self.assertEqual(con.execute('PRAGMA integrity_check').fetchone(), ('ok',)); con.close()
        self.backup(success=False)
        self.restore(success=False)
        self.assertEqual((out / 'quarantine/spool/outputs/job1.json').read_text(), (self.root / 'spool/outputs/job1.json').read_text())

    def limited_script(self, *, byte_limit=None, file_limit=None):
        text = SCRIPT.read_text()
        if byte_limit is not None:
            text = text.replace('LIMIT = 1024**3', f'LIMIT = {byte_limit}')
        if file_limit is not None:
            text = text.replace('MAX_FILES = 100000', f'MAX_FILES = {file_limit}')
        self.script = self.base / 'limited_snapshot.py'
        self.script.write_text(text)

    def test_launcher_counts_toward_file_limit(self):
        # Five data files, plus the launcher: the sixth file must count.
        self.limited_script(file_limit=5)
        self.backup(success=False)
        self.assertFalse(self.zip.exists())

    def test_launcher_counts_toward_byte_limit(self):
        data_size = sum(p.stat().st_size for p in self.root.rglob('*') if p.is_file())
        self.limited_script(byte_limit=data_size + self.launcher.stat().st_size - 1)
        self.backup(success=False)
        self.assertFalse(self.zip.exists())

    def test_zip_overhead_refused_before_publication(self):
        data_size = sum(p.stat().st_size for p in self.root.rglob('*') if p.is_file())
        self.limited_script(byte_limit=data_size + self.launcher.stat().st_size + 64)
        self.backup(success=False)
        self.assertFalse(self.zip.exists())

    def test_interrupted_restore_keeps_startup_block(self):
        self.backup()
        spec = importlib.util.spec_from_file_location('snapshot_fixture_module', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        original_rename = module.os.rename
        destination = self.base / 'interrupted'
        def interrupt_after_database(source, target):
            original_rename(source, target)
            if Path(target).name == 'opencode.db':
                raise OSError('synthetic publication interruption')
        from types import SimpleNamespace
        args = SimpleNamespace(archive=str(self.zip), destination=str(destination),
                               sha256=hashlib.sha256(self.zip.read_bytes()).hexdigest())
        with patch.object(module.os, 'rename', interrupt_after_database), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(module.Refused):
                module.restore(args)
        self.assertTrue((destination / 'opencode.db').exists())
        self.assertTrue((destination / 'RESTORE_REVIEW_REQUIRED').is_file())
        self.assertFalse((destination / 'spool').exists())

    def test_missing_assertion(self):
        self.backup(success=False, assertion=False)
        self.assertFalse(self.zip.exists())

    def test_active_owner_unknown_and_recover(self):
        for name in ('worker.lock','.owner','.recover','unexpected'):
            p=self.root/'spool'/name; p.mkdir(mode=0o700)
            self.backup(success=False); p.rmdir()
        self.assertFalse(self.zip.exists())

    def test_wal_shm_journal_and_review_block(self):
        for name in ('opencode.db-wal','opencode.db-shm','opencode.db-journal','RESTORE_REVIEW_REQUIRED'):
            p=self.root/name; p.touch(mode=0o600)
            self.backup(success=False); p.unlink()

    def test_nonterminal_and_invalid_task(self):
        for state in ('queued','running','cancelling','unknown'):
            self.put('tasks/job1.json',{'version':1,'id':'job1','state':state})
            self.backup(success=False)

    def test_indeterminate_quarantined(self):
        self.put('tasks/job1.json',{'version':1,'id':'job1','state':'indeterminate'})
        self.backup(); self.restore()
        self.assertFalse((self.base/'restored/spool').exists())

    def test_symlink_hardlink_and_insecure_mode(self):
        p=self.root/'spool/outputs/link.json'; p.symlink_to(self.launcher)
        self.backup(success=False); p.unlink()
        os.link(self.root/'spool/outputs/job1.json',p)
        self.backup(success=False); p.unlink()
        self.launcher.chmod(0o644); self.backup(success=False)

    def test_bad_archive_sha_and_corrupt_db(self):
        self.backup(); self.restore(success=False,sha='0'*64)
        self.zip.unlink()
        (self.root/'opencode.db').write_bytes(b'not SQLite')
        self.backup(success=False)

    def rewrite(self, mode):
        bad=self.base/'bad.zip'
        with zipfile.ZipFile(self.zip) as src, zipfile.ZipFile(bad,'w') as dst:
            for item in src.infolist():
                raw=src.read(item.filename)
                if mode=='corrupt' and item.filename=='database/opencode.db': raw=b'X'+raw[1:]
                if mode=='version' and item.filename=='manifest.json':
                    m=json.loads(raw);m['format']='unknown';raw=json.dumps(m).encode()
                dst.writestr(item,raw)
            if mode=='traversal': dst.writestr('../escape','no')
            if mode=='absolute': dst.writestr('/tmp/escape','no')
            if mode=='owner': dst.writestr('queue/worker.lock/owner.json','{}')
            if mode=='duplicate': dst.writestr('manifest.json','{}')
            if mode=='symlink':
                z=zipfile.ZipInfo('queue/outputs/link.json');z.create_system=3;z.external_attr=(stat.S_IFLNK|0o777)<<16
                dst.writestr(z,'../../outside')
            if mode=='compressed': dst.writestr('queue/outputs/zipbomb.json','x'*1000000,compress_type=zipfile.ZIP_DEFLATED)
        bad.chmod(0o600)
        return bad

    def test_malicious_and_corrupt_archives(self):
        self.backup()
        for mode in ('traversal','absolute','owner','duplicate','symlink','compressed','version','corrupt'):
            with self.subTest(mode=mode):
                p=self.rewrite(mode);self.restore(path=p,success=False);p.unlink()
                self.assertFalse((self.base/'restored').exists())

    def test_excluded_files_not_archived(self):
        for name in ('credentials.env','secret.log','opencode2-node','font.ttf'):
            p=self.root/name;p.write_text('synthetic-excluded');p.chmod(0o600)
        self.backup()
        with zipfile.ZipFile(self.zip) as z:
            self.assertEqual(set(z.namelist()), {'manifest.json','database/opencode.db','launcher/start-sharing',
                'queue/requests/req1.json','queue/replies/req1.json','queue/tasks/job1.json','queue/outputs/job1.json'})

if __name__=='__main__':
    unittest.main()
