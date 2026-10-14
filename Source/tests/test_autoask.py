"""Shared scenario refusals and the same event executor for workers and cameras."""
import copy
from types import SimpleNamespace
import json

from tests.conftest import Clock
from vms.autoask import Executor, scenarios
from vms.recording_books import Unconfirmed
from tests.test_book_names import raises


def item(name='a-to-b', **kw):
    return {'name':name,'when':{'camera':'A','kind':'motion'},
            'then':{'camera':'B','action':'preset','arg':3,'within':10},**kw}


def settings(items):
    return {'shared':{'auto':{'scenarios':items}}}


def test_missing_or_duplicate_names_are_rejected_by_position_without_generated_ids():
    good=item()
    unnamed=item();del unnamed['name']
    entries=[good,unnamed,item('duplicate'),item('duplicate'),'bad']
    valid,refused=scenarios(settings(entries))
    assert valid==[good]
    assert refused=={'#2':'name is required','#3':'name is repeated','#4':'name is repeated','#5':'name is required'}


def test_damaged_scenarios_refuse_with_nonsecret_reasons_and_others_continue():
    bads=[{'when':None},{'then':[]},{'extra':'secret-value'},{'enabled':1},{'rate_per_minute':-1}]
    bads += [{'then':{'camera':'B','action':'preset','within':x}} for x in (0,float('nan'),float('inf'),10**400)]
    entries=[{**item('bad-'+str(n)),**change} for n,change in enumerate(bads)]
    valid,refused=scenarios(settings([*entries,item('ok'),item('off',enabled=False)]))
    assert valid==[item('ok')]
    assert set(refused)=={x['name'] for x in entries}
    assert 'secret-value' not in str(refused) and 'then' not in str(refused)
    assert scenarios(settings('bad'))==([],{'#1':'scenarios is not a list'})


def executor(items):
    doc=SimpleNamespace(items=items)
    shared=SimpleNamespace(settings=lambda:settings(doc.items))
    clock=Clock(100)
    calls=[]
    class Asker:
        def __init__(self,by):self.by=by
        def outcome(self,target,aid,deadline):
            return None
        def ask(self,target,action,within):
            calls.append((self.by,target,action,within))
            return 'ingest','id'
    return Executor(shared,Asker,clock),doc,clock,calls


def test_executor_keeps_raw_then_and_event_deadline_and_ignores_other_triggers():
    ex,doc,clock,calls=executor([item()])
    assert ex.on_event('other','motion')==[] and not calls
    assert ex.on_event('A','other')==[] and not calls
    result=ex.on_event('A','motion',{'ts':97})
    assert calls==[('A','B',item()['then'],7)]
    assert result[0]['state']=='asked' and result[0]['deadline']==107
    assert doc.items==[item()]  # serializing a request never mutates the signed document


def test_summaries_expired_events_rate_and_document_removal_do_not_ask_again():
    ex,doc,clock,calls=executor([item(rate_per_minute=1)])
    assert ex.on_event('A','motion',{'repeats':2})==[]
    assert 'deadline' in ex.on_event('A','motion',{'ts':89})[0]['state'] and not calls
    assert ex.on_event('A','motion')[0]['state']=='asked'
    assert 'ceiling' in ex.on_event('A','motion')[0]['state'] and len(calls)==1
    clock.advance(61)
    assert ex.on_event('A','motion')[0]['state']=='asked'
    doc.items=[]
    assert ex.on_event('A','motion')==[] and not ex.fired


def test_refusals_describe_current_pass_and_clear_after_document_fix():
    ex,doc,clock,calls=executor([item(enabled='bad')])
    assert ex.on_event('A','motion')==[]
    assert ex.heartbeat()=={'refused':{'a-to-b':'invalid enabled flag'}}
    doc.items=[item()]
    ex.on_event('A','motion')
    assert ex.heartbeat()=={'a-to-b':{'asked':100}}
    def refused(_):raise Unconfirmed('must-not-leak-token-or-body')
    ex.asker=refused
    ex.on_event('A','motion')
    assert ex.heartbeat()['a-to-b']['last']=='no token at this cluster: the ask authority could not be confirmed'
    assert 'refused' not in ex.heartbeat()
    assert 'must-not-leak' not in str(ex.heartbeat())


