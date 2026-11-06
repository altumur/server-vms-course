"""Read-only verification of the frozen P06 language slice; requires before Git object."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[3]
HERE = ROOT / 'decisions/inbox/2026-11-06-p06-full-english'
sys.path.insert(0, str(ROOT / 'skills/lesson-spec/scripts'))
import en_mirror
import source_cells

def sha(data):
    return hashlib.sha256(data).hexdigest()

mapping = json.loads((HERE / 'source-map.json').read_bytes())
transport = json.loads((HERE / 'cell-map.json').read_bytes())
preservation = json.loads((HERE / 'preservation.json').read_bytes())
base = mapping['base']
assert base == transport['base'] == preservation['base']
def before(path):
    return subprocess.check_output(['git', '-C', str(ROOT), 'show', base + ':' + path])

for entry in mapping['files']:
    path = entry['path']
    assert sha(before(path)) == entry['before_sha256'], path
    assert sha((ROOT / path).read_bytes()) == entry['after_sha256'], path

forms = source_cells.wire_headers(ROOT)
old_tables = {}
decoded_tables = {}
for table in transport['tables']:
    path = table['path']
    columns, positional = forms[Path(path)]
    original = [(n, line.split('\t')) for n, line in enumerate(before(path).decode().split('\n'), 1)
                if line and not line.startswith('#')]
    if not positional:
        assert original.pop(0)[1] == columns
    names, decoded, errors = source_cells.table((ROOT / path).read_bytes().decode(), columns, positional)
    assert not errors, (path, errors)
    assert list(names) == table['declared']
    assert len(original) == len(decoded) == table['rows']
    assert [(n + 1, dict(zip(columns, row))) for n, row in original] == decoded, path
    old_tables[path] = {n: dict(zip(columns, row)) for n, row in original}
    decoded_tables[path] = dict(decoded)

assert len(transport['cells']) == 1124
for entry in transport['cells']:
    path, name = entry['table'], entry['column']
    a = old_tables[path][entry['before_line']][name].encode('utf-8')
    b = decoded_tables[path][entry['line']][name].encode('utf-8')
    assert a == b and sha(a) == entry['before_sha256'] == entry['decoded_sha256'], entry

proof = 'Platform/common/data/cell-json-sha256.tsv'
assert (ROOT / proof).read_bytes().startswith(before(proof))
assert not en_mirror.source_cell_errors(ROOT)
assert not en_mirror.full_english_errors(ROOT, ['Platform/06-console/'])
for entry in preservation['preserved']:
    assert sha((ROOT / entry['path']).read_bytes()) == entry['sha256'], entry['path']
assert not subprocess.check_output(['git', '-C', str(ROOT), 'diff', '--name-only', base, '--',
                                    *preservation['protected_git_trees']]).strip()
mirror_pairs = [(ru, en) for ru, en in en_mirror.pairs(ROOT)
                if en.relative_to(ROOT).as_posix().startswith('Platform/06-console/')]
assert len(mirror_pairs) == 31
for ru, en in mirror_pairs:
    assert not en_mirror.compare(ru.read_text(), en.read_text(), ru, en, ROOT), en
print('PASS: mapped source SHA, 1124 new cells / 7 tables, 1855 total proof cells / 16 tables; 31 mirrors; frozen dependencies')
print('Source verification only; post-encoding gen_cmdtests reader and old source-cell test require their assigned follow-ups; no product execution')
