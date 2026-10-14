"""Worker-loop and embedded hosts of the C6 scenario executor."""
import hashlib
import json
from types import SimpleNamespace

from tests.test_autoask import item, road_fixture, settings
from tests.test_autoworker import _Log, ev
from tests.test_book_names import raises
from vms.autoworker import AutoWorker
from vms.config import SPEC
from vms.recording_books import Unconfirmed
from w2cplatform.trust.documents import sign


def shared(e, items):
    doc=sign({'term':1,'rev':1,'settings':settings(items)},e.issuer)
    raw=json.dumps(doc).encode()
    e.box.objects.put('domain/shared',raw)
    e.box.vars.put('domain/shared',{'term':1,'rev':1,'sha256':hashlib.sha256(raw).hexdigest()})


def site():
    e=road_fixture()
    e.ingest.ask=lambda *a,**kw:'ask-id'
    shared(e,[item()])
    e.box.vars.put('cam/cameras/1',SPEC.items({'id':1,'ref':'A','enabled':True}))
    index=_Log([ev(e.box.wall()-1,'cam','1','motion')])
    worker=AutoWorker('a-1',e.box.vars,e.box.objects,index=index,
        clock=e.box.clock,wall=e.box.wall,server='server',env={},
        ask_dial=e.dial,token_requests=e.door)
    worker.heartbeat_once()
    return SimpleNamespace(**locals())


def test_unassigned_worker_executes_local_trigger_and_rereads_no_event_twice():
    s=site();w,e=s.worker,s.e
    assert w.assignment().units==[]
    w.reconcile_once()
    assert e.calls==[('ask','B','A')] and e.dialled==['http://home/ingest']
    assert ('cam','motion','1') in w.wants()
    assert s.index.asked[-1]['unit']=='cam/1'
    w.reconcile_once()
    assert len(e.calls)==1 and len(e.dialled)==2
    assert s.worker.heartbeat_fields()['asks']=={'a-to-b':{'asked':e.box.wall()}}


def test_nonlocal_disabled_and_fenced_trigger_events_are_not_asks():
    for mode in ('nonlocal','disabled','fenced','summary','old'):
        s=site();e=s.e
        if mode=='nonlocal':e.box.vars.put('cam/cameras/1',SPEC.items({'id':1,'ref':'other'}))
        elif mode=='disabled':e.box.vars.put('cam/cameras/1',SPEC.items({'id':1,'ref':'A','enabled':False}))
        elif mode=='fenced':s.index.events[0]['fenced']=True
        elif mode=='summary':s.index.events[0]['repeats']=2
        else:s.index.events[0]['occurred']=e.box.wall()-20
        s.worker.reconcile_once()
        assert not e.calls and not e.dialled


def test_only_elected_worker_runs_shared_scenarios_and_slot_loss_cannot_dial():
    s=site();e=s.e
    other=AutoWorker('a-2',e.box.vars,e.box.objects,index=s.index,
        clock=e.box.clock,wall=e.box.wall,env={},ask_dial=e.dial,token_requests=e.door)
    other.heartbeat_once();other.reconcile_once()
    assert not e.calls
    request=e.door.request
    def reply_after_loss(kind,ref,by):
        reply=request(kind,ref,by)
        key=s.worker.sub.slot_key(s.worker.name)
        row,_=e.box.vars.get(key)
        e.box.vars.put(key,{**row,'holder':'another-instance'})
        return reply
    e.door.request=reply_after_loss
    s.worker.reconcile_once()
    assert e.calls==[('ask','B','A')] and not e.dialled
    assert s.worker.heartbeat_fields()['asks']=={'a-to-b':{'last':'no token at camera: the ask authority could not be confirmed'}}


