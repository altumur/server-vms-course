#!/usr/bin/env python3
"""Reproduce the carrier-transfer comparison against the exact source commit."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[3]
BASE = '813ea367c7694ca85291fd0cf0ba52752905e1d2'


def before(path):
    return subprocess.check_output(['git', 'show', f'{BASE}:{path}'], cwd=ROOT).decode()


def section(text, name):
    marker = re.search(r'^#{2,3} '+re.escape(name)+r'\n', text, re.M)
    assert marker, name
    tail = text[marker.end():]
    end = re.search(r'^#{2,3} ', tail, re.M)
    return tail[:end.start()] if end else tail


def rows(text, name):
    lines = section(text, name).splitlines()
    separator = re.compile(r'^\|[- :|]+\|$')
    return [line for i, line in enumerate(lines) if line.startswith('| ') and not separator.match(line)
            and not (i + 1 < len(lines) and separator.match(lines[i + 1]))]


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


result = {'base': BASE, 'tables': [], 'inventories': [], 'history': []}
for lang, names in [('', ['First approved budgets', 'Case groups', 'Measurement definitions', 'Probe debt']),
                    ('ru/', ['Первые утверждённые бюджеты', 'Группы случаев', 'Определения измерений', 'Долг проб'])]:
    oldpath = f'Platform/01-store/{lang}spec/production-acceptance.md'
    qpath = f'Platform/01-store/{lang}qualification/README.md'
    original = before(oldpath)
    qualified = (ROOT/qpath).read_text()
    for name in names:
        old_rows, new_rows = rows(original, name), rows(qualified, name)
        assert old_rows == new_rows, (lang, name)
        result['tables'].append({'language': lang or 'en', 'section': name,
                                 'rows': [{'key': line.split('|')[1].strip(), 'sha256': digest(line), 'equal': True}
                                          for line in old_rows], 'equal': True})
    for name in (['Qualified inputs', 'Clocks in a group', 'Evidence and outcomes', 'Related parsing and scope'] if not lang
                 else ['Квалифицированные входы', 'Часы в группе', 'Доказательства и исходы', 'Связанный разбор и область']):
        old_text, new_text = section(original, name), section(qualified, name)
        assert old_text == new_text, (lang, name)
        result['tables'].append({'language': lang or 'en', 'section': name, 'sha256': digest(old_text), 'equal': True})
    # The previous complete source and translation are recoverable from literal journal rows.
    journal = (ROOT/'decisions/journal/platform/01-store/history.tsv').read_text()
    saved = [line.split('\t', 4)[4] for line in journal.splitlines() if '\tP01.294;' in line]
    for line in original.splitlines():
        if line.strip():
            assert line in saved, (oldpath, 'history', line)
    result['history'].append({'source': oldpath, 'all_nonempty_lines_preserved': True})

for path in ['Platform/01-store/forms/production.tsv', 'Platform/01-store/forms/production/bindings.tsv',
             'Platform/01-store/forms/process-1.1.scenarios.tsv', 'Platform/01-store/forms/process-1.3.scenarios.tsv',
             'Platform/01-store/forms/stages.tsv', 'Platform/01-store/forms/stages.kit.tsv',
             'Platform/01-store/forms/targets.tsv']:
    old_text = before(path)
    new_text = (ROOT/path).read_text()
    expected = old_text.replace('Platform/01-store/spec/production-acceptance.md', 'Platform/01-store/qualification/README.md')
    expected = expected.replace('production-acceptance.md#case-groups', 'qualification/README.md#case-groups')
    expected = expected.replace('production-acceptance.md#clocks-in-a-group', 'qualification/README.md#clocks-in-a-group')
    expected = expected.replace('spec/production-acceptance.md', 'qualification/README.md')
    assert new_text == expected, (path, 'non-address change')
    result['inventories'].append({'path': path, 'only_source_address_changed': True})

for lang, marker in [('', ' (judge-only: qualification procedures)'), ('ru/', ' (только для судьи: процедуры квалификации)')]:
    for chapter in ['1', '3']:
        path = f'Platform/01-store/{lang}spec/01.{chapter}-store.norms.md'
        normalized = (ROOT/path).read_text().replace(marker, '')
        normalized = normalized.replace('../qualification/README.md', 'production-acceptance.md')
        normalized = normalized.replace('`qualification/README.md`', '`spec/production-acceptance.md`')
        assert normalized == before(path), (path, 'non-address change')
        result['inventories'].append({'path': path, 'only_source_address_and_marker_changed': True})
    for relative in ('acceptance/1/README.md', 'acceptance/3/README.md', 'probes/README.md'):
        path = f'Platform/01-store/{lang}{relative}'
        normalized = (ROOT/path).read_text().replace(marker, '')
        normalized = normalized.replace('qualification/README.md', 'spec/production-acceptance.md')
        assert normalized == before(path), (path, 'non-address change')
        result['inventories'].append({'path': path, 'only_source_address_and_marker_changed': True})

for lang, marker in [('', ' (judge-only: qualification procedures)'), ('ru/', ' (только для судьи: процедуры квалификации)')]:
    path = f'Platform/common/{lang}acceptance/seams.md'
    normalized = (ROOT/path).read_text().replace(marker, '')
    normalized = normalized.replace('qualification/README.md', 'spec/production-acceptance.md')
    assert normalized == before(path), (path, 'non-address change')
    result['inventories'].append({'path': path, 'only_source_address_and_marker_changed': True})

m = (ROOT/'Platform/01-store/spec/production-acceptance.md').read_text()
assert not re.search(r'RUN-|BUDGET_|WORKLOAD_|ADR-0|## (Qualified inputs|First approved budgets|Case groups|Measurement definitions|Public executable probes|Evidence and outcomes)', m)
assert 'strictly below its corresponding budget' in (ROOT/'Platform/01-store/spec/01.1-store.norms.md').read_text()
manifest = json.loads((ROOT/'Platform/common/qualification-input-filter.json').read_text())
assert manifest['version'] == 1
paths = [row['path'] for row in manifest['files']]
assert len(paths) == len(set(paths))
for row in manifest['files']:
    assert row['disposition'] == 'include' and row['basis']
    assert (ROOT/row['path']).is_file() and '/ru/' not in row['path']
journal_path = 'decisions/journal/platform/01-store/history.tsv'
old_journal = before(journal_path).splitlines()
new_journal = (ROOT/journal_path).read_text().splitlines()
readdressed = []
for old_row, new_row in zip(old_journal, new_journal):
    if old_row != new_row:
        old_cells, new_cells = old_row.split('\t'), new_row.split('\t')
        assert old_cells[0] == new_cells[0] and old_cells[2:] == new_cells[2:]
        export_address = re.fullmatch(r'forms/export\.json#/(model|judge)/(\d+)(/.*)?', old_cells[1])
        if export_address:
            side, index, suffix = export_address.groups()
            old_export = json.loads(before('Platform/01-store/forms/export.json'))
            new_export = json.loads((ROOT/'Platform/01-store/forms/export.json').read_text())
            carrier = old_export[side][int(index)]['path']
            new_index = next(i for i, row in enumerate(new_export[side]) if row['path'] == carrier)
            assert new_cells[1] == f'forms/export.json#/{side}/{new_index}{suffix or ""}'
        else:
            assert new_cells[1] == old_cells[1].replace('spec/production-acceptance.md#', 'qualification/README.md#')
        readdressed.append({'old': old_cells[1], 'new': new_cells[1], 'removed_unchanged': True})
result['historical_carrier_addresses'] = readdressed
result['filter'] = {'explicit_files': len(paths), 'existing_unique_english_paths': True}
old_export = json.loads(before('Platform/01-store/forms/export.json'))
new_export = json.loads((ROOT/'Platform/01-store/forms/export.json').read_text())
q_source = 'Platform/01-store/qualification/README.md'
q_translation = 'Platform/01-store/ru/qualification/README.md'
result['export_q_records'] = []
for side in ('model', 'judge'):
    retained = [row for row in new_export[side] if row['path'] not in (q_source, q_translation)]
    assert retained == old_export[side], (side, 'previous export record changed')
    for path in (q_source, q_translation):
        record = next(row for row in new_export[side] if row['path'] == path)
        expected = 'judge_only' if side == 'model' else ('exclude' if path == q_translation else 'include')
        assert record['disposition'] == expected
        result['export_q_records'].append({'side': side, 'path': path, 'disposition': expected})
m_groups = {
    'RUN-W01': 'Incremental write cost', 'RUN-W02': 'Import validation and cost',
    'RUN-W03': 'Replay retention', 'RUN-W04': 'Replay resources',
    'RUN-T01': 'Early refusal', 'RUN-T02': 'Early refusal', 'RUN-T03': 'Input phase deadlines',
    'RUN-L01': 'Consistent copy and publication', 'RUN-L02': 'Snapshot output and release',
    'RUN-L03': 'Graceful stop', 'RUN-F01': 'Proven pre-effect failure',
    'RUN-F02': 'Unknown storage result', 'RUN-F03': 'Complete record and failed barrier',
    'RUN-F04': 'Batch and id recovery', 'RUN-H01': 'Backup CLI and artifact',
    'RUN-H02': 'HTTP copy', 'RUN-H03': 'Incomplete copy output'}
result['m_obligations'] = []
for group, heading in m_groups.items():
    body = section(m, heading)
    assert body.strip(), group
    result['m_obligations'].append({'group': group, 'section': heading, 'sha256': digest(body),
                                    'meaning_review': 'See the group-by-group matrix in the task note.'})
result['m_without_procedure_tables'] = True
result['pass'] = True
print(json.dumps(result, ensure_ascii=False, indent=2))
