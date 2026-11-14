"""Prepare exact-C evidence and bind accepted filter deltas before pair creation."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import time

B, W = (Path(x).resolve() for x in sys.argv[1:3])
C = sys.argv[3]
T = Path('/home/pilot/cammeta-sessions/tasks')
prior = Path('/home/pilot/P04.37-evidence')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(name, value):
    (B / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def git(*args):
    return subprocess.check_output(['git', '-C', str(W), *args])


def run(name, argv, cwd=None):
    start = time.monotonic()
    r = subprocess.run(argv, cwd=cwd, capture_output=True)
    (B / (name + '.out')).write_bytes(r.stdout)
    (B / (name + '.err')).write_bytes(r.stderr)
    (B / (name + '.exit')).write_text(str(r.returncode) + '\n')
    dump(name + '.run.json', {'argv': argv, 'cwd': str(cwd or W), 'C': C,
         'exit': r.returncode, 'seconds': time.monotonic() - start,
         'stdout_sha256': hashlib.sha256(r.stdout).hexdigest(),
         'stderr_sha256': hashlib.sha256(r.stderr).hexdigest()})
    assert r.returncode == 0, (name, r.returncode)
    return r.stdout


assert git('rev-parse', 'origin/main').decode().strip() == C
assert git('rev-parse', 'HEAD').decode().strip() == C
assert len(C) == 40 and all(c in '0123456789abcdef' for c in C)
B.mkdir(exist_ok=True)
assert not (B / 'C.txt').exists(), 'retain previous evidence; never overwrite a source'
(B / 'C.txt').write_text(C + '\n')
task = (T / 'P04.43.yaml').read_bytes()
assert 'Разрешаю: собирай пару с текущего main'.encode() in task
(B / 'TASK-at-source.yaml').write_bytes(task)
(B / 'reviews').mkdir()
rows = []
for name in ('P02.52', 'P04.37', 'P02.75', 'P04.42'):
    raw = (T / 'accepted' / (name + '.json')).read_bytes()
    accepted = json.loads(raw)
    assert accepted['status'] == 'accepted'
    subprocess.run(['git', '-C', str(W), 'merge-base', '--is-ancestor',
                    accepted['commit'], C], check=True)
    (B / 'reviews' / (name + '-accepted.json')).write_bytes(raw)
    rows.append({'task': name, 'commit': accepted['commit'], 'ancestor_C': True,
                 'receipt_sha256': hashlib.sha256(raw).hexdigest()})
run('SOURCE-CLONE', ['git', 'clone', '--bare', '--no-hardlinks', str(W), str(B / 'source.git')])
(B / 'archive-C').mkdir()
p = subprocess.Popen(['git', '--git-dir', str(B / 'source.git'), 'archive', C], stdout=subprocess.PIPE)
r = subprocess.run(['tar', '-x', '-C', str(B / 'archive-C')], stdin=p.stdout)
p.stdout.close()
assert p.wait() == r.returncode == 0
(B / 'operator').mkdir()
hashes = {}
for name in ('b7_export_pair.py', 'judge_input_export.py', 'm_passport.py', 'check_m_passport.py'):
    old, new = prior / 'operator' / name, B / 'operator' / name
    shutil.copyfile(old, new)
    if name in ('b7_export_pair.py', 'judge_input_export.py'):
        assert new.read_bytes() == git('show', C + ':decisions/inbox/2026-11-11-P02.52-операторы/operator/' + name)
    hashes[name] = sha(new)
dump('OPERATOR-UNCHANGED.json', {'source': str(prior / 'operator'), 'files_sha256': hashes,
     'canonical_P02.52_byte_equal': True, 'unchanged': True})
(B / 'scripts').mkdir()
for path in Path(__file__).resolve().parent.glob('*.py'):
    shutil.copyfile(path, B / 'scripts' / path.name)
dump('SOURCE-COMPOSITION.json', {'C': C, 'dependencies': rows, 'task_sha256': sha(B / 'TASK-at-source.yaml'),
     'latest_fetched_main_at_source': C, 'OK': True})
run('PREFLIGHT', [sys.executable, '-B', str(B / 'scripts/preflight.py'), C, str(B / 'source.git')])
(B / 'PREFLIGHT.json').write_bytes((B / 'PREFLIGHT.out').read_bytes())
old_C = (prior / 'C.txt').read_text().strip()
delta = json.loads(run('FILTER-DELTA', [sys.executable, '-B', str(B / 'scripts/filter_delta.py'),
                                       old_C, C, str(B / 'source.git')]))
dump('FILTER-DELTA.json', delta)
assert not delta['removed'] and not delta['changed'], 'unexpected reclassification'
inherited = json.loads((prior / 'FILTER-REVIEWS.json').read_text())
assert inherited['all_delta_records_covered'] and inherited['C'] == old_C
shutil.copyfile(prior / 'FILTER-REVIEWS.json', B / 'reviews/P04.37-filter-reviews.json')
review_rows = []
covered = set()
for task_id in ('P02.75', 'P04.42'):
    accepted = json.loads((B / 'reviews' / (task_id + '-accepted.json')).read_text())
    assert accepted['window'] == 'term_a7b4a64c-6bce-4945-a1d5-7e132f904899'
    definition = (T / (task_id + '.yaml')).read_bytes()
    assert b'provider: codex' in definition
    (B / 'reviews' / (task_id + '-task.yaml')).write_bytes(definition)
    paths = set(git('diff-tree', '--no-commit-id', '--name-only', '-r', accepted['commit']).decode().splitlines())
    records = [r['path'] for r in delta['added'] if r['path'] in paths]
    assert records and not (covered & set(records))
    covered.update(records)
    review_rows.append({'task': task_id, 'accepted_commit': accepted['commit'], 'records': records,
        'author_provider': 'OpenAI', 'reviewer_provider': 'Anthropic',
        'accepted_receipt': 'reviews/' + task_id + '-accepted.json',
        'review': 'reviews/' + task_id + '-accepted.json',
        'review_sha256': sha(B / 'reviews' / (task_id + '-accepted.json')),
        'review_kind': 'accepted Architect receipt, as accepted P04.37 binding procedure'})
assert covered == {r['path'] for r in delta['added']}
sources = set(delta['M_sources_to']) | set(delta['JI_sources_to'])
source_proofs = []
for path in sorted(sources):
    before = git('rev-parse', old_C + ':' + path).decode().strip()
    after = git('rev-parse', C + ':' + path).decode().strip()
    if before != after:
        owner = {'Platform/02-installer/forms/export.json': 'P02.75',
                 'Platform/04-controller/forms/export.json': 'P04.42'}[path]
        accepted = json.loads((B / 'reviews' / (owner + '-accepted.json')).read_text())
        assert git('rev-parse', accepted['commit'] + ':' + path).decode().strip() == after
        source_proofs.append({'path': path, 'before': before, 'after': after, 'accepted_task': owner})
dump('FILTER-REVIEWS.json', {'C': C, 'delta_sha256': sha(B / 'FILTER-DELTA.json'),
     'deltas': review_rows, 'all_delta_records_covered': True,
     'inherited_review': 'reviews/P04.37-filter-reviews.json',
     'inherited_review_sha256': sha(B / 'reviews/P04.37-filter-reviews.json'),
     'filter_author_provider': 'OpenAI; unchanged accepted baseline classifications inherited',
     'filter_reviewer_provider': 'Anthropic; accepted Architect receipts',
     'changed_filter_sources': source_proofs,
     'other_filter_sources_equal_P04.37': True,
     'provider_evidence': 'Architect window matches accepted P04.37: Claude (Anthropic)'})
run('CHECK-SPEC-C', [sys.executable, '-B', 'skills/lesson-spec/scripts/check_spec.py',
                    '--scope', 'platform'], cwd=B / 'archive-C')
print(json.dumps({'C': C, 'evidence': str(B), 'check_spec_exit': 0, 'preflight_exit': 0,
                  'new_filter_records': len(covered)}, ensure_ascii=False))
