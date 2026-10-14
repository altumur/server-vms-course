"""Document scope on two unrelated platform test subsystems."""
import copy
import json
import tempfile
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from tests.test_book_runtime import site
from tests.test_book_names import raises
from tests.test_token_requests import raw_spec, client, signed, serving
from tests.test_unit_token_requests import publish
from w2cplatform import catalog
from w2cplatform.console import Bounds, UnixConsoleServer
from w2cplatform.configstorevars import unix_transport
from w2cplatform.spec import SubsystemSpec
from w2cplatform.domain import declared, placement, tokenrequest
from w2cplatform.domain.agent import DomainAgent
from w2cplatform.domain.carry import HolderDoor, Refused
from w2cplatform.domain.shared import SharedSettings
from w2cplatform.trust.tokens import DeclaredIssuer, verify

BINDING = {'doc':'testsub2','items':'rules','name':'name','enabled':'enabled',
 'trigger':'when.item','target':'then.item','act':'then','placement':'testsub2',
 'ref_claim':'ref','trigger_claim':'by','acts_claim':'acts','up_claim':'up','audience_claim':'aud'}


def scoped(sub='testsub'):
    raw=raw_spec(sub)
    raw['domain']['ref']='name'
    raw['domain']['tokens']['tally']={'lifetime':60,'claims':['ref','by','acts','up','aud'],
        'grant':[sub+'worker'],'scenario':dict(BINDING)}
    return raw


def item(name='one',by='trigger',ref='target',**kw):
    return {'name':name,'when':{'item':by},'then':{'item':ref,'add':2,'within':10},**kw}


@contextmanager
def issuing():
    with site(two=True) as e:
        raws=[scoped(s.name) for s in e.specs]
        raws[1]['domain']['tokens']['tally2']=raws[1]['domain']['tokens'].pop('tally')
        raws[1]['domain']['shared']=[{'name':'rules','type':'json','schema':{'type':'array'}}]
        specs=[SubsystemSpec.from_dict(r) for r in raws]
        with patch.object(catalog,'_loaded',{s.name:s for s in specs}),patch.object(catalog,'_derived',{}):
            e.specs=specs
            e.north.vars.put('domain/holder',{'doc':json.dumps({'holder':'north','term':1})})
            e.door=HolderDoor(e.north.vars,e.north.objects,wall=e.wall,
                token_issuer=DeclaredIssuer(e.signer.tokens,declared.token_kinds()))
            e.settings=SharedSettings(e.north.vars,e.north.objects,e.signer.tokens,wall=e.wall)
            for sub in ('testsub','testsub2'):
                publish(e,sub=sub,refs=('trigger',))
                publish(e,member='north',sub=sub,refs=('target',))
            set_items(e,[item()])
            yield e


def set_items(e,items):
    doc,_=e.settings.current()
    e.settings.edit(lambda s:s.update(shared={'testsub2':{'rules':items}}),doc['rev'])


def request(e,sub='testsub',member='south',ref='target',by='trigger',role=None):
    return client(e,member).request_token(sub,'tally' if sub=='testsub' else 'tally2',ref,role or sub+'worker',by)


def claims(e,**kw):
    return verify(request(e,**kw)['token'],e.signer.tokens.keyset(),now=e.wall())


def test_loader_closes_paths_claims_and_scope_combinations_in_two_subsystems():
    for sub in ('testsub','testsub2'):
        raw=scoped(sub)
        assert SubsystemSpec.from_dict(raw).domain.tokens['tally']['scenario']==BINDING
        for key in set(BINDING)-{'placement'}:
            broken=copy.deepcopy(raw);del broken['domain']['tokens']['tally']['scenario'][key]
            raises(ValueError,lambda:SubsystemSpec.from_dict(broken))
        for changes in ({'other':1},{'doc':'../bad'},{'placement':''},{'trigger':'when..item'},
                        {'items':[]},{'enabled':1},{'target':''},{'acts_claim':'ref'},{'up_claim':'unknown'}):
            broken=copy.deepcopy(raw);broken['domain']['tokens']['tally']['scenario'].update(changes)
            raises(ValueError,lambda:SubsystemSpec.from_dict(broken))
        for other in ('unit','placement'):
            broken=copy.deepcopy(raw);broken['domain']['tokens']['tally'][other]={}
            raises(ValueError,lambda:SubsystemSpec.from_dict(broken))
        for key in ('grant','scenario'):
            broken=copy.deepcopy(raw);del broken['domain']['tokens']['tally'][key]
            raises(ValueError,lambda:SubsystemSpec.from_dict(broken))


