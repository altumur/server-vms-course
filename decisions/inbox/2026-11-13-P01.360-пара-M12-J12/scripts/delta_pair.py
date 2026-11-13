"""Exact M12/J12 deltas against accepted M11/J11.

Only own delta.git is mutated; no implementation is executed.
Usage: spec-python -B delta_pair.py <evidence> <report directory>
"""
from pathlib import Path
import collections
import csv
import json
import subprocess
import sys

B, D = (Path(x).resolve() for x in sys.argv[1:3])
I = json.loads((B / 'IDENTITIES.json').read_text())
R = B / 'delta.git'
assert not R.exists()
subprocess.run(['git', 'init', '--quiet', '--bare', str(R)], check=True)


def g(*args):
    return subprocess.check_output(['git', '--git-dir', str(R), *args])


def tree(commit):
    result = {}
    for row in g('ls-tree', '-r', '-l', '-z', commit).split(b'\0'):
        if row:
            meta, name = row.split(b'\t', 1)
            mode, kind, blob, size = meta.decode().split()
            result[name.decode()] = {'mode': mode, 'type': kind, 'blob': blob, 'bytes': int(size)}
    return result


baselines = {'M11': Path('/home/pilot/P01.355-evidence/r2/IDENTITIES.json')}

result = {'to_C': I['C'], 'line_method': "git diff --no-renames --numstat -z; '-' means binary", 'baselines': {}}
table = []
for label, identity in baselines.items():
    old = json.loads(identity.read_text())
    views = {
        'M': (old['M_git'], old['M'], I['M_git'], I['M']),
        'J': (old['J_git'], old['J'], I['J_git'], I['J']),
        'J-input': (old['JI_git'], old['JI'], I['JI_git'], I['JI']),
    }
    out = {'from_C': old['C'], 'to_C': I['C'], 'views': {}}
    for name, (od, oc, nd, nc) in views.items():
        for gd, commit, side in ((od, oc, 'before'), (nd, nc, 'after')):
            subprocess.run(['git', '--git-dir', str(R), 'fetch', '--quiet', '--no-tags', gd,
                            commit + ':refs/heads/' + label + '-' + name + '-' + side], check=True)
        a, b = tree(oc), tree(nc)
        changes = []
        counts = collections.Counter()
        groups = collections.defaultdict(collections.Counter)
        nums = {}
        for row in g('diff', '--no-renames', '--numstat', '-z', oc, nc).split(b'\0'):
            if row:
                plus, minus, path = row.decode().split('\t', 2)
                nums[path] = plus, minus
        expected = {p for p in set(a) | set(b) if a.get(p) != b.get(p)}
        assert set(nums) == expected
        for path in sorted(expected):
            action = 'add' if path not in a else 'delete' if path not in b else 'modify'
            plus, minus = nums[path]
            changes.append({'path': path, 'action': action, 'lines_added': plus, 'lines_deleted': minus,
                            'before': a.get(path), 'after': b.get(path)})
            counts[action] += 1
            groups[path.split('/')[1]][action] += 1
            table.append([label, name, path, action, plus, minus,
                          a.get(path, {}).get('blob', '-'), b.get(path, {}).get('blob', '-')])
        out['views'][name] = {
            'before': {'commit': oc, 'files': len(a), 'bytes': sum(x['bytes'] for x in a.values())},
            'after': {'commit': nc, 'files': len(b), 'bytes': sum(x['bytes'] for x in b.values())},
            'counts': {key: counts[key] for key in ('add', 'modify', 'delete')},
            'lines_added': sum(int(v[0]) for v in nums.values() if v[0] != '-'),
            'lines_deleted': sum(int(v[1]) for v in nums.values() if v[1] != '-'),
            'binary_changes': sum(v[0] == '-' for v in nums.values()), 'groups': dict(groups), 'paths': changes}
    result['baselines'][label] = out
(B / 'DELTA-PAIR.json').write_text(json.dumps(result, ensure_ascii=False, indent=1) + '\n')
header = ['baseline', 'view', 'path', 'action', 'lines_added', 'lines_deleted', 'blob_before', 'blob_after']
for target in (B / 'DELTA-FILES.tsv', D / 'DELTA-FILES.tsv'):
    with target.open('w', newline='') as f:
        writer = csv.writer(f, delimiter='\t', lineterminator='\n')
        writer.writerow(header)
        writer.writerows(table)
lines = ['# P01.360 — дельта M12/J12 к M11/J11', '',
         f"C12: `{I['C']}`.", '',
         'Сравнены все пути, режимы и blob. Числа строк — `git diff --no-renames --numstat`; служебный COURSE_COMMIT учтён.', '',
         '| Базис | Выгрузка | Файлов до → после | Добавлено | Изменено | Удалено | +строк | −строк |',
         '|---|---|---:|---:|---:|---:|---:|---:|']
for label, out in result['baselines'].items():
    for name, row in out['views'].items():
        count = row['counts']
        lines.append(f"| {label} | {name} | {row['before']['files']} → {row['after']['files']} | {count['add']} | {count['modify']} | {count['delete']} | {row['lines_added']} | {row['lines_deleted']} |")
lines += ['', '[DELTA-FILES.tsv](DELTA-FILES.tsv) перечисляет каждый изменённый файл, число строк и оба blob. Машинная опись с режимами и размерами до/после — DELTA-PAIR.json в каталоге доказательств.', '',
          'Новая M отобрана текущим pair_m точного C с обязательным COURSE_COMMIT. J содержит всю Platform из C с маркером; J-вход — точный include собранного фильтра. Журнал изменений норм — [CHANGED-NORMS.md](CHANGED-NORMS.md).', '']
(D / 'DELTA-PAIR.md').write_text('\n'.join(lines))
print(json.dumps({label: {name: row['counts'] for name, row in out['views'].items()}
                  for label, out in result['baselines'].items()}, indent=1))
