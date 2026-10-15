"""Lesson 17 — a chain: site, relay, centre.

Cameras nobody can dial, recorded by a relay nobody above can dial, watched from a centre everybody can
reach. Each level dials the level above: the camera its relay (media) and the centre (books, reports); the
relay the centre. The want travels down, the stream up. The star: a relay that cannot be pushed to takes
its cameras' streams from the centre. A relay: a camera that can reach only its relay cluster reaches the domain
through it both ways — the relay copies down what the domain left for it and carries its report up in one
summary object.

Every ingest here lives in a RECORDER of its cluster, and the relay's forwarder in the relay's recorder
(`RecWorker.host_ingest`; ADR-0065, its addition of 2026-10-08): the domain finds the centre's ingest in its recorder's
heartbeat (`ingest`), and what the forwarder carried and lost is in the relay's (`upstream`, the product's words).
"""

from tests.member_console import device_console, admit_fixtures
from tests.reporting import sync as report_sync
from tests.domainvms.recording_domain import RecordingDomain, RecordingInputs, camera_pusher, role_requests
import json

from w2cplatform.cluster.variables import FakeVariables

from w2cplatform.domain.agent import ClusterTrust, DomainAgent, DomainPublisher
from vms.forwarder import UPSTREAM_PATH
from w2cplatform.domain.relay import bundle
from vms.camera_cluster import DeviceCluster, Ram
from w2cplatform.domain.federation import Federation, Unreachable
from vms.gateway import Gateway
from vms.ingest import LINGER, CameraPusher, IngestLiveEndpoint, audience
from w2cplatform.domain.readview import ReadView
from w2cplatform.trust.signer import Signer
from w2cplatform.domain.uplink import member_copy
from tests.domain.conftest import Clock, make_cluster
from tests.vmsconftest import ingest_recorder

SERIAL = "SN7001"
RELAY_URLS = ["srt://ingest.east.relay:9000"]
CENTRE_URLS = ["srt://ingest.centre.example:9000"]


def _chain(wall, star=frozenset()):
    from vms.config import REC_SPEC
    from w2cplatform.spec import SpecController
    fed = Federation()
    north, _ = make_cluster("north", domain=True)                     # the centre: holds the domain, has an ingest
    east, _ = make_cluster("east")                                     # the relay: records the site's cameras
    fed.add(north); fed.add(east)
    signer = Signer("acme", north.vars, now=wall)
    DomainPublisher(north.vars).publish_keys(signer.tokens.keyset())
    relay_agent = DomainAgent("east", north.vars, east.vars, now=wall)
    report_sync(relay_agent)
    SpecController(REC_SPEC, east.vars, east.objects, wall=wall).create({"name": SERIAL, "cam": f"ref:{SERIAL}"})
    at: dict = {}                                                      # the ingests, by who answers which address

    cam = DeviceCluster(SERIAL, FakeVariables(), wall=wall, pushes=True)
    cam.boot(); cam.door_open = False                                  # nobody dials the camera
    fed.add(member_copy(cam.name, north.objects, wall=wall))
    cam_agent = DomainAgent(cam.name, north.vars, cam.flash, now=wall, domain_objects=north.objects, published=cam.local_objects())
    report_sync(cam_agent)
    view = ReadView(fed, wall=wall); view.refresh()
    crossings = RecordingInputs(north.vars, view, wall, centre="north", star=star)
    recording_domain = RecordingDomain(crossings, signer, agents=[cam_agent, relay_agent], devices=[cam])
    recording_domain.assign(SERIAL, "east")
    recording_domain.collect()

    dialled = []

    def dial_from(who, reachable):
        def dial(url):
            dialled.append((who, url))
            if url in RELAY_URLS and "relay" in reachable:
                return at["relay"]
            if url in CENTRE_URLS:
                return at["centre"]
            raise Unreachable(f"{url} did not answer {who}")
        return dial

    # The centre's ingest in a recorder of the centre; the relay's, and its forwarder, in a recorder of the relay — each
    # says where it takes streams in its heartbeat, and the relay's says what its forwarder carried (`upstream`)
    recs = {"north": ingest_recorder("north", CENTRE_URLS[0], wall, north.vars, north.objects),
            "east": ingest_recorder("east", RELAY_URLS[0], wall, east.vars, east.objects, dial=dial_from("relay", set()),
                                    archive=lambda ref, t0, t1: [("east-archive", ref, t0, t1)], needs=lambda ref: True)}
    centre, relay, fwd = recs["north"].ingest, recs["east"].ingest, recs["east"].forwarder
    from tests.domainvms.recording_domain import role_requests
    fwd.tokens.door = role_requests(east.vars, "recworker")
    at.update(centre=centre, relay=relay)
    pusher = camera_pusher(SERIAL, cam.flash, dial_from("camera", {"relay"} if not star else set()), clock=wall)

    def domain_pass():
        for r in recs.values():
            r.heartbeat_once()                                         # where each recorder's ingest is, said again
        view.refresh()
        recording_domain.observe("east", [{"id": SERIAL, "cam": "ref:"+SERIAL, "enabled": True}],
            [{"id": SERIAL, "phase": "running"}], ingest=RELAY_URLS[0])
        recording_domain.collect()
        recording_domain.collect()
        report_sync(cam_agent); report_sync(relay_agent)

    domain_pass.inputs, domain_pass.recorders = crossings, recs
    domain_pass.recording_domain = recording_domain
    domain_pass(); domain_pass()
    return north, east, centre, relay, pusher, fwd, dialled, domain_pass


def _upstream(rec) -> dict:
    """What the relay's recorder says of its forwarder, in its heartbeat (`upstream`), said now."""
    rec.heartbeat_once()
    return json.loads(rec.objects.get(f"rec/heartbeats/{rec.name}")).get("upstream", {})


def _in_book(rec, ref, mode="push") -> None:
    """Explicit C3 fixture observations; credentials are requested and kept in memory."""
    from types import SimpleNamespace
    from w2cplatform.trust.tokens import TokenIssuer
    own, now = rec.ingest.cluster, rec.wall()
    rec.vars.put("domain/member", {"cluster": own})
    rec.vars.put("domain/placed/rec/"+ref, {"cluster": own, "origin": "camera", "copies": "[]",
        "reason": "operator", "at": str(now), "rev": "1"})
    rec.vars.put("domain/member-topology", {"doc": json.dumps({"rev": 1, "centre": "north",
        "star": [own] if mode == "pull" else [], "via": {}})})
    def add(path, member, value):
        items, idx = rec.vars.get(path)
        row = {**(items or {}), "": json.dumps({"missing": []}), ref: json.dumps({
            "entries": [{"member": member, "item": "w1/"+ref, "value": value}], "missing": []})}
        rec.vars.put(path, row, cas=idx)
    add("domain/cam/sources", "camera", {"ref": ref, "to": [own], "live_url": "rtsp://camera/live",
        "server": "camera", "as_of": now, "polls": True})
    add(UPSTREAM_PATH, "north", {"ref": ref, "to": [own], "urls": CENTRE_URLS})
    issuer = TokenIssuer("fixture")
    rec.forwarder.tokens.door = SimpleNamespace(request=lambda kind, name: {"request_id": "fixture",
        "exp": rec.wall()+86400, "token": issuer.issue(own, 86400, now=rec.wall(), kind=kind, ref=name, aud=["north"])})


def test_a_viewer_in_the_centre_the_want_travels_down_and_the_stream_up():
    wall = Clock()
    north, east, centre, relay, pusher, fwd, dialled, _ = _chain(wall)
    gw = Gateway("gw-centre", where=lambda c: audience("north"), endpoint=lambda w: IngestLiveEndpoint(centre, lambda t, c: "anna"))
    vq = gw.watch(SERIAL, "anna-token", "anna")                        # the centre wants it
    assert pusher.pass_once(["f0"])["pushed"] == 0                     # not yet: the relay has not heard
    fwd.pass_once()                                                    # the relay hears, and wants it from the camera
    assert pusher.pass_once(["f1", "f2"])["pushed"] == 2
    fwd.pass_once()                                                    # up it goes
    gw.pump()
    assert vq.drain() == ["f1", "f2"]

    gw.leave(SERIAL, "anna"); wall.advance(LINGER + 1)
    fwd.pass_once()                                                    # the centre no longer wants it: nor does the relay
    wall.advance(LINGER + 1)
    assert pusher.pass_once(["f3"])["pushed"] == 0
    assert {u for who, u in dialled if who == "camera"} == set(RELAY_URLS)       # the camera dialled its relay only


def test_a_relay_the_centre_stopped_wanting_lets_go_of_its_subscription_and_the_next_viewer_gets_no_old_frames():
    """The scenario «камера — офис — центр», N7: when the centre no longer wanted the stream, the relay's forwarder let go
    of its want — and stayed subscribed to the camera's stream at its own ingest, its queue filling (up to
    `FORWARD_FRAMES`) while the relay's recorder still took the camera. The next viewer in the centre got the backlog
    first — up to ~10 s of old frames before the live edge. Now a stream nobody up there wants is unsubscribed (its losses
    counted), and a viewer that comes later starts at the live edge."""
    wall = Clock()
    north, east, centre, relay, pusher, fwd, dialled, _ = _chain(wall)
    relay.want(SERIAL, "recorder:east")                                # the relay's own recorder takes the camera
    rq = relay.subscribe(SERIAL, "recorder:east")
    gw = Gateway("gw-centre", where=lambda c: audience("north"), endpoint=lambda w: IngestLiveEndpoint(centre, lambda t, c: "anna"))
    vq = gw.watch(SERIAL, "anna-token", "anna")
    fwd.pass_once(); pusher.pass_once(["f1", "f2"]); fwd.pass_once(); gw.pump()
    assert vq.drain() == ["f1", "f2"]
    gw.leave(SERIAL, "anna"); wall.advance(LINGER + 1)
    fwd.pass_once()                                                    # the centre wants it no more
    assert fwd.up not in relay.tees[(SERIAL, "live")].subscribers      # …and the relay is no longer subscribed
    assert pusher.pass_once(["old1", "old2", "old3"])["pushed"] == 3   # the relay's recorder still takes the camera
    assert rq.drain()[-3:] == ["old1", "old2", "old3"]
    vq = gw.watch(SERIAL, "anna-token", "anna")                        # a new viewer in the centre
    fwd.pass_once(); pusher.pass_once(["new1"]); fwd.pass_once(); gw.pump()
    assert vq.drain() == ["new1"]                                      # the live edge, nothing old


def test_the_centres_copy_is_fed_by_the_relay_and_the_camera_serves_one_session():
    """An important camera kept in the centre too (a backup recording on the centre's volume, М10B Lesson 26).
    The camera still serves one session — to its relay; the centre receives from the relay."""
    wall = Clock()
    north, east, centre, relay, pusher, fwd, dialled, _ = _chain(wall)
    centre.want(SERIAL, "recorder:centre")
    rq = centre.subscribe(SERIAL, "recorder:centre")
    fwd.pass_once(); pusher.pass_once(["a", "b", "c"]); fwd.pass_once()
    assert rq.drain() == ["a", "b", "c"]
    assert len(relay.tees[(SERIAL, "live")].subscribers) == 1         # one subscriber of the camera's stream: the forwarder


def test_the_relay_archive_asked_for_by_the_centre_is_uploaded_by_the_relay():
    wall = Clock()
    north, east, centre, relay, pusher, fwd, dialled, _ = _chain(wall)
    rid = centre.request_range(SERIAL, 5000.0, 5600.0)
    fwd.pass_once()
    assert centre.landed(SERIAL) == [(5000.0, 5600.0)]
    assert centre.answer(SERIAL, rid) == [("east-archive", SERIAL, 5000.0, 5600.0)]   # out of the relay's archive