def test_signed_request_derives_canonical_raw_actions_for_two_subsystems():
    from w2cplatform.trust.jcs import jcs
    with issuing() as e:
        other=item('two');other['then']={'add':1,'item':'target','extra':{'n':3}}
        set_items(e,[item(),item('same-action'),other])
        for sub in ('testsub','testsub2'):
            got=claims(e,sub=sub)
            assert (got['ref'],got['by'],got['sub'])==('target','trigger','south')
            assert got['acts']==sorted([item()['then'],other['then']],key=jcs)
            assert got['aud']==['north'] and 'up' not in got
        assert tokenrequest.grants()['tally']==('testsub',('testsubworker',))
        token=request(e)['token']
        for c in e.fed.clusters.values():
            assert all(token not in str(c.vars.get(k)[0]) for k in c.vars.list(''))
            assert all(token.encode() not in (c.objects.get(k) or b'') for k in c.objects.list(''))


def test_bad_disabled_duplicate_missing_name_or_wrong_pair_refuses():
    with issuing() as e:
        for items in ([],[item(enabled=False)],[item(enabled='yes')],[item(),item()],
                      [{k:v for k,v in item().items() if k!='name'}],[item(ref='other')],[item(by='other')]):
            set_items(e,items)
            assert raises(Refused,lambda:request(e)).status==403
        set_items(e,[item()])
        for kw in ({'by':'target'},{'member':'north'},{'role':'domain'}):
            assert raises(Refused,lambda:request(e,**kw)).status==403
        assert raises(Refused,lambda:request(e,by=None)).status==400


def test_forged_claims_unsigned_bytes_and_unverified_document_refuse():
    with issuing() as e:
        for extra in ({'acts':[]},{'aud':['south']},{'up':'south'}):
            raw,sig=signed(e,{'request_id':'one','role':'testsubworker','ref':'target','by':'trigger',**extra})
            assert raises(Refused,lambda:e.door.token('south','testsub','tally',raw,sig)).status==400
        raw,sig=signed(e,{'request_id':'one','role':'testsubworker','ref':'target','by':'trigger'})
        assert raises(Refused,lambda:e.door.token('south','testsub','tally',raw+b' ',sig)).status==401
        pointer,_=e.north.vars.get('domain/shared');e.north.objects.put(pointer['object'],b'{}')
        assert raises(Refused,lambda:request(e)).status==403


def test_withdrawn_or_corrupt_trigger_cannot_reuse_previous_report():
    from w2cplatform.domain.reports import read
    from w2cplatform.domain.uplink import base
    with issuing() as e:
        assert claims(e)['by']=='trigger'
        publish(e,refs=())
        assert raises(Refused,lambda:request(e)).status==403
        publish(e,refs=('trigger',))
        assert claims(e)['by']=='trigger'
        snap=read('south',e.north.objects)
        e.north.objects.put(base('south')+'reports/'+str(snap.mark['rev']),b'{')
        assert raises(Refused,lambda:request(e)).status==403


def test_assignment_home_centre_star_and_missing_policy_are_authoritative():
    with issuing() as e:
        for row,topology,expected in (
            ({'cluster':'north'},{'rev':1,'centre':'south'},['north','south']),
            ({'cluster':'south'},{'rev':2,'centre':'north','star':['south']},['north']),
            ({'cluster':'south'},{'rev':3,'centre':'south'},['south'])):
            placement.assign(e.north.vars,'testsub2','target',row,e.wall)
            e.north.vars.put('domain/topology',{'doc':json.dumps(topology)})
            assert claims(e)['aud']==expected
        e.north.vars.put('domain/topology',{'doc':'{'})
        assert raises(Refused,lambda:request(e)).status==409


