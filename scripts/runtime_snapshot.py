#!/usr/bin/env python3
"""Offline-only sensitive local snapshots. No encryption, upload, owner takeover or replay."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sqlite3
import stat
import sys
import tempfile
import time
import zipfile

FORMAT = 'opencode-offline-runtime-v1'
PROTOCOL = 'files-v1-requests-replies-tasks-outputs'
GROUPS = ('requests', 'replies', 'tasks', 'outputs')
STATES = {'completed', 'failed', 'cancelled', 'indeterminate'}
LIMIT = 1024**3
MAX_FILES = 100000
ID = r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}'

class Refused(Exception):
    pass

def require(ok, message):
    if not ok:
        raise Refused(message)

def private_dir(p):
    s = p.lstat()
    require(p.is_absolute() and p.resolve() == p and stat.S_ISDIR(s.st_mode)
            and s.st_uid == os.getuid() and not s.st_mode & 0o077,
            'Expected an owned private canonical directory')

def checked(p, maximum=LIMIT):
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    f = os.fdopen(fd, 'rb')
    s = os.fstat(fd)
    if not (stat.S_ISREG(s.st_mode) and s.st_uid == os.getuid()
            and not s.st_mode & 0o077 and s.st_nlink == 1 and s.st_size <= maximum):
        f.close()
        raise Refused('Expected a bounded owned private regular file, without links')
    return f

def digest(p):
    with checked(p) as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def safe_json(p, limit=65536):
    with checked(p, limit) as f:
        return json.load(f)

def unchanged_signature(p):
    s = p.lstat()
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)

def allowed(name):
    if name in ('database/opencode.db', 'launcher/start-sharing'):
        return True
    return re.fullmatch(r'queue/(requests|replies|tasks|outputs)/' + ID + r'\.json', name) is not None

def inspect_root(root):
    private_dir(root)
    spool = root / 'spool'
    private_dir(spool)
    # Any unexpected entry is a fail-closed protocol mismatch, including all lock/recover files.
    require(set(x.name for x in spool.iterdir()) == set(GROUPS),
            'Spool is owned, recovering, or has an unrecognized layout; use the owning terminal')
    for name in ('worker.lock', '.owner', '.recover', 'RESTORE_REVIEW_REQUIRED',
                 'opencode.db-wal', 'opencode.db-shm', 'opencode.db-journal'):
        require(not os.path.lexists(root / name),
                'Runtime has owner/recovery/journal state; do not remove it for backup')
    entries = {'database/opencode.db': root / 'opencode.db'}
    counts = {s: 0 for s in sorted(STATES)}
    for group in GROUPS:
        folder = spool / group
        private_dir(folder)
        for p in sorted(folder.iterdir()):
            name = 'queue/' + group + '/' + p.name
            require(allowed(name), 'Unrecognized spool entry; review the current source protocol')
            with checked(p, 1024*1024 if group == 'outputs' else 65536):
                pass
            if group == 'tasks':
                task = safe_json(p)
                require(isinstance(task, dict) and task.get('version') == 1
                        and task.get('id') == p.stem and task.get('state') in STATES,
                        'Nonterminal or invalid task; wait for jobs in the owning terminal')
                counts[task['state']] += 1
            entries[name] = p
    with checked(entries['database/opencode.db']):
        pass
    require(len(entries) <= MAX_FILES, 'Too many snapshot files')
    require(sum(x.stat().st_size for x in entries.values()) <= LIMIT, 'Snapshot exceeds byte limit')
    return entries, counts

def db_metadata(p):
    # Only schema metadata and integrity checks, never user rows or credentials.
    con = sqlite3.connect(p.as_uri() + '?mode=ro&immutable=1', uri=True)
    try:
        require(con.execute('PRAGMA integrity_check').fetchall() == [('ok',)], 'Snapshot integrity check failed')
        schema = con.execute('SELECT type, name, tbl_name, sql FROM sqlite_schema ORDER BY type, name').fetchall()
        return {'user_version': con.execute('PRAGMA user_version').fetchone()[0],
                'schema_sha256': hashlib.sha256(json.dumps(schema, ensure_ascii=True).encode()).hexdigest(),
                'table_count': sum(row[0] == 'table' for row in schema)}
    finally:
        con.close()

def copy_private(src, dest):
    dest.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with checked(src) as f, dest.open('xb') as g:
        os.chmod(dest, 0o600)
        shutil.copyfileobj(f, g, 1024*1024)

def create(args):
    require(args.owner_stopped_in_owning_terminal,
            'First verify orderly owner exit and stop all writers in the actual owning execution')
    root, output, launcher = map(Path, (args.root, args.output, args.launcher))
    private_dir(output.parent)
    require(output.is_absolute() and not os.path.lexists(output), 'Output already exists or is not absolute')
    require(not output.is_relative_to(root), 'Keep backup staging outside the runtime')
    require(re.fullmatch('[0-9a-f]{40}', args.source_sha) is not None, 'Use the verified full source SHA')
    require(re.fullmatch('[0-9a-f]{64}', args.binary_sha256) is not None, 'Use the verified binary checksum')
    require(re.fullmatch(r'[A-Za-z0-9._+-]{1,160}', args.version) is not None, 'Use the verified version')
    require(Path(args.workspace).is_absolute(), 'Use the canonical workspace path')
    before, counts = inspect_root(root)
    with checked(launcher, 1024*1024):
        pass
    before['launcher/start-sharing'] = launcher
    require(len(before) <= MAX_FILES, 'Too many snapshot files including launcher')
    require(sum(x.stat().st_size for x in before.values()) <= LIMIT,
            'Snapshot including launcher exceeds byte limit')
    signatures = {name: unchanged_signature(p) for name, p in before.items()}
    with tempfile.TemporaryDirectory(prefix='.snapshot-', dir=output.parent) as temp:
        staging = Path(temp)
        database = staging / 'database/opencode.db'
        database.parent.mkdir(mode=0o700)
        src = sqlite3.connect(before['database/opencode.db'].as_uri() + '?mode=ro&immutable=1', uri=True)
        dest = sqlite3.connect(database)
        try:
            src.backup(dest)
        finally:
            dest.close()
            src.close()
        os.chmod(database, 0o600)
        meta = db_metadata(database)
        for name, source in before.items():
            if name != 'database/opencode.db':
                copy_private(source, staging / name)
        after, after_counts = inspect_root(root)
        after['launcher/start-sharing'] = launcher
        require(set(before) == set(after) and counts == after_counts and all(
            signatures[name] == unchanged_signature(after[name]) for name in before),
            'A writer changed the runtime during the snapshot; stop and investigate')
        files = {name: {'size': (staging / name).stat().st_size, 'sha256': digest(staging / name)}
                 for name in sorted(before)}
        manifest = {'format': FORMAT, 'protocol': PROTOCOL, 'created_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                    'source_sha': args.source_sha, 'binary_version': args.version,
                    'binary_sha256': args.binary_sha256, 'workspace': args.workspace,
                    'database': meta, 'task_counts': counts, 'files': files}
        manifest_bytes = (json.dumps(manifest, indent=2) + '\n').encode()
        require(len(manifest_bytes) <= 16*1024**2, 'Snapshot manifest exceeds byte limit')
        archive = staging / 'snapshot.zip'
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_STORED) as z:
            z.writestr('manifest.json', manifest_bytes)
            for name in files:
                z.write(staging / name, name)
        os.chmod(archive, 0o600)
        require(archive.stat().st_size <= LIMIT, 'Archive including ZIP overhead exceeds byte limit')
        with zipfile.ZipFile(archive) as z:
            validate_archive(z)
        # Atomic no-overwrite publication on the same filesystem; no live files are modified.
        os.link(archive, output)
    print(json.dumps({'local_sensitive_archive': str(output), 'sha256': digest(output),
                      'files': len(files), 'task_counts': counts, 'encrypted': False}))

def validate_archive(z):
    infos = z.infolist()
    require(0 < len(infos) <= MAX_FILES + 1, 'Invalid archive entry count')
    names = [x.filename for x in infos]
    require(len(names) == len(set(names)), 'Duplicate archive paths')
    require('manifest.json' in names and set(names) >= {'database/opencode.db', 'launcher/start-sharing'},
            'Missing snapshot components')
    require(sum(i.file_size for i in infos) <= LIMIT + 16*1024**2, 'Archive exceeds byte limit')
    for info in infos:
        name = info.filename
        require((name == 'manifest.json' or allowed(name)) and not info.is_dir()
                and PurePosixPath(name).as_posix() == name and '\\' not in name,
                'Unsafe or unrecognized archive path')
        mode = info.external_attr >> 16
        require(stat.S_IFMT(mode) in (0, stat.S_IFREG), 'Archive contains a link or special entry')
        require(info.compress_type == zipfile.ZIP_STORED and not info.flag_bits & 1,
                'Expected an uncompressed local snapshot; decrypt GPG first')
        require(not info.extra, 'Unsupported archive extension')
    require(z.getinfo('manifest.json').file_size <= 16*1024**2, 'Oversized manifest')
    manifest = json.loads(z.read('manifest.json'))
    require(manifest.get('format') == FORMAT and manifest.get('protocol') == PROTOCOL,
            'Unsupported archive schema or spool protocol')
    require(isinstance(manifest.get('files'), dict) and set(manifest['files']) == set(names) - {'manifest.json'},
            'Manifest entry mismatch')
    require(re.fullmatch('[0-9a-f]{40}', str(manifest.get('source_sha'))) is not None
            and re.fullmatch('[0-9a-f]{64}', str(manifest.get('binary_sha256'))) is not None,
            'Invalid source provenance metadata')
    for name, meta in manifest['files'].items():
        require(isinstance(meta, dict) and meta.get('size') == z.getinfo(name).file_size
                and re.fullmatch('[0-9a-f]{64}', str(meta.get('sha256'))) is not None,
                'Invalid file metadata')
    return manifest

def restore(args):
    archive, destination = Path(args.archive), Path(args.destination)
    private_dir(destination.parent)
    require(destination.is_absolute() and not os.path.lexists(destination), 'Restore destination must be new')
    require(re.fullmatch('[0-9a-f]{64}', args.sha256) is not None and digest(archive) == args.sha256,
            'Archive checksum mismatch')
    with checked(archive) as raw, zipfile.ZipFile(raw) as z:
        manifest = validate_archive(z)
        with tempfile.TemporaryDirectory(prefix='.restore-', dir=destination.parent) as temp:
            staging = Path(temp) / 'runtime'
            staging.mkdir(mode=0o700)
            for name, meta in manifest['files'].items():
                if name == 'database/opencode.db':
                    target = staging / 'opencode.db'
                elif name == 'launcher/start-sharing':
                    target = staging / 'reference-start-sharing.py'
                else:
                    target = staging / 'quarantine/spool' / name.removeprefix('queue/')
                target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                with z.open(name) as source, target.open('xb') as out:
                    os.chmod(target, 0o600)
                    remaining = meta['size']
                    while remaining:
                        chunk = source.read(min(1024*1024, remaining))
                        require(bool(chunk), 'Truncated archive data')
                        out.write(chunk)
                        remaining -= len(chunk)
                    require(not source.read(1), 'Archive size mismatch')
                require(digest(target) == meta['sha256'], 'Restored file checksum mismatch')
            require(db_metadata(staging / 'opencode.db') == manifest.get('database'), 'Database schema/version mismatch')
            for group in GROUPS:
                (staging / 'quarantine/spool' / group).mkdir(parents=True, exist_ok=True, mode=0o700)
            (staging / 'RESTORE_REVIEW_REQUIRED').write_text(
                'Do not start automatically. Rebuild the recorded source; review DB credentials, schema, workspace mapping and quarantined tasks. Never replay requests blindly.\n')
            (staging / 'snapshot-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
            # mkdir is the no-overwrite claim. Never rename over an existing directory.
            destination.mkdir(mode=0o700)
            try:
                # Establish the startup block before publishing the credential-bearing DB.
                marker = staging / 'RESTORE_REVIEW_REQUIRED'
                os.rename(marker, destination / marker.name)
                for child in staging.iterdir():
                    os.rename(child, destination / child.name)
            except Exception:
                # Preserve a partial destination for inspection; do not remove unrelated data.
                raise Refused('Restore publication incomplete; preserve and inspect the new destination') from None
    print(json.dumps({'restored_private_directory': str(destination), 'integrity_check': 'ok',
                      'queue': 'quarantined', 'startup': 'blocked_pending_review'}))

def main():
    os.umask(0o077)
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    c = sub.add_parser('create')
    for name in ('root', 'launcher', 'output', 'source-sha', 'binary-sha256', 'version', 'workspace'):
        c.add_argument('--' + name, required=True)
    c.add_argument('--owner-stopped-in-owning-terminal', action='store_true')
    r = sub.add_parser('restore')
    for name in ('archive', 'sha256', 'destination'):
        r.add_argument('--' + name, required=True)
    args = p.parse_args()
    try:
        (create if args.command == 'create' else restore)(args)
    except Refused as e:
        print('Snapshot refused: ' + str(e), file=sys.stderr)
        return 2
    except Exception:
        # Never leak a DB error, row, task payload, credential, or malformed file content.
        print('Snapshot failed safely; inspect only non-secret metadata and preserve the source.', file=sys.stderr)
        return 2
    return 0

if __name__ == '__main__':
    sys.exit(main())
