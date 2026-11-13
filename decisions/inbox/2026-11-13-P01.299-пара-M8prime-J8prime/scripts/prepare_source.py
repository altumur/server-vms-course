"""Prepare a fresh exact-C source and unchanged operators after accepted P01.323.

Usage: spec-python -B prepare_source.py <new evidence directory> <own worktree> <C>
This does not emit an export, choose a pin, deliver or run a candidate.
"""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import time

B, W = (Path(x).resolve() for x in sys.argv[1:3])
C = sys.argv[3]
assert len(C) == 40 and all(x in "0123456789abcdef" for x in C)
receipt = json.loads(Path('/home/pilot/cammeta-sessions/tasks/accepted/P01.323.json').read_text())
assert receipt['status'] == 'accepted'
subprocess.run(['git', '-C', str(W), 'merge-base', '--is-ancestor', receipt['commit'], C], check=True)
B.mkdir()
(B / 'C.txt').write_text(C + '\n')
subprocess.run(['git', 'clone', '--bare', '--no-hardlinks', str(W), str(B / 'source.git')], check=True, capture_output=True)
(B / 'archive-C').mkdir()
producer = subprocess.Popen(['git', '--git-dir', str(B / 'source.git'), 'archive', C], stdout=subprocess.PIPE)
consumer = subprocess.run(['tar', '-x', '-C', str(B / 'archive-C')], stdin=producer.stdout)
producer.stdout.close()
assert producer.wait() == consumer.returncode == 0
(B / 'operator').mkdir()
hashes = {}
for name in ('b7_export_pair.py', 'm_passport.py', 'check_m_passport.py', 'judge_input_export.py',
             'test_b7_export_pair.py', 'test_judge_input_export.py'):
    original = Path('/home/pilot/P01.277-evidence/operator') / name
    target = B / 'operator' / name
    shutil.copyfile(original, target)
    assert original.read_bytes() == target.read_bytes()
    hashes[name] = hashlib.sha256(target.read_bytes()).hexdigest()
(B / 'OPERATOR-UNCHANGED.json').write_text(json.dumps({'source': '/home/pilot/P01.277-evidence/operator',
    'files_sha256': hashes, 'unchanged': True}, indent=1) + '\n')
(B / 'scripts').mkdir()
for original in Path(__file__).resolve().parent.glob('*.py'):
    shutil.copyfile(original, B / 'scripts' / original.name)
(B / 'reviews').mkdir()
for task in ('P01.294', 'P01.323'):
    shutil.copyfile(Path('/home/pilot/cammeta-sessions/tasks/accepted') / (task + '.json'),
                    B / 'reviews' / (task + '-accepted.json'))
shutil.copyfile('/home/pilot/cammeta-sessions/tasks/P01.299.yaml', B / 'TASK-at-source.yaml')
argv = [sys.executable, '-B', 'skills/lesson-spec/scripts/check_spec.py', '--scope', 'platform']
start = time.monotonic()
result = subprocess.run(argv, cwd=B / 'archive-C', capture_output=True)
(B / 'CHECK-SPEC-C.out').write_bytes(result.stdout)
(B / 'CHECK-SPEC-C.err').write_bytes(result.stderr)
(B / 'CHECK-SPEC-C.exit').write_text(str(result.returncode) + '\n')
(B / 'CHECK-SPEC-C.run.json').write_text(json.dumps({'argv': argv, 'cwd': str(B / 'archive-C'), 'C': C,
    'exit': result.returncode, 'seconds': time.monotonic() - start}, indent=1) + '\n')
assert result.returncode == 0
for name, args in (
    ('PREFLIGHT', ['preflight.py', C, str(B / 'source.git')]),
    ('FILTER-DELTA', ['filter_delta.py', '70c969fe200a8d785a8b86f698f938d24310cf2c', C, str(B / 'source.git')]),
):
    argv = [sys.executable, '-B', str(B / 'scripts' / args[0]), *args[1:]]
    result = subprocess.run(argv, capture_output=True)
    (B / (name + '.json')).write_bytes(result.stdout)
    (B / (name + '.err')).write_bytes(result.stderr)
    (B / (name + '.run.json')).write_text(json.dumps({'argv': argv, 'exit': result.returncode}, indent=1) + '\n')
    assert result.returncode == 0
print(json.dumps({'C': C, 'evidence': str(B), 'check_exit': 0, 'preflight_exit': 0}, indent=1))
