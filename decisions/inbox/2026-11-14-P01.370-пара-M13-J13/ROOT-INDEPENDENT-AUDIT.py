from pathlib import Path
import hashlib
import json
import os
import stat
import subprocess

B = Path('/home/pilot/P01.370-evidence')
W = Path('/home/pilot/wt-task-P01.370')
i = json.loads((B / 'IDENTITIES.json').read_text())


def git(repo, *args):
    return subprocess.check_output(['git', '--git-dir', str(repo), *args])


def tree(repo, ref, *paths):
    result = {}
    for line in git(repo, 'ls-tree', '-rz', ref, *paths).split(b'\0'):
        if not line:
            continue
        meta, path = line.split(b'\t', 1)
        mode, kind, oid = meta.decode().split()
        assert kind == 'blob' and mode in ('100644', '100755')
        result[path.decode()] = (mode, oid)
    return result


source = tree(B / 'source.git', i['C'], 'Platform')
j = tree(i['J_git'], i['J'])
m = tree(i['M_git'], i['M'])
ji = tree(i['JI_git'], i['JI'])
marker = 'Platform/COURSE_COMMIT'
expected_j = {p: meta for p, meta in source.items() if p.startswith('Platform/')}
assert marker not in expected_j
assert {p: meta for p, meta in j.items() if p != marker} == expected_j
assert git(i['J_git'], 'show', i['J'] + ':' + marker).decode().strip() == i['C']
assert m.items() <= j.items()
assert ji.items() <= j.items()
assert not any('/ru/' in p or '/qualification/' in p for p in m)
assert 'Platform/common/vectors/log-mask/cases.tsv' not in m
assert 'Platform/common/vectors/log-mask/cases.tsv' in ji
assert git(i['JI_git'], 'show', i['JI'] + ':Platform/common/vectors/log-mask/cases.tsv') == git(B / 'source.git', 'show', i['C'] + ':Platform/common/vectors/log-mask/cases.tsv')
common = json.loads(git(B / 'source.git', 'show', i['C'] + ':Platform/common/acceptance/judge-input-filter.json'))
rows = list(common['files'])
for p in source:
    if p.startswith('Platform/') and p.endswith('/forms/export.json'):
        rows += json.loads(git(B / 'source.git', 'show', i['C'] + ':' + p))['judge']
assert len({r['path'] for r in rows}) == len(rows)
expected_ji = {r['path'] for r in rows if r['disposition'] == 'include'} | {marker}
assert set(ji) == expected_ji
results = {}
for label, entries in (('M', m), ('JI', ji)):
    root = B / label
    actual = {str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}
    assert actual == set(entries)
    assert not (root / '.git').exists()
    manifests = []
    for p in [root, *root.rglob('*')]:
        assert not p.is_symlink()
        mode = stat.S_IMODE(p.stat().st_mode)
        if p.is_dir():
            assert mode == 0o555
            continue
        relative = str(p.relative_to(root))
        gitmode, oid = entries[relative]
        wantmode = 0o555 if gitmode == '100755' else 0o444
        assert mode == wantmode
        data = p.read_bytes()
        actual_blob = hashlib.sha1(b'blob %d\0' % len(data) + data).hexdigest()
        assert actual_blob == oid
        manifests.append({'path': relative, 'blob': oid, 'sha256': hashlib.sha256(data).hexdigest(), 'mode': oct(mode)})
    results[label] = {'count': len(entries), 'physical_blobs_match': True, 'readonly_modes_match': True,
                      'manifest_sha256': hashlib.sha256(json.dumps(sorted(manifests, key=lambda r: r['path']), sort_keys=True).encode()).hexdigest()}
result = {'C': i['C'], 'M': i['M'], 'J': i['J'], 'JI': i['JI'], 'J_exact_Platform_C': True,
          'M_subset_J_mode_blob': True, 'JI_exact_filter_include': True,
          'new_log_mask_vectors_in_JI': True, 'unpacked': results, 'OK': True}
(B / 'ROOT-INDEPENDENT-AUDIT.json').write_text(json.dumps(result, indent=1) + '\n')
print(json.dumps(result))
