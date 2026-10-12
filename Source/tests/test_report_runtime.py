"""ADR-0074 runtime acceptance uses testsub reports, actual signatures and store snapshots."""
import json
import tempfile
from types import SimpleNamespace

from w2cplatform.objects import FsObjectStore
from w2cplatform.cluster.variables import FakeVariables
from w2cplatform.domain.carry import HolderDoor, CarryClient, Refused, publication_bytes
from w2cplatform.domain.members import Members
from w2cplatform.domain.relay import RelayDoor, relayed
from w2cplatform.domain.reports import read, accept
from w2cplatform.domain.topology import Topology
from w2cplatform.domain.steps import one_pass
from w2cplatform.domain.uplink import member_copy
from w2cplatform.trust.memberkey import MemberKey, sign_request


def _site():
    now=[1000.]
    variables=FakeVariables()
    objects=FsObjectStore(tempfile.mkdtemp())
    keys={name:MemberKey.new() for name in ('a','relay','b')}
    members=Members(variables,wall=lambda:now[0])
    for name,key in keys.items(): members.add(name,'test',key=key.pub,seal=key.seal_pub)
    Topology(variables).edit(lambda d:d.update(via={'a':'relay'}),base_rev=0)
    return now,keys,HolderDoor(variables,objects,wall=lambda:now[0])


def _body(key,at):
    return json.dumps(dict(sent_at=at,key=key.pub,seal=key.seal_pub,objects={},rows={},pages={}),indent=2).encode()


def _refused(fn,status):
    try: fn()
    except Refused as e: assert e.status==status,(e.status,e.detail)
    else: raise AssertionError('must refuse')


def test_signed_direct_ingress_keeps_original_bytes_and_replay_does_not_refresh():
    now,keys,door=_site()
    raw=_body(keys['a'],now[0])
    sig=sign_request(keys['a'],'POST','/api/member/a',raw,now[0])
    door.member('a',raw,sig)
    old=read('a',door.objects)
    assert old.raw==raw and old.mark['signature']==sig
    now[0]+=1
    door.member('a',raw,sig)
    assert read('a',door.objects).mark==old.mark
    changed=raw+b' '
    _refused(lambda:door.member('a',changed,sig),401)
    signed=sign_request(keys['a'],'POST','/api/member/a',changed,now[0])
    _refused(lambda:door.member('a',changed,signed),409)
    _refused(lambda:door.member('b',raw,sig),401)


def test_relay_checks_member_signature_and_holder_checks_topology_and_keeps_nested_bytes():
    now,keys,door=_site()
    store=FsObjectStore(tempfile.mkdtemp())
    agent=SimpleNamespace(now=lambda:now[0],relayed={'a':{'key':keys['a'].pub}},cluster='relay')
    relay=RelayDoor(agent,store)
    raw=_body(keys['a'],now[0])
    sig=sign_request(keys['a'],'POST','/api/member/a',raw,now[0])
    _refused(lambda:relay.member('a',raw+b' ',sig),401)
    relay.member('a',raw,sig)
    client=CarryClient(door,'relay',keys['relay'],wall=lambda:now[0])
    assert client.relay_up(relayed(['a'],store))=={'refused':{}}
    snap=read('a',door.objects)
    assert snap.raw==raw and snap.mark['via']=='relay' and snap.mark['signature']==''
    now[0]+=1
    client.relay_up(relayed(['a'],store))
    assert read('a',door.objects).mark==snap.mark
    assert 'b' in client.relay_up({'b':raw})['refused']


def test_one_pass_pins_generation_and_next_pass_reads_new_generation():
    # The platform's declared row exists independently of any subsystem.
    from w2cplatform.domain.agent import ROOT_PATH
    store=FsObjectStore(tempfile.mkdtemp())
    def body(n):
        return publication_bytes(dict(sent_at=n,objects={},pages={},rows={ROOT_PATH:{'items':{'n':str(n)},'idx':n}}))
    accept('a',body(1),store,received_at=1000)
    copy=member_copy('a',store,wall=lambda:1000)
    with one_pass():
        assert copy.vars.get(ROOT_PATH)[0]=={'n':'1'}
        accept('a',body(2),store,received_at=1000)
        assert copy.vars.get(ROOT_PATH)[0]=={'n':'1'}
    with one_pass(): assert copy.vars.get(ROOT_PATH)[0]=={'n':'2'}


def test_freshness_survives_reader_restart_and_relay_replay():
    from w2cplatform.domain.federation import Unreachable
    from w2cplatform.domain.uplink import last_report_at
    now,keys,door=_site()
    raw=_body(keys['a'],now[0])
    client=CarryClient(door,'relay',keys['relay'],wall=lambda:now[0])
    client.relay_up({'a':raw})
    received=now[0]
    now[0]+=60
    client.relay_up({'a':raw})
    copy=member_copy('a',door.objects,wall=lambda:now[0])
    try:
        copy.vars.get('domain/root')
        raise AssertionError('restart or replay must not refresh a silent member')
    except Unreachable:
        pass
    assert last_report_at('a',door.objects,wall=lambda:now[0])==received


