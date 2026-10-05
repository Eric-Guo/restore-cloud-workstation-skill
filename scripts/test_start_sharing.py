#!/usr/bin/env python3
"""Run launcher against inert fake wrapper/binary; no credentials or model calls."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

TEMPLATE=Path(__file__).with_name('start_sharing_template.py')

class SharingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='sharing-fixture-')
        self.base=Path(self.temp.name);self.root=self.base/'runtime'
        self.wrapper=self.base/'wrapper.py'
        self.wrapper.write_text('''def read_credentials(path):
    assert path.name == "credentials.env"
    return {"FAKE_FROM_MEMORY": "fake-only"}
def environment(parent, credentials, root):
    assert parent.get("OPENCODE_CONFIG_CONTENT") == "synthetic-default"
    return {"PATH": "/usr/bin:/bin", "HOME": str(root/"home"), **credentials}
''');self.wrapper.chmod(0o700)
        self.binary=self.base/'binary'
        self.binary.write_text('#!/usr/bin/python3\nimport json,os,sys\nprint(json.dumps({"args":sys.argv[1:],"cwd":os.getcwd(),"db":os.environ.get("OPENCODE_DB"),"fake":os.environ.get("FAKE_FROM_MEMORY")}))\n')
        self.binary.chmod(0o700)
        s=TEMPLATE.read_text().replace('/REPLACE_WITH_PRIVATE_SHARING_ROOT',str(self.root)).replace('/REPLACE_WITH_CANONICAL_WORKSPACE',str(self.base))
        s=s.replace('/REPLACE_WITH_REVIEWED_PRIVATE_WRAPPER',str(self.wrapper)).replace('/REPLACE_WITH_VERIFIED_BINARY',str(self.binary))
        s=s.replace('REPLACE_WITH_40_HEX_SOURCE_SHA','a'*40).replace('REPLACE_WITH_VERIFIED_VERSION','0.0.0-test')
        s=s.replace('REPLACE_WITH_WRAPPER_64_HEX_SHA256',hashlib.sha256(self.wrapper.read_bytes()).hexdigest()).replace('REPLACE_WITH_BINARY_64_HEX_SHA256',hashlib.sha256(self.binary.read_bytes()).hexdigest())
        self.launcher=self.base/'start-sharing';self.launcher.write_text(s);self.launcher.chmod(0o700)

    def tearDown(self): self.temp.cleanup()
    def run_launcher(self,*args):
        return subprocess.run([sys.executable,str(self.launcher),*args],env={'PATH':'/usr/bin:/bin','OPENCODE_CONFIG_CONTENT':'synthetic-default'},capture_output=True,text=True)
    def test_foreground_arguments_and_persistence(self):
        r=self.run_launcher();self.assertEqual(r.returncode,0,r.stderr)
        data=json.loads(r.stdout.splitlines()[-1])
        self.assertEqual(data['args'],['serve','--hostname','127.0.0.1','--port','0','--workspace-sharing',str(self.root/'spool')])
        self.assertEqual(data['cwd'],str(self.base));self.assertEqual(data['db'],str(self.root/'opencode.db'))
        self.assertEqual(data['fake'],'fake-only');self.assertFalse((self.base/'credentials.env').exists())
        self.assertEqual(self.run_launcher().returncode,0)
    def test_changed_binary_and_wrapper_refused(self):
        for p in (self.binary,self.wrapper):
            original=p.read_text();p.write_text(original+'\n# changed\n')
            self.assertEqual(self.run_launcher().returncode,2);p.write_text(original)
    def test_atomic_binary_replacement_executes_verified_inode(self):
        old_hash=hashlib.sha256(self.wrapper.read_bytes()).hexdigest()
        modified=self.wrapper.read_text().replace(
            '    assert path.name == "credentials.env"',
            '    assert path.name == "credentials.env"\n'
            '    import os\n    from pathlib import Path\n'
            '    replacement = path.parent / "replacement"\n'
            '    replacement.write_text("#!/usr/bin/python3\\nprint(\\\"UNVERIFIED\\\")\\n")\n'
            '    replacement.chmod(0o700)\n'
            '    os.replace(replacement, path.parent / "binary")')
        self.wrapper.write_text(modified)
        new_hash=hashlib.sha256(self.wrapper.read_bytes()).hexdigest()
        self.launcher.write_text(self.launcher.read_text().replace(old_hash,new_hash))
        r=self.run_launcher();self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn('UNVERIFIED',self.binary.read_text())
        self.assertNotIn('UNVERIFIED',r.stdout)
        self.assertEqual(json.loads(r.stdout.splitlines()[-1])['fake'],'fake-only')
    def test_existing_owner_and_restore_review_refused(self):
        self.root.mkdir(mode=0o700);(self.root/'spool').mkdir(mode=0o700)
        for name in ('worker.lock','.owner','.recover'):
            p=self.root/'spool'/name;p.mkdir(mode=0o700)
            self.assertEqual(self.run_launcher().returncode,2);p.rmdir()
        (self.root/'RESTORE_REVIEW_REQUIRED').touch(mode=0o600)
        self.assertEqual(self.run_launcher().returncode,2)
    def test_dangling_owner_and_review_markers_refused(self):
        self.root.mkdir(mode=0o700);(self.root/'spool').mkdir(mode=0o700)
        for p in [self.root/'RESTORE_REVIEW_REQUIRED', *[self.root/'spool'/n for n in ('worker.lock','.owner','.recover')]]:
            p.symlink_to(self.base/'missing-marker-target')
            self.assertEqual(self.run_launcher().returncode,2)
            p.unlink()

    def test_help_does_not_read_or_start(self):
        self.wrapper.unlink();self.binary.unlink()
        r=self.run_launcher('--help');self.assertEqual(r.returncode,0)
        self.assertFalse(self.root.exists())
        self.assertEqual(self.run_launcher('unexpected').returncode,2)

if __name__=='__main__':unittest.main()
