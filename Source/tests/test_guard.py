"""ADR-0074: a delayed slot owner cannot publish control state, on every store."""
import json
import tempfile

import pytest

from w2cplatform.variables import FileVariables, GuardFailed, Forbidden, Conflict
from w2cplatform.memvariables import MemVariables
from w2cplatform.cluster.variables import FakeVariables
from w2cplatform.configstorevars import ConfigstoreVariables, StoreAmbiguous
from w2cplatform.storemachine import StoreMachine, Rights, local_transport, answer
from tests.conftest import Box, testsub
from tests.test_worker_life import _bare


def _stores():
    yield FileVariables(tempfile.mkdtemp(), volatile=True)
    yield MemVariables()
    yield FakeVariables()
    yield ConfigstoreVariables('', transport=local_transport(StoreMachine().apply, Rights(), 'admin'))


def _race(v, prefix='testsub'):
    slot, target = prefix+'/slots/w-1', prefix+'/slots/contribution'
    old = v.put(slot, {'holder': 'old'})
    guard = {'key': slot, 'index': old}
    v.put(target, {'n': 'old'}, cas=0, guard=guard)
    new = v.put(slot, {'holder': 'new'}, cas=old)
    current = v.put(target, {'n': 'new'}, guard={'key': slot, 'index': new})
    for op in (lambda: v.put(target, {'n': 'late'}, cas=current, guard=guard),
               lambda: v.delete(target, cas=current, guard=guard)):
        try:
            op()
        except GuardFailed as e:
            assert e.key == slot and e.index == new
        else:
            raise AssertionError("late owner wrote")
        assert v.get(target) == ({'n': 'new'}, current)
    with pytest.raises(GuardFailed):
        v.put(target, {}, guard={'key':slot,'index':str(new)+'0'})
    with pytest.raises(Conflict):
        v.put(target, {}, cas=0, guard={'key': slot, 'index': new})
    v.delete(target, cas=current, guard={'key': slot, 'index': new})
    assert v.get(target) == (None, 0)


def test_late_owner_cannot_put_or_delete_even_with_current_target_cas():
    for v in _stores():
        _race(v)


def test_guard_requires_read_permission_and_never_grants_target_write_permission():
    for v in _stores():
        i = v.put('testsub/slots/w-1', {})
        for allowed in (['testsub/slots/contribution'], ['testsub/slots/w-1']):
            w = v.as_writer('testsubworker', allowed)
            with pytest.raises(Forbidden):
                w.put('testsub/slots/contribution', {}, guard={'key':'testsub/slots/w-1', 'index':i})
    r = Rights({'testsubworker': {'read':['testsub/slots/contribution'], 'write':['testsub/*']}})
    calls = []
    code, _ = answer('POST','/v1/write',json.dumps({'op':'put','key':'testsub/slots/contribution','items':{},
                     'guard':{'key':'testsub/slots/w-1','index':'1'}}).encode(), 'testsubworker',r,calls.append)
    assert code == 403 and not calls


def test_partial_or_malformed_guard_is_refused_before_any_write():
    for v in _stores():
        for bad in ({}, {'key':'testsub/a'}, {'index':0}, {'key':'testsub/a','index':True},
                    {'key':'testsub/../a','index':0}, {'key':'testsub/a','index':None},
                    {'key':'testsub/a','index':0,'extra':1}):
            with pytest.raises(ValueError):
                v.put('testsub/a', {}, guard=bad)
            assert v.get('testsub/a') == (None, 0)


