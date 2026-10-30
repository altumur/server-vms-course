"""Finite counterexamples to ADR-0100 policy mechanisms, not an implementation or SUT test; CT103."""
from copy import deepcopy
import hashlib
from itertools import permutations
import json
import os
from pathlib import Path
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parent
OUT = Path(os.environ['CHECK_OUT'])
HEAD = '8aa4a15b34c0fece8bd137ca2276642b790e2c35'

def may_prefix(grants, assigned_admin, disabled=False, stale=False, glass=False):
    # Existing may 1-4, followed by exactly the new step 4a. No grant rows needed in these controls.
    if glass: return 'allow'
    if disabled: return 'disabled'
    if grants is None: return 'no_grant'
    if stale: return 'stale'
    if assigned_admin: return 'allow'
    return 'no_grant'

def count_admins(groups):
    # Two readable, enabled, nondeleting, expires=0 users; admin assigned permanently to both groups.
    return len(set(groups['g1']) | set(groups['g2']))

def explore(read_guards):
    histories = []
    for order in permutations(('prepare1', 'commit1', 'prepare2', 'commit2')):
        if any(order.index('prepare'+n) > order.index('commit'+n) for n in ('1','2')): continue
        groups = {'g1': ['a'], 'g2': ['b']}; versions = {'g1': 1, 'g2': 1}; turn = 17
        pending = {}; trace = []
        for event in order:
            n = event[-1]; own, other = 'g'+n, 'g'+('2' if n == '1' else '1')
            if event.startswith('prepare'):
                proposed = deepcopy(groups); proposed[own] = []
                allowed = count_admins(proposed) > 0
                guards = dict(versions) if read_guards else {own: versions[own]}
                pending[n] = dict(allowed=allowed, guards=guards, turn=turn)
                trace.append(dict(event=event, allowed=allowed, post_count=count_admins(proposed), guards=guards))
            else:
                p = pending[n]
                accepted = p['allowed'] and p['turn'] == turn and all(versions[k] == v for k,v in p['guards'].items())
                if accepted: groups[own] = []; versions[own] += 1
                trace.append(dict(event=event, accepted=accepted, count=count_admins(groups)))
        histories.append(dict(order=order, zero=count_admins(groups) == 0, trace=trace))
    return histories

with tempfile.TemporaryDirectory(prefix='rv-adr100-') as directory:
    source = Path(directory)
    with tarfile.open(ROOT / 'source.tar') as archive:
        assert archive.pax_headers['comment'] == HEAD
        archive.extractall(source, filter='data')
    texts = {str(p.relative_to(source)): p.read_text() for p in source.rglob('*') if p.is_file()}
    adr = texts['decisions/0100-встроенный-администратор.md']
    may = texts['Platform/common/contracts/may.md']
    roles = texts['decisions/0098-роли-и-группы-людей-в-домене.md']
    assert 'Новый шаг 4а после шага 4' in adr
    assert may.index('3. grants = null') < may.index('4. as_of')
    assert 'CAS всех затронутых строк' in roles and 'нечитаемая группа\n    ролей своим людям не даёт' in roles
    null_case = dict(input=dict(grants=None, assigned_admin=True, disabled=False, as_of=None),
                     trace=['1 glass=false', '2 disabled=false', '3 grants=null -> deny no_grant; 4a unreachable'],
                     actual=may_prefix(None, True), promised='allow')
    assert null_case['actual'] != null_case['promised']
    controls = {
        'admin_with_empty_doc': may_prefix({}, True) == 'allow',
        'disabled_precedes_admin': may_prefix({}, True, disabled=True) == 'disabled',
        'stale_precedes_admin': may_prefix({}, True, stale=True) == 'stale',
        'ordinary_user_no_grant': may_prefix({}, False) == 'no_grant',
        'glass_precedes_null': may_prefix(None, False, glass=True) == 'allow',
    }
    weak, guarded = explore(False), explore(True)
    bad = [h for h in weak if h['zero']]
    assert len(weak) == len(guarded) == 6 and len(bad) == 4 and not any(h['zero'] for h in guarded)
    # Same observed unreadable group supports both possible real memberships.
    # Manager's own role and the legacy administrator b remain readable in both worlds.
    worlds = [{'actual_admin_a': value, 'observed_members': 'unreadable',
               'manager_may': 'allow', 'legacy_b_proven': True,
               'positive_only_admin_only': 'allow password change',
               'unknown_closed': '503 unavailable'} for value in (False, True)]
    assert worlds[0]['observed_members'] == worlds[1]['observed_members']
    assert worlds[1]['actual_admin_a'] and worlds[1]['positive_only_admin_only'].startswith('allow')
    assert 'Проход не пишет имя в `domain/disabled` по сроку' in roles
    # ADR-0098 section 3's retained expiry fallback counts direct domain grant rows only.
    # Fresh ADR-0100 installs have no such rows, despite a permanent built-in administrator.
    expiry = dict(permanent_builtin_admins=1, legacy_direct_admin_rows=0, target='ordinary expiring user',
                  old_section3_result='keep enabled and log domain.user.expiry_kept',
                  required='disable expired ordinary user; permanent built-in administrator remains')
    controls.update(serial_last_removal_rejected=all(not h['zero'] for h in weak if h['order'][1].startswith('commit')),
                    read_set_guards_close_all_schedules=not any(h['zero'] for h in guarded),
                    unreadable_never_proves_ordinary=worlds[1]['unknown_closed'] == '503 unavailable')
    assert all(controls.values())
    result = dict(head=HEAD, SUT=0, kind='finite model of normative rules; no implementation executed',
                  source_sha256={name: hashlib.sha256(text.encode()).hexdigest() for name,text in texts.items()},
                  model_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  may_null=null_case, last_admin=dict(total_schedules=6, violating_schedules=bad, guarded=guarded),
                  unreadable_target=worlds, expiry_fallback=expiry, positive_controls=controls)
    (OUT / 'model-evidence.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(dict(head=HEAD, source_files=len(texts), schedules=6, bad_schedules=len(bad),
                         guarded_bad=0, controls=len(controls), all_controls=True, SUT=0)), flush=True)
