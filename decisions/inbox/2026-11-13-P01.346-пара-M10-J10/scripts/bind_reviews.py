"""Bind two added Q classifications to accepted different-provider review."""
from pathlib import Path
import csv
import hashlib
import json
import shutil
import subprocess
import sys

B = Path(sys.argv[1]).resolve()
C = (B / 'C.txt').read_text().strip()
T = Path('/home/pilot/cammeta-sessions/tasks')
delta = json.loads((B / 'FILTER-DELTA.json').read_text())
assert delta['from'] == 'bacf1dd2171aa69b49d4bc5cdd6a2c7a9a4fac30' and delta['to'] == C
expected = {'Platform/01-store/forms/production/' + name: ('judge_only', 'include')
            for name in ('soak.json', 'soak.schema.json')}
assert not delta['changed'] and not delta['removed']
assert {r['path']: (r['M'], r['JI']) for r in delta['added']} == expected
with (T.parent / 'sessions.tsv').open() as f:
    rows = [dict(zip(('name', 'handle', 'model'), row[:3]))
            for row in csv.reader(f, delimiter='\t') if row and row[0] == 'architect']
assert len(rows) == 1 and rows[0]['model'] == 'Claude'
identity = rows[0]
author = '\n'.join(line for line in (T / 'P01.341.yaml').read_text().splitlines()
                   if line.startswith(('id:', 'provider:'))) + '\n'
assert 'provider: codex' in author
(B / 'reviews/P01.341-author.txt').write_text(author)
accepted_path = B / 'reviews/P01.341-accepted.json'
accepted = json.loads(accepted_path.read_text())
assert accepted['status'] == 'accepted' and accepted['window'] == identity['handle']
subprocess.run(['git', '--git-dir', str(B / 'source.git'), 'merge-base', '--is-ancestor',
                accepted['commit'], C], check=True)
review = B / 'reviews/P01.341-accepted-review.json'
shutil.copyfile(accepted_path, review)
(B / 'reviews/P01.341-reviewer.json').write_text(json.dumps({
    'source': '/home/pilot/cammeta-sessions/sessions.tsv', 'fields': identity,
    'accepted_window': accepted['window'], 'window_match': True,
    'provider': 'Anthropic'}, indent=1) + '\n')
inherited = Path('/home/pilot/P01.339-evidence/FILTER-REVIEWS.json')
shutil.copyfile(inherited, B / 'reviews/P01.339-inherited-filter-reviews.json')
result = {'C': C, 'baseline': 'accepted P01.339 pair; unchanged semantic classifications inherited',
    'delta_sha256': hashlib.sha256((B / 'FILTER-DELTA.json').read_bytes()).hexdigest(),
    'deltas': [{'task': 'P01.341', 'records': sorted(expected),
        'author_provider': 'OpenAI', 'reviewer_provider': 'Anthropic',
        'provider_evidence': 'accepted.window equals actual architect Claude handle; accepted receipt is review record',
        'accepted_receipt': 'reviews/P01.341-accepted.json',
        'review': 'reviews/P01.341-accepted-review.json',
        'review_sha256': hashlib.sha256(review.read_bytes()).hexdigest()}],
    'filter_author_provider': 'per-record actual provider in deltas',
    'filter_reviewer_provider': 'different actual provider per record in deltas',
    'all_delta_records_covered': True,
    'inherited_review': 'reviews/P01.339-inherited-filter-reviews.json',
    'inherited_review_sha256': hashlib.sha256(inherited.read_bytes()).hexdigest()}
(B / 'FILTER-REVIEWS.json').write_text(json.dumps(result, ensure_ascii=False, indent=1) + '\n')
print(json.dumps({'C': C, 'added_records_reviewed': len(expected)}, indent=1))