def test_the_relay_passes_on_the_recording_the_centre_named_and_says_when_its_archive_could_not_read():
    """The card's rule one level up, all of it (the sixth review found it on the camera; the relay answers ranges the
    same way). The recording the centre names reaches the relay's archive reader — unnamed, the relay would answer
    out of whichever recording of the camera it reads first; and an archive that could not read the range is said as
    RANGE FAILED, at once: the centre's copy fails and asks again, instead of waiting out its timeout on a relay
    whose pass fell over."""
    from vms.ingest import RangeFailed
    wall = Clock()
    north, east, centre, relay, pusher, fwd, dialled, _ = _chain(wall)
    asked = []

    def archive(ref, t0, t1, recording=None):
        asked.append(recording)
        if recording == "SN7001-lost":
            raise OSError("the archive door of r-east did not answer")
        return [("east-archive", recording, t0, t1)]
    fwd.archive = archive
    rid = centre.request_range(SERIAL, 5000.0, 5600.0, recording="SN7001-copy")
    fwd.pass_once()
    assert asked == ["SN7001-copy"] and centre.result(SERIAL, rid) == [("east-archive", "SN7001-copy", 5000.0, 5600.0)]
    rid = centre.request_range(SERIAL, 5000.0, 5600.0, recording="SN7001-lost")
    fwd.pass_once()
    try:
        centre.result(SERIAL, rid)
        raise AssertionError("an archive that could not read the range was answered")
    except RangeFailed as e:
        assert "did not answer" in str(e)
    assert centre.cams[SERIAL].ranges == {}                           # the request is over: the centre asks again later


def test_the_star_the_camera_pushes_to_the_centre_and_the_relay_pulls_its_cameras_from_there():
    """The assigned recorder remains east; its primary observation sends the one camera transport
    to north. East calls out to pull the very same bytes, in order, without dialing camera or relay."""
    from w2cplatform.domain.placement import placed
    from w2cplatform.trust.tokens import verify
    wall = Clock()
    north, east, centre, relay, pusher, fwd, dialled, _ = _chain(wall, star={"east"})
    entry = pusher.entry()
    assert entry["primary"] == "east" and set(entry["channels"]) == {"east"}
    assert entry["channels"]["east"]["urls"] == CENTRE_URLS
    assert entry["channels"]["east"]["cluster"] == "north"
    assignment = placed(pusher.flash, "rec", SERIAL)
    assert assignment["cluster"] == "east" and assignment["copies"] == []
    token = pusher.assigned.stream_token()
    claims = verify(token, ClusterTrust(pusher.flash).keyset(), now=wall(), kind="stream")
    assert set(claims["aud"]) == {"east", "north"} and claims["ref"] == SERIAL
    centre._check(token, SERIAL)
    rq = relay.subscribe(SERIAL, "recorder:east")
    cq = centre.subscribe(SERIAL, "recorder:centre")
    frames = [{"t": wall(), "key": True, "body": b"\x00\xff-star-key"},
              {"t": wall()+0.04, "key": False, "body": b"\x80\x00-star-delta"}]
    fwd.pass_once()                                                    # the relay's pull wants the camera at the centre
    assert pusher.pass_once(frames)["pushed"] == len(frames)
    fwd.pass_once()
    assert cq.drain() == frames and rq.drain() == frames
    pusher.pass_once([]); fwd.pass_once(); fwd.pass_once()
    assert cq.drain() == [] and rq.drain() == []                       # repeated polls/pulls deliver no frame twice
    assert set(pusher.assigned.channels) == {"east"}                   # no second camera cursor/transport for north
    assert {(w, u) for w, u in dialled} == {(w, CENTRE_URLS[0]) for w in ("camera", "relay")}


def test_the_star_camera_uploads_a_named_card_range_to_the_centre_over_its_only_transport():
    """A historical range goes to the same centre that receives live bytes; the camera's actual
    card answers the named recording. The inaccessible relay is never dialled for that answer."""
    import shutil
    from tests.domain.conftest import real_card
    from vms.worker import fake_samples
    wall = Clock()
    north, east, centre, relay, pusher, fwd, dialled, _ = _chain(wall, star={"east"})
    t0, t1 = wall()-100, wall()-94
    card = real_card(t0, t1, size=64)
    try:
        pusher.card = card.pieces
        fwd.pass_once(); pusher.pass_once([])                          # establish the camera/centre clock mapping
        rid = centre.request_range(SERIAL, t0, t1, recording="1-card")
        assert pusher.pass_once([])["uploaded"] == [(t0, t1)]
        got = centre.result(SERIAL, rid)
        expected = fake_samples(t0, t1, size=64)
        assert [(s.begin, s.end, s.key, s.body) for s in got] == [
            (s.begin, s.end, s.key, s.body) for s in expected]
        assert centre.result(SERIAL, rid) is None and centre.cams[SERIAL].ranges == {}
        assert set(pusher.assigned.channels) == {"east"}
        assert {(w, u) for w, u in dialled} == {(w, CENTRE_URLS[0]) for w in ("camera", "relay")}
        assert not relay.cams.get(SERIAL) or not relay.cams[SERIAL].ranges
    finally:
        card.close()
        shutil.rmtree(card.path, ignore_errors=True)


def test_the_star_recorders_card_range_fetches_the_named_camera_recording_through_the_centre():
    """The actual relay recorder asks through its forwarder. The centre asks the camera, and the
    real card's named samples return to the recorder; successful and timed-out requests leave no state."""
    from concurrent.futures import ThreadPoolExecutor
    import shutil
    import threading
    from tests.domain.conftest import real_card
    from vms.ingest import RangeFailed, card_range
    from vms.worker import fake_samples
    wall = Clock()
    north, east, centre, relay, pusher, fwd, dialled, domain_pass = _chain(wall, star={"east"})
    rec = domain_pass.recorders["east"]
    t0, t1 = wall()-100, wall()-94
    card = real_card(t0, t1, size=64)
    real_card(t0, t1, recording="2-card", size=96, card=card)             # same times; different bytes expose a wrong recording
    pusher.card = card.pieces
    fwd.pass_once(); pusher.pass_once([])
    ready, requests = threading.Event(), []
    request_range = centre.request_range

    def requested(ref, start, end, recording=None):
        rid = request_range(ref, start, end, recording)
        requests.append((ref, start, end, recording))
        ready.set()                                                    # the real centre request is visible before the camera polls
        return rid

    def clean(ingest):
        cam = ingest.cams.get(SERIAL)
        return cam is None or all(not getattr(cam, field) for field in ("ranges", "answers", "parts", "failed"))

    centre.request_range = requested
    src = {"recording": "2-card", "cam": "ref:"+SERIAL}
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(rec.card_range, src, t0, t1)
            assert ready.wait(2.0), "the relay recorder never requested the range at the centre"
            assert requests == [(SERIAL, t0, t1, "2-card")]
            assert not future.done()                                  # a request is not yet the camera's answer
            assert clean(relay)                                       # nobody waits for a poll at the inaccessible relay
            assert pusher.pass_once([])["uploaded"] == [(t0, t1)]
            got = future.result(timeout=3.0)
            expected = fake_samples(t0, t1, size=96)
            assert [(s.begin, s.end, s.key, s.body) for s in got] == [
                (s.begin, s.end, s.key, s.body) for s in expected]
            assert clean(centre) and clean(relay)

            ready.clear()
            short_wait = card_range(fwd, lambda source: SERIAL, wait=0.2)
            future = pool.submit(short_wait, src, t0, t1)
            assert ready.wait(2.0), "the retry never reached the centre"
            try:
                future.result(timeout=3.0)                            # deliberately no camera poll for this request
                raise AssertionError("an unanswered centre fetch succeeded")
            except RangeFailed as error:
                assert "did not answer" in str(error)
            assert requests == [(SERIAL, t0, t1, "2-card")] * 2
            assert clean(centre) and clean(relay)                     # timeout cancels the real request and its partial answer
        assert set(pusher.assigned.channels) == {"east"}
        assert {(w, u) for w, u in dialled} == {(w, CENTRE_URLS[0]) for w in ("camera", "relay")}
    finally:
        centre.request_range = request_range
        card.close()
        shutil.rmtree(card.path, ignore_errors=True)


def test_frames_the_relay_could_not_push_up_or_whose_pull_answer_was_lost_are_sent_again_not_dropped():
    """The seventh review's rule for the camera — nothing moves until it is taken — one level up. The relay drained
    what the camera sent and pushed it to the centre; a push that failed took those frames with it, and its
    `Unreachable` ended the whole pass. Now they are pushed again first, and the pass goes on. In the star, the centre
    drained what it handed the relay; an answer lost on its way down lost the frames — now the relay says which batch
    it last got, and the centre hands the lost one over again."""
    from w2cplatform.domain.federation import Unreachable as Gone
    wall = Clock()
    north, east, centre, relay, pusher, fwd, dialled, _ = _chain(wall)
    centre.want(SERIAL, "recorder:centre")
    rq = centre.subscribe(SERIAL, "recorder:centre")
    fwd.pass_once(); pusher.pass_once(["a", "b"])
    push, left = centre.push, {"n": 1}

    def flaky(*a, **kw):
        if left["n"]:
            left["n"] -= 1
            raise Gone("the centre's connection dropped")
        return push(*a, **kw)
    centre.push = flaky
    assert "stopped answering" in fwd.pass_once()[SERIAL] and rq.drain() == []
    pusher.pass_once(["c"]); fwd.pass_once()
    assert rq.drain() == ["a", "b", "c"]                               # pushed again, first, and nothing twice

    wall = Clock()
    north, east, centre, relay, pusher, fwd, dialled, _ = _chain(wall, star={"east"})
    rq = relay.subscribe(SERIAL, "recorder:east")
    cq = centre.subscribe(SERIAL, "recorder:centre")
    frames = [{"t": wall(), "key": True, "body": b"\x00-first-key"},
              {"t": wall()+0.04, "key": False, "body": b"\xff-second-delta"}]
    fwd.pass_once()
    assert pusher.pass_once(frames)["pushed"] == 2
    pull, left = centre.pull, {"n": 1}

    def lost(*a, **kw):
        out = pull(*a, **kw)
        if left["n"]:
            left["n"] -= 1
            raise Gone("the answer to the pull was lost")
        return out
    centre.pull = lost
    assert "stopped answering" in fwd.pass_once()[SERIAL] and rq.drain() == []
    wall.advance(1)
    more = {"t": wall(), "key": True, "body": b"\x80-third-key"}
    assert pusher.pass_once([more])["pushed"] == 1
    fwd.pass_once()
    assert rq.drain() == [*frames, more]                               # lost batch first, then newer bytes, exactly once
    assert cq.drain() == [*frames, more]                               # no duplicate camera push while the pull retries
    pusher.pass_once([]); fwd.pass_once(); fwd.pass_once()
    assert rq.drain() == [] and cq.drain() == []
    assert set(pusher.assigned.channels) == {"east"}
    assert {(w, u) for w, u in dialled} == {(w, CENTRE_URLS[0]) for w in ("camera", "relay")}


