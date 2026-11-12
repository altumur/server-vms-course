#!/usr/bin/env python3
"""Reproduce the carrier-transfer comparison against the exact source commit."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[3]
BASE = '813ea367c7694ca85291fd0cf0ba52752905e1d2'
REJECTED = '8da025ff27b9dd66689bd72ce5df7ebbc083be9b'


def at(revision, path):
    return subprocess.check_output(['git', 'show', f'{revision}:{path}'], cwd=ROOT).decode()


def before(path):
    return at(BASE, path)


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


R147 = {
    '': '**Input phase deadlines.** The implementation MUST declare finite positive intervals: idle strictly below 60 s, headers strictly below 10 s, body strictly below 30 s, and refusal-drain strictly below 5 s. These intervals are measured by monotonic time.',
    'ru/': '**Сроки фаз ввода.** Реализация ДОЛЖНА объявить конечные положительные интервалы: простой строго меньше 60 с, заголовки строго меньше 10 с, тело строго меньше 30 с, слив отказа строго меньше 5 с. Эти интервалы измеряются по монотонным часам.'}
INTRO_DELTA = {
    '': ('This section is their only source; other text uses the names.',
         'The bounds on declared input-phase intervals come from [P/01.1-R147 in N2.1 Request parsing](../spec/01.1-store.norms.md#n21-request-parsing). This section is the source of the other thresholds; other text uses their names.'),
    'ru/': ('Этот раздел — их единственный источник; остальной текст использует имена.',
            'Пределы объявляемых интервалов фаз ввода заданы в [P/01.1-R147 раздела N2.1 «Разбор запроса»](../spec/01.1-store.norms.md#n21-разбор-запроса). Этот раздел — источник остальных порогов; остальной текст использует их имена.')}
PHASES = {
    '': {'BUDGET_IDLE': ('60 s', 'idle'), 'BUDGET_HEADERS': ('10 s', 'header'),
         'BUDGET_BODY': ('30 s', 'body'), 'BUDGET_DRAIN': ('5 s and at most the `-max-body` value in raw bytes', 'refusal-drain')},
    'ru/': {'BUDGET_IDLE': ('60 с', 'простоя'), 'BUDGET_HEADERS': ('10 с', 'заголовков'),
            'BUDGET_BODY': ('30 с', 'тела'), 'BUDGET_DRAIN': ('5 с и не более значения `-max-body` сырых байтов', 'слива отказа')}}


def r147_line(text, language):
    prefix = '**Input phase deadlines.**' if not language else '**Сроки фаз ввода.**'
    found = [line for line in text.splitlines() if line.startswith(prefix)]
    assert len(found) == 1
    return found[0]


def approved_q_row(old_row, language):
    cells = old_row.split('|')
    name = cells[1].strip(' `')
    old_value, interval = PHASES[language][name]
    assert cells[2] == ' '+old_value+' ', (name, 'previous exact phase bound')
    if not language:
        new_value = f'[The upper bound for the declared {interval} interval in P/01.1-R147](../spec/01.1-store.norms.md#n21-request-parsing)'
        if name == 'BUDGET_DRAIN':
            new_value += ' and at most the `-max-body` value in raw bytes'
    else:
        new_value = f'[Верхний предел объявляемого интервала {interval} из P/01.1-R147](../spec/01.1-store.norms.md#n21-разбор-запроса)'
        if name == 'BUDGET_DRAIN':
            new_value += ' и не более значения `-max-body` сырых байтов'
    cells[2] = ' '+new_value+' '
    assert not re.search(r'\b(?:60|10|30|5)\s*(?:s|с)\b', cells[2])
    return '|'.join(cells)


result = {'base': BASE, 'rejected': REJECTED, 'approved_answer': '2026-11-12T22:56:42Z',
          'tables': [], 'inventories': [], 'history': [], 'r147_delta': [], 'q_interval_delta': []}
for lang, names in [('', ['First approved budgets', 'Case groups', 'Measurement definitions', 'Probe debt']),
                    ('ru/', ['Первые утверждённые бюджеты', 'Группы случаев', 'Определения измерений', 'Долг проб'])]:
    oldpath = f'Platform/01-store/{lang}spec/production-acceptance.md'
    qpath = f'Platform/01-store/{lang}qualification/README.md'
    original = before(oldpath)
    qualified = (ROOT/qpath).read_text()
    for name in names:
        old_rows, new_rows = rows(original, name), rows(qualified, name)
        expected_rows = []
        for line in old_rows:
            key = line.split('|')[1].strip(' `')
            expected = approved_q_row(line, lang) if key in PHASES[lang] else line
            expected_rows.append(expected)
        assert expected_rows == new_rows, (lang, name, 'outside the four approved bound cells')
        result['tables'].append({'language': lang or 'en', 'section': name,
                                 'rows': [{'key': old.split('|')[1].strip(), 'source_sha256': digest(old),
                                           'current_sha256': digest(new), 'equal': old == new,
                                           'approved_bound_reference_delta': old != new}
                                          for old, new in zip(old_rows, new_rows)], 'matches_approved_delta': True})
    for name in (['Qualified inputs', 'Clocks in a group', 'Evidence and outcomes', 'Related parsing and scope'] if not lang
                 else ['Квалифицированные входы', 'Часы в группе', 'Доказательства и исходы', 'Связанный разбор и область']):
        old_text, new_text = section(original, name), section(qualified, name)
        assert old_text == new_text, (lang, name)
        result['tables'].append({'language': lang or 'en', 'section': name, 'sha256': digest(old_text), 'equal': True})
    rejected_q = at(REJECTED, qpath)
    expected_rejected = original.replace('canonical `spec/production-acceptance.md`', 'canonical `qualification/README.md`')
    expected_rejected = expected_rejected.replace('[HTTP contract](01-store.api.openapi.yaml)', '[HTTP contract](../spec/01-store.api.openapi.yaml)')
    expected_rejected = expected_rejected.replace('производный от `spec/production-acceptance.md`', 'производный от `qualification/README.md`')
    assert rejected_q == expected_rejected, (lang, 'rejected Q versus the original carrier')
    intro_old, intro_new = INTRO_DELTA[lang]
    assert rejected_q.count(intro_old) == 1
    expected_q = rejected_q.replace(intro_old, intro_new)
    for key in PHASES[lang]:
        old_row = next(line for line in rejected_q.splitlines() if line.startswith(f'| `{key}` | '))
        new_row = approved_q_row(old_row, lang)
        assert expected_q.count(old_row) == 1
        expected_q = expected_q.replace(old_row, new_row)
        result['q_interval_delta'].append({'language': lang or 'en', 'name': key, 'old': old_row, 'new': new_row,
                                          'only_bound_cell_changed': True, 'no_numeric_duplicate': True})
    assert qualified == expected_q, (lang, 'unapproved Q change outside four cells and source sentence')
    normpath = f'Platform/01-store/{lang}spec/01.1-store.norms.md'
    current_norm = (ROOT/normpath).read_text()
    rejected_norm = at(REJECTED, normpath)
    previous_r147 = r147_line(rejected_norm, lang)
    assert r147_line(current_norm, lang) == R147[lang]
    assert ('### N2.1 Request parsing' if not lang else '### N2.1 Разбор запроса') in current_norm
    assert current_norm == rejected_norm.replace(previous_r147, R147[lang]), (lang, 'unapproved norm change')
    result['r147_delta'].append({'language': lang or 'en', 'old': previous_r147, 'new': R147[lang],
                                'finite_positive': True, 'strict_bounds': [60, 10, 30, 5],
                                'monotonic_time_preserved': True, 'no_q_dependency': True})
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
    marker_delta = path in ('Platform/01-store/forms/stages.tsv', 'Platform/01-store/forms/stages.kit.tsv')
    if marker_delta:
        old_comment = '# Functional gates and engineering group preparation are separate from production qualification: qualification/README.md.'
        new_comment = '# Functional gates and engineering group preparation are separate from production qualification: qualification/README.md (judge-only: qualification procedures).'
        assert expected.count(old_comment) == 1
        expected = expected.replace(old_comment, new_comment)
    assert new_text == expected, (path, 'non-address or marker change')
    result['inventories'].append({'path': path, 'only_source_address_changed': not marker_delta,
                                  'source_address_and_judge_only_marker': marker_delta})

for lang, marker in [('', ' (judge-only: qualification procedures)'), ('ru/', ' (только для судьи: процедуры квалификации)')]:
    for chapter in ['1', '3']:
        path = f'Platform/01-store/{lang}spec/01.{chapter}-store.norms.md'
        normalized = (ROOT/path).read_text()
        if chapter == '1':
            assert normalized.count(R147[lang]) == 1
            normalized = normalized.replace(R147[lang], r147_line(at(REJECTED, path), lang))
        normalized = normalized.replace(marker, '')
        normalized = normalized.replace('../qualification/README.md', 'production-acceptance.md')
        normalized = normalized.replace('`qualification/README.md`', '`spec/production-acceptance.md`')
        assert normalized == before(path), (path, 'non-address change')
        result['inventories'].append({'path': path, 'only_source_address_and_marker_changed': chapter != '1',
                                      'exact_approved_r147_delta': chapter == '1'})
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
assert 'strictly below its corresponding budget' not in r147_line((ROOT/'Platform/01-store/spec/01.1-store.norms.md').read_text(), '')
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
norm_dependency = 'Platform/01-store/spec/01.1-store.norms.md'
assert norm_dependency in paths
rejected_filter = json.loads(at(REJECTED, 'Platform/common/qualification-input-filter.json'))
assert [row for row in manifest['files'] if row['path'] != norm_dependency] == rejected_filter['files']
assert next(row for row in manifest['files'] if row['path'] == norm_dependency)['disposition'] == 'include'
result['filter'] = {'explicit_files': len(paths), 'existing_unique_english_paths': True,
                    'r147_source_included': norm_dependency, 'all_previous_records_unchanged': True}
for lang in ('', 'ru/'):
    path = f'Platform/01-store/{lang}README.md'
    rejected_readme = at(REJECTED, path)
    assert rejected_readme.count('spec/../qualification/README.md') == 1
    assert (ROOT/path).read_text() == rejected_readme.replace('spec/../qualification/README.md', 'qualification/README.md')
    result['inventories'].append({'path': path, 'only_redundant_path_segment_removed': True})

# The corrected requirement, four replaced Q rows, source sentence and minor links are literal history.
current_history = (ROOT/'decisions/journal/platform/01-store/history.tsv').read_text()
current_chapter_history = (ROOT/'decisions/journal/platform/01-store/history-1.tsv').read_text()
saved_rows = [line.split('\t', 4)[4] for line in (current_history+'\n'+current_chapter_history).splitlines()
              if len(line.split('\t')) == 5 and '\tP01.294 attempt 2;' in line]
for lang in ('', 'ru/'):
    normpath = f'Platform/01-store/{lang}spec/01.1-store.norms.md'
    assert r147_line(at(REJECTED, normpath), lang) in saved_rows
    qpath = f'Platform/01-store/{lang}qualification/README.md'
    rejected_q = at(REJECTED, qpath)
    for key in PHASES[lang]:
        old_row = next(line for line in rejected_q.splitlines() if line.startswith(f'| `{key}` | '))
        assert old_row in saved_rows
    old_intro_line = next(line for line in rejected_q.splitlines() if INTRO_DELTA[lang][0] in line)
    assert old_intro_line in saved_rows
    readme_path = f'Platform/01-store/{lang}README.md'
    old_readme_line = next(line for line in at(REJECTED, readme_path).splitlines() if 'spec/../qualification/README.md' in line)
    assert old_readme_line in saved_rows
for path in ('Platform/01-store/forms/stages.tsv', 'Platform/01-store/forms/stages.kit.tsv'):
    old_comment = next(line for line in at(REJECTED, path).splitlines() if 'production qualification: qualification/README.md.' in line)
    assert old_comment in saved_rows
result['approved_delta_history_literal'] = True
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