def test_one_worker_pass_accumulates_refusals_across_events_until_refresh():
    ex,doc,clock,calls=executor([item('first'),item('second')])
    doc.items[1]['when']['camera']='C'
    def refused(_):raise Unconfirmed('private')
    ex.asker=refused
    ex.refresh()
    ex.on_event('A','motion',refresh=False)
    ex.on_event('C','motion',refresh=False)
    assert set(ex.heartbeat())=={'first','second'}
    assert all(v['last'].startswith('no token at ') for v in ex.heartbeat().values())
    doc.items=[];ex.refresh()
    assert ex.heartbeat()=={}


def road_fixture(*, trust=True):
    from tests.conftest import Box
    from vms.autoask import Asker, BOOK
    from vms.role_tokens import RoleTokens
    from w2cplatform.trust.tokens import TokenIssuer
    box = Box()
    box.vars.put('domain/member', {'cluster':'camera'})
    box.vars.put('domain/holder', {'doc':json.dumps({'holder':'centre','term':1})})
    box.vars.put('domain/member-topology', {'doc':json.dumps({'rev':1,'centre':'centre','star':[],'via':{}})})
    value = {'target':'B','by':['A'],'acts':[item()['then']],
             'urls':['http://home/ingest'],'to':['camera']}
    def publish(value=value, *, member='home', missing=(), path=BOOK):
        box.vars.put(path, {'':json.dumps({'missing':list(missing)}),
            'B':json.dumps({'entries':[{'member':member,'item':'w1/B','value':value}], 'missing':list(missing)})})
    publish()
    issuer = TokenIssuer('site')
    from w2cplatform.trust.memberkey import MemberKey
    issuer.book_seal = MemberKey.new().seal_pub
    if trust:
        box.vars.put('domain/keys', issuer.keyset().to_items())
    calls, dialled = [], []
    claims = {'kind':'ask','ref':'B','by':'A','acts':[item()['then']],'aud':['home']}
    class Door:
        def request(self, kind, ref, by):
            calls.append((kind,ref,by))
            token=issuer.issue('camera',100,now=box.wall(),**claims)
            return {'token':token,'exp':box.wall()+100}
    door = Door()
    ingest = SimpleNamespace(ask=lambda *args,**kw:('ask-id',args,kw), ask_outcome=lambda *args:None)
    def dial(url):
        dialled.append(url)
        return ingest
    tokens = RoleTokens('autoworker',door,clock=box.clock)
    asker = Asker('A',box.vars,dial,tokens,box.wall)
    return SimpleNamespace(**locals())


def test_book_reader_and_role_token_preserve_raw_action_and_origin():
    e=road_fixture()
    ingest, result=e.asker.ask('B',item()['then'],7)
    aid,args,kw=result
    assert aid=='ask-id' and ingest is e.ingest
    assert args[1:]==('B',item()['then'],e.box.wall()+7)
    assert kw=={'camera_now':e.box.wall()}
    assert e.calls==[('ask','B','A')] and e.dialled==['http://home/ingest']
    assert 'token' not in str(e.box.vars.get('domain/auto/asks')[0])


def test_corrupt_policy_refuses_before_token_request_and_is_nonsecret_in_pulse():
    for key, value in (
        ('domain/holder', {'doc':'private-malformed'}),
        ('domain/member-topology', {'doc':'private-malformed'}),
        ('domain/placement/rec/B', {'cluster':'home', 'rev':'private-malformed'}),
    ):
        e=road_fixture()
        e.box.vars.put(key,value)
        raises(Unconfirmed,lambda:e.asker.ask('B',item()['then'],7))
        ex=Executor(SimpleNamespace(settings=lambda:settings([item()])),lambda _:e.asker,e.box.wall)
        assert ex.on_event('A','motion')[0]['state'].startswith('no token at ')
        assert ex.heartbeat()=={'a-to-b':{'last':'no token at camera: the ask authority could not be confirmed'}}
        assert not e.calls and not e.dialled


