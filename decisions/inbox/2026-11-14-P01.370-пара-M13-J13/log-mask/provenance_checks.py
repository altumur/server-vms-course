"""Additional controls after verify.py; reads the exact published module only."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess

B = Path(__file__).resolve().parent
module = json.loads((B / 'MODULES.out').read_text())
repository = '/home/pilot/git/common-modules.git'
commit = 'e19621128ad83f7e50267d58cfe1a2f029e70a28'
files = []
for row in subprocess.check_output(['git', '--git-dir=' + repository, 'ls-tree', '-r', '-z', commit, 'log-mask']).split(b'\0'):
    if not row:
        continue
    meta, path = row.split(b'\t', 1)
    mode, kind, oid = meta.decode().split()
    name = path.decode().removeprefix('log-mask/')
    source = subprocess.check_output(['git', '--git-dir=' + repository, 'cat-file', 'blob', oid])
    actual = (Path(module['Dir']) / name).read_bytes()
    assert actual == source
    files.append({'path': name, 'blob': oid, 'sha256': hashlib.sha256(actual).hexdigest(), 'OK': True})
(B / 'MODULE-BYTE-IDENTITY.json').write_text(json.dumps({'module_commit': commit, 'module_directory': module['Dir'], 'files': files, 'OK': True}, indent=1) + '\n')
negative = B / 'negative.py'
if not negative.exists():
    shutil.copyfile('/home/pilot/obsh75-evidence/scripts/negative.py', negative)
p = subprocess.run(['/home/pilot/venv-spec/bin/python', '-B', str(B / 'vecrun.py'), str(B / 'source'), 'common/log-mask', '/home/pilot/venv-spec/bin/python -B ' + str(negative) + ' {input}', str(B / 'NEGATIVE.json')], capture_output=True)
(B / 'NEGATIVE.out').write_bytes(p.stdout)
(B / 'NEGATIVE.err').write_bytes(p.stderr)
r = json.loads((B / 'NEGATIVE.json').read_text())
assert p.returncode == 1 and r['rows'] == 50 and r['green'] == 0 and len(r['red']) == 50
print(json.dumps({'module_source_identity': True, 'files': len(files), 'negative': {'rows': 50, 'green': 0, 'exit': p.returncode}}))
