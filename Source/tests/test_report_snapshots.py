"""ADR-0074: publication interleavings return a pinned whole report or explicit unknown."""
import json
import tempfile
import threading

import pytest

from w2cplatform.objects import FsObjectStore
from w2cplatform.domain.reports import accept, read, prune, export, StaleReport
from w2cplatform.domain.federation import Unreachable
from w2cplatform.domain.uplink import base, REPORTED


def _store():
    return FsObjectStore(tempfile.mkdtemp())


def _body(seq):
    return json.dumps({'sent_at':seq,'objects':{},'pages':{},
                      'rows':{'testsub/status':{'items':{'n':str(seq)},'idx':seq},
                              'testsub2/status':{'items':{'n':str(seq)},'idx':seq}}},indent=1).encode()


def test_every_publication_boundary_reads_whole_old_or_new_and_preserves_original_bytes():
    store=_store()
    accept('a',_body(1),store,received_at=100)
    pinned=read('a',store)
    old_new=store.put
    def inspect(key,raw):
        assert read('a',store).raw == _body(1)
        result=old_new(key,raw)
        if key.endswith('/reports/2'):
            assert read('a',store).raw == _body(1)
        return result
    store.put=inspect
    accept('a',_body(2),store,received_at=101)
    assert read('a',store).raw == _body(2) and pinned.raw == _body(1)
    assert not any('/v/' in k or '/o/' in k or '/p/' in k for k in store.list(base('a')))


def test_crash_before_pointer_recovers_with_new_body_after_restart():
    store=_store()
    accept('a',_body(1),store,received_at=1)
    put=store.put
    def crash(key,raw):
        if key.endswith('/reported'): raise OSError('power loss')
        put(key,raw)
    store.put=crash
    with pytest.raises(OSError): accept('a',_body(2),store,received_at=2)
    assert read('a',store).raw==_body(1)
    assert base('a')+'reports/2' not in export(store).objects
    store=FsObjectStore(store.root)
    accept('a',_body(3),store,received_at=3)
    snap=read('a',store)
    assert snap.raw==_body(3) and snap.mark['rev']==2
    assert store.get(base('a')+'reports/1')==_body(1)
    assert accept('a',_body(3),store,received_at=999).mark==snap.mark
    with pytest.raises(StaleReport): accept('a',_body(2),store,received_at=999)
    with pytest.raises(StaleReport): accept('a',_body(3)+b' ',store,received_at=999)
    assert read('a',store).mark==snap.mark


def test_concurrent_requests_cannot_overwrite_an_accepted_body():
    store=_store()
    accept('a',_body(1),store,received_at=1)
    wrote,resume,started=threading.Event(),threading.Event(),threading.Event()
    put=store.put
    errors=[]
    def delayed(key,raw):
        put(key,raw)
        if key.endswith('/reports/2'):
            wrote.set()
            assert resume.wait(5)
    store.put=delayed
    def send(n):
        try:
            if n==3: started.set()
            accept('a',_body(n),store,received_at=n)
        except BaseException as e: errors.append(e)
    first=threading.Thread(target=send,args=(2,));first.start()
    assert wrote.wait(5)
    second=threading.Thread(target=send,args=(3,));second.start()
    assert started.wait(5)
    assert read('a',store).raw==_body(1)
    resume.set();first.join(5);second.join(5)
    assert not errors and not first.is_alive() and not second.is_alive()
    assert read('a',store).mark['rev']==3
    assert store.get(base('a')+'reports/2')==_body(2)
    assert read('a',store).raw==_body(3)


def test_missing_or_corrupt_parts_are_unknown_and_never_repaired_from_other_generations():
    for broken in (None,b'{}',b'{'):
        store=_store()
        accept('a',_body(1),store,received_at=1)
        accept('a',_body(2),store,received_at=2)
        key=base('a')+'reports/2'
        if broken is None:
            store.delete(key)
        else:
            store.put(key,broken)
        with pytest.raises(Unreachable):
            read('a',store)
    for part in ('objects','rows','pages'):
        doc=json.loads(_body(1));del doc[part]
        with pytest.raises(ValueError):
            accept('a',json.dumps(doc).encode(),_store(),received_at=1)


def test_pruning_keeps_two_generations_and_a_pinned_reader_survives_move_and_cleanup():
    store=_store()
    accept('a',_body(1),store,received_at=1)
    pinned=read('a',store)
    for seq in (2,3,4):
        accept('a',_body(seq),store,received_at=seq)
    assert prune('a',store)==2
    assert store.list(base('a')+'reports/')==[base('a')+'reports/3',base('a')+'reports/4']
    assert pinned.document()['rows']['testsub/status']['items']=={'n':'1'}
    other=_store()
    for key in store.list(base('a')):
        other.put(key,store.get(key))
    assert read('a',other).raw==_body(4)
    assert read('a',other).mark==read('a',store).mark


def test_a_reader_pins_the_pointer_before_a_concurrent_prune_and_never_switches_generations():
    store=_store()
    accept('a',_body(1),store,received_at=1)
    get=store.get
    fired=[False]
    def race(key):
        if key==base('a')+'reports/1' and not fired[0]:
            fired[0]=True
            accept('a',_body(2),store,received_at=2)
            accept('a',_body(3),store,received_at=3)
            prune('a',store)
        return get(key)
    store.get=race
    with pytest.raises(Unreachable):
        read('a',store)
    assert read('a',store).raw==_body(3)


def test_corrupt_pointer_is_not_reset_and_signature_is_in_the_mark():
    store=_store()
    accept('a',_body(1),store,received_at=1,signature='signed-body')
    original=read('a',store).mark
    assert original['signature']=='signed-body'
    for rev in (None,True,0,-1,1.5,2**53):
        mark={**original,'rev':rev}
        store.put(base('a')+REPORTED,json.dumps(mark).encode())
        with pytest.raises(ValueError): accept('a',_body(2),store,received_at=2)
        with pytest.raises(Unreachable): read('a',store)


def test_orphans_are_pruned_but_not_exported():
    store=_store()
    accept('a',_body(1),store,received_at=1)
    store.put(base('a')+'reports/2',_body(2))
    assert base('a')+'reports/2' not in export(store).objects
    assert prune('a',store)==1
    assert read('a',store).raw==_body(1)


def test_export_omits_whole_damaged_members_and_counts_them():
    store=_store()
    for member in ('good','bad-body','bad-mark','missing-body','bad-previous'):
        accept(member,_body(1),store,received_at=1)
        accept(member,_body(2),store,received_at=2)
    store.put(base('bad-body')+'reports/2',b'broken')
    store.put(base('bad-mark')+REPORTED,b'broken')
    store.delete(base('missing-body')+'reports/2')
    store.put(base('bad-previous')+'reports/1',b'\xff')
    result=export(store)
    assert result.skipped==('bad-body','bad-mark','bad-previous','missing-body')
    assert result.skipped_count==4
    assert set(result.objects)=={base('good')+s for s in ('reported','reports/1','reports/2')}
    assert read('good',store).mark['rev']==2