# -- the eighth review ---------------------------------------------------------------------------------------------------
def test_a_centre_that_restarts_in_the_middle_of_a_pull_with_two_answers_lost_hands_every_frame_down():
    """The eighth review, blocker 2, run as its probe ran it. The relay had got batch 2; the centre restarted — its
    count back at nought — and the first two answers after it were lost on the way down. The relay still said "2", the
    new count reached 2, and the third pull was taken for "the relay has batch 2": frames 3 and 4 never arrived, and
    nothing counted them. A batch's mark is `(boot, n)` now, and a mark from another boot is never this boot's: the
    last batch goes again until the relay has a mark of this boot. Every frame arrives, once, in order; a relay that
    restarted itself says no mark, and gets the last batch once more — a repeat its ingest drops."""
    def centre():                                                      # the centre's recorder, its process (re)started
        ing = ingest_recorder("north", CENTRE_URLS[0], keys=lambda: {}).ingest
        ing._check = lambda *a, **k: {}                                # (the tokens are the other tests')
        ing.subscribe("7", "up:east", maxsize=1000)                    # the relay's subscription, from its first pull
        return ing
    at = {"centre": centre()}
    host = ingest_recorder("east", RELAY_URLS[0], keys=lambda: {}, dial=lambda url: at["centre"], needs=lambda ref: True)
    relay, fwd = host.ingest, host.forwarder
    _in_book(host, "7", mode="pull")                                   # confirmed route; transport alone is under test
    rq = relay.subscribe("7", "recorder:east", maxsize=1000)

    def pull(t, lost=False):
        ing = at["centre"]
        ing._take("7", [{"t": float(t), "key": True}])                # what the camera pushed to the centre since
        real = ing.pull
        if lost:
            def answer_lost(*a, **kw):
                real(*a, **kw)
                raise Unreachable("the answer to the pull was lost")
            ing.pull = answer_lost
        try:
            fwd._pull(ing, "7", fwd.book()["7"])
        except Unreachable:
            pass
        ing.pull = real
    pull(1); pull(2)
    at["centre"] = centre()                                            # the centre restarts
    pull(3, lost=True); pull(4, lost=True); pull(5); pull(6)
    assert [f["t"] for f in rq.drain()] == [1, 2, 3, 4, 5, 6]
    fwd.pulled.clear()                                                 # the relay's forwarder restarts
    pull(7)
    assert [f["t"] for f in rq.drain()] == [7] and relay.tees[("7", "live")].repeats >= 1


def test_frames_the_centre_took_but_whose_answer_was_lost_reach_its_recorder_once():
    """The eighth review's major, one level up: the relay pushes again what the centre did not acknowledge — and when the
    centre HAD taken it and only the answer was lost, the centre's recorder got it twice, out of order. The centre's
    ingest gives no subscriber a frame not newer than the last it was given."""
    from w2cplatform.domain.federation import Unreachable as Gone
    wall = Clock()
    north, east, centre, relay, pusher, fwd, dialled, _ = _chain(wall)
    centre.want(SERIAL, "recorder:centre")
    rq = centre.subscribe(SERIAL, "recorder:centre", maxsize=1000)
    fwd.pass_once()

    def second():
        wall.advance(1)
        pusher.pass_once([{"t": wall(), "key": True}])
    second(); second()
    push, left = centre.push, {"n": 1}

    def took_but_lost(*a, **kw):
        out = push(*a, **kw)
        if left["n"]:
            left["n"] -= 1
            raise Gone("the answer was lost")
        return out
    centre.push = took_but_lost
    fwd.pass_once()                                                    # taken; the answer lost: kept to push again
    second(); fwd.pass_once()                                          # pushed again, with what came since
    got = [f["t"] for f in rq.drain()]
    assert len(got) == 3 and got == sorted(set(got)) and centre.tees[(SERIAL, "live")].repeats == 2


def test_the_forwarder_keeps_what_it_holds_in_seconds_and_bytes_and_says_what_it_dropped():
    """The eighth review, a minor: "the relay does not lose frames when a push fails" held about a second and a half —
    thirty frames waiting, fifty kept — and what it dropped was counted where nobody looked. It keeps `FORWARD_HOLD`
    seconds now, at most `FORWARD_BYTES`, cut clean to a key frame, and its recorder's heartbeat says how many frames it
    dropped past that (`upstream.<ref>.up_dropped`, the product's word)."""
    from vms.forwarder import FORWARD_HOLD
    host = ingest_recorder("east", RELAY_URLS[0], keys=lambda: {}, dial=lambda url: None)
    fwd = host.forwarder
    frames = [{"t": 1000 + i / 25, "key": i % 50 == 0} for i in range(25 * 30)]   # thirty seconds at 25 frames a second
    kept = fwd._kept("7", frames)
    assert kept[0]["key"] and frames[-1]["t"] - kept[0]["t"] <= FORWARD_HOLD and kept[-1] is frames[-1]
    assert len(kept) >= 25 * (FORWARD_HOLD - 2) and fwd.dropped["7"] == len(frames) - len(kept)
    fat = [{"t": 1000 + i, "key": True, "body": b"x" * (4 << 20)} for i in range(8)]
    assert len(fwd._kept("8", fat)) == 4                               # sixteen mebibytes, whatever the seconds
    _in_book(host, "7")                                                # a camera of the relay's upstream book
    fwd.state["7"] = "forwarding"
    up = _upstream(host)["7"]
    assert up["up_dropped"] == fwd.dropped["7"] and up["mode"] == "push" and up["state"] == "forwarding"


def _site_of(n_relays, per_relay, wall):
    north, _ = make_cluster("north", domain=True)
    store = _Counting(Ram())
    relays, fed = {}, Federation()
    fed.add(north)
    for o in range(n_relays):
        relay_store = Ram()
        cams = []
        for i in range(per_relay):
            d = DeviceCluster(f"SN{o:02d}{i:03d}", FakeVariables(), wall=wall)
            d.boot()
            cams.append((d, DomainAgent(d.name, north.vars, d.flash, now=wall, domain_objects=relay_store, published=d.local_objects())))
            fed.add(member_copy(d.name, store, wall=wall, via=f"relay-{o}"))
        relays[f"relay-{o}"] = (relay_store, cams)
    return north, store, relays, fed


class _Counting:
    def __init__(self, inner): self.inner, self.puts, self.largest = inner, 0, 0
    def put(self, k, v): self.puts += 1; self.largest = max(self.largest, len(v)); return self.inner.put(k, v)
    def get(self, k): return self.inner.get(k)
    def list(self, p): return self.inner.list(p)
    def delete(self, k): return self.inner.delete(k)


def test_relay_reports_are_two_atomic_writes_per_member_and_age_independently():
    """ADR-0074: each member has its own immutable generation and atomic marker at the holder.
    A relay that stops forwarding leaves its thirty members silent; other relays keep reporting."""
    wall = Clock()
    north, store, relays, fed = _site_of(10, 30, wall)

    def round_(skip=()):
        for name, (relay_store, cams) in relays.items():
            for d, a in cams:
                d.publish(); report_sync(a)
            if name not in skip:
                bundle(name, [d.name for d, _ in cams], relay_store, store, received_at=wall())

    round_()
    view = ReadView(fed, wall=wall); view.refresh()
    assert view.list(size=400)["total"] == 300 and view.list()["complete"]
    wall.advance(10); store.puts = 0
    round_()
    assert store.puts == 600                                            # body and marker for each of 300 members
    assert store.largest < 64 * 1024                                    # each member body remains below this bound
    view.refresh()                                                      # the domain sees this round's reports

    wall.advance(60); round_(skip=("relay-3",))
    view.refresh()
    page = view.list(size=400)
    silent = {n for n, s in page["clusters"].items() if s == "unreachable"}
    assert silent == {d.name for d, _ in relays["relay-3"][1]}        # its thirty cameras, all at once


def test_a_camera_that_sees_only_its_relay_reaches_the_domain_through_it_both_ways():
    """The summary report's reason: the camera can reach its relay and nothing else. The relay is its road
    to the domain in both directions — the relay's agent relays down everything the domain leaves for the
    camera, the camera reports into the relay, and the relay carries the report up in its bundle. Grants,
    a kept edit and its outcome, the book with the stream token, the list in the centre: all through the relay.
    And how current the camera's books are is when the RELAY last reached the domain."""
    from vms.config import REC_SPEC
    from vms.recworker import DOMAIN_SEEN
    from w2cplatform.spec import SpecController
    from w2cplatform.domain.api import ConsoleAPI
    from w2cplatform.domain.relay import Relay
    from w2cplatform.domain.federation import DomainDirectory
    from w2cplatform.domain.grants import Grant
    from w2cplatform.domain.pending import PendingEdits

    wall = Clock()
    fed = Federation()
    north, north_link = make_cluster("north", domain=True)
    east, _ = make_cluster("east")
    fed.add(north); fed.add(east)
    signer = Signer("acme", north.vars, now=wall)
    DomainPublisher(north.vars).publish_keys(signer.tokens.keyset())
    cam = DeviceCluster(SERIAL, FakeVariables(), wall=wall, pushes=True)
    cam.boot(); cam.door_open = False
    fed.add(member_copy(cam.name, north.objects, wall=wall, via="east"))
    relay_agent = DomainAgent("east", north.vars, east.vars, now=wall, domain_objects=north.objects,
                               bundle_store=east.objects, bundle_members=[cam.name], relay_members=[cam.name])
    through = Relay(relay_agent, east.objects)                         # all the camera can reach: east, and what it keeps
    cam_agent = DomainAgent(cam.name, through.vars, cam.flash, now=wall, console=device_console(cam),
                            domain_objects=through.objects, published=cam.local_objects(), seen_store=cam.local_objects())
    host = ingest_recorder("east", RELAY_URLS[0], wall, east.vars, east.objects)   # the relay's ingest, in its recorder
    relay = host.ingest
    SpecController(REC_SPEC, east.vars, east.objects, wall=wall).create({"name": SERIAL, "cam": f"ref:{SERIAL}"})

    def passes():
        host.heartbeat_once()
        report_sync(relay_agent); report_sync(cam_agent); report_sync(relay_agent)

    passes()
    view = ReadView(fed, wall=wall); view.refresh()
    assert [r["ref"] for r in view.list()["rows"] if r["cluster"] == cam.name] == [SERIAL]   # up: the bundle

    from tests.domain.books_fixture import initial_books
    initial_books(fed, signer, wall, {"north": (north.vars, north.objects),
                  "east": (east.vars, east.objects), cam.name: (cam.flash, cam.local_objects())})
    # Enrollment above pins the real member identities; the relay's asks use those same keys.
    from w2cplatform.trust.memberkey import MemberKey
    relay_agent.key = MemberKey.load_or_make(east.vars)
    cam_agent.key = MemberKey.load_or_make(cam.flash)
    DomainPublisher(north.vars).publish_grants(cam.name, [Grant("anna", "edit", None, wall() + 3600)])
    passes()
    assert [g.subject for g in ClusterTrust(cam.flash).grants()] == ["anna"]                   # down: the relay

    pending = PendingEdits(north.vars, wall)

    def no_door(name):
        raise Unreachable(f"{name} is reached only through its relay")

    admit_fixtures(north.vars, fed.clusters)
    api = ConsoleAPI(DomainDirectory(fed, wall=wall), verifier=lambda t: t, pending=pending, last_known=view.last_known)
    assert api.update_unit(SERIAL, {"enabled": False}, idempotency_key="k1", token="anna", sub="cam")["kept"]
    passes()
    assert cam.row()["enabled"] is False                                 # carried down by the relay, applied by the camera
    view.refresh(); pending.collect(fed)
    assert pending.of(cam.name) == {}                                  # the outcome came up in the bundle

    crossings = RecordingInputs(north.vars, view, wall)
    recording_domain = RecordingDomain(crossings, signer, agents=[relay_agent, cam_agent], devices=[cam])
    recording_domain.assign(SERIAL, "east")
    recording_domain.collect(); recording_domain.collect()
    recording_domain.observe("east", [{"id": SERIAL, "cam": "ref:"+SERIAL, "enabled": True}],
        [{"id": SERIAL, "phase": "running"}], ingest=RELAY_URLS[0])
    recording_domain.collect(); recording_domain.collect()
    passes()
    pusher = camera_pusher(SERIAL, cam.flash, lambda url: relay if url in RELAY_URLS else (_ for _ in ()).throw(Unreachable(url)))
    relay.want(SERIAL, "recorder:east")
    assert pusher.pass_once(["f"])["pushed"] == 1                      # the stream token came down the same road

    last = wall()
    north_link.up = False                                              # the relay loses the centre
    for _ in range(4):
        wall.advance(20); report_sync(relay_agent); report_sync(cam_agent)        # the camera still reaches its relay
    assert abs(json.loads(cam.ram.get(DOMAIN_SEEN))["ts"] - last) < 1e-6          # …and knows its books are as old as the relay's