def test_role_request_time_never_extends_the_event_deadline():
    for delay in (2,8):
        e=road_fixture();request=e.door.request;start=e.box.wall()
        def delayed(kind,ref,by):
            reply=request(kind,ref,by)
            e.box.wall.advance(delay)
            return reply
        e.door.request=delayed
        if delay==8:
            raises(Unconfirmed,lambda:e.asker.ask('B',item()['then'],7))
            assert not e.dialled
        else:
            _,result=e.asker.ask('B',item()['then'],7)
            assert result[1][-1]==start+7
            assert result[2]['camera_now']==start+delay


def test_partial_flat_or_unaddressed_books_never_request_a_token():
    for mode in ('partial','flat','recipient','trigger','action'):
        e=road_fixture()
        if mode=='partial':e.publish(missing=['away'])
        elif mode=='flat':e.box.vars.put('domain/auto/asks',{'B':json.dumps(e.value)})
        else:
            value=copy.deepcopy(e.value)
            value[{'recipient':'to','trigger':'by','action':'acts'}[mode]] = (
                [item()['then'] | {'arg':4}] if mode=='action' else ['stranger'])
            e.publish(value)
        raises(Unconfirmed,lambda:e.asker.ask('B',item()['then'],7))
        assert not e.calls and not e.dialled


def test_book_never_expands_signed_audience_upward_hop_or_action():
    for change in ({'aud':['elsewhere']},{'up':'centre'}, {'acts':[item()['then']|{'arg':4}]},
                   {'by':'other'}, {'ref':'other'}, {'aud':'home'}):
        e=road_fixture();e.claims.update(change)
        try:
            assert e.asker.ask('B',item()['then'],7) is None
        except Unconfirmed:
            pass
        assert not e.dialled


def test_holder_reads_own_generation_instead_of_leftover_copy():
    e=road_fixture()
    e.box.vars.put('domain/holder',{'doc':json.dumps({'holder':'camera','term':2})})
    raises(Unconfirmed,lambda:e.asker.ask('B',item()['then'],7))
    assert not e.calls
    e.publish(path='domain/auto/asks/camera')
    assert e.asker.ask('B',item()['then'],7)[0] is e.ingest


def test_changes_during_role_request_forget_pair_and_never_dial():
    for mode in ('book','topology','identity','missing','placement'):
        e=road_fixture();request=e.door.request
        def changed(kind,ref,by):
            reply=request(kind,ref,by)
            if mode=='book':e.publish(member='other')
            elif mode=='missing':e.publish(missing=['away'])
            elif mode=='identity':e.box.vars.put('domain/member',{'cluster':'other'})
            elif mode=='placement':e.box.vars.put('domain/placed/rec/B',{'cluster':'other','origin':'camera',
                'copies':'[]','reason':'operator','at':str(e.box.wall()),'rev':'2'})
            else:e.box.vars.put('domain/member-topology',{'doc':json.dumps({'rev':2,'centre':'other','star':[],'via':{}})})
            return reply
        e.door.request=changed
        raises(Unconfirmed,lambda:e.asker.ask('B',item()['then'],7))
        assert not e.dialled and not e.tokens.cached


def test_absent_trust_fails_closed_and_outcome_has_bounded_wait():
    e=road_fixture(trust=False)
    raises(Unconfirmed,lambda:e.asker.ask('B',item()['then'],7))
    assert not e.dialled
    assert e.asker.outcome('B','id',e.box.wall()) is None
    assert e.asker.outcome('B','id',0).startswith('lost:')


def publisher_fixture(own='home', *, assigned=True, star=()):
    from w2cplatform.contract import Heartbeat, Eyes
    e=road_fixture()
    roster=['camera','centre','home','relay','stranger']
    e.box.vars.put('domain/member',{'cluster':own})
    e.box.vars.put('domain/member-list',{'doc':json.dumps({'rev':1,'members':{n:{} for n in roster}})})
    e.box.vars.put('domain/member-topology',{'doc':json.dumps({'rev':1,'centre':'centre',
        'star':list(star),'via':{'camera':'relay'}})})
    if own == 'centre':
        e.box.vars.put('domain/members',e.box.vars.get('domain/member-list')[0])
        e.box.vars.put('domain/topology',e.box.vars.get('domain/member-topology')[0])
    if assigned:
        e.box.vars.put('domain/placed/rec/B',{'cluster':'home','origin':'stranger','copies':'[]',
            'reason':'operator','at':str(e.box.wall()),'rev':'1'})
    e.worker=SimpleNamespace(vars=e.box.vars,objects=e.box.objects,name='a-1',
        eyes=Eyes(e.box.clock,e.box.wall))
    def beat(sub,name,**extra):
        e.box.objects.put(sub+'/heartbeats/'+name,Heartbeat(name,e.box.wall(),extra=extra).to_bytes())
    e.beat=beat
    beat('auto','a-1');beat('rec','r-1',ingest='http://'+own+'/ingest')
    return e