def test_unknown_answer_reuses_the_same_guarded_write_and_never_reapplies_it():
    machine = StoreMachine()
    transport = local_transport(machine.apply, Rights(), 'admin')
    first = [True]
    ids = []
    def lost(method, path, raw, headers, timeout):
        if method == 'POST':
            ids.append(json.loads(raw)['id'])
        result = transport(method,path,raw,headers,timeout)
        if method == 'POST' and first[0]:
            first[0] = False
            raise OSError('answer lost')
        return result
    v = ConfigstoreVariables('',transport=lost)
    guard={'key':'testsub/slots/w-1','index':0}
    with pytest.raises(StoreAmbiguous):
        v.put('testsub/a',{'n':'1'},cas=0,guard=guard)
    index = machine.rows['testsub/a'][1]
    machine.apply({'op':'put','key':'testsub/slots/w-1','items':{'holder':'new'}})
    assert v.put('testsub/a',{'n':'1'},cas=0,guard=guard) == index
    assert ids[0] == ids[1]
    with pytest.raises(GuardFailed):
        v.put('testsub/a',{'n':'2'},guard=guard)
    assert machine.rows['testsub/a'][0] == {'n':'1'}
    changed={'op':'put','key':'testsub/a','items':{'n':'1'},'cas':0,'id':ids[0],
             'guard':{'key':'testsub/slots/w-1','index':2}}
    assert 'another write' in machine.apply(changed)['error']


def test_worker_rechecks_ownership_after_guard_refusal_and_never_publishes_in_grace():
    box=Box()
    w=_bare(box,testsub(),'w-1')
    path='testsub/slots/contribution'
    original=box.vars.put
    def switch(key, items, cas=None, *, guard=None):
        if guard is not None:
            _bare(box,testsub(),'w-1')
        return original(key,items,cas=cas,guard=guard)
    box.vars.put=switch
    with pytest.raises(GuardFailed):
        w.put_under_slot(path,{'n':'old'})
    box.vars.put=original
    with pytest.raises(GuardFailed):
        w.put_under_slot(path,{'n':'old'})
    assert box.vars.get(path) == (None,0)
    current=_bare(box,testsub(),'w-1')
    current.put_under_slot(path,{'n':'new'})
    box.wall.advance(current.slot_ttl+1)
    with pytest.raises(GuardFailed):
        current.put_under_slot(path,{'n':'expired'})
    assert box.vars.get(path)[0] == {'n':'new'}


def test_a_fenced_worker_does_not_publish_even_while_its_slot_row_still_names_it():
    box=Box()
    w=_bare(box,testsub(),'w-1')
    w.writing_allowed=False
    with pytest.raises(GuardFailed):
        w.put_under_slot('testsub/slots/contribution',{})
    assert box.vars.get('testsub/slots/contribution')==(None,0)


def test_same_owner_renewal_refuses_the_old_guard_but_a_fresh_ownership_check_can_publish():
    box=Box()
    w=_bare(box,testsub(),'w-1')
    original=box.vars.put
    once=[True]
    def renewed(key,items,cas=None,*,guard=None):
        if guard is not None and once[0]:
            once[0]=False
            assert w.renew_slot()
        return original(key,items,cas=cas,guard=guard)
    box.vars.put=renewed
    with pytest.raises(GuardFailed):
        w.put_under_slot('testsub/slots/contribution',{'n':'first'})
    w.put_under_slot('testsub/slots/contribution',{'n':'second'})
    assert box.vars.get('testsub/slots/contribution')[0]=={'n':'second'}


def test_guard_wire_refusal_has_the_exact_412_body_and_does_not_become_a_cas_conflict():
    m=StoreMachine()
    current=m.apply({'op':'put','key':'testsub/slots/w-1','items':{}})['index']
    code,body=answer('POST','/v1/write',json.dumps({'op':'put','key':'testsub/a','items':{},
                     'guard':{'key':'testsub/slots/w-1','index':''}}).encode(),'admin',Rights(),m.apply)
    assert code==412 and body=={'kind':'guard','error':'guard','key':'testsub/slots/w-1','index':str(current)}
    assert 'testsub/a' not in m.rows
    code,body=answer('POST','/v1/write',json.dumps({'op':'put','key':'testsub/a','items':{},
                     'guard':None}).encode(),'admin',Rights(),m.apply)
    assert code==400 and 'testsub/a' not in m.rows