def test_an_ask_from_a_camera_at_another_site_goes_by_the_centre_and_the_relay_carries_it_down():
    """The gate camera is at another site: it reaches the centre, not the east relay. Its book names two roads
    to the yard camera — the relay that records it, then the centre the relay forwards it to. The relay's
    ingest does not answer, so the ask is left at the centre; the relay's forwarder, polling the centre, carries
    it down to the camera's poll, and the outcome back up."""
    from tests.domain.conftest import SharedDoor
    wall = Clock()
    north, east, centre, relay, pusher, fwd, dialled, domain_pass = _chain(wall)
    gate = DeviceCluster("SN7002", FakeVariables(), wall=wall, pushes=True)
    gate.boot(); gate.door_open = False
    done = []
    pusher.perform = lambda action: done.append(action) or "performed"
    # the gate camera is a member like the yard camera: its report makes it known to the domain's view
    crossings = domain_pass.inputs
    crossings.view.fed.add(member_copy(gate.name, north.objects, wall=wall))
    gate_agent = DomainAgent(gate.name, north.vars, gate.flash, now=wall, domain_objects=north.objects,
                             published=gate.local_objects())
    domain_pass.recording_domain.add_agent(gate_agent, gate)
    domain_pass()
    action = {"camera": SERIAL, "action": "preset", "arg": 3}
    signer = domain_pass.recording_domain.signer
    SharedDoor(north.vars, north.objects, signer, wall).set_scenarios([
        {"name": "other-site-to-yard", "when": {"camera": "SN7002", "kind": "vehicle"}, "then": action}])
    domain_pass(); domain_pass()

    def gate_dial(url):
        if url in CENTRE_URLS:
            return centre
        raise Unreachable(f"{url} did not answer the gate camera")

    gate.host_scenarios(gate_agent, gate_dial, steady=wall)
    asker = gate.asks.executor.asker("SN7002")
    assert {r.member for r in asker._roads(SERIAL)[1]} == {"east", "north"}
    [left] = gate.on_event("vehicle")
    ing, aid = left["ingest"], left["ask"]
    assert ing is centre and centre.ask_outcome(SERIAL, aid) is None
    fwd.pass_once()                                                    # down to the relay's ingest
    assert pusher.pass_once([])["asks"] == [(action, "performed")] and done == [action]
    fwd.pass_once()                                                    # the outcome, up
    assert centre.ask_outcome(SERIAL, aid) == "performed"
    assert done == [action]                                     # carried twice, done once


def test_a_camera_that_sees_only_its_relay_and_that_nobody_records_polls_its_relay():
    """One site, one relay: the gate camera and a PTZ camera kept for live view, both reaching only the east
    relay, neither recorded. A scenario ties them. The book of polls must send the PTZ camera to its RELAY's
    ingest — the centre's, or the domain holder's, is exactly what it cannot reach, and a scenario inside one
    site would never act. The gate camera's book of asks names the same relay; the ask goes there and back."""
    from w2cplatform.domain.relay import Relay
    from tests.domain.conftest import SharedDoor

    wall = Clock()
    fed = Federation()
    north, _ = make_cluster("north", domain=True)
    east, _ = make_cluster("east")
    fed.add(north); fed.add(east)
    signer = Signer("acme", north.vars, now=wall)
    DomainPublisher(north.vars).publish_keys(signer.tokens.keyset())
    hosts = [ingest_recorder("north", CENTRE_URLS[0], wall, north.vars, north.objects)]   # there IS an ingest up there: the wrong one
    through = Relay(None, east.objects)                                # all a camera of this site can reach
    cams, agents = {}, []
    for n in ("SN7002", "SN7003"):                                     # the gate, the PTZ
        d = DeviceCluster(n, FakeVariables(), wall=wall, pushes=True)
        d.boot(); d.door_open = False
        fed.add(member_copy(d.name, north.objects, wall=wall, via="east"))
        agents.append(DomainAgent(d.name, through.vars, d.flash, now=wall, domain_objects=through.objects,
                                  cluster_objects=d.disk, published=d.local_objects(), seen_store=d.local_objects()))
        cams[n] = d
    members = [d.name for d in cams.values()]
    relay_agent = DomainAgent("east", north.vars, east.vars, now=wall, domain_objects=north.objects,
                               bundle_store=east.objects, bundle_members=members, relay_members=members)
    through.door.agent = relay_agent                                   # what the cameras ask: what east keeps
    report_sync(relay_agent)
    def centre_dial(url):
        if url in CENTRE_URLS:
            return hosts[0].ingest
        raise Unreachable(f"{url} is beyond the relay network")

    hosts.append(ingest_recorder("east", RELAY_URLS[0], wall, east.vars, east.objects, dial=centre_dial))
    relay = hosts[-1].ingest

    inputs = RecordingInputs(north.vars, ReadView(fed, wall=wall), wall, centre="north")
    recording_domain = RecordingDomain(inputs, signer,
        agents=[*agents, relay_agent], devices=list(cams.values()), recorders=hosts)
    recording_domain.collect()
    SharedDoor(north.vars, north.objects, signer, wall).set_scenarios([
        {"name": "test_lesson17_chain-1", "when": {"camera": "SN7002", "kind": "vehicle"}, "then": {"camera": "SN7003", "action": "preset", "arg": 3}}])

    def domain_pass():
        recording_domain.collect()
        report_sync(relay_agent)                                            # the new books relayed down
        for a in agents:
            report_sync(a)

    domain_pass(); domain_pass(); domain_pass()
    fwd = hosts[-1].forwarder
    fwd.tokens.door = role_requests(east.vars, "recworker")

    dialled = []

    def site_dial(url):
        dialled.append(url)
        if url in RELAY_URLS:
            return relay
        raise Unreachable(f"{url} is beyond the site's network")

    done = []
    ptz = camera_pusher("SN7003", cams["SN7003"].flash, site_dial, clock=wall,
                       perform=lambda action: done.append(action) or "performed")
    e = ptz.entry()
    assert e["polls_only"] and e["cluster"] == "east" and e["ingest"]["urls"] == RELAY_URLS
    assert "asks only" in ptz.pass_once([])["state"]                   # it reached its poll

    gate = cams["SN7002"].host_scenarios(next(a for a in agents if a.cluster == cams["SN7002"].name), site_dial, steady=wall)
    asker = gate.asks.executor.asker("SN7002")
    assert {r.member for r in asker._roads("SN7003")[1]} == {"east", "north"}
    left = gate.on_event("vehicle")
    assert [x["state"] for x in left] == ["asked"] and left[0]["ingest"] is relay
    assert ptz.pass_once([])["asks"] == [({"camera": "SN7003", "action": "preset", "arg": 3}, "performed")]
    assert asker.outcome("SN7003", left[0]["ask"], left[0]["deadline"]) == "performed"


    # A camera with no recording still reaches a centre viewer through its home.
    from w2cplatform.domain.placement import placed
    assert placed(east.vars, "rec", "SN7003") is None
    centre = hosts[0].ingest
    fwd.pass_once()
    assert ptz.pass_once(["before-viewer"])["pushed"] == 0
    queue = centre.subscribe("SN7003", "viewer")
    centre.want("SN7003", "viewer")
    fwd.pass_once()
    result = ptz.pass_once(["live-for-centre"])
    assert result["pushed"] == 1, (result, fwd.state, east.vars.get(UPSTREAM_PATH)[0])
    fwd.pass_once()
    assert queue.drain() == ["live-for-centre"]
    assert set(dialled) == set(RELAY_URLS)
    centre.release("SN7003", "viewer")
    centre.unsubscribe("SN7003", "viewer", kind="live")
    wall.advance(LINGER + 1)
    fwd.pass_once()
    wall.advance(LINGER + 1)
    assert ptz.pass_once(["after-viewer"])["pushed"] == 0
    fwd.pass_once()
    assert queue.drain() == []


# -- a scenario between two relays: the road up through one's own relay, by event -------------------------
EAST_URLS = RELAY_URLS
WEST_URLS = ["srt://ingest.west.relay:9000"]
GATE7, PTZ7, YARD7 = "SN7102", "SN7103", "SN7104"    # the gate and a PTZ at an east site; the yard at a west site