def test_publisher_emits_home_centre_and_relay_roads_with_raw_unique_actions():
    from vms.autoask import contribution
    for own in ('home','centre','relay','stranger'):
        e=publisher_fixture(own)
        second=item('second');second['when']['camera']='C'
        result=contribution(e.worker,settings([item(),item('same'),second]))
        if own=='stranger':
            assert result=={};continue
        row=json.loads(result['B'])
        assert row['target']=='B' and row['by']==['A','C'] and row['acts']==[item()['then']]
        assert row['urls']==['http://'+own+'/ingest'] and 'token' not in str(row)
        if own=='relay':assert row['to']==['camera'] and row['up']=='centre'
        else:assert row['to']==['camera','centre','home','relay','stranger'] and 'up' not in row


def test_publisher_election_and_ingest_freshness_and_document_removal():
    from vms.autoask import contribution
    e=publisher_fixture()
    assert contribution(e.worker,settings([item()]))
    e.beat('auto','a-0')
    assert contribution(e.worker,settings([item()]))=={}
    e.box.clock.advance(46)
    e.box.wall.advance(46)
    e.beat('auto','a-1')
    assert contribution(e.worker,settings([item()]))=={}
    e.beat('rec','r-1',ingest='http://new/ingest')
    assert json.loads(contribution(e.worker,settings([item()]))['B'])['urls']==['http://new/ingest']
    assert contribution(e.worker,settings([]))=={}


def test_unassigned_target_has_centre_and_relay_roads_and_star_moves_home():
    from vms.autoask import contribution
    for own in ('centre','relay'):
        e=publisher_fixture(own,assigned=False)
        assert contribution(e.worker,settings([item()]))
    e=publisher_fixture('home',star=['home'])
    assert contribution(e.worker,settings([item()]))=={}
    e=publisher_fixture('relay',assigned=False)
    value={'ref':'B','to':['relay','centre'],'live_url':'','server':'camera','as_of':e.box.wall(),'polls':True}
    e.box.vars.put('domain/cam/sources',{'':json.dumps({'missing':[]}),
        'B':json.dumps({'entries':[{'member':'camera','item':'w1/B','value':value}],'missing':[]})})
    row=json.loads(contribution(e.worker,settings([item()]))['B'])
    assert 'up' not in row and 'stranger' in row['to']


def test_untrusted_signed_or_revoked_token_cannot_start_transport():
    from w2cplatform.trust.tokens import verify
    for mode in ('signature','kind','revoked','unreadable'):
        e=road_fixture()
        if mode=='signature':
            e.box.vars.put('domain/keys',{'current':'wrong','book_seal':e.issuer.book_seal})
        elif mode=='kind':e.claims['kind']='pull'
        elif mode=='unreadable':
            get = e.box.vars.get
            def unavailable(path):
                if path == 'domain/revoked':
                    raise OSError('revocations store did not answer')
                return get(path)
            e.box.vars.get = unavailable
        else:
            original=e.door.request
            def revoked(kind,ref,by):
                reply=original(kind,ref,by)
                claims=verify(reply['token'],e.issuer.keyset(),now=e.box.wall())
                from w2cplatform.trust.tokens import RevocationList
                revocations=RevocationList();revocations.revoke(claims)
                e.box.vars.put('domain/revoked',revocations.to_items())
                return reply
            e.door.request=revoked
        raises(OSError if mode == 'unreadable' else Unconfirmed,
               lambda:e.asker.ask('B',item()['then'],7))
        assert not e.dialled