def test_invalid_and_partial_windows_are_said_without_leaking_settings():
    s=site();e=s.e
    shared(e,[{**item(),'enabled':'private-value'}])
    s.worker.reconcile_once()
    assert s.worker.heartbeat_fields()['asks']=={'refused':{'a-to-b':'invalid enabled flag'}}
    shared(e,[item()])
    query=s.index.query
    s.index.query=lambda *a,**kw:{**query(*a,**kw),'truncated':True}
    s.worker.reconcile_once()
    assert s.worker.heartbeat_fields()['asks']=={'a-to-b':{'holding':{'cam/1':'trigger event window is incomplete'}}}
    s.index.query=query
    s.worker.reconcile_once()
    assert 'holding' not in s.worker.heartbeat_fields()['asks']['a-to-b']
    assert e.calls==[('ask','B','A')]


def test_duplicate_local_identity_and_unverified_shared_document_cannot_run():
    s=site();e=s.e
    e.box.vars.put('cam/cameras/2',SPEC.items({'id':2,'ref':'A','enabled':True}))
    s.worker.reconcile_once()
    assert s.worker.heartbeat_fields()['asks']=={'a-to-b':{'holding':{'cam/A':'trigger identity is not unique locally'}}}
    assert not e.calls
    e.box.vars.delete('cam/cameras/2')
    pointer,_=e.box.vars.get('domain/shared')
    e.box.vars.put('domain/shared',{**pointer,'sha256':'wrong'})
    s.worker.reconcile_once()
    assert not e.calls and not s.worker.domain_scenarios.watched


def test_embedded_device_calls_agent_as_autoworker_without_an_auto_worker():
    from vms.domainpart.device import DeviceCluster
    e=road_fixture();shared(e,[item()])
    e.ingest.ask=lambda *a,**kw:'ask-id'
    device=DeviceCluster('A',e.box.vars,wall=e.box.wall,disk=e.box.objects)
    device.boot()
    requests=[]
    def request(sub,kind,ref,role,by,request_id):
        requests.append((sub,kind,ref,role,by,request_id))
        return {**e.door.request(kind,ref,by),'request_id':request_id}
    agent=SimpleNamespace(request_token=request)
    device.host_scenarios(agent,e.dial,steady=e.box.clock)
    device.door_open=False  # a camera behind NAT still executes its local events
    assert device.on_event('motion')[0]['state']=='asked'
    assert requests[0][:5]==('cam','ask','B','autoworker','A')
    assert requests[0][5] and not e.box.objects.list('auto/heartbeats/')
    shared(e,[{**item(),'enabled':'private-value'}]);device.on_event('motion');device.publish()
    hb=json.loads(device.ram.get('cam/heartbeats/A'))
    assert hb['asks']=={'refused':{'a-to-b':'invalid enabled flag'}}
    device.power_off();assert device.on_event('motion')==[]
    device.boot();assert device.on_event('motion')==[]  # no agent or token cache survives a reboot


def test_embedded_reply_requires_exact_correlation():
    from vms.autoask_runtime import AgentDoor
    for response in ({'token':'private','exp':100,'request_id':'wrong'},{}):
        agent=SimpleNamespace(request_token=lambda *a:response)
        raises(Unconfirmed,lambda:AgentDoor(agent).request('ask','B','A'))


def test_embedded_publisher_uses_common_facts_and_withdraws_when_path_changes():
    from tests.test_autoask import publisher_fixture
    from vms.autoask_runtime import EmbeddedPublisher
    e = publisher_fixture('home')
    shared(e, [item()])
    e.box.objects.delete('auto/heartbeats/a-1')
    publisher = EmbeddedPublisher('A', e.box.vars, e.box.objects, e.box.objects, e.box.wall, e.box.clock)
    publisher.publish()
    row = e.box.vars.get('auto/asks/A')[0]
    assert json.loads(row['B'])['urls'] == ['http://home/ingest']
    assert not e.box.objects.list('auto/heartbeats/')
    assert not e.box.vars.list('auto/scenarios/')
    # It remains the same publisher when topology/placement stops making this
    # camera an endpoint. Its old authority must disappear, not age out in RAM.
    assignment = e.box.vars.get('domain/placed/rec/B')[0]
    e.box.vars.put('domain/placed/rec/B', {**assignment, 'cluster':'stranger','rev':'2'})
    publisher.publish()
    assert e.box.vars.get('auto/asks/A')[0] == {}


