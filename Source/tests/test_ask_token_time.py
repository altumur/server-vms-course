"""C6 receipt time is shared by ordinary and embedded callers (d13efef8)."""
import json

from tests.conftest import Clock
from tests.test_autoask import item, road_fixture
from tests.test_book_names import raises
from vms.autoask import Asker
from vms.recording_books import Unconfirmed
from vms.role_tokens import RoleTokens
from w2cplatform.domain.tokenrequest import WorkerTokenDoor


def test_fresh_role_reply_works_with_unset_or_far_future_local_wall():
    for now in (0,10**12):
        e=road_fixture()
        asker=Asker('A',e.box.vars,e.dial,e.tokens,Clock(now))
        assert asker.ask('B',item()['then'],7)[0] is e.ingest
        assert e.calls==[('ask','B','A')]


def test_a_cached_receipt_advances_without_wall_and_failure_never_renews_it():
    e=road_fixture();scope=(1,)
    token=e.tokens.get('ask','B',scope,by='A')
    start=e.tokens.verification_time('ask','B',scope,token,by='A')
    e.box.clock.advance(75)
    def unavailable(*a):raise OSError('not answering')
    e.door.request=unavailable
    assert e.tokens.get('ask','B',scope,by='A')==token
    assert e.tokens.verification_time('ask','B',scope,token,by='A')==start+75
    e.box.clock.advance(16)
    raises(Unconfirmed,lambda:e.tokens.get('ask','B',scope,by='A'))
    raises(Unconfirmed,lambda:e.tokens.verification_time('ask','B',scope,token,by='A'))


def test_a_restarted_cache_requires_a_new_role_response():
    e=road_fixture();token=e.tokens.get('ask','B',(1,),by='A')
    restarted=RoleTokens('autoworker',e.door,clock=e.box.clock)
    raises(Unconfirmed,lambda:restarted.verification_time('ask','B',(1,),token,by='A'))
    replacement=restarted.get('ask','B',(1,),by='A')
    assert len(e.calls)==2
    restarted.verification_time('ask','B',(1,),replacement,by='A')


def test_old_request_id_cannot_create_a_time_anchor_or_extend_a_previous_one():
    e=road_fixture();responses=[]
    door=WorkerTokenDoor.__new__(WorkerTokenDoor);door.timeout=1
    def call(method,path,body,headers,timeout):
        request=json.loads(body)
        if not responses:
            responses.append({**e.door.request('ask','B','A'),'request_id':request['request_id']})
        return 200,json.dumps(responses[0]).encode()
    door.call=call
    tokens=RoleTokens('autoworker',door,clock=e.box.clock)
    token=tokens.get('ask','B',(1,),by='A')
    start=tokens.verification_time('ask','B',(1,),token,by='A')
    e.box.clock.advance(75)
    assert tokens.get('ask','B',(1,),by='A')==token
    assert tokens.verification_time('ask','B',(1,),token,by='A')==start+75
    e.box.clock.advance(16)
    raises(Unconfirmed,lambda:tokens.get('ask','B',(1,),by='A'))


def test_changed_road_during_correlated_response_forgets_the_receipt():
    e=road_fixture();request=e.door.request
    def changed(kind,ref,by):
        reply=request(kind,ref,by)
        e.publish(member='other')
        return reply
    e.door.request=changed
    raises(Unconfirmed,lambda:e.asker.ask('B',item()['then'],7))
    assert not e.tokens.cached and not e.dialled


def test_waiting_for_a_correlated_response_consumes_the_event_deadline():
    for delay in (2,8):
        e=road_fixture();request=e.door.request;start=e.box.wall()
        def delayed(kind,ref,by):
            reply=request(kind,ref,by)
            e.box.clock.advance(delay);e.box.wall.advance(delay)
            return reply
        e.door.request=delayed
        if delay==8:
            raises(Unconfirmed,lambda:e.asker.ask('B',item()['then'],7))
            assert not e.dialled
        else:
            _,result=e.asker.ask('B',item()['then'],7)
            assert result[1][-1]==start+7


def test_receipt_does_not_authorize_wrong_kind_audience_trigger_or_actions():
    for change in ({'kind':'poll'},{'aud':['other']},{'by':'other'}, {'acts':[]}):
        e=road_fixture();e.claims.update(change)
        try:
            assert e.asker.ask('B',item()['then'],7) is None
        except Unconfirmed:
            pass
        assert not e.dialled