def test_runtime_status_settles_without_new_events_and_drops_removed_scenarios():
    ex,doc,clock,calls=executor([item()])
    observed=[]
    answers=[None,'performed']
    class Requester:
        def ask(self,*args):return object(),'id'
        def outcome(self,*args):
            observed.append(args)
            return answers.pop(0)
    ex.asker=lambda _:Requester()
    ex.on_event('A','motion')
    pulse=ex.heartbeat()
    assert pulse=={'a-to-b':{'asked':100}}
    assert isinstance(pulse['a-to-b']['asked'],(float,int))
    json.dumps(pulse)  # no live ingest, token or raw action escapes
    ex.settle();assert 'last' not in ex.heartbeat()['a-to-b']
    ex.settle();assert ex.heartbeat()['a-to-b']['last']=='performed'
    assert observed==[('B','id',110),('B','id',110)] and not ex.pending
    pulse['a-to-b']['last']='mutated'
    assert ex.heartbeat()['a-to-b']['last']=='performed'
    doc.items=[];ex.refresh()
    assert ex.heartbeat()=={} and not ex.pending


def test_outcome_distinguishes_restart_unreadable_and_unreachable_after_grace():
    from w2cplatform.domain.federation import Unreachable
    for mode,expected in (
        ('missing','lost: no ingest knows this ask — it restarted, or the ask never arrived'),
        ('unread',"lost: the ingest's answer does not read"),
        ('offline','lost: the ingest does not answer'),
    ):
        e=road_fixture()
        if mode=='unread':e.ingest.ask_outcome=lambda *a:{'private':'wrong shape'}
        if mode=='offline':
            def unavailable(*a):raise Unreachable('private-url')
            e.ingest.ask_outcome=unavailable
        assert e.asker.outcome('B','id',e.box.wall()) is None
        assert e.asker.outcome('B','id',0)==expected
    for value in ('performed','refused: camera cannot do this','expired'):
        e=road_fixture();e.ingest.ask_outcome=lambda *a:value
        assert e.asker.outcome('B','id',e.box.wall())==value


def test_unreadable_ask_ack_is_not_followed_and_does_not_leak_to_pulse():
    ex,doc,clock,calls=executor([item()])
    ex.asker=lambda _:SimpleNamespace(ask=lambda *a:(object(),{'private':'token'}))
    ex.on_event('A','motion')
    assert ex.heartbeat()=={'a-to-b':{'asked':100,'last':
        "asked; the ingest's answer does not read, so its outcome is not followed"}}
    assert not ex.pending


def test_product_words_for_deadline_ceiling_no_answer_token_and_ingest_refusal():
    from vms.ingest import Refused
    from vms.autoask import NoAskToken
    ex,doc,clock,calls=executor([item(rate_per_minute=1)])
    ex.on_event('A','motion',{'ts':89})
    assert ex.heartbeat()['a-to-b']['last']=="an event seen after its scenario's deadline: not asked"
    ex.on_event('A','motion');ex.on_event('A','motion')
    assert ex.heartbeat()['a-to-b']['last']=='over its ceiling of 1 a minute: not asked'
    for error,expected in ((None,'no ingest answered'),
        (NoAskToken('office'),'no token at office: a current role token could not be obtained'),
        (Refused('the complete action is not authorized'),'refused: the complete action is not authorized')):
        ex,doc,clock,calls=executor([item()])
        def request(*a):
            if error:raise error
            return None
        ex.asker=lambda _:SimpleNamespace(ask=request)
        ex.on_event('A','motion')
        assert ex.heartbeat()=={'a-to-b':{'last':expected}}


def test_multiple_asks_of_one_scenario_are_all_followed():
    ex,doc,clock,calls=executor([item()]);ids=iter(['one','two']);observed=[]
    class Requester:
        def ask(self,*a):return object(),next(ids)
        def outcome(self,target,aid,deadline):
            observed.append(aid)
            return None
    ex.asker=lambda _:Requester()
    ex.on_event('A','motion');ex.on_event('A','motion')
    observed.clear();ex.settle()
    assert observed==['one','two'] and len(ex.pending)==2
    doc.items=[];ex.refresh()
    assert not ex.pending and ex.heartbeat()=={}


def test_asked_is_the_send_timestamp_even_when_camera_wall_clock_starts_at_zero():
    ex,doc,clock,calls=executor([item()])
    requester=SimpleNamespace(sent=0,ask=lambda *a:(object(),'id'))
    ex.asker=lambda _:requester
    ex.on_event('A','motion')
    assert ex.heartbeat()=={'a-to-b':{'asked':0}}