def test_local_role_socket_preserves_request_id_and_by_and_refuses_claims():
    with issuing() as e,tempfile.TemporaryDirectory() as tmp:
        agent=DomainAgent('south',client(e),e.fed.clusters['south'].vars,now=e.wall,key=e.memberkeys['south'])
        path=str(Path(tmp)/'role.sock')
        with serving(UnixConsoleServer(path,tokenrequest.local_handler(agent,'testsubworker'),Bounds())):
            got=tokenrequest.WorkerTokenDoor(path).request('tally','target','trigger')
            assert verify(got['token'],e.signer.tokens.keyset(),now=e.wall())['by']=='trigger'
            raw=json.dumps({'request_id':'original','ref':'target','by':'trigger'}).encode()
            code,body=unix_transport(path)('POST','/tokens/tally',raw,{},1)
            assert code==200 and json.loads(body)['request_id']=='original'
            raw=json.dumps({'request_id':'original','ref':'target','by':'trigger','aud':['south']}).encode()
            assert unix_transport(path)('POST','/tokens/tally',raw,{},1)[0]==400


def test_relay_has_only_its_childs_upward_scope_and_wrong_via_cannot_ask():
    from tests.conftest import Box
    from w2cplatform.domain.federation import Cluster
    from w2cplatform.trust.memberkey import MemberKey
    with issuing() as e:
        box=Box()
        relay=Cluster('relay',box.vars,box.objects)
        e.fed.add(relay)
        e.memberkeys['relay']=MemberKey.new()
        roster=json.loads(e.north.vars.get('domain/members')[0]['doc'])
        roster['members']['relay']={'key':e.memberkeys['relay'].pub,'seal':e.memberkeys['relay'].seal_pub}
        roster['rev']+=1
        e.north.vars.put('domain/members',{'doc':json.dumps(roster)})
        publish(e,member='relay',refs=())
        placement.assign(e.north.vars,'testsub2','target',{'cluster':'north'},e.wall)
        e.north.vars.put('domain/topology',{'doc':json.dumps({'rev':1,'centre':'north','via':{'south':'relay'}})})
        got=claims(e)
        assert got['aud']==['relay'] and got['up']=='north' and got['sub']=='south'
        got=claims(e,member='relay')
        assert got['aud']==['north'] and 'up' not in got and got['sub']=='relay' and got['by']=='trigger'
        # Moving the child away immediately removes the relay's authority.
        e.north.vars.put('domain/topology',{'doc':json.dumps({'rev':2,'centre':'north'})})
        assert raises(Refused,lambda:request(e,member='relay')).status==403
        assert claims(e)['aud']==['north']
        e.north.vars.put('domain/topology',{'doc':json.dumps({'rev':3,'via':{'south':'relay'}})})
        assert raises(Refused,lambda:request(e)).status==409


def test_scope_without_assignment_uses_unique_reported_target_home():
    with issuing() as e:
        assert claims(e)['aud']==['north']
        publish(e,member='south',refs=('target','trigger'))
        assert raises(Refused,lambda:request(e)).status==403
        publish(e,member='north',refs=())
        assert claims(e)['aud']==['north']  # the unrecorded target polls its confirmed holder


def test_by_never_expands_placement_or_unit_scope():
    from tests.test_token_requests import issuing as placed
    from tests.test_unit_token_requests import issuing as unit
    for setup in (placed,unit):
        with setup() as e:
            assert raises(Refused,lambda:client(e).request_token('testsub','tally','badge','testsubworker','another')).status==400


def test_one_issuance_pins_each_accepted_generation_before_a_concurrent_publication():
    from w2cplatform.domain import scenarioscope
    with issuing() as e:
        actual=scenarioscope.references
        changed=[]
        def racing(door,spec,member):
            refs=actual(door,spec,member)
            if member=='south' and not changed:
                changed.append(True)
                publish(e,refs=('target',))
            return refs
        with patch.object(scenarioscope,'references',racing):
            # The target-home lookup uses the same south generation as the trigger check.
            assert claims(e)['aud']==['north']
        assert raises(Refused,lambda:request(e)).status==403
