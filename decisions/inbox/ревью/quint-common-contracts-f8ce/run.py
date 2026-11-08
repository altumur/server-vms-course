#!/usr/bin/env python3
"""Runs the common-contracts Quint project. Raw stdout+stderr of every run goes to runs/<id>.out; the table to results.tsv."""
import os, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE); os.makedirs('runs', exist_ok=True)
ENV = dict(os.environ, JAVA_HOME='/opt/quint/jdk', PATH='/opt/quint/jdk/bin:' + os.environ['PATH'])
SIM = {'samples': '100000', 'steps': '40', 'seed': '0x2026', 'threads': '8'}
H, V = 'hold', 'violate'
C = [ # file, main, invariant, expected, kind
 ('turn.qnt','turn_ok','fenced',H,'safety'),('turn.qnt','turn_ok','onlyHolderWrites',H,'safety'),('turn.qnt','turn_ok','singleConfident',H,'safety'),
 ('turn.qnt','turn_ok','noTakeover',V,'witness'),('turn.qnt','turn_ok','noLateRefused',V,'witness'),('turn.qnt','turn_ok','noApplied',V,'witness'),
 ('turn.qnt','turn_drift','fenced',H,'safety'),('turn.qnt','turn_drift','onlyHolderWrites',H,'safety'),('turn.qnt','turn_drift','singleConfident',V,'finding-probe'),
 ('turn.qnt','turn_mut_noguard','fenced',V,'mutant'),('turn.qnt','turn_mut_nowait','singleConfident',V,'mutant'),('turn.qnt','turn_mut_anchor','singleConfident',V,'mutant'),
 ('presence_lock.qnt','presence_ok','holderVisible',H,'safety'),('presence_lock.qnt','presence_ok','noRetry',V,'witness'),('presence_lock.qnt','presence_ok','noDelete',V,'witness'),('presence_lock.qnt','presence_ok','neverHolding',V,'witness'),
 ('presence_lock.qnt','presence_mut_nostat','holderVisible',V,'mutant'),('presence_lock.qnt','presence_mut_lateunlink','holderVisible',V,'mutant'),
 ('request_mark.qnt','rm_ok','atMostOneCall',H,'safety'),('request_mark.qnt','rm_ok','performedStays',H,'safety'),('request_mark.qnt','rm_ok','expiredNoCall',H,'safety'),
 ('request_mark.qnt','rm_ok','noLate',V,'witness'),('request_mark.qnt','rm_ok','noUnknown',V,'witness'),
 ('request_mark.qnt','rm_mut_nomark','atMostOneCall',V,'mutant'),('request_mark.qnt','rm_mut_blind','performedStays',V,'mutant'),
 ('tombstone.qnt','ts_owner','noResurrection',H,'safety'),('tombstone.qnt','ts_owner','ackMeansGone',H,'safety'),('tombstone.qnt','ts_owner','noRemoval',V,'witness'),('tombstone.qnt','ts_owner','notStuckWithSilent',V,'witness'),
 ('tombstone.qnt','ts_any','noResurrection',V,'finding-probe'),('tombstone.qnt','ts_any','ackMeansGone',V,'finding-probe'),('tombstone.qnt','ts_mut_ack','ackMeansGone',V,'mutant'),
 ('accept_gen.qnt','acc_keep','markHasObject',H,'safety'),('accept_gen.qnt','acc_keep','noOldLeak',H,'safety'),('accept_gen.qnt','acc_keep','noFalseSilent',V,'witness'),
 ('accept_gen.qnt','acc_literal','noOldLeak',V,'finding-probe'),('accept_gen.qnt','acc_mut_markfirst','markHasObject',V,'mutant'),
]
BOUNDS = {'turn.qnt': [8, 10, 12], 'tombstone.qnt': [8, 10, 12], 'request_mark.qnt': [8, 10, 12], 'presence_lock.qnt': [10, 14, 18], 'accept_gen.qnt': [10, 14, 18]}
LIMIT = 280
def go(rid, argv):
    t = time.time()
    try:
        r = subprocess.run(argv, env=ENV, capture_output=True, text=True, timeout=LIMIT); out = r.stdout + r.stderr; code = r.returncode
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b'').decode() if isinstance(e.stdout, bytes) else (e.stdout or ''); code = 'timeout'
    open(f'runs/{rid}.out', 'w', encoding='utf-8').write('# argv: ' + ' '.join(argv) + f'\n# exit: {code}\n' + out)
    return code, round(time.time() - t, 1), out
def verdict(code, out):
    if code == 'timeout': return 'timeout'
    if 'violation] Found' in out or 'Invariant violated' in out or 'error: Invariant' in out: return 'violate'
    if 'No violation found' in out or '[ok]' in out: return 'hold'
    return 'error'
rows = [['id', 'tool', 'file', 'main', 'invariant', 'kind', 'expected', 'bound', 'exit', 'observed', 'seconds', 'match']]
for i, (f, m, inv, exp, kind) in enumerate(C):
    rid = f'{i:02d}-sim-{m}-{inv}'
    a = ['quint', 'run', f'--main={m}', f'--invariant={inv}', f"--max-samples={SIM['samples']}", f"--max-steps={SIM['steps']}", f"--seed={SIM['seed']}", '--backend=rust', f"--n-threads={SIM['threads']}", f]
    code, sec, out = go(rid, a); v = verdict(code, out)
    rows.append([rid, 'run/rust', f, m, inv, kind, exp, f"{SIM['samples']}x{SIM['steps']}", code, v, sec, 'yes' if v == exp else 'NO']); print(rows[-1], flush=True)
    if kind in ('safety', 'finding-probe', 'mutant'):
        for b in BOUNDS[f]:
            rid = f'{i:02d}-ver{b}-{m}-{inv}'
            a = ['quint', 'verify', f'--main={m}', f'--invariant={inv}', f'--max-steps={b}', f]
            code, sec, out = go(rid, a); v = verdict(code, out)
            rows.append([rid, 'verify/apalache', f, m, inv, kind, exp, b, code, v, sec, 'yes' if v == exp else ('bound' if v in ('hold', 'timeout') and exp == 'violate' else 'NO')]); print(rows[-1], flush=True)
            if v in ('timeout', 'error', 'violate'): break
open('results.tsv', 'w', encoding='utf-8').write('\n'.join('\t'.join(map(str, r)) for r in rows) + '\n')
print('DONE', len(rows) - 1, 'runs; mismatches', [r[0] for r in rows[1:] if r[-1] == 'NO'])
