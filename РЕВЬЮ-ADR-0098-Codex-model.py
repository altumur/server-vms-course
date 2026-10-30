"""Finite design witnesses for ADR-0098. Not an implementation or a SUT test.

Run only through CT 103. Sources must be a git archive of the reviewed commit.
The model explores composition/expiry/backup/size, not the full may algorithm.
"""
import hashlib
import itertools
import json
import os
from pathlib import Path
import tarfile
import tempfile

COMMIT = '1b9035f898742d4b89b730a0cdca331cb414fbc1'
ROOT = Path(__file__).resolve().parent
OUT = Path(os.environ['CHECK_OUT'])

def jcs(value):
    # Inputs here contain ASCII strings, booleans and exact small integers only.
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))

def weight(items):
    return sum(len(k.encode())+len(v.encode()) for k, v in items.items())

def active(until, now):
    return until == 0 or now < until

def allows_admin(grant, assigned):
    return grant == 'admin' and assigned

def remaining_admin(users, disabled, require_permanent=False):
    # All users in this finite example have a permanent direct domain admin * grant,
    # a readable row and no deletion marker. Existing last_admin tests these flags.
    return any(not u['disabled'] and name not in disabled
               and (not require_permanent or u['expires'] == 0)
               for name, u in users.items())

def run(sources):
    adr = (sources/'decisions/0098-роли-и-группы-людей-в-домене.md').read_text()
    p08 = (sources/'Platform/08-domain/spec/08.8-domain.norms.md').read_text()
    p01 = (sources/'Platform/01-store/spec/01.1-store.norms.md').read_text()
    assert 'с тем же `as_of`' in adr and 'отдельное поле и отдельная копия' in adr
    assert 'ceiling: 524288' in p01
    state_section = p08.split('  state:', 1)[1].split('  objects:', 1)[0]
    assert 'domain/grants/*' in state_section and 'domain/users/*' in state_section
    assert 'domain/groups' not in state_section and 'domain/roles' not in state_section

    mixed = []
    policies = list(itertools.product(('view', 'admin'), (False, True)))
    for old, new in itertools.product(policies, repeat=2):
        if allows_admin(*old) or allows_admin(*new):
            continue
        for first in ('grants', 'roles'):
            grant = new[0] if first == 'grants' else old[0]
            assigned = new[1] if first == 'roles' else old[1]
            if allows_admin(grant, assigned):
                mixed.append(dict(old=dict(cap=old[0], assigned=old[1]),
                                  new=dict(cap=new[0], assigned=new[1]),
                                  first_copy=first, mixed=dict(cap=grant, assigned=assigned),
                                  old_allows_admin=False, new_allows_admin=False,
                                  mixed_allows_admin=True))
    assert len(mixed) == 2 and {v['first_copy'] for v in mixed} == {'grants', 'roles'}
    # The same mixed reads may happen at the holder around one atomic policy
    # replacement; a single response timestamp does not identify the source state.
    mixed_holder = dict(grants_read='old', roles_read='new', response_as_of=100,
                        copies_as_of=[100, 100], grants='admin', assigned=True)
    assert allows_admin(mixed_holder['grants'], mixed_holder['assigned'])

    users = {'owner': dict(disabled=False, expires=20)}
    admitted_at_10 = remaining_admin(users, disabled=set())
    mirror_at_20 = {name for name, u in users.items()
                    if u['disabled'] or (u['expires'] != 0 and 20 >= u['expires'])}
    after_expiry = remaining_admin(users, mirror_at_20)
    assert admitted_at_10 and not after_expiry

    state = {'domain/users/u': {'name': 'u'},
             'domain/groups/G': {'members': ['u']},
             'domain/roles/R': {'assigned': [{'group': 'G', 'until': 0}]},
             'domain/grants/member': {'lines': [{'subject': 'role:R', 'cap': 'view', 'scope': '*', 'until': 0}]}}
    restored = {k: v for k, v in state.items()
                if k.startswith(('domain/users/', 'domain/grants/'))}
    assert 'domain/roles/R' not in restored and 'domain/groups/G' not in restored
    orphaned = [line for line in restored['domain/grants/member']['lines']
                if line['subject'].startswith('role:')
                and 'domain/roles/'+line['subject'][5:] not in restored]
    assert len(orphaned) == 1

    people = ['p'+str(n).zfill(63) for n in range(5000)]
    role = 'R'*64
    assert len(set(people)) == 5000 and all(len(n) == 64 and n.isalnum() for n in people)
    group_items = dict(name='G', title='', comment='', members=jcs(people), source='local', at='0', by='owner')
    role_items = dict(name=role, title='', comment='', assigned=jcs([dict(group='G', until=0)]), at='0', by='owner')
    user_items = dict(name=people[0], how='password', pwhash_secret='pbkdf2-sha256$600000$'+'0'*32+'$'+'0'*64,
                      disabled='false', title='', email='', expires='0', at='0', by='owner')
    table = {p: [dict(role=role, until=0)] for p in people}
    table_json = jcs(table)
    size = dict(people=len(people), person_name_bytes=64, role_name_bytes=64, ceiling=524288,
                group_row_weight=weight(group_items), role_row_weight=weight(role_items),
                user_row_weight=weight(user_items),
                group_request_bytes=len(jcs(dict(name='G', members=people)).encode()),
                expanded_table_json_bytes=len(table_json.encode()),
                expanded_names_alone_bytes=sum(len(p.encode())+len(role.encode()) for p in people))
    assert max(size['group_row_weight'], size['role_row_weight'], size['user_row_weight']) <= size['ceiling']
    assert size['group_request_bytes'] < 1048576
    assert size['expanded_names_alone_bytes'] > size['ceiling']

    controls = {}
    def control(name, value):
        assert value, name
        controls[name] = True
    control('finite_expiry_cannot_be_only_permanent_admin', not remaining_admin(users, set(), require_permanent=True))
    control('another_permanent_admin_allows_finite_account', remaining_admin(dict(users, second=dict(disabled=False, expires=0)), set(), True))
    control('omitted_expires_default_zero_is_permanent', remaining_admin({'old': dict(disabled=False, expires=0)}, set(), True))
    control('assignment_until_boundary', active(20, 19) and not active(20, 20))
    control('grant_until_and_assignment_until_both_apply', not (active(10, 10) and active(0, 10)))
    return dict(kind='finite design counterexamples; no implementation evaluated', SUT=0,
                witnesses=dict(mixed_snapshots=dict(member=mixed, holder=mixed_holder),
                               last_admin_expiry=dict(admitted_at_10=admitted_at_10, disabled_at_20=sorted(mirror_at_20),
                                                      remaining_admin_at_20=after_expiry),
                               backup=dict(authoritative_keys=sorted(state), restored_keys=sorted(restored),
                                           grants_removed_as_orphans=orphaned),
                               expansion_size=size), controls=controls)

with tempfile.TemporaryDirectory(prefix='rv-adr98-') as directory:
    sources = Path(directory)
    before = hashlib.sha256((ROOT/'sources.tar').read_bytes()).hexdigest()
    with tarfile.open(ROOT/'sources.tar') as stream:
        assert stream.pax_headers['comment'] == COMMIT
        stream.extractall(sources, filter='data')
    hashes = {}
    for record in filter(None, (ROOT/'sources.ls-tree').read_bytes().split(b'\0')):
        metadata, name = record.split(b'\t', 1)
        mode, kind, wanted = metadata.split()
        assert kind == b'blob' and mode == b'100644'
        data = (sources/name.decode()).read_bytes()
        assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest() == wanted.decode()
        hashes[name.decode()] = hashlib.sha256(data).hexdigest()
    result = run(sources)
    assert hashlib.sha256((ROOT/'sources.tar').read_bytes()).hexdigest() == before
    result.update(commit=COMMIT, source_files=len(hashes), source_sha256=hashes,
                  archive_sha256=before, inputs_unchanged=True,
                  model_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (OUT/'adr98-model-evidence.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k != 'source_sha256'}, ensure_ascii=False), flush=True)
