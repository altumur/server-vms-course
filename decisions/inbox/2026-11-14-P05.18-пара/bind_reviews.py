"""Bind P05.18 source prerequisites and accepted filter changes; no export invocation."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys

B = Path(sys.argv[1]).resolve()
C = (B / 'C.txt').read_text().strip()
T = Path('/home/pilot/cammeta-sessions/tasks')
prior = Path('/home/pilot/P04.43-evidence')

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def dump(name, value):
    (B / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

def git(*args):
    return subprocess.check_output(['git', '--git-dir', str(B / 'source.git'), *args])

assert not (B / 'FILTER-REVIEWS.json').exists()
for path in (prior / 'reviews').iterdir():
    if path.is_file():
        shutil.copyfile(path, B / 'reviews' / path.name)
shutil.copyfile(prior / 'FILTER-REVIEWS.json', B / 'reviews/P04.43-filter-reviews.json')
inherited = json.loads((prior / 'FILTER-REVIEWS.json').read_text())
assert inherited['all_delta_records_covered']
rows = []
receipts = {}
for name in ('P02.52', 'P04.43', 'P05.16', 'P05.17', 'P04.44', 'OBSH.90', 'OBSH.91', 'OBSH.93', 'OBSH.95', 'OBSH.97'):
    raw = (T / 'accepted' / (name + '.json')).read_bytes()
    accepted = json.loads(raw)
    assert accepted['id'] == name and accepted['status'] == 'accepted'
    subprocess.run(['git', '--git-dir', str(B / 'source.git'), 'merge-base', '--is-ancestor', accepted['commit'], C], check=True)
    destination = B / 'reviews' / (name + '-accepted.json')
    destination.write_bytes(raw)
    receipts[name] = accepted
    rows.append({'task': name, 'commit': accepted['commit'], 'ancestor_C': True,
                 'receipt': str(destination.relative_to(B)), 'sha256': sha(destination)})
delta = json.loads((B / 'FILTER-DELTA.json').read_text())
assert delta['from'] == inherited['C'] and delta['to'] == C
assert not delta['changed'] and not delta['removed']
review_rows = []
covered = set()
for name in ('P04.44', 'P05.17'):
    accepted = receipts[name]
    definition = (T / (name + '.yaml')).read_bytes()
    assert b'provider: codex' in definition
    (B / 'reviews' / (name + '-task.yaml')).write_bytes(definition)
    assert accepted['from'] == 'architect' and accepted['window'] == receipts['P04.43']['window']
    changed_paths = set(git('diff-tree', '--no-commit-id', '--name-only', '-r', accepted['commit']).decode().splitlines())
    records = [r['path'] for r in delta['added'] if r['path'] in changed_paths]
    assert len(records) == 2 and not (covered & set(records))
    covered.update(records)
    review = B / 'reviews' / (name + '-accepted.json')
    kind = 'accepted Architect receipt; same reviewer window as accepted P04.43 (Claude), author task Codex'
    if name == 'P04.44':
        review = B / 'reviews/P04.44-filter-review.md'
        review.write_bytes(git('show', C + ':decisions/inbox/ревью/2026-11-14-P04.44-ревью-фильтра.md'))
        assert 'Claude' in review.read_text() and 'Codex' in review.read_text()
        assert all(p in review.read_text() for p in records)
        kind = 'explicit filter review and accepted receipt'
    review_rows.append({'task': name, 'accepted_commit': accepted['commit'], 'records': records,
        'author_provider': 'OpenAI', 'reviewer_provider': 'Anthropic',
        'accepted_receipt': 'reviews/' + name + '-accepted.json',
        'review': str(review.relative_to(B)), 'review_sha256': sha(review), 'review_kind': kind})
assert covered == {r['path'] for r in delta['added']}
source_proofs = []
for path in sorted(set(delta['M_sources_to']) | set(delta['JI_sources_to'])):
    before = git('rev-parse', delta['from'] + ':' + path).decode().strip()
    after = git('rev-parse', C + ':' + path).decode().strip()
    if before != after:
        owner = {'Platform/04-controller/forms/export.json': 'P04.44',
                 'Platform/05-resource/forms/export.json': 'P05.17'}[path]
        assert git('rev-parse', receipts[owner]['commit'] + ':' + path).decode().strip() == after
        source_proofs.append({'path': path, 'before': before, 'after': after, 'accepted_task': owner})
dump('FILTER-REVIEWS.json', {'C': C, 'baseline': delta['from'],
    'delta_sha256': sha(B / 'FILTER-DELTA.json'), 'deltas': review_rows,
    'all_delta_records_covered': True, 'changed_filter_sources': source_proofs,
    'other_filter_sources_equal_P04.43': True,
    'inherited_review': 'reviews/P04.43-filter-reviews.json',
    'inherited_review_sha256': sha(B / 'reviews/P04.43-filter-reviews.json'),
    'filter_author_provider': 'OpenAI; accepted baseline classifications inherited',
    'filter_reviewer_provider': 'Anthropic; explicit review and accepted Architect receipts'})
dump('SOURCE-COMPOSITION.json', {'C': C, 'dependencies': rows,
    'task_sha256': sha(B / 'TASK-at-source.yaml'), 'latest_fetched_main_at_source': C, 'OK': True})
print(json.dumps({'C': C, 'prerequisites': len(rows), 'new_filter_records': len(covered), 'OK': True}))
