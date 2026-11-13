"""Exact-C archive and unchanged P02.52 operators for P01.355; no delivery."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import time

B, W = (Path(x).resolve() for x in sys.argv[1:3])
C = sys.argv[3]
assert len(C) == 40 and all(x in '0123456789abcdef' for x in C)
assert subprocess.check_output(['git', '-C', str(W), 'rev-parse', 'origin/main']).decode().strip() == C
T = Path('/home/pilot/cammeta-sessions/tasks')
task = (T / 'P01.355.yaml').read_bytes()
assert b'P01.347' in task and b'OBSH.69' in task
B.mkdir()
(B / 'C.txt').write_text(C + '\n')
(B / 'TASK-at-source.yaml').write_bytes(task)
(B / 'reviews').mkdir()
rows = []
for name in ('P01.346', 'P01.347', 'P01.350', 'OBSH.70'):
    raw = (T / 'accepted' / (name + '.json')).read_bytes()
    r = json.loads(raw)
    assert r['status'] == 'accepted', name
    subprocess.run(['git', '-C', str(W), 'merge-base', '--is-ancestor', r['commit'], C], check=True)
    (B / 'reviews' / (name + '-accepted.json')).write_bytes(raw)
    rows.append({'task': name, 'status': r['status'], 'commit': r['commit'], 'utc': r['utc'],
                 'accepted_sha256': hashlib.sha256(raw).hexdigest(), 'ancestor_C': True})
subprocess.run(['git', 'clone', '--bare', '--no-hardlinks', str(W), str(B / 'source.git')], check=True, capture_output=True)
(B / 'archive-C').mkdir()
p = subprocess.Popen(['git', '--git-dir', str(B / 'source.git'), 'archive', C], stdout=subprocess.PIPE)
r = subprocess.run(['tar', '-x', '-C', str(B / 'archive-C')], stdin=p.stdout)
p.stdout.close()
assert p.wait() == r.returncode == 0
(B / 'operator').mkdir()
hashes = {}
originals = {}
for name in ('b7_export_pair.py', 'm_passport.py', 'check_m_passport.py', 'judge_input_export.py',
             'test_b7_export_pair.py', 'test_judge_input_export.py'):
    old = Path('/home/pilot/P01.346-evidence/operator') / name
    new = B / 'operator' / name
    shutil.copyfile(old, new)
    prior = Path('/home/pilot/P01.299-evidence/r2/operator') / name
    assert old.read_bytes() == new.read_bytes() == prior.read_bytes()
    hashes[name] = hashlib.sha256(new.read_bytes()).hexdigest()
    if name in ('b7_export_pair.py', 'judge_input_export.py'):
        original = 'decisions/inbox/2026-11-11-P02.52-операторы/operator/' + name
        canonical = subprocess.check_output(['git', '-C', str(W), 'show', C + ':' + original])
        assert canonical == new.read_bytes(), ('P02.52 operator changed', name)
        originals[name] = {'path': original, 'source_C': C,
                           'sha256': hashes[name], 'byte_equal': True}
(B / 'OPERATOR-UNCHANGED.json').write_text(json.dumps({
    'source': '/home/pilot/P01.346-evidence/operator',
    'also_equal': '/home/pilot/P01.299-evidence/r2/operator', 'files_sha256': hashes,
    'unchanged': True, 'canonical_P02.52': originals}, indent=1) + '\n')
(B / 'scripts').mkdir()
for old in Path(__file__).resolve().parent.glob('*.py'):
    shutil.copyfile(old, B / 'scripts' / old.name)
# OBSH.69 is an Architect task accepted by the owner, without accepted/*.json.
# Bind the exact main commits, rather than manufacture an acceptance receipt.
for revision in ('28f4de46d', '55a672b89', '7e21f987d'):
    commit = subprocess.check_output(['git', '-C', str(W), 'rev-parse', revision]).decode().strip()
    subprocess.run(['git', '-C', str(W), 'merge-base', '--is-ancestor', commit, C], check=True)
    rows.append({'task': 'OBSH.69', 'status': 'on_origin_main', 'commit': commit,
                 'ancestor_C': True, 'acceptance_receipt': None})
for name, revision in (('OBSH.77', '69345c641'), ('OBSH.74', '69e14d0cd')):
    commit = subprocess.check_output(['git', '-C', str(W), 'rev-parse', revision]).decode().strip()
    subprocess.run(['git', '-C', str(W), 'merge-base', '--is-ancestor', commit, C], check=True)
    rows.append({'task': name, 'status': 'on_origin_main', 'commit': commit,
                 'ancestor_C': True, 'acceptance_receipt': None})
(B / 'SOURCE-COMPOSITION.json').write_text(json.dumps({
    'C': C, 'dependencies': rows, 'task_sha256': hashlib.sha256(task).hexdigest(),
    'latest_fetched_main_at_source': C, 'OK': True}, ensure_ascii=False, indent=1) + '\n')
argv = [sys.executable, '-B', 'skills/lesson-spec/scripts/check_spec.py', '--scope', 'platform']
start = time.monotonic()
r = subprocess.run(argv, cwd=B / 'archive-C', capture_output=True)
for ext, raw in [('out', r.stdout), ('err', r.stderr)]:
    (B / ('CHECK-SPEC-C.' + ext)).write_bytes(raw)
(B / 'CHECK-SPEC-C.exit').write_text(str(r.returncode) + '\n')
(B / 'CHECK-SPEC-C.run.json').write_text(json.dumps({
    'argv': argv, 'cwd': str(B / 'archive-C'), 'C': C, 'exit': r.returncode,
    'seconds': time.monotonic() - start,
    'roster_check': 'filesystem roster checked on exact-C archive; OBSH.69 present at C'}, indent=1) + '\n')
assert r.returncode == 0
for name, args in [('PREFLIGHT', ['preflight.py', C, str(B / 'source.git')]),
                   ('FILTER-DELTA', ['filter_delta.py', '431c32debbc1bb35e57e4dfa323f8f091335172a', C, str(B / 'source.git')])]:
    argv = [sys.executable, '-B', str(B / 'scripts' / args[0]), *args[1:]]
    r = subprocess.run(argv, capture_output=True)
    (B / (name + '.json')).write_bytes(r.stdout)
    (B / (name + '.err')).write_bytes(r.stderr)
    (B / (name + '.run.json')).write_text(json.dumps({'argv': argv, 'exit': r.returncode}, indent=1) + '\n')
    assert r.returncode == 0, (name, r.stderr.decode())
print(json.dumps({'C': C, 'evidence': str(B), 'check_exit': 0, 'preflight_exit': 0}, indent=1))
