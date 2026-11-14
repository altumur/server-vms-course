#!/usr/bin/env python3
"""Повторный разбор сохранённой истории; стенд и кандидат не запускаются.

Независимая проверка: полный перебор порядков четырёх операций регистра.
Отбрасывание остальных операций допустимо только после доказательства, что
ни одна другая запись всей истории не может вернуть наблюдаемое старое значение.
"""
import argparse
from functools import lru_cache
import gzip
import hashlib
import itertools
import json
from pathlib import Path
import subprocess


def sha(data):
    return hashlib.sha256(data).hexdigest()


def orders(ops):
    """Все последовательные исполнения, сохраняющие порядок неперекрытия."""
    answer, chronological = [], 0
    for perm in itertools.permutations(ops):
        position = {x['id']: i for i, x in enumerate(perm)}
        if any(a['t1'] < b['t0'] and position[a['id']] > position[b['id']]
               for a in ops for b in ops):
            continue
        chronological += 1
        state = ''
        for op in perm:
            if op['f'] == 'put':
                state = op['v']
            elif op['f'] == 'read' and op['out'] != state:
                break
        else:
            answer.append([x['id'] for x in perm])
    return {'orders_total': len(list(itertools.permutations(ops))),
            'orders_preserving_real_time': chronological,
            'legal_orders': answer}


def git_blob(repo, commit, name):
    return subprocess.check_output(['git', '--git-dir=' + str(repo),
                                    'show', commit + ':' + name])


