"""Snapshot bounded review facts; never copy a session's note or environment.
Usage: spec-python -B snapshot_reviews.py <evidence> <own course worktree>
"""
from pathlib import Path
import csv
import json
import sys

B, W = map(lambda x: Path(x).resolve(), sys.argv[1:3])

def retain(path, raw):
    if path.exists():
        assert path.read_bytes() == raw, str(path)
    else:
        path.write_bytes(raw)

rows = []
with Path('/home/pilot/cammeta-sessions/sessions.tsv').open() as source:
    for values in csv.reader(source, delimiter='\t'):
        if values and values[0] == 'architect':
            rows.append(dict(zip(('name', 'handle', 'model'), values[:3])))
assert len(rows) == 1
p323 = json.loads((B / 'reviews/P01.323-accepted.json').read_text())
row = rows[0]
assert row['handle'] == p323['window'] and row['model'] == 'Claude'
identity = {'source': '/home/pilot/cammeta-sessions/sessions.tsv', 'fields': row,
    'accepted_window': p323['window'], 'window_match': True, 'provider': 'Anthropic'}
retain(B / 'reviews/P01.323-reviewer.json', (json.dumps(identity, indent=1) + '\n').encode())
retain(B / 'reviews/P01.323-review.md', (B / 'reviews/P01.323-accepted.json').read_bytes())
retain(B / 'reviews/P01.294-review.md', (W / 'decisions/inbox/2026-11-12-P01.294-judge-Claude.md').read_bytes())
for task in ('P01.294', 'P01.323'):
    lines = Path('/home/pilot/cammeta-sessions/tasks/' + task + '.yaml').read_text().splitlines()
    fields = [line for line in lines if line.startswith(('id:', 'provider:'))]
    retain(B / 'reviews' / (task + '-author.txt'), ('\n'.join(fields) + '\n').encode())
print('review facts retained')
