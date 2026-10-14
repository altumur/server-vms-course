"""C3: an ordinary guarded centre publisher and strictly addressed observations."""
import json

from tests.vmsconftest import Box, recorder
from tests.test_recording_publication import placement
from vms.recording_upstream import observation
from w2cplatform.domain.bookmerge import collect
from vms.config import REC_SPEC


def test_centre_publishes_to_recording_cluster_only_and_one_live_recorder_is_the_publisher():
    box = Box()
    placement(box, "centre", primary="relay")
    box.vars.put("domain/member-topology", {"doc": json.dumps({"rev": 1, "centre": "centre", "star": [], "via": {}})})
    first, second = recorder(box, "r-1"), recorder(box, "r-2")
    first.host_ingest("centre", "http://centre/a"); second.host_ingest("centre", "http://centre/b")
    first.heartbeat_once(); second.heartbeat_once(); first.heartbeat_once()
    row = box.vars.get("rec/upstream/r-1")[0]
    value = json.loads(row["serial"])
    assert value == {"ref": "serial", "to": ["relay"], "urls": ["http://centre/a", "http://centre/b"]}
    assert box.vars.get("rec/upstream/r-2")[0] == {}
    reports = {"centre": {"rec/upstream/r-1": row}, "relay": {}, "camera": {}, "reserve1": {}}
    got = collect(REC_SPEC.domain.merged["upstream"], reports, list(reports))
    assert "serial" in got.rows["relay"] and set(got.rows["camera"]) == {""} and set(got.rows["reserve1"]) == {""}
    box.vars.put("domain/rec/upstream", got.rows["relay"])
    box.vars.put("domain/member", {"cluster": "relay"})
    assert observation(box.vars, "relay", "serial")[0].member == "centre"




def publisher_fixture():
    from types import SimpleNamespace
    from w2cplatform.contract import Eyes
    box = Box()
    placement(box, "centre", primary="relay")
    box.vars.put("domain/member-topology", {"doc": json.dumps({"rev": 1, "centre": "centre", "star": [], "via": {}})})
    worker = SimpleNamespace(name="r-1", vars=box.vars, objects=box.objects,
                             ingest_url="http://centre/a", eyes=Eyes(box.clock, box.wall))
    return box, worker


def test_publisher_election_ignores_malformed_or_misnamed_heartbeats_and_uses_judges_time():
    from vms.recording_upstream import upstream
    box, worker = publisher_fixture()
    def heartbeat(name, url, **over):
        body = {"worker": name, "ts": box.wall(), "status": [], "ingest": url, **over}
        box.objects.put("rec/heartbeats/" + name, json.dumps(body).encode())
    heartbeat("r-1", "http://centre/b")
    heartbeat("r-2", "http://centre/a", ts=box.wall() + 100000)
    heartbeat("a-misnamed", "http://rogue", worker="a-rogue")
    heartbeat("a-torn", "http://rogue", status=["not an object"])
    heartbeat("a-nonstring", ["http://rogue"])
    box.objects.put("rec/heartbeats/a-garbage", b"{")
    value = json.loads(upstream(worker, [])["serial"])
    assert value == {"ref": "serial", "to": ["relay"], "urls": ["http://centre/a", "http://centre/b"]}
    box.wall.advance(-500000)
    assert upstream(worker, [])
    box.clock.advance(46)
    heartbeat("r-2", "http://centre/a")
    assert upstream(worker, []) == {}
    worker.name = "r-2"
    assert json.loads(upstream(worker, [])["serial"])["urls"] == ["http://centre/a"]
    heartbeat("r-1", "http://centre/b")
    assert upstream(worker, []) == {}
    worker.name = "r-1"
    assert len(json.loads(upstream(worker, [])["serial"])["urls"]) == 2


def test_publisher_requires_its_confirmed_centre_and_only_foreign_assignments():
    from w2cplatform.contract import Heartbeat
    from vms.recording_upstream import upstream
    box, worker = publisher_fixture()
    box.objects.put("rec/heartbeats/r-1", Heartbeat("r-1", box.wall(), extra={"ingest": "http://centre/a"}).to_bytes())
    assert list(upstream(worker, [])) == ["serial"]
    placement(box, "centre", primary="centre", copies=("relay",))
    assert upstream(worker, []) == {}
    placement(box, "centre", primary="relay")
    for value in ("{", "[]", json.dumps({"rev": 0, "centre": "centre"}), json.dumps({"rev": 1, "centre": "other"})):
        box.vars.put("domain/member-topology", {"doc": value})
        assert upstream(worker, []) == {}