def _two_relays(wall):
    from w2cplatform.domain.relay import Relay
    from tests.domain.conftest import SharedDoor

    fed = Federation()
    north, _ = make_cluster("north", domain=True)
    east, _ = make_cluster("east")
    west, _ = make_cluster("west")
    for c in (north, east, west):
        fed.add(c)
    signer = Signer("acme", north.vars, now=wall)
    DomainPublisher(north.vars).publish_keys(signer.tokens.keyset())
    ing: dict = {}
    centre_up = {"on": True}

    def reach(urls, owner):
        def dial(url):
            if url in urls and (owner != "relay" or centre_up["on"]):
                return next(i for i in ing.values() if url in i.urls)
            raise Unreachable(f"{url} does not answer {owner}")
        return dial
    # Each cluster's ingest in a recorder of its own; each relay's forwarder in its relay's recorder (ADR-0065)
    hosts = {name: ingest_recorder(name, urls[0], wall, c.vars, c.objects,
                                   dial=reach(CENTRE_URLS, "relay") if name != "north" else None)
             for name, c, urls in (("north", north, CENTRE_URLS), ("east", east, EAST_URLS), ("west", west, WEST_URLS))}
    ing.update({name: h.ingest for name, h in hosts.items()})
    cams, agents, relays = {}, [], []
    for relay, serials in (("east", (GATE7, PTZ7)), ("west", (YARD7,))):
        store = east if relay == "east" else west
        through = Relay(None, store.objects)                           # all a camera of that site reaches
        members = []
        for n in serials:
            d = DeviceCluster(n, FakeVariables(), wall=wall, pushes=True)
            d.boot(); d.door_open = False
            fed.add(member_copy(d.name, north.objects, wall=wall, via=relay))
            agents.append(DomainAgent(d.name, through.vars, d.flash, now=wall, domain_objects=through.objects,
                                      cluster_objects=d.disk, published=d.local_objects(), seen_store=d.local_objects()))
            cams[n] = d
            members.append(d.name)
        relays.append(DomainAgent(relay, north.vars, store.vars, now=wall, domain_objects=north.objects,
                                   bundle_store=store.objects, bundle_members=members, relay_members=members))
        through.door.agent = relays[-1]                                # what the camera asks: what this relay keeps
    for o in relays:
        report_sync(o)
    inputs = RecordingInputs(north.vars, ReadView(fed, wall=wall), wall, centre="north")
    recording_domain = RecordingDomain(inputs, signer, agents=[*agents, *relays], devices=cams.values())
    from w2cplatform.domain.carry import CarryClient
    north.vars.put("domain/topology", {"doc": json.dumps({"rev": 2, "centre": "north", "star": [],
        "via": {c.name: c.via for c in fed.clusters.values() if c.via}})})
    for agent in relays:
        agent.domain_vars = CarryClient(recording_domain.door, agent.cluster, agent.key, wall)
        agent.domain_objects = None
    for relay, refs in (("east", (GATE7, PTZ7)), ("west", (YARD7,))):
        for ref in refs:
            recording_domain.assign(ref, relay)
        hosts[relay].forwarder.tokens.door = role_requests(hosts[relay].vars, "recworker")

    def domain_pass():
        for h in hosts.values():
            h.heartbeat_once()
        for d in cams.values():
            d.publish()
        for a in agents:
            report_sync(a)
        for o in relays:
            report_sync(o)
        for relay, refs in (("east", (GATE7, PTZ7)), ("west", (YARD7,))):
            recording_domain.observe(relay,
                [{"id": ref, "cam": "ref:"+ref, "enabled": True} for ref in refs],
                [{"id": ref, "phase": "running"} for ref in refs], ingest=ing[relay].urls[0])
        recording_domain.collect(); recording_domain.collect()
        inputs.view.refresh()
        for o in relays:
            report_sync(o)
        for a in agents:
            report_sync(a)

    domain_pass()                     # complete names before the operator writes
    SharedDoor(north.vars, north.objects, signer, wall).set_scenarios([
        {"name": "test_lesson17_chain-2", "when": {"camera": GATE7, "kind": "vehicle"}, "then": {"camera": YARD7, "action": "preset", "arg": 3}},
        {"name": "test_lesson17_chain-3", "when": {"camera": GATE7, "kind": "vehicle"}, "then": {"camera": PTZ7, "action": "preset", "arg": 1}}])
    domain_pass(); domain_pass()
    fwd = {"east": hosts["east"].forwarder, "west": hosts["west"].forwarder}
    done = {PTZ7: [], YARD7: []}
    ptz = camera_pusher(PTZ7, cams[PTZ7].flash, reach(EAST_URLS, "site"), clock=wall,
                       perform=lambda a: done[PTZ7].append(a) or "performed")
    yard = camera_pusher(YARD7, cams[YARD7].flash, reach(WEST_URLS, "site"), clock=wall,
                        perform=lambda a: done[YARD7].append(a) or "performed")
    gate = cams[GATE7].host_scenarios(next(a for a in agents if a.cluster == cams[GATE7].name),
                                    reach(EAST_URLS, "site"), steady=wall)
    gate.recording_domain = recording_domain
    return ing, fwd, ptz, yard, gate, done, centre_up


def test_an_ask_to_another_relay_goes_up_through_ones_own_and_an_ask_inside_the_relay_does_not():
    """The gate camera sees only the east relay. The PTZ camera is in the same relay: its book names the east
    ingest directly, and the ask never leaves the site. The yard camera is behind the west relay: the book
    names the east ingest again, marked UP; the east forwarder takes it to the centre with the relay's own
    token for that pair, the west forwarder carries it down, and the outcome comes back hop by hop."""
    wall = Clock()
    ing, fwd, ptz, yard, gate, done, _ = _two_relays(wall)
    asker = gate.asks.executor.asker(GATE7)
    assert [(r.member, r.value.get("up")) for r in asker._roads(PTZ7)[1]] == [("east", None), ("north", None)]      # token selects the directly reachable home
    assert [(r.member, r.value.get("up")) for r in asker._roads(YARD7)[1]] == [("east", "north"), ("north", None), ("west", None)]  # token selects its relay and upward hop
    from vms.autoask import Asker
    assert Asker(GATE7, fwd["east"].vars, lambda _: None)._roads(YARD7)[1]                     # the relay may carry that pair
    assert YARD7 in fwd["west"].book()                                 # the centre has a road down to the yard

    left = {x["target"]: x for x in gate.on_event("vehicle")}
    assert {t: (x["state"], x["ingest"]) for t, x in left.items()} == {PTZ7: ("asked", ing["east"]), YARD7: ("asked", ing["east"])}
    assert ptz.pass_once([])["asks"] == [({"camera": PTZ7, "action": "preset", "arg": 1}, "performed")]
    assert PTZ7 not in ing["north"].cams                               # the centre never heard of the PTZ's ask

    assert fwd["east"].woken.is_set()                                  # the ask woke the east forwarder
    assert list(fwd["east"].lift().values()) == ["up"]
    fwd["west"].pass_once()                                            # the centre answers west's poll: down it goes
    assert yard.pass_once([])["asks"] == [({"camera": YARD7, "action": "preset", "arg": 3}, "performed")]
    assert fwd["west"].woken.is_set()                                  # the yard's answer woke the west forwarder
    fwd["west"].lift()                                                 # …which answers the centre
    assert list(fwd["east"].lift().values()) == ["performed"]          # …and east takes the outcome back down
    x = left[YARD7]
    assert gate.asks.executor.asker(GATE7).outcome(YARD7, x["ask"], x["deadline"]) == "performed"
    assert done == {PTZ7: [{"camera": PTZ7, "action": "preset", "arg": 1}], YARD7: [{"camera": YARD7, "action": "preset", "arg": 3}]}


def test_an_ask_going_up_dies_at_its_deadline_on_the_way_and_is_not_kept():
    """The east relay has lost the centre. The ask waits at the relay — tried again on every event — and when
    its deadline passes it dies there: the gate camera reads "expired", and the centre never saw it."""
    wall = Clock()
    ing, fwd, ptz, yard, gate, done, centre_up = _two_relays(wall)
    centre_up["on"] = False
    x = next(x for x in gate.on_event("vehicle") if x["target"] == YARD7)
    assert list(fwd["east"].lift().values()) == ["the centre did not answer"]
    wall.advance(31)
    centre_up["on"] = True
    fwd["east"].lift()
    assert gate.asks.executor.asker(GATE7).outcome(YARD7, x["ask"], x["deadline"]) == "expired"
    assert YARD7 not in ing["north"].cams and done[YARD7] == []


def test_by_event_the_whole_road_takes_milliseconds_while_every_timer_is_a_second():
    """Both forwarders as processes, the yard camera in its own long poll, every fallback timer one second. The
    gate camera sees a vehicle; the ask goes east → centre → west → yard, the answer yard → west → centre → east,
    each hop woken by the one before — done in far less than one timer."""
    import threading
    import time as _t
    wall = Clock()
    ing, fwd, ptz, yard, gate, done, _ = _two_relays(wall)
    stop = threading.Event()
    threads = fwd["east"].serve(stop, period=1.0) + fwd["west"].serve(stop, period=1.0)

    def camera():
        while not stop.is_set():
            yard.pass_once([], wait=1.0)
    cam = threading.Thread(target=camera, daemon=True)
    cam.start()
    _t.sleep(0.2)                                                      # everyone settles into a held poll
    try:
        t0 = _t.monotonic()
        x = next(x for x in gate.on_event("vehicle") if x["target"] == YARD7)
        out = None
        while out is None and _t.monotonic() - t0 < 3.0:
            out = gate.asks.executor.asker(GATE7).outcome(YARD7, x["ask"], x["deadline"])
            _t.sleep(0.005)
        took = _t.monotonic() - t0
    finally:
        stop.set()
        for t in threads + [cam]:
            t.join(timeout=2.0)
    assert out == "performed" and done[YARD7] == [{"camera": YARD7, "action": "preset", "arg": 3}]
    assert took < 0.5, f"took {took:.3f} s: something waited for a timer"


def test_a_relay_that_lost_the_centre_tries_again_each_camera_at_its_own_moment():
    """The product's cross-check (D): the camera's pusher, its ingest lost, tried again after exactly 2 s — every camera
    lost it at the same moment, so every camera came back at the same millisecond, and again, and again. The course's
    pusher has no timer of its own (its process's pass drives it); the relay's forwarder has one per camera, and it
    was the same: `period` exactly, after a centre that did not answer. Now each wait is `period` give or take half,
    drawn afresh every time (`retry_wait`) — the cameras spread out instead of marching."""
    import threading
    import time as _t
    wall = Clock()
    ing, fwd, ptz, yard, gate, done, centre_up = _two_relays(wall)
    assert fwd["east"].book(), "the east relay forwards nobody: nothing would try again"
    centre_up["on"] = False
    waits = []

    class Stop(threading.Event):
        def wait(self, timeout=None):
            name = threading.current_thread().name
            if timeout is not None and name.startswith("fwd-") and not name.startswith(("fwd-asks-", "fwd-outcomes-")):
                waits.append(timeout)
            return super().wait(0.005 if timeout is not None else None)

    stop = Stop()
    threads = fwd["east"].serve(stop, period=2.0)
    t0 = _t.monotonic()
    while len(waits) < 20 and _t.monotonic() - t0 < 3.0:
        _t.sleep(0.01)
    stop.set()
    for t in threads:
        t.join(timeout=2.0)
    assert len(waits) >= 20, waits
    assert all(1.0 <= w <= 3.0 for w in waits), waits                  # period, give or take half
    assert len({round(w, 6) for w in waits}) > len(waits) // 2, waits  # …and not one number for every camera


def test_a_torn_heartbeat_or_book_entry_is_that_ones_trouble_and_the_relay_forwards_on():
    """A malformed unrelated heartbeat does not hide a working centre. The holder rebuilds a torn
    upstream result from signed recorder facts; a relay retains its established route through a torn
    observation. A fresh forwarder cannot open that route until the observation is complete again.
    A damaged ask observation never establishes fresh authority."""
    from vms.forwarder import UPSTREAM_PATH
    wall = Clock()
    north, east, centre, relay, pusher, fwd, dialled, domain_pass = _chain(wall)
    centre.want(SERIAL, "recorder:centre")
    fwd.pass_once()  # Establish a flow before losing the report.
    before = fwd.book()[SERIAL]
    north.objects.put("rec/heartbeats/torn", b'{"worker": "torn", "ts": ')
    domain_pass()
    assert fwd.book()[SERIAL] == before
    # The holder repairs its result from signed worker facts, never reissues a book token.
    items, idx = north.vars.get(f"{UPSTREAM_PATH}/east")
    north.vars.put(f"{UPSTREAM_PATH}/east", {**items, SERIAL: "{"}, cas=idx)
    domain_pass.recording_domain.collect()
    assert fwd.book()[SERIAL] == before
    items, idx = east.vars.get(UPSTREAM_PATH)
    east.vars.put(UPSTREAM_PATH, {**items, SERIAL: '{"urls": ["srt://'}, cas=idx)
    assert fwd.book()[SERIAL] == before
    assert "forwarding" in fwd.pass_once()[SERIAL]
    from vms.forwarder import Forwarder
    fresh = Forwarder("east", relay, east.vars, lambda url: centre)
    fresh.tokens.door = role_requests(east.vars, "recworker")
    assert fresh.book() == {}  # A broken observation cannot establish a new flow.
    from vms.autoask import Asker, BOOK
    from vms.recording_books import Unconfirmed
    from tests.test_book_names import raises
    east.vars.put(BOOK, {"": '{"missing":[]}', SERIAL: "{"})
    raises(Unconfirmed, lambda: Asker("SN7002", east.vars, lambda _: centre)._roads(SERIAL))
    assert fwd.book()[SERIAL] == before  # No damaged ask book interrupts the established stream.


