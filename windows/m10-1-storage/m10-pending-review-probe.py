import json, os, subprocess, sys, tempfile
from pathlib import Path
from unittest.mock import patch
from w2cplatform import variables as v
from w2cplatform.variables import FileVariables, _Replay
from w2cplatform.configstorevars import StoreAmbiguous
from tests.storage_acceptance import NativeAPI
out = []
for operation in ('put', 'delete'):
    for failed_barrier in ('vars', 'root'):
        with tempfile.TemporaryDirectory() as root:
            original = FileVariables(root, volatile=False)
            at = original.put('acc/row', {'v': 'old'})
            slot = original.put('acc/slot', {'owner': 'a'})
            cmd = {'op': operation, 'key': 'acc/row', 'cas': at, 'id': 'ab',
                   'guard': {'key': 'acc/slot', 'index': slot}}
            if operation == 'put': cmd['items'] = {'v': 'one'}
            real_dir, calls = v.durable_dir, []
            # First root call is the index reservation, before publication.
            fail_path = original.dir if failed_barrier == 'vars' else root
            failures = [2]
            def barrier(path):
                calls.append(path)
                published = original.get('acc/row')[1] != at
                if path == fail_path and published and failures[0]:
                    failures[0] -= 1
                    raise OSError('injected post-publication barrier failure')
                real_dir(path)
            with patch.object(v, 'durable_dir', barrier):
                api = NativeAPI(original)
                wire = {**cmd, 'cas': str(at), 'guard': {'key': 'acc/slot', 'index': str(slot)}}
                raw = json.dumps(wire).encode()
                assert api.request('POST', '/v1/write', raw) == (503, {'kind':'ambiguous'})
                receipt_index = int(Path(original.index_file).read_text())
                assert 'ab' in original._replay.pending
                # A reopened volatile handle must still finish the original durable write.
                retry = FileVariables(root, volatile=True)
                before = len(calls)
                assert NativeAPI(retry).request('POST', '/v1/write', raw) == (503, {'kind':'ambiguous'})
                repeat_calls = calls[before:]
                assert repeat_calls == [fail_path]
                # Do not replay either current CAS or guard; do not restore the old row.
                newer = retry.put('acc/row', {'v': 'newer'})
                retry.put('acc/slot', {'owner': 'b'})
                before = len(calls)
                assert NativeAPI(retry).request('POST', '/v1/write', raw) == (200, {'index': str(receipt_index), 'again':True})
                finished_calls = calls[before:]
                expected = [original.dir, root] if failed_barrier == 'vars' else [root]
                assert finished_calls == expected
                assert original.get('acc/row') == ({'v':'newer'}, newer)
                assert 'ab' not in original._replay.pending
                # No barriers after completion; changed payload still refuses.
                before = len(calls)
                assert retry.write(cmd) == {'index': receipt_index, 'again':True}
                assert len(calls) == before
                changed = {**wire, 'cas': ''}
                assert NativeAPI(retry).request('POST', '/v1/write', json.dumps(changed).encode())[0] == 400
                assert len(calls) == before
                out.append({'operation': operation, 'failed': failed_barrier, 'retry_only_missing': True,
                            'volatile_retry_original_finalizer': True, 'guard_cas_not_replayed':True})
# Pending receipt retention: both minima, and bounded forgetting only afterwards.
clock=[0.0]; memory=_Replay(); applied=[0]
def apply():
    applied[0] += 1
    return {'index':applied[0], 'again':False}
def fail(): raise OSError('still pending')
with patch.object(v.time, 'monotonic', lambda:clock[0]):
    try: memory.run({'id':'0'},apply,fail)
    except StoreAmbiguous: pass
    clock[0]=10000
    memory.run({'id':'1'},apply)
    assert '0' in memory.pending # age alone is insufficient
    clock[0]=0
    for n in range(2,50002): memory.run({'id':format(n,'x')},apply)
    assert '0' in memory.pending # count alone is insufficient
    clock[0]=119.999
    memory.run({'id':'fffff'},apply)
    assert '0' in memory.pending
    count=applied[0]
    try: memory.run({'id':'0'},apply)
    except StoreAmbiguous: pass
    else: raise AssertionError('pending receipt reported success without barriers')
    assert applied[0] == count
    clock[0]=120.0
    memory.run({'id':'ffffe'},apply)
    assert '0' not in memory.done and '0' not in memory.pending
out.append({'retention':'pending survives count-only and age-only pressure; eligible after both minima'})
# Real process death at the first post-publication directory barrier: only process
# memory is lost, no new replay file/tombstone is created, versions remain monotonic.
with tempfile.TemporaryDirectory() as root:
    code = '''import os,sys
from w2cplatform import variables as v
s=v.FileVariables(sys.argv[1],volatile=False)
real=v.durable_dir
def barrier(path):
 if path==s.dir and s.get('acc/row')[0] is not None: os._exit(73)
 real(path)
v.durable_dir=barrier
s.write({'op':'put','key':'acc/row','items':{'v':'one'},'id':'ab'})
'''
    p=subprocess.run([sys.executable,'-c',code,root])
    assert p.returncode == 73
    store=FileVariables(root,volatile=False)
    first=store.get('acc/row')[1]
    second=store.write({'op':'put','key':'acc/row','items':{'v':'one'},'id':'ab'})
    assert second['again'] is False and second['index'] > first
    names=sorted(str(p.relative_to(root)) for p in Path(root).rglob('*') if p.is_file())
    assert names == ['index','lock','vars/acc%2Frow.json']
    out.append({'process_death_after_publish':73, 'new_process_forgets_id':True, 'versions_not_reused':True, 'files':names})
print(json.dumps(out, ensure_ascii=False, indent=2))
