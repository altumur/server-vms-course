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
REJECTED2 = '38c759f3f7c11daadc123354be2dc6d20589d6ab'


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


def r147_q_row(old_row, language):
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


R234 = {
    '': 'Discard stops at the declared body length when framing supplies one. Discard stops earlier at the declared raw-byte limit; this limit MUST NOT exceed the configured `-max-body` value. Discard stops earlier at the absolute monotonic drain deadline. A chunked sender need not send a terminal chunk for discard to finish. The drain volume and time are declared in item 9 of «Implementation decides».',
    'ru/': 'Слив прекращается на заявленной длине тела, если framing задаёт длину. Слив прекращается раньше при достижении объявленного предела сырых байтов; этот предел НЕ ДОЛЖЕН превышать настроенное значение `-max-body`. Слив прекращается раньше при достижении абсолютного монотонного срока слива. Для завершения слива chunked отправитель не обязан прислать завершающую часть. Объём и срок слива объявлены в п. 9 «Решает реализация».'}
MANAGER_RULE = {
    '': 'The qualification stand sets the actual manager stop deadline consistently with `BUDGET_STOP`.',
    'ru/': 'Стенд квалификации задаёт фактический срок остановки менеджера согласованно с `BUDGET_STOP`.'}
SOURCE_RULE3 = {'': 'The bounds on declared input-phase intervals come from [P/01.1-R147 in N2.1 Request parsing](../spec/01.1-store.norms.md#n21-request-parsing), and the bound on the declared raw-byte drain limit comes from [P/01.1-R234 in N2.1 Request parsing](../spec/01.1-store.norms.md#n21-request-parsing). Other named normative limits retain their existing sources; this section defines the measurement thresholds and other text uses their names.', 'ru/': 'Пределы объявляемых интервалов фаз ввода заданы в [P/01.1-R147 раздела N2.1 «Разбор запроса»](../spec/01.1-store.norms.md#n21-разбор-запроса), предел объявляемого объёма сырого слива — в [P/01.1-R234 раздела N2.1 «Разбор запроса»](../spec/01.1-store.norms.md#n21-разбор-запроса). Остальные названные нормативные пределы сохраняют свои источники; этот раздел задаёт измерительные пороги, а остальной текст использует их имена.'}
RAW_LIMIT = {
    '': (' and at most the `-max-body` value in raw bytes',
         ' and [the bound on the declared raw-byte drain limit in P/01.1-R234](../spec/01.1-store.norms.md#n21-request-parsing)'),
    'ru/': (' и не более значения `-max-body` сырых байтов',
            ' и [предел объявляемого объёма сырого слива по P/01.1-R234](../spec/01.1-store.norms.md#n21-разбор-запроса)')}


def r234_line(text, language):
    prefix = 'Discard stops at the declared body length' if not language else 'Слив прекращается на заявленной длине тела'
    found = [line for line in text.splitlines() if line.startswith(prefix)]
    assert len(found) == 1
    return found[0]


def raw_reference_row(previous, language):
    old_value, new_value = RAW_LIMIT[language]
    assert previous.startswith('| `BUDGET_DRAIN` | ') and previous.count(old_value) == 1
    return previous.replace(old_value, new_value)


def approved_q_row(old_row, language):
    new = r147_q_row(old_row, language)
    if old_row.startswith('| `BUDGET_DRAIN` | '):
        new = raw_reference_row(new, language)
        assert '-max-body' not in new
    return new


def approved_stop_row(old_row, language):
    expected = ('| `BUDGET_STOP` | 15 s | `graceful_stop_elapsed` | RUN-L03 | limit `norm`; margin `judgement` |' if not language
                else '| `BUDGET_STOP` | 15 с | `graceful_stop_elapsed` | RUN-L03 | предел `norm`; запас `judgement` |')
    assert old_row == expected
    cells = old_row.split('|')
    assert cells[5] == (' limit `norm`; margin `judgement` ' if not language else ' предел `norm`; запас `judgement` ')
    cells[5] = ' `judgement` '
    return '|'.join(cells)


