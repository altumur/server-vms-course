"""Build J-input, verify all payloads, and compare M against accepted P04.37."""
from pathlib import Path
import csv
import hashlib
import io
import json
import stat
import subprocess
import sys
import time

B = Path(sys.argv[1]).resolve()
C = (B / 'C.txt').read_text().strip()
prior = Path('/home/pilot/P04.37-evidence')
sys.path.insert(0, str(B / 'operator'))
import b7_export_pair as operator
import judge_input_export as ji


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(name, value):
    (B / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def git(repo, *args):
    return subprocess.check_output(['git', '--git-dir', str(repo), *args])


def tree(repo, commit):
    out = {}
    for row in git(repo, 'ls-tree', '-rz', commit).split(b'\0'):
        if row:
            header, path = row.split(b'\t', 1)
            mode, kind, oid = header.decode().split()
            assert kind == 'blob' and mode in ('100644', '100755')
            out[path.decode()] = (mode, oid)
    return out


def run(name, argv):
    start = time.monotonic()
    r = subprocess.run(argv, capture_output=True)
    (B / (name + '.out')).write_bytes(r.stdout)
    (B / (name + '.err')).write_bytes(r.stderr)
    dump(name + '.run.json', {'argv': argv, 'exit': r.returncode,
         'seconds': time.monotonic() - start,
         'stdout_sha256': hashlib.sha256(r.stdout).hexdigest(),
         'stderr_sha256': hashlib.sha256(r.stderr).hexdigest()})
    assert r.returncode == 0, (name, r.returncode)
    return r.stdout


pair = json.loads((B / 'PAIR-PASSPORT.json').read_text())
assert pair['C'] == C and pair['OK']
M, J = pair['M'], pair['J']
jrepo = Path(pair['J_git'])
je = tree(jrepo, J)
raw_filter, _ = ji.assemble(str(jrepo), je)
filter_blob = ji.blob_id(raw_filter)
passport = json.loads(run('JI', [sys.executable, '-B', str(B / 'operator/judge_input_export.py'),
    '--j-git-dir', str(jrepo), '--j-commit', J, '--filter-blob', filter_blob,
    '--output', str(B / 'judge-input')]))
repo = B / 'judge-input/JI.git'
JI = passport['j_input_commit']
assert passport['source_C'] == C and passport['j_commit'] == J
assert (B / 'judge-input/FILTER-JI.json').read_bytes() == raw_filter
ie = tree(repo, JI)
_, included = ji.parse_filter(raw_filter)
assert ie == {p: je[p] for p in included}
assert git(repo, 'rev-list', '--parents', JI).decode().split() == [JI]
assert git(repo, 'for-each-ref', '--format=%(objectname)').decode().split() == [JI]
assert not git(repo, 'remote').strip() and not (repo / 'objects/info/alternates').exists()
physical = set(git(repo, 'cat-file', '--batch-all-objects', '--batch-check=%(objectname)').splitlines())
reachable = set(git(repo, 'rev-list', '--objects', '--no-object-names', JI).splitlines())
assert physical == reachable
run('FSCK-JI', ['git', '--git-dir', str(repo), 'fsck', '--strict', '--full'])
root = B / 'JI'
root.mkdir()
p = subprocess.Popen(['git', '--git-dir', str(repo), 'archive', JI], stdout=subprocess.PIPE)
r = subprocess.run(['tar', '-x', '-C', str(root)], stdin=p.stdout)
p.stdout.close()
assert p.wait() == r.returncode == 0
rows = []
for rel, (mode, blob) in sorted(ie.items()):
    path = root / rel
    assert stat.S_ISREG(path.lstat().st_mode)
    raw = path.read_bytes()
    assert operator._blob_id(raw) == blob
    path.chmod(0o555 if mode == '100755' else 0o444)
    rows.append({'path': rel, 'mode': mode, 'blob': blob, 'bytes': len(raw), 'sha256': sha(path)})
for path in sorted((p for p in root.rglob('*') if p.is_dir()), reverse=True):
    path.chmod(0o555)
root.chmod(0o555)
dump('UNPACKED-JI.json', {'C': C, 'commit': JI, 'directory': str(root), 'count': len(rows),
                        'files': rows, 'paths_blobs_modes_equal_git': True, 'all_write_bits_cleared': True})
read_only = {}
for side in ('M', 'J', 'JI'):
    home = B / side
    actual = {p.relative_to(home).as_posix() for p in home.rglob('*') if p.is_file()}
    record = json.loads((B / ('UNPACKED-' + side + '.json')).read_text())
    assert actual == {r['path'] for r in record['files']}
    for row in record['files']:
        path = home / row['path']
        assert stat.S_ISREG(path.lstat().st_mode) and sha(path) == row['sha256']
        assert operator._blob_id(path.read_bytes()) == row['blob']
        assert bool(path.stat().st_mode & 0o111) == (row['mode'] == '100755')
    read_only[side] = all(not p.lstat().st_mode & 0o222 for p in (home, *home.rglob('*')))
assert all(read_only.values())
assert (B / 'M' / operator.MARKER).read_text() == (B / 'J' / operator.MARKER).read_text() == (B / 'JI' / operator.MARKER).read_text() == C + '\n'
me = tree(Path(pair['M_git']), M)
old_passport = json.loads((prior / 'PAIR-PASSPORT.json').read_text())
old = tree(Path(old_passport['M_git']), old_passport['M'])
added, removed = sorted(me.keys() - old.keys()), sorted(old.keys() - me.keys())
changed = sorted(p for p in me.keys() & old.keys() if me[p] != old[p])
assert added == ['Platform/04-controller/forms/targets.tsv'] and not removed
reason = {p: 'P02.75' for p in (
    'Platform/02-installer/acceptance/5/README.md',
    'Platform/02-installer/forms/refusals.tsv',
    'Platform/02-installer/spec/02.4-installer.norms.md',
    'Platform/02-installer/spec/02.5-installer.norms.md')}
reason.update({p: 'P04.42' for p in (
    'Platform/04-controller/forms/targets.tsv',
    'Platform/common/acceptance/forms/targets.README.md',
    'Platform/common/acceptance/runner-targets.tsv')})
reason[operator.MARKER] = 'new source C (delivery marker)'
assert set(added + changed) == reason.keys()
comparison = []
for path in sorted(added + changed):
    comparison.append({'path': path, 'kind': 'added' if path in added else 'changed',
        'cause': reason[path], 'before_mode_blob': old.get(path), 'after_mode_blob': me[path],
        'before_sha256': sha(prior / 'M' / path) if path in old else None,
        'after_sha256': sha(B / 'M' / path)})
for path in me.keys() & old.keys():
    if path not in changed:
        assert (prior / 'M' / path).read_bytes() == (B / 'M' / path).read_bytes()
dump('M-COMPARISON.json', {'baseline_C': old_passport['C'], 'baseline_M': old_passport['M'],
    'C': C, 'M': M, 'baseline_files': len(old), 'files': len(me),
    'added': added, 'removed': removed, 'changes': comparison,
    'unchanged_files': len(old) - len(changed), 'unchanged_files_byte_equal': True,
    'other_P04_lesson_files_byte_equal': True,
    'authority': 'P04.43 answered 2026-11-14T12:13:42Z: P02.75 dependency changes permitted', 'OK': True})
def read_rows(home, rel):
    text = (home / rel).read_text()
    return list(csv.DictReader(io.StringIO('\n'.join(x for x in text.splitlines() if not x.startswith('#'))), delimiter='\t'))
target_path = 'Platform/04-controller/forms/targets.tsv'
routing_path = 'Platform/04-controller/forms/targets.routing.tsv'
targets = read_rows(B / 'M', target_path)
routing = read_rows(B / 'JI', routing_path)
assert len(targets) == len(routing) == 27
assert {r['id'] for r in targets} == {r['id'] for r in routing}
assert target_path in me and routing_path not in me and target_path in ie and routing_path in ie
assert all((B / side / target_path).read_bytes() == (B / 'M' / target_path).read_bytes() for side in ('J', 'JI'))
candidate_task = Path('/home/pilot/cammeta-sessions/tasks/P04.39.yaml').read_bytes()
candidate_receipt = Path('/home/pilot/cammeta-sessions/tasks/handed/P04.39.json').read_bytes()
assert 'M из P04.37'.encode() in candidate_task
(B / 'reviews/P04.39-task.yaml').write_bytes(candidate_task)
(B / 'reviews/P04.39-handed.json').write_bytes(candidate_receipt)
final = {**pair, 'format': 'P04.43-pair-with-JI/1', 'JI': JI, 'JI_tree': passport['j_input_tree'],
    'JI_directory': str(root), 'JI_git': str(repo), 'JI_count': len(ie),
    'JI_passport': str(B / 'judge-input/PASSPORT-JI.json'),
    'JI_passport_sha256': sha(B / 'judge-input/PASSPORT-JI.json'), 'JI_filter_blob': filter_blob,
    'JI_projection_exact': True, 'JI_objects': len(physical), 'JI_fsck_exit': 0,
    'read_only_directories': read_only, 'P04_targets_in_M_J_JI': 27,
    'P04_routing_only_J_JI': True, 'M_comparison': str(B / 'M-COMPARISON.json'),
    'candidate': {'task': 'P04.39', 'generated_from_M': old_passport['M'],
        'generated_from_pair': 'P04.37', 'court_uses_J': J, 'court_uses_JI': JI,
        'generation_repeated': False, 'court_executed_by_this_task': False}, 'OK': True}
dump('FINAL-PASSPORT.json', final)
checksums = []
for side in ('M', 'J', 'JI'):
    record = json.loads((B / ('UNPACKED-' + side + '.json')).read_text())
    checksums.extend((r['sha256'], side + '/' + r['path']) for r in record['files'])
for name in ('FINAL-PASSPORT.json', 'PAIR-PASSPORT.json', 'PASSPORT-M.json', 'NARROW-M.json',
             'MODULE-PINS.json', 'SPEC_VERSION', 'M-COMPARISON.json', 'UNPACKED-M.json',
             'UNPACKED-J.json', 'UNPACKED-JI.json', 'judge-input/PASSPORT-JI.json',
             'judge-input/FILTER-JI.json', 'FILTER-REVIEWS.json', 'FILTER-DELTA.json', 'TASK-at-source.yaml'):
    checksums.append((sha(B / name), name))
(B / 'SHA256SUMS').write_text(''.join(h + '  ' + p + '\n' for h, p in sorted(checksums, key=lambda r: r[1])))
for digest, path in checksums:
    assert sha(B / path) == digest
dump('VERIFY-FINAL.json', {'C': C, 'M': M, 'J': J, 'JI': JI, 'sha256_records_verified': len(checksums),
    'SHA256SUMS_sha256': sha(B / 'SHA256SUMS'), 'read_only': read_only,
    'payload_rosters_blobs_modes_and_sha256_verified': True,
    'M_comparison_sha256': sha(B / 'M-COMPARISON.json'), 'OK': True})
print(json.dumps({'C': C, 'M': M, 'J': J, 'JI': JI, 'counts': [len(me), len(je), len(ie)],
                  'M_changes': len(comparison), 'unchanged': len(old) - len(changed), 'OK': True}))