def test_holder_rebuilds_torn_ask_results_from_current_signed_contributions():
    from vms.autoask import BOOK
    wall = Clock()
    ing, fwd, ptz, yard, gate, done, _ = _two_relays(wall)
    vars_ = gate.flash
    # The relay's carried book and the holder's result are separate generations.
    east = fwd["east"].vars
    own = vars_.get("domain/member")[0]["cluster"]
    # Rebuild through the actual signed-report fixture used by the scenario.
    # The fixture is returned on the same relay host, rather than synthesizing a book.
    publication = gate.recording_domain
    holder_vars = publication.vars
    result = f"{BOOK}/{own}"
    good = holder_vars.get(result)[0]
    holder_vars.put(result, {**good, YARD7: "{"})
    publication.collect()
    assert holder_vars.get(result)[0] == good
    # Tearing upstream output does not stop new asks: their authority comes from
    # current placement and scenario settings, not a previously issued road token.
    holder_vars.put(f"{UPSTREAM_PATH}/east", {YARD7: "{"})
    publication.collect()
    left = {x["target"]: x for x in gate.on_event("vehicle")}
    assert all(x["state"] == "asked" for x in left.values())
    assert ptz.pass_once([])["asks"] == [({"camera": PTZ7, "action": "preset", "arg": 1}, "performed")]
    assert "token" not in json.dumps(holder_vars.get(result)[0])


def test_torn_ask_target_refuses_new_authority_without_stopping_another_target():
    from vms.autoask import BOOK
    from vms.recording_books import Unconfirmed
    from tests.test_book_names import raises
    wall = Clock()
    ing, fwd, ptz, yard, gate, done, _ = _two_relays(wall)
    asker = gate.asks.executor.asker(GATE7)
    assert asker._roads(YARD7)[1]  # Previously readable authority is not cached across damage.
    good = gate.flash.get(BOOK)[0]
    gate.flash.put(BOOK, {**good, YARD7: '{"entries":['})
    raises(Unconfirmed, lambda: asker._roads(YARD7))
    assert asker._roads(PTZ7)[1]
    left = {x["target"]: x for x in gate.on_event("vehicle")}
    own = gate.flash.get('domain/member')[0]['cluster']
    assert left[YARD7]["state"] == f"no token at {own}: the ask authority could not be confirmed" and left[PTZ7]["state"] == "asked"
    assert ptz.pass_once([])["asks"] == [({"camera": PTZ7, "action": "preset", "arg": 1}, "performed")]
    assert YARD7 not in ing["east"].cams


def test_a_cameras_own_snapshot_carries_no_secret_and_no_password_in_an_address():
    """vmsserver's eleventh review, blocker 4, and the product's cross-check (the domain's snapshot): a camera that is its
    own cluster publishes its row as its snapshot, and an edit through its door takes any field — a `cred_secret`, or a
    `source` with `?pwd=…`, went into the domain's directory as written. The snapshot carries no secret field and no
    credential in an address (`secrets.mask_secrets`), as a cluster's shards do. Since vmsserver's twelfth review (blocker
    9) the door refuses such an address (`Device._update`); a row an older build stored is published hidden."""
    from w2cplatform.domain.api import ApiError
    cam = DeviceCluster(SERIAL, FakeVariables(), wall=Clock())
    cam.boot()
    try:
        cam._update(1, {"source": "http://10.0.0.5/videostream.cgi?usr=admin&pwd=Hunter2"}, None)
        raise AssertionError("the camera's own console took a password in an address")
    except ApiError as e:
        assert e.status == 400 and "Hunter2" not in e.detail
    items, idx = cam.flash.get("cam/cameras/1")
    cam._put_row({**cam.row(), "source": "http://10.0.0.5/videostream.cgi?usr=admin&pwd=Hunter2",
                  "cred_secret": "Hunter2"}, cas=idx)                          # as an older build stored it
    cam.publish()
    snap = cam.ram.get(f"cam/snapshot/{SERIAL}")
    assert b"Hunter2" not in snap and json.loads(snap)["cameras"][0]["source"].endswith("usr=admin&pwd=***")


# -- the ninth review ----------------------------------------------------------------------------------------------------
def test_a_batch_whose_answer_was_lost_just_before_the_centre_restarted_is_counted_as_a_possible_hole():
    """The ninth review, a minor (and the product's sibling E): the centre keeps the batch it handed over until the relay
    says it has it — in memory. The answer to batch 3 was lost on the way down, the centre restarted, and frame 3 went
    with it: nothing anywhere counted it. The relay cannot know whether such a batch was there, but it knows the centre
    restarted — the mark's `boot` changed — and counts that as a possible hole (`holes`; in its recorder's heartbeat the
    product's `upstream.<ref>.down_breaks`), once per restart; a pull whose answer is lost with no restart is handed over
    again and counts nothing."""
    def centre():                                                      # the centre's recorder, its process (re)started
        ing = ingest_recorder("north", CENTRE_URLS[0], keys=lambda: {}).ingest
        ing._check = lambda *a, **k: {}                                # (the tokens are the other tests')
        ing.subscribe("7", "up:east", maxsize=1000)
        return ing
    at = {"centre": centre()}
    host = ingest_recorder("east", RELAY_URLS[0], keys=lambda: {}, dial=lambda url: at["centre"], needs=lambda ref: True)
    relay, fwd = host.ingest, host.forwarder
    _in_book(host, "7", mode="pull")                                   # a star's camera: pulled down from the centre
    rq = relay.subscribe("7", "recorder:east", maxsize=1000)

    def pull(t, lost=False):
        ing = at["centre"]
        ing._take("7", [{"t": float(t), "key": True}])
        real = ing.pull
        if lost:
            def answer_lost(*a, **kw):
                real(*a, **kw)
                raise Unreachable("the answer to the pull was lost")
            ing.pull = answer_lost
        try:
            fwd._pull(ing, "7", fwd.book()["7"])
        except Unreachable:
            pass
        ing.pull = real
    pull(1); pull(2, lost=True); pull(4)
    assert [f["t"] for f in rq.drain()] == [1, 2, 4] and _upstream(host)["7"]["down_breaks"] == 0   # handed over again
    pull(5, lost=True)                                                  # batch 5 handed over, its answer lost…
    at["centre"] = centre()                                             # …and the centre restarts
    pull(6); pull(7)
    assert [f["t"] for f in rq.drain()] == [6, 7]                       # 5 is gone with the centre —
    assert _upstream(host)["7"]["down_breaks"] == 1 and fwd.holes["7"] == 1   # — and counted, once


def test_the_cameras_card_holds_what_its_relay_took_until_the_centre_has_written_it():
    """The product's DY, checked in the course: with a relay, the camera counted delivered whatever the relay's ingest
    TOOK — and its card let go of it — though the centre above had not written it: frames the forwarder dropped, or that
    the centre's recorder never wrote, were on no copy, and the card had let them go first. The forwarder leaves the
    centre's `have` at the relay's ingest while it carries the camera up (`Ingest.up_have`), the relay's answer to the
    camera says the lesser of its own and the centre's (`Ingest._have`), and the camera counts delivered nothing past it
    (`CameraPusher.owed_spans`): the card holds what the relay took until the centre has written it. When the centre no
    longer takes the camera, its word is gone with it."""
    wall = Clock()
    north, east, centre, relay, pusher, fwd, dialled, _ = _chain(wall)
    centre.want(SERIAL, "recorder:centre")
    rq = centre.subscribe(SERIAL, "recorder:centre", maxsize=1000)
    written = [None]
    centre.written = lambda ref: written[0]
    fwd.pass_once()
    sent = []
    for i in range(30):
        f = {"t": wall() + 0.5, "key": True}                            # two frames a second
        sent.append(f["t"])
        pusher.pass_once([{"t": wall(), "key": True}, f])
        fwd.pass_once()
        rq.drain()
        if i < 10:
            written[0] = f["t"]                                         # the centre's recorder writes, then stalls
        wall.advance(1.0)
    pusher.pass_once([])
    owed = pusher.owed_spans()
    assert owed[-1][0] <= sent[9] + 1e-6 and owed[-1][1] == float("inf"), (owed, sent[9])   # the twenty after: owed
    assert relay.up_have[SERIAL] == sent[9]
    written[0] = sent[-1]                                               # the centre catches up
    fwd.pass_once()
    pusher.pass_once([])
    assert pusher.owed_spans()[-1][0] >= sent[-1] - 1e-6, pusher.owed_spans()
    centre.release(SERIAL, "recorder:centre")
    centre.cams[SERIAL].wants.clear()                                   # the centre takes the camera no longer
    fwd.pass_once()
    assert SERIAL not in relay.up_have



# -- the centre's word, kept across a restart of the relay (ADR-0019: the product's `recproc/upkept.go`, r22) ------------
# The row lands in the relay's store, where its recorder keeps it (`rec/ingest/up/<ref>.json`). A restart of the relay is a
# new process of its recorder over the same stores — a recorder of its own name here, the old one's slot not lapsed yet.
def _gone(url):
    raise Unreachable(f"{url} did not answer the relay")


def _restarted(east, wall, objects=None, dial=_gone):
    """The relay's recorder, started again over the relay's stores (`objects`: another store — one that kept nothing)."""
    return ingest_recorder("east", RELAY_URLS[0], wall, east.vars, objects if objects is not None else east.objects,
                           name="r-again", dial=dial, keys=lambda: {})


def test_a_relay_restarted_while_the_centre_is_unreachable_still_has_the_centres_have():
    """The product first (`upkept.go`): the centre's `have` was in the relay's memory alone, and a relay restarted while the
    centre was unreachable told the camera its own `have` — the card let go of what the centre does not have. The
    forwarder writes the confirmed centre's name and word down in the relay's store (`rec/ingest/up/<ref>.json`,
    ADR-0074) — not on every answer: once when the centre starts wanting the stream, then at most once a minute while
    its `have` moves (`UP_KEPT_EVERY`), at once when it goes back — and the restarted relay seeds `up_have` from it before
    its first pass."""
    from vms.forwarder import UP_KEPT_EVERY, up_key
    wall = Clock()
    north, east, centre, relay, pusher, fwd, dialled, domain_pass = _chain(wall)
    rows = east.objects                                                 # the relay's store, its recorder's
    centre.want(SERIAL, "recorder:centre")
    written = [wall() + 0.25]
    centre.written = lambda ref: written[0]
    fwd.pass_once()
    row = json.loads(rows.get(up_key(SERIAL)))
    assert row == {"v": 2, "centre": "north", "have": int(written[0] * 1000), "heard": int(wall() * 1000)}, row
    for _ in range(30):                                                 # half a minute of `have` moving on: not written
        wall.advance(1.0); written[0] += 1.0
        fwd.pass_once()
    assert fwd.up_writes[SERIAL] == 1 and relay.up_have[SERIAL] == written[0]
    wall.advance(UP_KEPT_EVERY); written[0] += UP_KEPT_EVERY
    fwd.pass_once()                                                     # a minute on: written
    written[0] -= 5.0
    fwd.pass_once()                                                     # gone back: written at once
    assert fwd.up_writes[SERIAL] == 3
    assert json.loads(rows.get(up_key(SERIAL)))["have"] == int(written[0] * 1000)

    up = _upstream(domain_pass.recorders["east"])[SERIAL]               # said in the relay's recorder's heartbeat
    assert up["up_kept_writes"] == 3 and abs(up["up_have"] - written[0]) < 1e-3 and up["up_kept"] is False

    host = _restarted(east, wall)                                       # the relay restarts; the centre is unreachable
    restarted, again = host.ingest, host.forwarder
    assert abs(restarted.up_have[SERIAL] - written[0]) < 1e-3          # before its first pass
    again.pass_once()
    assert abs(restarted._have(SERIAL) - written[0]) < 1e-3            # what the camera is told: the centre's word
    up = _upstream(host)[SERIAL]
    assert up["up_expired"] == 0 and up["up_kept"] is True              # …the word a process before kept

    nowhere = _restarted(east, wall, objects=Ram()).ingest   # a store that kept nothing
    assert SERIAL not in nowhere.up_have