def manager_rule_insert(text, language):
    retained = 'The R141 minimum is strictly more than' if not language else 'Минимум R141 — строго больше'
    assert text.count(retained) == 1 and MANAGER_RULE[language] not in text
    return text.replace(retained, MANAGER_RULE[language]+'\n\n'+retained)


result = {'base': BASE, 'rejected': REJECTED, 'rejected_attempt_2': REJECTED2,
          'approved_answers': ['2026-11-12T22:56:42Z', '2026-11-12T23:14:48Z'],
          'tables': [], 'inventories': [], 'history': [], 'r147_delta': [], 'q_interval_delta': [],
          'r234_delta': [], 'attempt_3_q_delta': [], 'stop_obligations_unchanged': []}
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
            expected = (approved_q_row(line, lang) if key in PHASES[lang] else
                        approved_stop_row(line, lang) if key == 'BUDGET_STOP' else line)
            expected_rows.append(expected)
        assert expected_rows == new_rows, (lang, name, 'outside the four phase cells and STOP basis')
        result['tables'].append({'language': lang or 'en', 'section': name,
                                 'rows': [{'key': old.split('|')[1].strip(), 'source_sha256': digest(old),
                                           'current_sha256': digest(new), 'equal': old == new,
                                           'approved_bound_reference_delta': old != new and old.split('|')[1].strip(' `') in PHASES[lang],
                                           'approved_stop_basis_delta': old.split('|')[1].strip(' `') == 'BUDGET_STOP'}
                                          for old, new in zip(old_rows, new_rows)], 'matches_approved_delta': True})
    for name in (['Qualified inputs', 'Clocks in a group', 'Evidence and outcomes', 'Related parsing and scope'] if not lang
                 else ['Квалифицированные входы', 'Часы в группе', 'Доказательства и исходы', 'Связанный разбор и область']):
        old_text, new_text = section(original, name), section(qualified, name)
        qualified_inputs = name in ('Qualified inputs', 'Квалифицированные входы')
        expected_text = manager_rule_insert(old_text, lang) if qualified_inputs else old_text
        assert expected_text == new_text, (lang, name, 'outside the one approved manager sentence')
        result['tables'].append({'language': lang or 'en', 'section': name,
                                 'source_sha256': digest(old_text), 'current_sha256': digest(new_text),
                                 'equal': old_text == new_text, 'approved_manager_rule_inserted': qualified_inputs})
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
        new_row = r147_q_row(old_row, lang)
        assert expected_q.count(old_row) == 1
        expected_q = expected_q.replace(old_row, new_row)
        result['q_interval_delta'].append({'slice': 'attempt_2', 'language': lang or 'en', 'name': key, 'old': old_row, 'new': new_row,
                                          'only_bound_cell_changed': True, 'no_numeric_duplicate': True})
    second_q = at(REJECTED2, qpath)
    assert second_q == expected_q, (lang, 'second rejected Q versus the approved R147 delta')
    old_drain = next(line for line in second_q.splitlines() if line.startswith('| `BUDGET_DRAIN` | '))
    old_stop = next(line for line in second_q.splitlines() if line.startswith('| `BUDGET_STOP` | '))
    new_drain = raw_reference_row(old_drain, lang)
    new_stop = approved_stop_row(old_stop, lang)
    assert second_q.count(INTRO_DELTA[lang][1]) == 1
    expected_q = manager_rule_insert(second_q.replace(old_drain, new_drain).replace(old_stop, new_stop), lang)
    expected_q = expected_q.replace(INTRO_DELTA[lang][1], SOURCE_RULE3[lang])
    assert qualified == expected_q, (lang, 'unapproved Q change outside DRAIN raw cell, STOP basis, manager rule and source phrase')
    result['attempt_3_q_delta'].append({'language': lang or 'en', 'drain_old': old_drain, 'drain_new': new_drain,
                                      'stop_old': old_stop, 'stop_new': new_stop, 'manager_rule': MANAGER_RULE[lang],
                                      'source_phrase_old': INTRO_DELTA[lang][1], 'source_phrase_new': SOURCE_RULE3[lang],
                                      'remaining_q_unchanged': True})
    normpath = f'Platform/01-store/{lang}spec/01.1-store.norms.md'
    current_norm = (ROOT/normpath).read_text()
    rejected_norm = at(REJECTED, normpath)
    previous_r147 = r147_line(rejected_norm, lang)
    assert r147_line(current_norm, lang) == R147[lang]
    assert ('### N2.1 Request parsing' if not lang else '### N2.1 Разбор запроса') in current_norm
    second_norm = at(REJECTED2, normpath)
    assert second_norm == rejected_norm.replace(previous_r147, R147[lang]), (lang, 'previous R147 correction changed')
    assert r147_line(second_norm, lang) == r147_line(current_norm, lang)
    previous_r234 = r234_line(second_norm, lang)
    assert r234_line(current_norm, lang) == R234[lang]
    assert current_norm == second_norm.replace(previous_r234, R234[lang]), (lang, 'unapproved change beyond exact R234')
    result['r234_delta'].append({'language': lang or 'en', 'old': previous_r234, 'new': R234[lang],
                                'r147_unchanged': True, 'remaining_norms_unchanged': True})
    for relative in ('spec/01.3-store.norms.md', 'spec/production-acceptance.md', 'lifecycle.md', 'spec/01-store.README.md'):
        unchanged_path = f'Platform/01-store/{lang}{relative}'
        content = (ROOT/unchanged_path).read_text()
        assert content == at(REJECTED2, unchanged_path), (unchanged_path, 'stop obligation changed')
        result['stop_obligations_unchanged'].append({'path': unchanged_path, 'sha256': digest(content), 'equal_to_attempt_2': True})
    stop_norm = (ROOT/'Platform/01-store/spec/01.3-store.norms.md').read_text()
    for req in ('P/01.3-R034', 'P/01.3-R277'):
        match = re.search(r'<!-- req: '+re.escape(req)+r' -->\n(.*?)(?=\n<!-- req:|\Z)', stop_norm, re.S)
        assert match
        result['stop_obligations_unchanged'].append({'requirement': req, 'sha256': digest(match[1]), 'unchanged': True})
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
            assert normalized.count(R234[lang]) == 1
            normalized = normalized.replace(R234[lang], r234_line(at(REJECTED, path), lang))
        normalized = normalized.replace(marker, '')
        normalized = normalized.replace('../qualification/README.md', 'production-acceptance.md')
        normalized = normalized.replace('`qualification/README.md`', '`spec/production-acceptance.md`')
        assert normalized == before(path), (path, 'non-address change')
        result['inventories'].append({'path': path, 'only_source_address_and_marker_changed': chapter != '1',
                                      'exact_approved_r147_and_r234_delta': chapter == '1'})
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
attempt3_saved = [line.split('\t', 4)[4] for line in (current_history+'\n'+current_chapter_history).splitlines()
                  if len(line.split('\t')) == 5 and '\tP01.294 attempt 3;' in line]
for lang in ('', 'ru/'):
    normpath = f'Platform/01-store/{lang}spec/01.1-store.norms.md'
    assert r234_line(at(REJECTED2, normpath), lang) in attempt3_saved
    qpath = f'Platform/01-store/{lang}qualification/README.md'
    second_q = at(REJECTED2, qpath)
    for key in ('BUDGET_DRAIN', 'BUDGET_STOP'):
        old_row = next(line for line in second_q.splitlines() if line.startswith(f'| `{key}` | '))
        assert old_row in attempt3_saved
    old_intro_line = next(line for line in second_q.splitlines() if INTRO_DELTA[lang][1] in line)
    assert old_intro_line in attempt3_saved
assert '-' in attempt3_saved
result['approved_attempt_3_history_literal'] = True
assert manifest == json.loads(at(REJECTED2, 'Platform/common/qualification-input-filter.json'))
result['filter']['r234_source_already_included'] = norm_dependency

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
