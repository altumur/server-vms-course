#!/usr/bin/env python3
"""Read saved receipts only; do not run a judge or candidate."""
import collections
import csv
import hashlib
import json
import pathlib
import subprocess

HERE = pathlib.Path(__file__).resolve().parent
A = pathlib.Path('/home/pilot/owner-receipts/P01.159-court-attempt6-20261111')
B = pathlib.Path('/home/pilot/owner-receipts/P01.188-court-claude-20261111')
J = '/home/pilot/run-p0226-pair-20261111/ji-4694190a17/JI.git'
J_SHA = '49e622795ca96b2e73904f1da5d203f2d103b2d5'
TARGETS = ['P_01_1_door', 'P_01_1_extra', 'P_01_2_rights',
           'P_01_3_daemon', 'P_01_3_group']
hashes = {}


def read(path):
    data = path.read_bytes()
    hashes[str(path)] = hashlib.sha256(data).hexdigest()
    return data


def jfile(path):
    data = subprocess.check_output(['git', '--git-dir=' + J, 'show', J_SHA + ':' + path])
    hashes['J:' + path] = hashlib.sha256(data).hexdigest()
    return data.decode()


def tablerows(text):
    return list(csv.DictReader((line for line in text.splitlines()
                               if line and not line.startswith('#')), delimiter='\t'))


rows = []
summary = {}
unexecuted = []
for target in TARGETS:
    a = json.loads(read(A / 'out-diag' / 'attempt6' / target / 'engine.json'))
    b = json.loads(read(B / 'out-diag' / 'claude' / target / 'engine.json'))
    assert a == b, target
    trace_path = B / 'replay188' / 'trace' / (target + '.jsonl')
    traced = {}
    if trace_path.exists():
        steps = {(s['table'], s['line']): s for s in b['steps']}
        for line in read(trace_path).decode().splitlines():
            item = json.loads(line)
            s = item['step']
            assert steps[(s['table'], s['line'])] == s
            traced[(s['table'], s['line'])] = item
        # Ordinary scenarios only; seam rows are not covered by replay.
        assert all((s['table'], s['line']) in traced
                   for s in b['steps'] if s['kind'] == 'scenario')
    count = collections.Counter()
    for step in a['steps']:
        if step['result'] == 'not_executed':
            unexecuted.append([a['target'], step['table'], step['line'], step['scenario'],
                               step.get('reason', '')])
        if step['result'] != 'red':
            continue
        n = step['line']
        reason = step['reason']
        if target.endswith('door'):
            case = 'E1'
        elif target.endswith('rights'):
            case = 'E2' if n in [21, 33] else 'E3'
        elif target.endswith('daemon'):
            case = 'E5' if n == 209 else 'E4'
        else:
            case = 'E6' if reason == 'store-start' else (
                'E7' if reason in ['expectation', 'transport'] else 'E4')
        count[case] += 1
        observed = traced.get((step['table'], n), {}).get('observation', {})
        rows.append([a['target'], step['table'], n, step['scenario'], step['class'],
                     reason, 'движок', case, 'independent.md: ' + case,
                     observed.get('status', '-'),
                     json.dumps(observed['body'], ensure_ascii=False) if 'body' in observed else '-'])
    summary[a['target']] = {
        'reports_equal': True,
        'red': sum(count.values()), 'classes': dict(sorted(count.items())),
        'steps': len(a['steps']), 'rows': len(a['rows']), 'entries': len(a['entries']),
        'unexecuted_steps': dict(sorted(collections.Counter(
            s.get('reason', '') for s in a['steps'] if s['result'] == 'not_executed').items()))}

extra = tablerows(jfile('Platform/common/acceptance/forms/extra.tsv'))
text = jfile('Platform/common/acceptance/forms/extra.scenarios.tsv')
machine = {line.split('\t')[0] for line in text.splitlines() if line and not line.startswith('#')}
missing = sorted(row['id'] for row in extra if row['target'] == 'P/01.1/extra'
                 and row['id'] not in machine)
assert missing == ['extra-forwarded-list', 'extra-full-key-declared']
assert len(rows) == 145
assert len({tuple(row[:3]) for row in rows}) == 145
assert [summary[k]['red'] for k in summary] == [1, 0, 10, 9, 125]

with (HERE / 'red-steps.tsv').open('w') as f:
    w = csv.writer(f, delimiter='\t', lineterminator='\n')
    w.writerow(['target', 'table', 'line', 'scenario', 'reported_class', 'reported_reason',
                'review_class', 'cause', 'explanation', 'replay_status', 'replay_body'])
    w.writerows(rows)
with (HERE / 'unexecuted-steps.tsv').open('w') as f:
    w = csv.writer(f, delimiter='\t', lineterminator='\n')
    w.writerow(['target', 'table', 'line', 'scenario', 'reported_reason'])
    w.writerows(unexecuted)
result = {'targets': summary, 'extra_without_machine_form': missing,
          'red_total': len(rows), 'input_sha256': hashes}
(HERE / 'evidence.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'red_total': len(rows), 'extra_without_machine_form': missing,
                  'class_counts': dict(collections.Counter(row[7] for row in rows))},
                 ensure_ascii=False))