def test_confirmed_observation_refuses_wrong_recipients_origin_and_flat_values():
    from vms.recording_upstream import confirmed
    from vms.recording_books import Unconfirmed
    for recipient, origin in ((["relay", "reserve"], "centre"), (["relay"], "rogue"), ("relay", "centre")):
        row = {"": json.dumps({"missing": []}), "serial": json.dumps({"missing": [], "entries": [
            {"member": origin, "item": "r1/serial", "value": {"ref": "serial", "to": recipient, "urls": ["http://centre"]}}]})}
        try:
            confirmed(row, "relay", "serial", "centre")
        except Unconfirmed:
            pass
        else:
            raise AssertionError("a foreign upstream was accepted")
    try:
        confirmed({"serial": json.dumps({"urls": ["http://centre"], "token_secret": "old"})}, "relay", "serial", "centre")
    except Unconfirmed:
        pass
    else:
        raise AssertionError("a former flat upstream was accepted")


def test_centre_publishes_unassigned_polling_source_to_its_exact_home_and_withdraws():
    from w2cplatform.contract import Heartbeat
    from vms.recording_upstream import upstream
    box, worker = publisher_fixture()
    box.vars.put('domain/holder',{'doc':json.dumps({'holder':'holder','term':1})})
    box.vars.put('domain/member-topology',{'doc':json.dumps({'rev':1,'centre':'centre','star':[],'via':{'camera':'relay'}})})
    box.objects.put('rec/heartbeats/r-1',Heartbeat('r-1',box.wall(),extra={'ingest':'http://centre/a'}).to_bytes())
    value={'ref':'free','to':['relay','centre'],'polls':True,'live_url':'','server':'camera','as_of':box.wall()}
    def source(value=value,missing=()):
        box.vars.put('domain/cam/sources',{'':json.dumps({'missing':list(missing)}),
            'free':json.dumps({'missing':list(missing),'entries':[{'member':'camera','item':'w/free','value':value}]})})
    source()
    assert json.loads(upstream(worker,[])['free'])=={'ref':'free','to':['relay'],'urls':['http://centre/a']}
    source({**value,'to':['relay']});assert 'free' not in upstream(worker,[])
    source({k:v for k,v in value.items() if k!='polls'});assert 'free' not in upstream(worker,[])
    source(missing=['camera']);assert 'free' not in upstream(worker,[])
    box.vars.put('domain/cam/sources',{});assert 'free' not in upstream(worker,[])


def test_unassigned_source_opens_centre_ingest_and_forwarder_follows_exact_home():
    from vms.domainpart.chain import Forwarder
    from vms.domainpart.ingest import Ingest
    from vms.recording_books import Unconfirmed
    from tests.test_book_names import raises
    box, worker = publisher_fixture()
    box.vars.put('domain/holder',{'doc':json.dumps({'holder':'holder','term':1})})
    box.vars.put('domain/member-topology',{'doc':json.dumps({'rev':1,'centre':'centre','star':[],'via':{'camera':'relay'}})})
    value={'ref':'free','to':['relay','centre'],'polls':True,'live_url':'','server':'camera','as_of':box.wall()}
    box.vars.put('domain/cam/sources',{'':json.dumps({'missing':[]}),
        'free':json.dumps({'missing':[],'entries':[{'member':'camera','item':'w/free','value':value}]})})
    rec = recorder(box,'r-2')
    assert rec._source_of_ref('ref:free')==('centre','ingest://centre/free')
    box.vars.put('domain/member',{'cluster':'relay'})
    fwd=Forwarder('relay',Ingest('relay',['http://relay'],lambda:None,wall=box.wall),box.vars,lambda _:None)
    assert fwd._policy('free')==(('unit','camera'),1,'centre','push')
    box.vars.put('domain/member-topology',{'doc':json.dumps({'rev':2,'centre':'centre','star':[],'via':{'camera':'other'}})})
    raises(Unconfirmed,lambda:fwd._policy('free'))
    box.vars.put('domain/cam/sources',{})
    raises(Unconfirmed,lambda:fwd._policy('free'))
