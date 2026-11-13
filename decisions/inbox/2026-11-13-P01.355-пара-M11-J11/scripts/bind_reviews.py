"""Bind every filter delta from M10 to its accepted different-provider review."""
from pathlib import Path
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys

B = Path(sys.argv[1]).resolve()
C = (B / 'C.txt').read_text().strip()
T = Path('/home/pilot/cammeta-sessions/tasks')
sys.path.insert(0, str(B / 'operator'))
import b7_export_pair as pair
import judge_input_export as ji


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git(*args):
    return subprocess.check_output(['git', '--git-dir', str(B / 'source.git'), *args])


def roles(commit):
    fd = pair._open_dir(pair._canonical(B / 'source.git'))
    try:
        entries = pair._source(fd, commit)
    finally:
        os.close(fd)
    entries[pair.MARKER] = ('100644', None, (commit + '\n').encode())
    _, model, _ = pair._assemble(entries)
    tree = {p: (mode, blob) for p, (mode, blob, _) in entries.items() if p != pair.MARKER}
    judge, _ = ji.assemble(str(B / 'source.git'), tree)
    return ({r['path']: r['disposition'] for r in model['files']},
            {r['path']: r['disposition'] for r in json.loads(judge)['files']})


delta = json.loads((B / 'FILTER-DELTA.json').read_text())
assert delta['from'] == '431c32debbc1bb35e57e4dfa323f8f091335172a' and delta['to'] == C
with (T.parent / 'sessions.tsv').open() as f:
    rows = [dict(zip(('name', 'handle', 'model'), row[:3]))
            for row in csv.reader(f, delimiter='\t') if row and row[0] == 'architect']
assert len(rows) == 1 and rows[0]['model'] == 'Claude'
identity = rows[0]
tasks = {}
for name in ('P01.350', 'OBSH.70'):
    author = '\n'.join(line for line in (T / (name + '.yaml')).read_text().splitlines()
                       if line.startswith(('id:', 'provider:'))) + '\n'
    assert 'provider: codex' in author
    (B / 'reviews' / (name + '-author.txt')).write_text(author)
    accepted_path = B / 'reviews' / (name + '-accepted.json')
    accepted = json.loads(accepted_path.read_text())
    assert accepted['status'] == 'accepted' and accepted['window'] == identity['handle']
    subprocess.run(['git', '--git-dir', str(B / 'source.git'), 'merge-base', '--is-ancestor',
                    accepted['commit'], C], check=True)
    changed = set(git('diff', '--no-renames', '--name-only', accepted['commit'] + '^',
                      accepted['commit']).decode().splitlines())
    tasks[name] = {'accepted': accepted, 'changed': changed, 'roles': roles(accepted['commit']),
                   'records': []}

for kind in ('added', 'removed', 'changed'):
    for row in delta[kind]:
        path = row['path']
        owners = [name for name, value in tasks.items() if path in value['changed']]
        assert len(owners) == 1, ('unreviewed or ambiguous filter delta', kind, path, owners)
        value = tasks[owners[0]]
        model, judge = value['roles']
        if kind == 'removed':
            assert path not in model and path not in judge
        else:
            expected = ((row['M'][-1], row['JI'][-1]) if kind == 'changed'
                        else (row['M'], row['JI']))
            assert (model.get(path), judge.get(path)) == expected
        value['records'].append(path)

reviews = []
for name, value in tasks.items():
    assert value['records'], name
    accepted = B / 'reviews' / (name + '-accepted.json')
    review = B / 'reviews' / (name + '-accepted-review.json')
    shutil.copyfile(accepted, review)
    (B / 'reviews' / (name + '-reviewer.json')).write_text(json.dumps({
        'source': '/home/pilot/cammeta-sessions/sessions.tsv', 'fields': identity,
        'accepted_window': value['accepted']['window'], 'window_match': True,
        'provider': 'Anthropic'}, indent=1) + '\n')
    reviews.append({'task': name, 'records': sorted(value['records']),
        'author_provider': 'OpenAI', 'reviewer_provider': 'Anthropic',
        'provider_evidence': 'accepted.window equals actual architect Claude handle; accepted receipt is review record',
        'accepted_receipt': str(accepted.relative_to(B)), 'review': str(review.relative_to(B)),
        'review_sha256': sha(review), 'roles_equal_accepted_commit': True,
        'paths_changed_by_accepted_task': True})

inherited = Path('/home/pilot/P01.346-evidence/FILTER-REVIEWS.json')
shutil.copyfile(inherited, B / 'reviews/P01.346-inherited-filter-reviews.json')
result = {'C': C, 'baseline': 'accepted P01.346 pair; unchanged semantic classifications inherited',
    'delta_sha256': sha(B / 'FILTER-DELTA.json'), 'deltas': reviews,
    'filter_author_provider': 'per-record actual provider in deltas',
    'filter_reviewer_provider': 'different actual provider per record in deltas',
    'all_delta_records_covered': True,
    'inherited_review': 'reviews/P01.346-inherited-filter-reviews.json',
    'inherited_review_sha256': sha(inherited)}
(B / 'FILTER-REVIEWS.json').write_text(json.dumps(result, ensure_ascii=False, indent=1) + '\n')
print(json.dumps({'C': C, 'delta_records_reviewed': sum(len(r['records']) for r in reviews)}, indent=1))
