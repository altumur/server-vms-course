"""Publish the exact final M11 as a read-only directory and verify its passport."""
from pathlib import Path
import hashlib
import json
import stat
import subprocess
import sys

B = Path(sys.argv[1]).resolve()
I = json.loads((B / 'IDENTITIES.json').read_text())
P = json.loads(Path(I['M_passport']).read_text())
root = Path(sys.argv[2]).resolve() if len(sys.argv) == 3 else B / 'M11'
assert not root.exists(), 'never overwrite an earlier export'
root.mkdir()
producer = subprocess.Popen(['git', '--git-dir', I['M_git'], 'archive', I['M']],
                            stdout=subprocess.PIPE)
consumer = subprocess.run(['tar', '-x', '-C', str(root)], stdin=producer.stdout)
producer.stdout.close()
assert producer.wait() == consumer.returncode == 0
expected = {row['path']: row for row in P['files']}
assert {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()} == expected.keys()
files = []
for relative, row in sorted(expected.items()):
    path = root / relative
    assert stat.S_ISREG(path.lstat().st_mode)
    raw = path.read_bytes()
    assert hashlib.sha1(b'blob %d\0' % len(raw) + raw).hexdigest() == row['blob']
    mode = 0o555 if row['mode'] == '100755' else 0o444
    path.chmod(mode)
    files.append({'path': relative, 'git_mode': row['mode'], 'blob': row['blob'],
                  'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw),
                  'filesystem_mode': oct(mode)})
for path in sorted((p for p in root.rglob('*') if p.is_dir()), reverse=True):
    path.chmod(0o555)
root.chmod(0o555)
assert all(not p.lstat().st_mode & 0o222 for p in (root, *root.rglob('*')))
argv = [sys.executable, '-I', '-B', str(B / 'operator/check_m_passport.py'),
        I['M_passport'], str(root), I['M']]
result = subprocess.run(argv, capture_output=True)
(B / 'M11-PASSPORT.out').write_bytes(result.stdout)
(B / 'M11-PASSPORT.err').write_bytes(result.stderr)
assert result.returncode == 0, result.stderr.decode()
out = {'C': I['C'], 'M': I['M'], 'directory': str(root), 'files_count': len(files),
       'passport': I['M_passport'], 'passport_sha256': I['M_passport_sha256'],
       'passport_check_argv': argv, 'passport_check_exit': result.returncode,
       'all_write_bits_cleared': True, 'exact_paths_blobs_and_executable_modes': True,
       'files': files, 'OK': True}
(B / 'UNPACKED-M11.json').write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n')
print(json.dumps({k: v for k, v in out.items() if k != 'files'}, ensure_ascii=False, indent=1))