def test_embedded_publisher_needs_a_live_ingest_and_obeys_slot_fencing():
    from tests.test_autoask import publisher_fixture
    from vms.autoask_runtime import EmbeddedPublisher
    from w2cplatform.worker import Worker
    from vms.config import AUTO_SPEC
    e = publisher_fixture('home')
    shared(e, [item()])
    e.box.objects.delete('rec/heartbeats/r-1')
    publisher = EmbeddedPublisher('A', e.box.vars, e.box.objects, e.box.objects, e.box.wall, e.box.clock)
    publisher.publish()
    assert not e.box.vars.list('auto/asks/') and not e.box.vars.list('auto/slots/')
    e.beat('rec','r-1',ingest='http://home/ingest')
    publisher.publish()
    assert e.box.vars.get('auto/asks/A')[0]
    other = Worker(AUTO_SPEC.sub, None, e.box.vars, e.box.objects, spec=AUTO_SPEC,
                   clock=e.box.clock, wall=e.box.wall)
    other.claim_slot('A')
    before = e.box.vars.get('auto/asks/A')
    publisher.publish()
    assert e.box.vars.get('auto/asks/A') == before
    assert publisher.worker.writing_allowed is False


def test_actual_worker_pulse_document_refusals_are_separate_from_missing_roads():
    s=site();e=s.e
    shared(e,[item('duplicate'),item('duplicate')])
    s.worker.reconcile_once();s.worker.heartbeat_once()
    pulse=json.loads(e.box.objects.get('auto/heartbeats/a-1'))['asks']
    assert pulse=={'refused':{'#1':'name is repeated','#2':'name is repeated'}}
    shared(e,[item()]);e.publish({**e.value,'by':['not-A']})
    s.worker.reconcile_once();s.worker.heartbeat_once()
    pulse=json.loads(e.box.objects.get('auto/heartbeats/a-1'))['asks']
    assert pulse=={'a-to-b':{'last':'the book of asks names no door for B: not asked'}}
    assert not e.calls


def test_worker_follows_outcome_on_next_pass_without_another_event():
    s=site();e=s.e
    s.worker.reconcile_once()
    e.ingest.ask_outcome=lambda *a:'refused: the camera is offline'
    s.worker.reconcile_once()
    assert s.worker.heartbeat_fields()['asks']=={'a-to-b':{
        'asked':e.box.wall(),'last':'refused: the camera is offline'}}
    assert len(e.calls)==1
    shared(e,[]);s.worker.reconcile_once()
    assert s.worker.heartbeat_fields()['asks']=={}


def test_runtime_pulse_contains_no_foreign_trigger_and_disabled_local_camera_has_why():
    s=site();e=s.e
    foreign=item('foreign');foreign['when']['camera']='elsewhere'
    shared(e,[item(),foreign])
    e.box.vars.put('cam/cameras/1',SPEC.items({'id':1,'ref':'A','enabled':False}))
    s.worker.reconcile_once()
    assert s.worker.heartbeat_fields()['asks']=={'a-to-b':{'why':'no camera A in this cluster'}}
    e.box.vars.put('cam/cameras/1',SPEC.items({'id':1,'ref':'A','enabled':True}))
    s.worker.reconcile_once()
    assert 'why' not in s.worker.heartbeat_fields()['asks']['a-to-b']


def test_embedded_heartbeat_observes_settle_without_more_camera_events():
    from vms.autoask_runtime import Embedded
    e=road_fixture();shared(e,[item()])
    e.ingest.ask=lambda *a,**kw:'id'
    def request(*args):
        return {**e.door.request('ask','B','A'),'request_id':args[-1]}
    embedded=Embedded('A',e.box.vars,e.box.objects,SimpleNamespace(request_token=request),
        e.dial,e.box.wall,e.box.clock)
    embedded.on_event('motion')
    e.ingest.ask_outcome=lambda *a:'performed'
    assert embedded.heartbeat()=={'a-to-b':{'asked':e.box.wall(),'last':'performed'}}
    shared(e,[])
    assert embedded.heartbeat()=={}