def test_a_centre_that_does_not_want_the_stream_drops_the_kept_word():
    from vms.forwarder import up_key
    wall = Clock()
    north, east, centre, relay, pusher, fwd, dialled, _ = _chain(wall)
    rows = east.objects                                                 # the relay's store, its recorder's
    centre.want(SERIAL, "recorder:centre")
    centre.written = lambda ref: wall()
    fwd.pass_once()
    assert rows.get(up_key(SERIAL)) is not None
    centre.release(SERIAL, "recorder:centre")
    centre.cams[SERIAL].wants.clear()                                   # the centre takes the camera no longer
    fwd.pass_once()
    assert rows.get(up_key(SERIAL)) is None and SERIAL not in relay.up_have
    restarted = _restarted(east, wall).ingest
    assert SERIAL not in restarted.up_have                              # nothing kept, nothing said


def test_a_kept_word_older_than_a_day_is_dropped_and_counted_and_a_silent_centre_expires_the_same_way():
    """`UP_KEPT_FOR`, the product's `UpKeptFor`: kept for ever, the word of a centre that never comes back had every
    camera behind the relay keep everything its card holds. A word written longer ago than a day is not said after the
    restart: dropped, counted (`up_expired`) and logged; a fresher one is said. While the relay runs, a centre silent that
    long is said no more, counted the same way — and answering again says it again."""
    from vms.forwarder import UP_KEPT_FOR, up_key
    wall = Clock()
    north, east, centre, relay, pusher, fwd, dialled, domain_pass = _chain(wall)
    rows = east.objects                                                 # the relay's store, its recorder's
    wall.advance(3 * UP_KEPT_FOR)

    def kept(age, have):
        rows.put(up_key(SERIAL), json.dumps({"v": 2, "centre": "north", "have": have,
                                           "heard": int((wall() - age) * 1000)}).encode())

    kept(UP_KEPT_FOR + 1, 5_000)
    host = _restarted(east, wall)
    stale, old = host.ingest, host.forwarder
    assert SERIAL not in stale.up_have and rows.get(up_key(SERIAL)) is None
    assert old.up_expired == {SERIAL: 1} and _upstream(host)[SERIAL]["up_expired"] == 1

    kept(UP_KEPT_FOR - 60, 7_000)                                       # a word not a day old: said
    fresh, now = (lambda h: (h.ingest, h.forwarder))(_restarted(east, wall))
    assert fresh.up_have[SERIAL] == 7.0
    now.pass_once()
    assert fresh.up_have[SERIAL] == 7.0 and now.up_expired == {}
    wall.advance(61)                                                    # …and past the day, the centre still silent
    now.pass_once()
    assert SERIAL not in fresh.up_have and now.up_expired == {SERIAL: 1}
    now.pass_once()
    assert now.up_expired == {SERIAL: 1}                                # counted once

    now.dial = fwd.dial                                                 # the centre answers again: its word is said again
    now.tokens.door = role_requests(east.vars, "recworker")
    for recorder in domain_pass.recorders.values():
        recorder.claim_slot(recorder.name)
    domain_pass()                                                       # three days on: the stream token issued anew
    centre.want(SERIAL, "recorder:centre")
    centre.written = lambda ref: wall()
    now.pass_once()
    assert fresh.up_have[SERIAL] == wall()
    assert json.loads(rows.get(up_key(SERIAL)))["heard"] == int(wall() * 1000)


# -- the eleventh review -------------------------------------------------------------------------------------------------
def test_ingest_losses_and_clock_steps_are_in_polled_and_forwarder_losses_in_its_heartbeat():
    """C7 decision 2c3c1fc3: ordinary rec/polled and upstream, auth on the platform view."""
    import urllib.error
    import urllib.request
    from w2cplatform.console import open_doors
    from w2cplatform.domain.federation import Unreachable as Gone
    from w2cplatform.domain.console import Console
    from w2cplatform.domain.api import ConsoleAPI
    from w2cplatform.domain.federation import DomainDirectory, published
    from w2cplatform.rows import counts
    wall = Clock()
    north, east, centre, relay, pusher, fwd, dialled, domain_pass = _chain(wall)
    centre.want(SERIAL, "recorder:centre")
    centre.subscribe(SERIAL, "recorder:centre", maxsize=1000)
    relay.subscribe(SERIAL, "viewer:v", maxsize=1, edge=True)          # a viewer at the relay that does not read
    fwd.pass_once()

    def second():
        wall.advance(1)
        pusher.pass_once([{"t": wall(), "key": True}])
    second(); second()
    push, left = centre.push, {"n": 1}

    def took_but_lost(*a, **kw):
        out = push(*a, **kw)
        if left["n"]:
            left["n"] -= 1
            raise Gone("the answer was lost")
        return out
    centre.push = took_but_lost
    fwd.pass_once(); second(); fwd.pass_once()                         # the centre gets two frames again: repeats
    fwd._kept(SERIAL, [{"t": 1000 + i / 25, "key": i % 50 == 0} for i in range(25 * 30)])   # past what it holds
    relay.cams[SERIAL].clock_steps = 2                                  # (as two moves of the held offset leave it)
    for r in domain_pass.recorders.values():
        r.heartbeat_once()                                              # each recorder writes its ingest's `rec/polled`
    east.objects.put("rec/polled/torn", b'{"cluster": "east", "lost": ')
    fed = Federation()
    fed.add(north); fed.add(east)
    docs = {}
    before = sum(counts().get("member_object", {}).values())
    for name, cluster in fed.clusters.items():
        for key in cluster.objects.list("rec/polled/"):
            doc = published(name, key, cluster.objects.get(key),
                            lambda d: (dict(d.get("lost") or {}), dict(d.get("clock_steps") or {})))
            if doc is not None:
                docs[name, key] = doc
    centre_doc = next(d for (name, _), d in docs.items() if name == "north")
    relay_doc = next(d for (name, _), d in docs.items() if name == "east")
    held = fwd.dropped[SERIAL]
    assert held > 0
    assert centre_doc["lost"][SERIAL]["repeats"] == 2
    assert sum(relay_doc["lost"][SERIAL]["dropped"].values()) > 0
    assert relay_doc["clock_steps"][SERIAL] == 2
    assert all("upstream" not in d for d in docs.values())
    up = _upstream(domain_pass.recorders["east"])[SERIAL]
    assert up["up_dropped"] >= held and up["mode"] == "push"
    assert sum(counts()["member_object"].values()) > before
    assert len(docs) == 2
    directory = DomainDirectory(fed, wall=wall)
    console = Console(directory, ReadView(fed, wall=wall), ConsoleAPI(directory, verifier=lambda t: t),
                      viewer=lambda subject: subject == "boris")
    console.view.refresh()
    srv = open_doors("127.0.0.1", 0, console.handler(),
                     unix_env="NO_SUCH_DOOR", say=False)
    try:
        def status(who=None):
            req = urllib.request.Request(f"http://127.0.0.1:{srv.server_address[1]}/domain/cam/cameras",
                                         headers={"Authorization": f"Bearer {who}"} if who else {})
            try:
                return urllib.request.urlopen(req).status
            except urllib.error.HTTPError as e:
                return e.code
        assert (status(), status("vera"), status("boris")) == (401, 403, 200)
    finally:
        srv.shutdown(); srv.server_close()


# -- the forwarder lives in the relay's recorder (ADR-0065 and its addition of 2026-10-08; ADR-0019) ----------------------
# Words of the product's `Forwarder.Stats` (`recproc/forwarder.go`) — only the ones the course counts (ADR-0065, its
# addition of 2026-10-10: the fifteenth review, major 3) — and the course's own `errors` (the fifteenth review's blocker):
# every camera's three, a pulled camera's one more, a pushed camera's five more — `up_have` only once the centre said one.
FORWARDER_WORDS = {"push": {"mode", "state", "errors", "up_dropped", "up_have", "up_kept", "up_expired", "up_kept_writes"},
                   "pull": {"mode", "state", "errors", "down_breaks"}}
FORWARDER_NOT_COUNTED = {"up_sent", "up_gaps", "up_resumed", "up_have_every", "up_unconfirmed_s", "up_polls", "up_cuts",
                         "down_taken", "down_dropped"}


def test_the_relays_recorder_says_what_its_forwarder_carried_and_lost_in_the_products_words_it_counts():
    """What the forwarder carried and lost is not an object of the relay's (`rec/forwarded/<name>` is gone) but its
    recorder's heartbeat: `upstream.<ref>`, per camera of the upstream book, in the product's words — only what the course
    counts; the nine it does not count are not said (a nought read as health). A pushed camera says what the centre
    confirmed (`up_have`) once it said it; a star's pulled camera says the down word; the centre, with no upstream book,
    says no `upstream`."""
    assert len(FORWARDER_NOT_COUNTED | FORWARDER_WORDS["push"] | FORWARDER_WORDS["pull"]) == 18   # the 17, and `errors`
    wall = Clock()
    north, east, centre, relay, pusher, fwd, dialled, domain_pass = _chain(wall)
    host = domain_pass.recorders["east"]
    assert set(_upstream(host)[SERIAL]) == FORWARDER_WORDS["push"] - {"up_have"}   # the centre has said nothing yet
    centre.want(SERIAL, "recorder:centre")
    rq = centre.subscribe(SERIAL, "recorder:centre", maxsize=1000)
    centre.written = lambda ref: wall()
    fwd.pass_once(); pusher.pass_once(["a", "b"]); fwd.pass_once()
    assert rq.drain() == ["a", "b"]
    up = _upstream(host)[SERIAL]
    assert set(up) == FORWARDER_WORDS["push"]
    assert up["mode"] == "push" and up["state"].startswith("forwarding") and up["up_have"] == wall()
    assert (up["up_dropped"], up["up_expired"], up["up_kept_writes"], up["up_kept"], up["errors"]) == (0, 0, 1, False, 0)
    assert "upstream" not in json.loads(north.objects.get("rec/heartbeats/r-1"))   # the centre forwards nothing

    north, east, centre, relay, pusher, fwd, dialled, domain_pass = _chain(Clock(), star={"east"})
    relay.subscribe(SERIAL, "recorder:east")
    fwd.pass_once(); pusher.pass_once(["s1"]); fwd.pass_once()
    up = _upstream(domain_pass.recorders["east"])[SERIAL]
    assert set(up) == FORWARDER_WORDS["pull"] and up["mode"] == "pull" and up["down_breaks"] == 0


