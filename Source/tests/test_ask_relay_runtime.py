"""C6 real ingest/relay path: raw actions, role authority and original deadline."""
from tests.test_autoask import item, road_fixture
from tests.test_book_names import raises
from vms.domainpart.chain import Forwarder
from vms.domainpart.ingest import Ingest, Refused, ANSWER_GRACE
from vms.role_tokens import RoleTokens
from w2cplatform.domain.federation import Unreachable


def ingest(e,name):
    return Ingest(name,['http://'+name+'/ingest'],e.issuer.keyset,wall=e.box.wall)


def token(e,**changes):
    claims={'kind':'ask','ref':'B','by':'A','acts':[item()['then']],'aud':['home']}
    claims.update(changes)
    return e.issuer.issue('camera',100,now=e.box.wall(),**claims)


def relay():
    e=road_fixture();local,home=ingest(e,'camera'),ingest(e,'home')
    fwd=Forwarder('camera',local,e.box.vars,lambda url:home,token_requests=e.door)
    fwd.tokens=RoleTokens('recworker',e.door,clock=e.box.clock)
    aid=local.ask(token(e,aud=['camera'],up='home'),'B',item()['then'],e.box.wall()+7)
    return e,local,home,fwd,aid


def test_ingest_accepts_only_cluster_list_and_complete_raw_then():
    e=road_fixture();home=ingest(e,'home');action=item()['then']
    aid=home.ask(token(e),'B',action,e.box.wall()+7)
    assert home.cams['B'].asks[aid]['action']==action
    for aud in ('home','ingest:home',[],['other'],['home','home'],['home',None]):
        raises(Refused,lambda:home.ask(token(e,aud=aud),'B',action,e.box.wall()+7))
    for change in ({'arg':9},{'within':9},{'camera':'other'},{'extra':True}):
        raises(Refused,lambda:home.ask(token(e),'B',{**action,**change},e.box.wall()+7))
    for key in action:
        changed={k:v for k,v in action.items() if k!=key}
        raises(Refused,lambda:home.ask(token(e),'B',changed,e.box.wall()+7))


def test_relay_requests_original_pair_and_carries_answer_back():
    e,local,home,fwd,aid=relay()
    assert fwd.lift()[aid]=='up' and e.calls==[('ask','B','A')]
    lifted=fwd.lifted[aid]
    assert home.cams['B'].asks[lifted['aid']]['action']==item()['then']
    credential=e.issuer.issue('camera',100,now=e.box.wall(),kind='stream',ref='B',aud=['home'])
    home.answer_ask(credential,'B',lifted['aid'],'performed')
    assert fwd.lift()[aid]=='performed'
    assert local.ask_outcome('B',aid)=='performed' and not fwd.lifted
    assert 'token' not in str(e.box.vars.get('domain/auto/asks')[0])


def test_token_wait_consumes_deadline_and_expired_reply_never_dials():
    for delay in (2,8):
        e,local,home,fwd,aid=relay();request=e.door.request;start=e.box.wall();dials=[]
        def delayed(kind,ref,by):
            response=request(kind,ref,by)
            e.box.clock.advance(delay);e.box.wall.advance(delay)
            return response
        e.door.request=delayed
        fwd.dial=lambda url:dials.append(url) or home
        fwd.lift()
        if delay==2:
            lifted=fwd.lifted[aid]
            assert home.cams['B'].asks[lifted['aid']]['deadline']==start+7
        else:
            assert not dials and not fwd.lifted
            fwd.lift();assert local.ask_outcome('B',aid)=='expired'


def test_centre_down_or_restarted_has_a_bounded_outcome():
    e,local,home,fwd,aid=relay()
    def down(url):raise Unreachable('centre down')
    fwd.dial=down
    fwd.lift();assert local.up[aid]['lifted'] is False
    e.box.wall.advance(8);fwd.lift()
    assert local.ask_outcome('B',aid)=='expired'
    e,local,home,fwd,aid=relay();fwd.lift()
    home.cams.clear()
    e.box.wall.advance(7+ANSWER_GRACE+1)
    assert fwd.lift()[aid].startswith('unknown:') and not fwd.lifted


def test_torn_or_partial_book_cannot_restore_an_old_road_or_request_authority():
    for raw in ('{',None):
        e,local,home,fwd,aid=relay()
        if raw is None:e.publish(missing=['away'])
        else:e.box.vars.put('domain/auto/asks',{'B':raw})
        dials=[];fwd.dial=lambda url:dials.append(url) or home
        fwd.lift()
        assert not e.calls and not dials and not fwd.lifted
        assert local.up[aid]['lifted'] is False


def test_nonfinite_or_unrepresentable_deadline_never_requests_a_role_token():
    from vms.recording_books import Unconfirmed
    for deadline in (float('nan'), float('inf'), 10**400, True, None):
        e = road_fixture()
        raises(Unconfirmed, lambda: e.asker.ask_until('B', item()['then'], deadline))
        assert not e.calls and not e.dialled


def test_failed_first_road_consumes_deadline_before_trying_another_url():
    from vms.recording_books import Unconfirmed
    e = road_fixture()
    e.publish({**e.value, 'urls':['http://first/ingest','http://second/ingest']})
    tried = []
    def dial(url):
        tried.append(url)
        e.box.wall.advance(8)
        raise Unreachable('first road timed out')
    e.asker.dial = dial
    raises(Unconfirmed, lambda:e.asker.ask('B',item()['then'],7))
    assert tried == ['http://first/ingest']
