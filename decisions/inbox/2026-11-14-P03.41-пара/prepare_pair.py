"""P03.41: prepare an exact-C source and unchanged accepted pair operators.

Run with venv-spec Python from the task worktree. All output is private evidence;
no candidate, module generation, deployment or privileged operation is performed.
"""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys

W = Path.cwd()
B = Path('/home/pilot/P03.41-evidence')
T = Path('/home/pilot/cammeta-sessions/tasks')
OLD = Path('/home/pilot/P02.72-evidence')
C = (B / 'C.txt').read_text().strip()


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def dump(name, obj):
    (B / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')


def git(*args):
    return subprocess.check_output(['git', *args], cwd=W)


assert git('rev-parse', 'HEAD').decode().strip() == C
assert not git('diff', '--name-only', C, '--', 'Platform', 'skills', 'decisions/0133-генерация-с-нуля-своим-циклом.md').strip()
if not (B / 'source.git').exists():
    subprocess.run(['git', 'clone', '--bare', '--no-hardlinks', str(W), str(B / 'source.git')], check=True,
                   stdout=(B / 'CLONE.out').open('wb'), stderr=(B / 'CLONE.err').open('wb'))
assert subprocess.check_output(['git', '--git-dir', str(B / 'source.git'), 'rev-parse', C]).decode().strip() == C
if not (B / 'archive-C').exists():
    (B / 'archive-C').mkdir()
    producer = subprocess.Popen(['git', 'archive', C], stdout=subprocess.PIPE)
    consumer = subprocess.run(['tar', '-x', '-C', str(B / 'archive-C')], stdin=producer.stdout)
    producer.stdout.close()
    assert producer.wait() == consumer.returncode == 0
for name in ('operator', 'scripts', 'reviews'):
    (B / name).mkdir(exist_ok=True)
identities = json.loads((OLD / 'OPERATOR-UNCHANGED.json').read_text())
operators = {}
for name, row in identities.items():
    p = B / 'operator' / name
    source = row.get('path')
    p.write_bytes(git('show', C + ':' + source) if source else (OLD / 'operator' / name).read_bytes())
    assert sha(p) == row['sha256'] == sha(OLD / 'operator' / name)
    operators[name] = {'sha256': sha(p), 'byte_equal_accepted_P02_72': True,
                       'source': source or str(OLD / 'operator' / name)}
dump('OPERATOR-UNCHANGED.json', operators)
for name in ('preflight.py', 'filter_delta.py'):
    raw = (OLD / 'scripts' / name).read_text().replace('P02.72', 'P03.41')
    (B / 'scripts' / name).write_text(raw)
baseline = (OLD / 'C.txt').read_text().strip()
for name, argv in (
    ('PREFLIGHT', [sys.executable, '-B', str(B / 'scripts/preflight.py'), C, str(B / 'source.git')]),
    ('FILTER-DELTA', [sys.executable, '-B', str(B / 'scripts/filter_delta.py'), baseline, C, str(B / 'source.git')]),
):
    r = subprocess.run(argv, capture_output=True)
    (B / (name + '.json')).write_bytes(r.stdout)
    (B / (name + '.err')).write_bytes(r.stderr)
    assert r.returncode == 0, (name, r.stderr.decode())

accepted = json.loads((T / 'accepted/P02.72.json').read_text())
assert accepted['status'] == 'accepted'
(B / 'reviews/P02.72-accepted.json').write_bytes((T / 'accepted/P02.72.json').read_bytes())
inherited = json.loads((OLD / 'FILTER-REVIEWS.json').read_text())
for path in (OLD / 'reviews').iterdir():
    if path.is_file():
        shutil.copyfile(path, B / 'reviews' / path.name)
(B / 'reviews/P02.72-inherited-filter-reviews.json').write_bytes((OLD / 'FILTER-REVIEWS.json').read_bytes())
delta = json.loads((B / 'FILTER-DELTA.json').read_text())
fixture = 'Platform/common/vectors/row-check/fixtures/testsub2.subsystem.yaml'
assert delta['added'] == [{'path': fixture, 'M': 'judge_only', 'JI': 'include'}]
assert not delta['removed'] and not delta['changed']
filter_task = 'OBSH.97'
filter_accepted_raw = (T / 'accepted' / (filter_task + '.json')).read_bytes()
filter_accepted = json.loads(filter_accepted_raw)
assert filter_accepted['status'] == 'accepted'
subprocess.run(['git', 'merge-base', '--is-ancestor', filter_accepted['commit'], C], check=True)
review_path = 'decisions/inbox/ревью/2026-11-14-OBSH.97-ревью-фильтра.md'
review = B / 'reviews/OBSH.97-review.md'
review.write_bytes(git('show', C + ':' + review_path))
assert 'Claude' in review.read_text() and 'Codex' in review.read_text() and fixture in review.read_text()
(B / 'reviews/OBSH.97-accepted.json').write_bytes(filter_accepted_raw)
author = '\n'.join(line for line in (T / 'OBSH.97.yaml').read_text().splitlines()
                   if line.startswith(('id:', 'provider:'))) + '\n'
assert 'provider: codex' in author
(B / 'reviews/OBSH.97-author.txt').write_text(author)
assert fixture in git('diff', '--name-only', filter_accepted['commit'] + '^', filter_accepted['commit']).decode().splitlines()
for file, side, expected in (('Platform/common/export-model-filter.json', 'model', 'judge_only'),
                             ('Platform/common/acceptance/judge-input-filter.json', 'judge', 'include')):
    records = json.loads(git('show', filter_accepted['commit'] + ':' + file))['files']
    assert next(row for row in records if row['path'] == fixture)['disposition'] == expected
review_rows = [{'task': filter_task, 'accepted_commit': filter_accepted['commit'], 'records': [fixture],
                'author_provider': 'OpenAI', 'reviewer_provider': 'Anthropic',
                'accepted_receipt': 'reviews/OBSH.97-accepted.json',
                'review': 'reviews/OBSH.97-review.md', 'review_sha256': sha(review),
                'roles_equal_accepted_commit': True, 'review_kind': 'explicit filter review'}]
dump('FILTER-REVIEWS.json', {
    'C': C, 'baseline': baseline, 'delta_sha256': sha(B / 'FILTER-DELTA.json'),
    'deltas': review_rows, 'all_delta_records_covered': True,
    'filter_author_provider': inherited['filter_author_provider'],
    'filter_reviewer_provider': inherited['filter_reviewer_provider'],
    'inherited_accepted_task': 'P02.72', 'accepted_commit': accepted['commit'],
    'accepted_receipt': 'reviews/P02.72-accepted.json',
    'inherited_review': 'reviews/P02.72-inherited-filter-reviews.json',
    'inherited_review_sha256': sha(B / 'reviews/P02.72-inherited-filter-reviews.json'),
    'unchanged_baseline_dispositions_plus_reviewed_fixture': True,
})
dependencies = []
for task in ('P02.52', 'P03.40', 'OBSH.90', 'OBSH.91', 'OBSH.93', 'OBSH.95', 'OBSH.97'):
    raw = (T / 'accepted' / (task + '.json')).read_bytes()
    row = json.loads(raw)
    assert row['status'] == 'accepted'
    subprocess.run(['git', 'merge-base', '--is-ancestor', row['commit'], C], check=True)
    p = B / 'reviews' / (task + '-accepted.json')
    p.write_bytes(raw)
    dependencies.append({'task': task, 'commit': row['commit'], 'status': 'accepted',
                         'ancestor_C': True, 'receipt': str(p.relative_to(B)), 'sha256': sha(p)})
dump('SOURCE-COMPOSITION.json', {'C': C, 'dependencies': dependencies, 'OK': True})
print(json.dumps({'C': C, 'preflight': json.loads((B / 'PREFLIGHT.json').read_text()),
                  'filter_delta': delta['counts'], 'source_dependencies': dependencies}, ensure_ascii=False, indent=2))
