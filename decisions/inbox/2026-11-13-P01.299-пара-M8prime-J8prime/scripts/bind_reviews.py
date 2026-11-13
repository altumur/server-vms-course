"""Bind actual accepted reviews to the entire semantic filter delta for P01.299.

Usage: spec-python -B bind_reviews.py <evidence>. Does not approve a new role.
All roles are inherited from P01.277 or explicitly reviewed in P01.294/P01.323.
"""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

B = Path(sys.argv[1]).resolve()
C = (B / 'C.txt').read_text().strip()
delta = json.loads((B / 'FILTER-DELTA.json').read_text())
assert delta['to'] == C and not delta['changed'] and not delta['removed']
expected = {
    'Platform/01-store/qualification/README.md': ('judge_only', 'include'),
    'Platform/01-store/ru/qualification/README.md': ('judge_only', 'exclude'),
    'Platform/common/qualification-input-filter.json': ('judge_only', 'exclude'),
}
assert {r['path']: (r['M'], r['JI']) for r in delta['added']} == expected
identity = json.loads((B / 'reviews/P01.323-reviewer.json').read_text())
p323 = json.loads((B / 'reviews/P01.323-accepted.json').read_text())
assert identity['fields']['name'] == 'architect'
assert identity['fields']['handle'] == identity['accepted_window'] == p323['window']
assert identity['fields']['model'] == 'Claude' and identity['provider'] == 'Anthropic'
rows = []
for task, paths, review in (
    ('P01.294', ['Platform/01-store/qualification/README.md', 'Platform/01-store/ru/qualification/README.md'], 'P01.294-review.md'),
    ('P01.323', ['Platform/common/qualification-input-filter.json'], 'P01.323-review.md'),
):
    accepted = json.loads((B / 'reviews' / (task + '-accepted.json')).read_text())
    assert accepted['status'] == 'accepted'
    subprocess.run(['git', '--git-dir', str(B / 'source.git'), 'merge-base', '--is-ancestor', accepted['commit'], C], check=True)
    assert 'provider: codex' in (B / 'reviews' / (task + '-author.txt')).read_text()
    rows.append({'task': task, 'author_provider': 'OpenAI', 'reviewer_provider': 'Anthropic',
        'provider_evidence': 'P01.323-reviewer.json linked to accepted.window' if task == 'P01.323' else 'accepted Claude review of P01.294',
        'records': paths, 'accepted_receipt': 'reviews/' + task + '-accepted.json', 'review': 'reviews/' + review,
        'review_sha256': hashlib.sha256((B / 'reviews' / review).read_bytes()).hexdigest()})
result = {'C': C, 'baseline': 'P01.277 accepted pair; unchanged semantic records inherited',
    'delta_sha256': hashlib.sha256((B / 'FILTER-DELTA.json').read_bytes()).hexdigest(), 'deltas': rows,
    'filter_author_provider': 'OpenAI (per-delta accepted task metadata)',
    'filter_reviewer_provider': 'Anthropic (actual reviews/window identity)', 'all_delta_records_covered': True}
(B / 'FILTER-REVIEWS.json').write_text(json.dumps(result, ensure_ascii=False, indent=1) + '\n')
print(json.dumps({'reviewed_added_records': 3, 'C': C}, indent=1))