def test_nothing_writes_where_the_ingest_or_the_forwarder_used_to_announce_itself():
    """ADR-0003, ADR-0065's addition: `rec/ingest` (the ingest's announcement) and `rec/forwarded/<name>` (the forwarder's
    losses) are gone without a migration — no writer, no reader, no spec line (`domain.reports[ingest]`,
    `objects.door[forwarded/*]`). A chain that pushes and pulls, its recorders beating, leaves neither in any store."""
    from vms.config import REC_SPEC
    from vms import forwarder as chain, ingest
    assert REC_SPEC.domain.reports == ("polled/",) and "forwarded/*" not in REC_SPEC.object_door
    assert not hasattr(ingest, "INGEST") and not hasattr(ingest, "FORWARDED")
    assert not hasattr(ingest.Ingest, "announce") and not hasattr(chain.Forwarder, "publish")
    for star in (frozenset(), {"east"}):
        wall = Clock()
        north, east, centre, relay, pusher, fwd, dialled, domain_pass = _chain(wall, star=star)
        centre.want(SERIAL, "recorder:centre")
        relay.subscribe(SERIAL, "recorder:east")
        for _ in range(3):
            fwd.pass_once(); pusher.pass_once([{"t": wall(), "key": True}]); wall.advance(1); domain_pass()
        for c in (north, east):
            keys = c.objects.list("rec/")
            assert "rec/heartbeats/r-1" in keys and any(k.startswith("rec/polled/") for k in keys), keys
            assert "rec/ingest" not in keys and not any(k.startswith("rec/forwarded") for k in keys), keys


# -- a store that failed once does not end the forwarder (the fifteenth review's blocker, minor 9; ADR-0065, its addition) --
class _FlakyStore(FakeVariables):
    """The relay's store, which answers — and, while `broken`, does not: the file store's `StoreBusy`, an `OSError`."""
    broken = False

    def get(self, path):
        if self.broken:
            from w2cplatform.variables import StoreBusy
            raise StoreBusy("the store did not answer")
        return super().get(path)


class _TakesAll:
    """A centre that wants every stream and takes all it is pushed."""
    def __init__(self):
        self.pushed = []

    def poll(self, token, ref, version=None, wait=0.0):
        return {"version": 1, "push": True, "ranges": {}, "asks": {}}

    def push(self, token, ref, frames):
        self.pushed.extend(frames)


def _until(cond, within: float = 5.0) -> bool:
    import time
    end = time.monotonic() + within
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.01)
    return cond()


def _alive(name: str) -> bool:
    import threading
    return any(t.name == name and t.is_alive() for t in threading.enumerate())


def _frames(n: int, start: float) -> list:
    return [{"t": start + i * 0.01, "key": i == 0} for i in range(n)]


def test_a_store_that_did_not_answer_once_is_counted_said_and_the_stream_up_goes_on_after_it():
    """The fifteenth review's blocker (ADR-0065, its addition; `resilience.mdc`, `observability.mdc`). One `StoreBusy` of
    the relay's store killed the camera's thread and the asks' thread of its forwarder for good — nothing logged, nothing
    counted, the camera's frames never reached the centre again while the heartbeat repeated "forwarding". Now a round
    that fails is counted (`upstream.<ref>.errors`, the recorder's `forwarder_errors`), said once by the `chain` logger
    and once more when it works again, and the next round goes on: the frames after the store came back reach the
    centre."""
    import logging
    import threading
    import time
    store, centre = _FlakyStore(), _TakesAll()
    rec = ingest_recorder("east", RELAY_URLS[0], time.time, store, dial=lambda url: centre)
    local, fwd = rec.ingest, rec.forwarder
    _in_book(rec, SERIAL)
    said: list[logging.LogRecord] = []
    catch = logging.Handler(logging.INFO)
    catch.emit = said.append
    chain_log = logging.getLogger("chain")
    level = chain_log.level
    chain_log.addHandler(catch); chain_log.setLevel(logging.INFO)
    stop = threading.Event()
    try:
        fwd.serve(stop, period=0.05, stream_every=0.01)
        assert _until(lambda: fwd.forwarding.get(SERIAL) and SERIAL in fwd.queues)
        local.inject(SERIAL, _frames(30, time.time() - 1))
        assert _until(lambda: len(centre.pushed) == 30)
        store.broken = True                                              # one blink of the store…
        assert _until(lambda: fwd.errors.get(SERIAL, 0) >= 2 and fwd.errors.get("asks", 0) >= 1)
        store.broken = False                                             # …and it answers again
        local.inject(SERIAL, _frames(30, time.time() - 0.5))
        assert _until(lambda: len(centre.pushed) == 60), len(centre.pushed)   # the stream up went on
        assert _alive(f"fwd-{SERIAL}") and _alive("fwd-asks-east") and _alive("fwd-outcomes-east")
    finally:
        stop.set()
        chain_log.removeHandler(catch); chain_log.setLevel(level)
    failed = [r.getMessage() for r in said if r.levelno == logging.WARNING and f"the stream of {SERIAL} up failed" in r.getMessage()]
    assert len(failed) == 1 and "StoreBusy" in failed[0], failed        # said once, not once a round
    assert any(f"the stream of {SERIAL} up works again" in r.getMessage() for r in said)
    assert any(r.levelno == logging.WARNING and "(lift) failed" in r.getMessage() for r in said)
    rec.heartbeat_once()
    hb = json.loads(rec.objects.get("rec/heartbeats/r-1"))
    assert hb["upstream"][SERIAL]["errors"] == fwd.errors[SERIAL] >= 2
    assert hb["forwarder_errors"] == sum(fwd.errors.values()) > hb["upstream"][SERIAL]["errors"]   # the asks' too


def test_a_camera_taken_out_of_the_upstream_book_ends_its_loop_and_its_subscription():
    """The fifteenth review, minor 9 (`sharding-and-backpressure.mdc`; the product's `Pass` closes the loop of a camera its
    book no longer names, `recproc/forwarder.go`). A camera's thread read the book and waited while its camera was gone
    from it — for ever, its subscription at the relay's ingest filling and dropping: threads and queues grew with every
    camera the relay ever forwarded. Now the loop ends, and lets go of its subscription and its want; the camera put back
    in the book is forwarded again by a loop of its own."""
    import threading
    import time
    from vms.forwarder import UPSTREAM_PATH
    store, centre = _FlakyStore(), _TakesAll()
    rec = ingest_recorder("east", RELAY_URLS[0], time.time, store, dial=lambda url: centre)
    local, fwd = rec.ingest, rec.forwarder
    _in_book(rec, SERIAL)
    stop = threading.Event()
    try:
        fwd.serve(stop, period=0.05, stream_every=0.01)
        assert _until(lambda: SERIAL in fwd.queues and _alive(f"fwd-{SERIAL}"))
        assert fwd.up in local.tees[(SERIAL, "live")].subscribers
        # Explicit withdrawal ends a working flow; a lost report preserves it.
        store.as_writer("domainagent").delete("domain/placed/rec/" + SERIAL)
        assert _until(lambda: not _alive(f"fwd-{SERIAL}"))
        assert SERIAL not in fwd.queues and SERIAL not in fwd.state
        assert fwd.up not in local.tees[(SERIAL, "live")].subscribers   # its subscription let go…
        assert local.cams[SERIAL].wants[fwd.up] <= time.time() + LINGER  # …and its want, as a viewer's
        assert SERIAL not in fwd.stats() and _alive("fwd-asks-east")
        _in_book(rec, SERIAL)                                            # back in the book: a loop of its own again
        fwd.woken.set()
        assert _until(lambda: SERIAL in fwd.queues and _alive(f"fwd-{SERIAL}"))
        local.inject(SERIAL, _frames(10, time.time() - 1))
        assert _until(lambda: len(centre.pushed) >= 10)
        assert sum(t.name == f"fwd-{SERIAL}" for t in threading.enumerate()) == 1
    finally:
        stop.set()


def test_what_the_chain_lost_is_on_rec_metrics_per_camera():
    """ADR-0065, its addition of 2026-10-10 (the fifteenth review, major 3): the losses the course counts are lines of
    the spec's `metrics:` over the recorders' heartbeats — `rec_upstream_{dropped,breaks,expired}_total` over the
    forwarder's `upstream.<camera>`, `rec_ingest_{cut,absurd_frames,ahead_losses,repeats_dropped}_total` over the ingest's
    `ingest_streams.<camera>` — each with the camera as its label, on the console's `/rec/metrics`."""
    import urllib.request
    from vms.config import REC_SPEC, SPEC
    from vms.console import serve
    from vms.controller import VmsController
    from w2cplatform.spec import SpecController
    from tests.vmsconftest import Box
    box = Box()
    rec = ingest_recorder("east", RELAY_URLS[0], box.wall, objects=box.objects)
    _in_book(rec, SERIAL)
    pull_rec = ingest_recorder("west", WEST_URLS[0], box.wall, objects=box.objects, name="r-pull")
    _in_book(pull_rec, "SN7002", mode="pull")
    pull_rec.forwarder.holes["SN7002"] = 2
    fwd, ing = rec.forwarder, rec.ingest
    fwd.dropped[SERIAL], fwd.up_expired[SERIAL] = 3, 1
    fwd.errors[SERIAL] = 2                                               # two rounds its store failed (the blocker)
    q = ing.subscribe(SERIAL, "recorder:r-9", maxsize=2)
    frames = _frames(5, box.wall() - 1)
    ing.inject(SERIAL, frames); ing.inject(SERIAL, frames)              # three past a queue of two; five repeats
    ing.ahead[SERIAL] = 4                                                # (refused at the door as absurd)
    rec.heartbeat_once(); pull_rec.heartbeat_once()
    hb = json.loads(box.objects.get("rec/heartbeats/r-1"))
    st = hb["ingest_streams"][SERIAL]
    assert q.dropped == 3 and "cut_for_full_queue" not in st and st["repeats_dropped"] == 5 and st["absurd_frames"] == 4
    ctl = VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)
    recs = SpecController(REC_SPEC, box.vars.as_writer("console", REC_SPEC.acl_console()), box.objects, wall=box.wall)
    srv = serve(ctl, box.resource_root, port=0, wall=box.wall, mounts={"rec": recs})
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{srv.server_address[1]}/rec/metrics", headers={"X-User": "anna"})
        text = urllib.request.urlopen(req).read().decode()
    finally:
        srv.shutdown()
    lines = text.splitlines()
    for line in (f'rec_upstream_dropped_total{{camera="{SERIAL}"}} 3', 'rec_upstream_breaks_total{camera="SN7002"} 2',
                 f'rec_upstream_expired_total{{camera="{SERIAL}"}} 1',
                 f'rec_forwarder_errors_total{{camera="{SERIAL}"}} 2',
                 f'rec_ingest_absurd_frames_total{{camera="{SERIAL}"}} 4',
                 f'rec_ingest_ahead_losses_total{{camera="{SERIAL}"}} {st["ahead_losses"]}',
                 f'rec_ingest_repeats_dropped_total{{camera="{SERIAL}"}} 5'):
        assert line in lines, (line, [x for x in lines if "upstream" in x or "ingest_" in x])
    for name in ("upstream_dropped_total", "upstream_breaks_total", "upstream_expired_total", "forwarder_errors_total",
                 "ingest_absurd_frames_total", "ingest_ahead_losses_total", "ingest_repeats_dropped_total"):
        assert f"# TYPE rec_{name} counter" in lines
    process_metrics = rec.metrics_text().splitlines()
    for line in ("rec_ingest_repeats_dropped 5", "rec_ingest_absurd_frames 4",
                 f"rec_ingest_ahead_losses {st['ahead_losses']}"):
        assert line in process_metrics