def test_relay_http_ingress_is_signed_and_preserves_publication_bytes():
    import threading
    from http.server import ThreadingHTTPServer
    from w2cplatform.domain.carry import _http_post
    from w2cplatform.domain.relay import door_handler
    now,keys,holder=_site()
    store=FsObjectStore(tempfile.mkdtemp())
    agent=SimpleNamespace(now=lambda:now[0],relayed={'a':{'key':keys['a'].pub}},cluster='relay')
    server=ThreadingHTTPServer(('127.0.0.1',0),door_handler(RelayDoor(agent,store)))
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    url='http://127.0.0.1:'+str(server.server_address[1])
    raw=_body(keys['a'],now[0])
    signature=sign_request(keys['a'],'POST','/api/member/a',raw,now[0])
    try:
        _refused(lambda:_http_post(url,'/api/member/a',raw,'invalid',2),401)
        _http_post(url,'/api/member/a',raw,signature,2)
        assert read('a',store).raw==raw
        client=CarryClient(holder,'relay',keys['relay'],wall=lambda:now[0])
        assert client.relay_up(relayed(['a'],store))=={'refused':{}}
        assert read('a',holder.objects).raw==raw
    finally:
        server.shutdown();server.server_close();thread.join(2)


def test_malformed_publication_is_refused_before_any_generation_is_written():
    now,keys,door=_site()
    for sent in (True,False,'1000',None):
        doc=json.loads(_body(keys['a'],now[0]));doc['sent_at']=sent
        raw=json.dumps(doc).encode()
        sig=sign_request(keys['a'],'POST','/api/member/a',raw,now[0])
        _refused(lambda:door.member('a',raw,sig),400)
    doc=json.loads(_body(keys['a'],now[0]));doc['outcomes']=[]
    raw=json.dumps(doc).encode()
    sig=sign_request(keys['a'],'POST','/api/member/a',raw,now[0])
    _refused(lambda:door.member('a',raw,sig),400)
    assert door.objects.list('domain/members/a/')==[]
    # Deep JSON is a bad request, not an exception escaping the signed relay handler.
    raw=b'{"relayed":'+b'['*2000+b'0'+b']'*2000+b'}'
    sig=sign_request(keys['relay'],'POST','/api/relay/relay',raw,now[0])
    _refused(lambda:door.relay('relay',raw,sig),400)


def test_real_holder_backup_and_move_preserve_accepted_bytes_and_replay_boundary():
    from tests.test_domain_platform import site
    from w2cplatform.domain.agent import DomainAgent, DomainPublisher
    from w2cplatform.domain.term import DomainHolder, move_domain
    from w2cplatform.domain.uplink import base
    from w2cplatform.trust.signer import Signer
    fed,wall=site()
    north,south=fed.clusters['north'],fed.clusters['south']
    signer=Signer('acme',north.vars,now=wall)
    DomainPublisher(north.vars).publish_keys(signer.tokens.keyset())
    key=MemberKey.new()
    for delta in (-2,-1):
        raw=_body(key,wall()+delta)
        signature=sign_request(key,'POST','/api/member/south',raw,wall()+delta)
        accept('south',raw,north.objects,received_at=wall()+delta,signature=signature)
    before=read('south',north.objects)
    orphan=base('south')+'reports/3'
    north.objects.put(orphan,_body(key,wall()))
    holder=DomainHolder(fed,'north',signer,1,wall,objects=north.objects)
    holder.claim()
    holder.backup(['south'],north.objects)
    assert DomainAgent('south',north.vars,south.vars,now=wall,domain_objects=north.objects,
                       cluster_objects=south.objects).sync()
    new,_=move_domain(fed,'south',signer.backup(),'acme',lambda n:fed.clusters[n].objects,wall)
    assert new.term==2
    after=read('south',south.objects)
    assert after.raw==before.raw and after.mark==before.mark
    assert south.objects.get(orphan) is None
    assert accept('south',before.raw,south.objects,received_at=wall()+300).mark==before.mark
    next_report=accept('south',_body(key,wall()),south.objects,received_at=wall())
    assert next_report.mark['rev']==before.mark['rev']+1


def test_knocking_pins_identity_time_and_count_to_one_generation():
    from w2cplatform.domain.uplink import base
    store=FsObjectStore(tempfile.mkdtemp())
    members=Members(FakeVariables())
    first,second=MemberKey.new(),MemberKey.new()
    accept('a',_body(first,1),store,received_at=1)
    get=store.get
    fired=[False]
    def race(path):
        raw=get(path)
        if path==base('a')+'reported' and not fired[0]:
            fired[0]=True
            accept('a',_body(second,2),store,received_at=2)
        return raw
    store.get=race
    shown=members.knocking(store)[0]
    assert (shown['last'],shown['times'],shown['key'])==(1,1,first.pub)
    shown=members.knocking(store)[0]
    assert (shown['last'],shown['times'],shown['key'])==(2,2,second.pub)
