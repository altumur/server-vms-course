"""Prepare a fresh P05.18 exact-C snapshot and unchanged accepted operators.

Call from the task worktree with spec Python: prepare_source.py <new-evidence-dir>.
The script refuses an existing evidence directory and retains every failed output.
"""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

W = Path.cwd()
B = Path(sys.argv[1]).resolve()
R = Path(__file__).resolve().parent
C = subprocess.check_output(['git', 'rev-parse', 'origin/main'], text=True).strip()
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip() == C
B.mkdir()
for name in ('scripts', 'operator', 'reviews'):
    (B / name).mkdir()
(B / 'C.txt').write_text(C + '\n')
(B / 'TASK-at-source.yaml').write_bytes(Path('/home/pilot/cammeta-sessions/tasks/P05.18.yaml').read_bytes())
for path in R.glob('*.py'):
    (B / 'scripts' / path.name).write_bytes(path.read_bytes())
operators = {}
for name in ('b7_export_pair.py', 'judge_input_export.py', 'm_passport.py', 'check_m_passport.py'):
    old = Path('/home/pilot/P04.43-evidence/operator') / name
    raw = old.read_bytes()
    if name in ('b7_export_pair.py', 'judge_input_export.py'):
        assert raw == subprocess.check_output(['git', 'show', C + ':decisions/inbox/2026-11-11-P02.52-операторы/operator/' + name])
    (B / 'operator' / name).write_bytes(raw)
    operators[name] = {'sha256': hashlib.sha256(raw).hexdigest(), 'source': str(old), 'byte_equal_accepted_P04_43': True}
(B / 'OPERATOR-UNCHANGED.json').write_text(json.dumps(operators, indent=2) + '\n')
with (B / 'CLONE.out').open('wb') as out, (B / 'CLONE.err').open('wb') as err:
    subprocess.run(['git', 'clone', '--bare', '--no-hardlinks', str(W), str(B / 'source.git')], stdout=out, stderr=err, check=True)
(B / 'archive-C').mkdir()
p = subprocess.Popen(['git', 'archive', C], stdout=subprocess.PIPE)
r = subprocess.run(['tar', '-x', '-C', str(B / 'archive-C')], stdin=p.stdout)
p.stdout.close()
assert p.wait() == r.returncode == 0
for name, args in (
    ('PREFLIGHT', [C, str(B / 'source.git')]),
    ('FILTER-DELTA', [Path('/home/pilot/P04.43-evidence/C.txt').read_text().strip(), C, str(B / 'source.git')]),
):
    script = 'preflight.py' if name == 'PREFLIGHT' else 'filter_delta.py'
    r = subprocess.run([sys.executable, '-B', str(B / 'scripts' / script), *args], capture_output=True)
    (B / (name + '.json')).write_bytes(r.stdout)
    (B / (name + '.err')).write_bytes(r.stderr)
    assert r.returncode == 0, (name, r.stderr.decode())
print(json.dumps({'C': C, 'evidence': str(B), 'preflight': 'pass'}))