def check_window(ops, initial):
    """Точный поиск по состоянию (значение, версия) в малом окне.

    info допускает отсутствие эффекта либо один эффект после вызова без
    верхней границы времени. Исходный checker и его отсечение не используются.
    """
    mandatory = sum(1 << i for i, op in enumerate(ops) if op['res'] != 'info')
    predecessors = [sum(1 << j for j, other in enumerate(ops)
                        if other['res'] != 'info' and other['t1'] < op['t0'])
                    for op in ops]

    @lru_cache(None)
    def visit(done, state):
        if done & mandatory == mandatory:
            return ()
        for i, op in enumerate(ops):
            if done & (1 << i) or predecessors[i] & done != predecessors[i]:
                continue
            next_state = state
            if op['res'] == 'fail':
                if op['f'] == 'cas' and op['why'] == 'cas_mismatch':
                    if state[1] == op['ei']:
                        continue
            elif op['f'] == 'read':
                if state != (op['out'], op.get('idx', '')):
                    continue
            else:
                if op['f'] == 'cas' and state[1] != op['ei']:
                    continue
                next_state = (('', '') if op['f'] == 'del' else
                              (op['v'], op.get('idx', 'unknown:' + str(op['id']))))
            rest = visit(done | (1 << i), next_state)
            if rest is not None:
                return (op['id'],) + rest
        return None

    result = visit(0, initial)
    return {'linearizable': result is not None, 'legal_order': result,
            'search_states': visit.cache_info().currsize}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--history', type=Path, default=Path(
        '/home/pilot/owner-receipts/P01.334-full82-20261113T2133Z/out/soak/long'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source = args.history
    published = dict((name, digest) for digest, name in
                     (line.split(None, 1) for line in
                      (source / 'SHA256SUMS').read_text().splitlines()))
    original = {x['name']: x for x in json.loads(
        (source / 'SOURCE-LOG-MANIFEST.json').read_text())}
    hashes, key, lines, seen_ids = {}, [], 0, set()
    for path in sorted(source.glob('ops-*.jsonl.gz')):
        packed = path.read_bytes()
        digest = sha(packed)
        assert published[path.name] == digest, path
        raw_hash, raw_bytes = hashlib.sha256(), 0
        with gzip.open(path, 'rb') as stream:
            for line in stream:
                raw_hash.update(line)
                raw_bytes += len(line)
                lines += 1
                op = json.loads(line)
                if op['k'] == 'soak/k001':
                    assert op['id'] not in seen_ids
                    seen_ids.add(op['id'])
                    assert op['t0'] <= op['t1']
                    key.append(op)
        name = path.name[:-3]
        assert original[name]['sha256'] == raw_hash.hexdigest(), path
        assert original[name]['bytes'] == raw_bytes, path
        hashes[path.name] = {'sha256': digest,
                             'original_sha256': raw_hash.hexdigest(),
                             'original_bytes': raw_bytes}

    key.sort(key=lambda x: (x['t0'], x['id']))
    by_id = {x['id']: x for x in key}
    ids = [92414, 92421, 92445, 92447]
    witness = [by_id[i] for i in ids]
    a, before, overwrite, after = witness
    assert all(x['res'] == 'ok' and len(x['att']) == 1 and
               x['att'][0]['st'] == 200 for x in witness)
    assert a['v'] == before['out'] == after['out'] == 'lc82.c7.11548'
    assert a['idx'] == before['idx'] == after['idx'] == '39481'
    assert overwrite['v'] == 'lc82.c5.11547' and overwrite['idx'] == '39488'
    assert before['t1'] < overwrite['t0'] < overwrite['t1'] < after['t0']
    assert overwrite['c'] == after['c'] == 5
    # Проверяем все исходы записей: даже неизвестная/неуспешная запись
    # не может восстановить A, потому что её входное значение другое.
    writers_a = [x['id'] for x in key if x.get('v') == a['v']]
    assert writers_a == [a['id']], writers_a
    # Начальное отсутствие подтверждает первое чтение ключа; значение A
    # рождается единственной записью позднее, а не существует до прогона.
    assert key[0]['f'] == 'read' and key[0]['res'] == 'ok' and key[0]['out'] == ''
    exhaustive = orders(witness)
    assert not exhaustive['legal_orders']
    controls = {}
    for omitted in [before['id'], overwrite['id'], after['id']]:
        result = orders([x for x in witness if x['id'] != omitted])
        assert result['legal_orders'], omitted
        controls['omit_' + str(omitted)] = result
    current_read = [dict(x) for x in witness]
    current_read[-1]['out'] = overwrite['v']
    controls['read_current_value'] = orders(current_read)
    assert controls['read_current_value']['legal_orders']

    # Всё перекрывающее окно, без исключения info и fail.
    lo, hi = 578801238578, 589735659463
    window = [x for x in key if x['t0'] <= hi and x['t1'] >= lo]
    anchor = by_id[92397]
    assert anchor['res'] == 'ok' and anchor['t1'] < lo
    assert not any(x['f'] != 'read' and x['t0'] <= anchor['t1'] and
                   (x['t1'] >= anchor['t1'] or x['res'] == 'info') for x in key)
    initial = (anchor['out'], anchor['idx'])
    window_check = check_window(window, initial)
    assert not window_check['linearizable']
    changed = [dict(x) for x in window]
    for op in changed:
        if op['id'] == after['id']:
            op['out'], op['idx'] = overwrite['v'], overwrite['idx']
    window_control = check_window(changed, initial)
    assert window_control['linearizable']
    events = []
    for line in (source / 'events.jsonl').read_text().splitlines():
        event = json.loads(line)
        if 543000000000 <= event['t'] <= 650000000000:
            events.append(event)
    logs = {}
    for path in sorted(source.glob('stand__logs__*.log.gz')):
        packed = path.read_bytes()
        assert sha(packed) == published[path.name], path
        raw = gzip.decompress(packed)
        name = path.name[:-3].replace('stand__logs__', 'stand/logs/')
        assert sha(raw) == original[name]['sha256'], path
        assert len(raw) == original[name]['bytes'], path
        hashes[path.name] = {'sha256': sha(packed), 'original_sha256': sha(raw)}
        logs[path.name] = [line for line in raw.decode().splitlines()
                           if any('2026-11-13T22:11:' + str(sec) in line
                                  for sec in range(44, 59))]
    for name in ['SOURCE-LOG-MANIFEST.json', 'events.jsonl', 'check.json', 'run.json']:
        raw = (source / name).read_bytes()
        assert sha(raw) == published[name], name
        hashes[name] = {'sha256': sha(raw)}

    code = {}
    repo = Path('/home/pilot/git/court-tools.git')
    for name in ['soak/cmd/soak/run.go', 'soak/internal/stand/stand.go',
                 'soak/internal/load/load.go', 'soak/internal/stand/http.go',
                 'soak/internal/hist/hist.go', 'soak/internal/linz/linz.go']:
        code['court-tools.git:440f611:' + name] = sha(git_blob(repo, '440f611', name))
    repo = Path('/home/pilot/git/claude81.git')
    for name in ['01-store/internal/group/backend.go',
                 '01-store/internal/group/frames.go', '01-store/internal/group/node.go']:
        old = git_blob(repo, '51976fe', name)
        new = git_blob(repo, '2ef34331261690e17a8985f12b7d6bd2f2ed3b2d', name)
        readable = Path('/home/pilot/owner-receipts/P01.334-review-inputs/candidate-claude82') / name
        assert new == readable.read_bytes(), name
        code[name] = {'claude82_sha256': sha(new), 'claude8_sha256': sha(old),
                      'unchanged_since_claude8': old == new}

    norm_path = 'Platform/01-store/spec/01.1-store.norms.md'
    norm = subprocess.check_output(['git', 'show',
        '0fbe6e55ceb0b07e4a70727e813934a2f06edb1b:' + norm_path]).decode()
    r062 = norm.split('<!-- req: P/01.1-R062 -->\n')[1].split('\n<!-- req:')[0].strip()
    current = Path(norm_path).read_text().split('<!-- req: P/01.1-R062 -->\n')[1].split('\n<!-- req:')[0].strip()
    assert current == r062
    assert lines == json.loads((source / 'run.json').read_text())['ops']
    assert lines == json.loads((source / 'check.json').read_text())['history']['ops']

    output = {'task': 'P01.368', 'conclusion': 'кандидат',
              'source': str(source), 'history_lines': lines, 'key_ops': len(key),
              'first_key_operation': key[0], 'only_writer_of_A': writers_a,
              'witness': witness, 'exhaustive_check': exhaustive,
              'controls': controls, 'window': window, 'events': events,
              'window_initial_observation': anchor, 'window_check': window_check,
              'window_control_read_current_value': window_control,
              'norm_M8doubleprime': {'course_source': '0fbe6e55ceb0b07e4a70727e813934a2f06edb1b',
                                     'path': norm_path, 'R062': r062,
                                     'R062_unchanged_in_worktree': True},
              'member_logs': logs, 'input_hashes': hashes, 'code_hashes': code,
              'method': 'Полный перебор четырёх операций + единственность писателя A во всей истории ключа; без исходного checker, CAS-модели и отсечения неизвестных записей.'}
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: output[k] for k in ['conclusion', 'history_lines', 'key_ops',
                                           'only_writer_of_A', 'exhaustive_check']},
                     ensure_ascii=False))


if __name__ == '__main__':
    main()
