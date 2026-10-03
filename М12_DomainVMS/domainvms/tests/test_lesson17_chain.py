"""Lesson 17 — a chain: site, relay, centre.

Cameras nobody can dial, recorded by a relay nobody above can dial, watched from a centre everybody can
reach. Each level dials the level above: the camera its relay (media) and the centre (books, reports); the
relay the centre. The want travels down, the stream up. The star: a relay that cannot be pushed to takes
its cameras' streams from the centre. A relay: a camera that can reach only its relay cluster reaches the domain
through it both ways — the relay copies down what the domain left for it and carries its report up in one
summary object.
"""
import json

from cluster.variables import FakeVariables

from domain.agent import ClusterTrust, DomainAgent, DomainPublisher
from domain.chain import Forwarder, bundle, publish_upstream
from domain.crossing import Crossings
from domain.device import DeviceCluster, Ram
from domain.federation import Federation, Unreachable
from domain.gateway import Gateway
from domain.ingest import LINGER, CameraPusher, Ingest, IngestLiveEndpoint, audience
from domain.readview import ReadView
from domain.signer import Signer
from domain.uplink import member_copy
from tests.conftest import Clock, make_cluster

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
    centre = Ingest("north", CENTRE_URLS, keys=lambda: ClusterTrust(north.vars).keyset(), wall=wall)
    centre.announce(north.objects)
    relay_agent = DomainAgent("east", north.vars, east.vars, now=wall)
    relay_agent.sync()
    relay = Ingest("east", RELAY_URLS, keys=lambda: ClusterTrust(east.vars).keyset(), wall=wall)
    relay.announce(east.objects)
    SpecController(REC_SPEC, east.vars, east.objects, wall=wall).create({"name": SERIAL, "cam": f"ref:{SERIAL}"})

    cam = DeviceCluster(SERIAL, FakeVariables(), wall=wall, pushes=True)
    cam.boot(); cam.door_open = False                                  # nobody dials the camera
    fed.add(member_copy(cam.name, north.objects, wall=wall))
    cam_agent = DomainAgent(cam.name, north.vars, cam.flash, now=wall, domain_objects=north.objects, published=cam.local_objects())
    cam_agent.sync()
    view = ReadView(fed, wall=wall); view.refresh()
    crossings = Crossings(north.vars, view, wall, issuer=signer.tokens, centre="north", star=star)
    crossings.record(SERIAL, on="east")

    dialled = []

    def dial_from(who, reachable):
        def dial(url):
            dialled.append((who, url))
            if url in RELAY_URLS and "relay" in reachable:
                return relay
            if url in CENTRE_URLS:
                return centre
            raise Unreachable(f"{url} did not answer {who}")
        return dial

    pusher = CameraPusher(SERIAL, cam.flash, dial_from("camera", {"relay"} if not star else set()), clock=wall)
    fwd = Forwarder("east", relay, east.vars, dial_from("relay", set()),
                    archive=lambda ref, t0, t1: [("east-archive", ref, t0, t1)], needs=lambda ref: True)

    def domain_pass():
        view.refresh(); crossings.publish(); crossings.publish_primaries()
        publish_upstream(crossings, "north", star=star)
        cam_agent.sync(); relay_agent.sync()

    domain_pass.crossings = crossings
    domain_pass()
    return north, east, centre, relay, pusher, fwd, dialled, domain_pass


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
    from domain.ingest import RangeFailed
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
    """A relay behind a mobile operator, or a cloud cluster that takes no inbound: nobody can push to it.
    The camera's book names the centre; the relay, wanting the stream for its recorder, pulls it — calling
    in. Nobody dials the camera, nobody dials the relay."""
    wall = Clock()
    north, east, centre, relay, pusher, fwd, dialled, _ = _chain(wall, star={"east"})
    assert pusher.entry()["ingest"]["urls"] == CENTRE_URLS
    rq = relay.subscribe(SERIAL, "recorder:east")
    fwd.pass_once()                                                    # the relay wants it: pulling is wanting at the centre
    assert pusher.pass_once(["s1", "s2"])["pushed"] == 2               # the camera pushes to the centre
    fwd.pass_once()                                                    # the relay pulls them down
    assert rq.drain() == ["s1", "s2"]
    assert {(w, u) for w, u in dialled} <= {("camera", u) for u in CENTRE_URLS} | {("relay", u) for u in CENTRE_URLS}


def test_frames_the_relay_could_not_push_up_or_whose_pull_answer_was_lost_are_sent_again_not_dropped():
    """The seventh review's rule for the camera — nothing moves until it is taken — one level up. The relay drained
    what the camera sent and pushed it to the centre; a push that failed took those frames with it, and its
    `Unreachable` ended the whole pass. Now they are pushed again first, and the pass goes on. In the star, the centre
    drained what it handed the relay; an answer lost on its way down lost the frames — now the relay says which batch
    it last got, and the centre hands the lost one over again."""
    from domain.federation import Unreachable as Gone
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

    north, east, centre, relay, pusher, fwd, dialled, _ = _chain(Clock(), star={"east"})
    rq = relay.subscribe(SERIAL, "recorder:east")
    fwd.pass_once(); pusher.pass_once(["s1", "s2"])
    pull, left = centre.pull, {"n": 1}

    def lost(*a, **kw):
        out = pull(*a, **kw)
        if left["n"]:
            left["n"] -= 1
            raise Gone("the answer to the pull was lost")
        return out
    centre.pull = lost
    assert "stopped answering" in fwd.pass_once()[SERIAL] and rq.drain() == []
    pusher.pass_once(["s3"]); fwd.pass_once()
    assert rq.drain() == ["s1", "s2", "s3"]                            # the lost batch again, then what came since
    fwd.pass_once()
    assert rq.drain() == []                                            # …and not a third time


# -- the eighth review ---------------------------------------------------------------------------------------------------
def test_a_centre_that_restarts_in_the_middle_of_a_pull_with_two_answers_lost_hands_every_frame_down():
    """The eighth review, blocker 2, run as its probe ran it. The relay had got batch 2; the centre restarted — its
    count back at nought — and the first two answers after it were lost on the way down. The relay still said "2", the
    new count reached 2, and the third pull was taken for "the relay has batch 2": frames 3 and 4 never arrived, and
    nothing counted them. A batch's mark is `(boot, n)` now, and a mark from another boot is never this boot's: the
    last batch goes again until the relay has a mark of this boot. Every frame arrives, once, in order; a relay that
    restarted itself says no mark, and gets the last batch once more — a repeat its ingest drops."""
    from domain.chain import Forwarder

    def centre():
        ing = Ingest("north", CENTRE_URLS, keys=lambda: {})
        ing._check = lambda *a, **k: {}                                # (the tokens are the other tests')
        ing.subscribe("7", "up:east", maxsize=1000)                    # the relay's subscription, from its first pull
        return ing
    at = {"centre": centre()}
    relay = Ingest("east", RELAY_URLS, keys=lambda: {})
    rq = relay.subscribe("7", "recorder:east", maxsize=1000)
    fwd = Forwarder("east", relay, FakeVariables(), lambda url: at["centre"], needs=lambda ref: True)

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
            fwd._pull(ing, "7", {"token": "t"})
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
    from domain.federation import Unreachable as Gone
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
    seconds now, at most `FORWARD_BYTES`, cut clean to a key frame, and the camera's state and `stats` say how many
    frames it dropped past that."""
    from domain.chain import FORWARD_HOLD, Forwarder
    fwd = Forwarder("east", Ingest("east", RELAY_URLS, keys=lambda: {}), FakeVariables(), lambda url: None)
    frames = [{"t": 1000 + i / 25, "key": i % 50 == 0} for i in range(25 * 30)]   # thirty seconds at 25 frames a second
    kept = fwd._kept("7", frames)
    assert kept[0]["key"] and frames[-1]["t"] - kept[0]["t"] <= FORWARD_HOLD and kept[-1] is frames[-1]
    assert len(kept) >= 25 * (FORWARD_HOLD - 2) and fwd.dropped["7"] == len(frames) - len(kept)
    fat = [{"t": 1000 + i, "key": True, "body": b"x" * (4 << 20)} for i in range(8)]
    assert len(fwd._kept("8", fat)) == 4                               # sixteen mebibytes, whatever the seconds
    fwd.state["7"] = "forwarding"
    assert fwd.stats()["7"]["dropped"] == fwd.dropped["7"]


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


def test_the_summary_report_one_object_per_relay_and_the_price_of_it():
    """Cameras that can reach only their relay report to it, and the relay folds their reports into one
    object in the centre. The price: when a relay goes quiet, its cameras go quiet with it — they have no
    other road, and the centre cannot tell the relay from its sites. The side effect: three hundred cameras
    in ten relays are ten writes per round instead of eight hundred."""
    wall = Clock()
    north, store, relays, fed = _site_of(10, 30, wall)

    def round_(skip=()):
        for name, (relay_store, cams) in relays.items():
            for d, a in cams:
                d.publish(); a.sync()
            if name not in skip:
                bundle(name, [d.name for d, _ in cams], relay_store, store)

    round_()
    view = ReadView(fed, wall=wall); view.refresh()
    assert view.list(size=400)["total"] == 300 and view.list()["complete"]
    wall.advance(10); store.puts = 0
    round_()
    assert store.puts == 10                                             # one per relay per round
    assert store.largest < 64 * 1024                                    # a bundle fits a Variable: ~30 cameras a relay
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
    from domain.api import ConsoleAPI
    from domain.chain import Relay
    from domain.federation import DomainDirectory
    from domain.grants import Grant
    from domain.pending import PendingEdits

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
    through = Relay(east.vars, east.objects)                           # all the camera can reach
    cam_agent = DomainAgent(cam.name, through.vars, cam.flash, now=wall, console=cam.local_console(), current=cam.current,
                            domain_objects=through.objects, published=cam.local_objects(), seen_store=cam.local_objects())
    relay = Ingest("east", RELAY_URLS, keys=lambda: ClusterTrust(east.vars).keyset(), wall=wall)
    relay.announce(east.objects)
    SpecController(REC_SPEC, east.vars, east.objects, wall=wall).create({"name": SERIAL, "cam": f"ref:{SERIAL}"})

    def passes():
        relay_agent.sync(); cam_agent.sync(); relay_agent.sync()

    passes()
    view = ReadView(fed, wall=wall); view.refresh()
    assert [r["ref"] for r in view.list()["rows"] if r["cluster"] == cam.name] == [SERIAL]   # up: the bundle

    DomainPublisher(north.vars).publish_grants(cam.name, [Grant("anna", "edit", None, wall() + 3600)])
    passes()
    assert [g.subject for g in ClusterTrust(cam.flash).grants()] == ["anna"]                   # down: the relay

    pending = PendingEdits(north.vars, wall)

    def no_door(name):
        raise Unreachable(f"{name} is reached only through its relay")

    api = ConsoleAPI(DomainDirectory(fed, wall=wall), no_door, verifier=lambda t: t, pending=pending, last_known=view.last_known)
    assert api.update_camera(SERIAL, {"name": "yard"}, idempotency_key="k1", token="anna")["pending"]
    passes()
    assert cam.row()["name"] == "yard"                                 # carried down by the relay, applied by the camera
    view.refresh(); pending.collect(fed)
    assert pending.of(cam.name) == {}                                  # the outcome came up in the bundle

    crossings = Crossings(north.vars, view, wall, issuer=signer.tokens)
    crossings.record(SERIAL, on="east"); crossings.publish_primaries()
    passes()
    pusher = CameraPusher(SERIAL, cam.flash, lambda url: relay if url in RELAY_URLS else (_ for _ in ()).throw(Unreachable(url)))
    relay.want(SERIAL, "recorder:east")
    assert pusher.pass_once(["f"])["pushed"] == 1                      # the stream token came down the same road

    last = wall()
    north_link.up = False                                              # the relay loses the centre
    for _ in range(4):
        wall.advance(20); relay_agent.sync(); cam_agent.sync()        # the camera still reaches its relay
    assert json.loads(cam.ram.get(DOMAIN_SEEN))["ts"] == last          # …and knows its books are as old as the relay's


def test_an_ask_from_a_camera_at_another_site_goes_by_the_centre_and_the_relay_carries_it_down():
    """The gate camera is at another site: it reaches the centre, not the east relay. Its book names two roads
    to the yard camera — the relay that records it, then the centre the relay forwards it to. The relay's
    ingest does not answer, so the ask is left at the centre; the relay's forwarder, polling the centre, carries
    it down to the camera's poll, and the outcome back up."""
    from domain.ingest import Asker, publish_asks
    wall = Clock()
    north, east, centre, relay, pusher, fwd, dialled, domain_pass = _chain(wall)
    gate = DeviceCluster("SN7002", FakeVariables(), wall=wall, pushes=True)
    gate.boot(); gate.door_open = False
    done = []
    pusher.perform = lambda action: done.append(action) or "performed"
    # the gate camera is a member like the yard camera: its report makes it known to the domain's view
    crossings = domain_pass.crossings
    crossings.view.fed.add(member_copy(gate.name, north.objects, wall=wall))
    gate_agent = DomainAgent(gate.name, north.vars, gate.flash, now=wall, domain_objects=north.objects,
                             published=gate.local_objects())
    gate_agent.sync()
    crossings.view.refresh()
    publish_asks(crossings, [{"trigger": "SN7002", "target": SERIAL, "actions": [{"preset": 3}]}])
    gate_agent.sync()

    def gate_dial(url):
        if url in CENTRE_URLS:
            return centre
        raise Unreachable(f"{url} did not answer the gate camera")

    asker = Asker("SN7002", gate.flash, gate_dial, clock=wall)
    assert [r["urls"] for r in asker.book()[SERIAL]] == [RELAY_URLS, CENTRE_URLS]
    ing, aid = asker.ask(SERIAL, {"preset": 3}, within=10)
    assert ing is centre and centre.ask_outcome(SERIAL, aid) is None
    fwd.pass_once()                                                    # down to the relay's ingest
    assert pusher.pass_once([])["asks"] == [({"preset": 3}, "performed")] and done == [{"preset": 3}]
    fwd.pass_once()                                                    # the outcome, up
    assert centre.ask_outcome(SERIAL, aid) == "performed"
    assert done == [{"preset": 3}]                                     # carried twice, done once


def test_a_camera_that_sees_only_its_relay_and_that_nobody_records_polls_its_relay():
    """One site, one relay: the gate camera and a PTZ camera kept for live view, both reaching only the east
    relay, neither recorded. A scenario ties them. The book of polls must send the PTZ camera to its RELAY's
    ingest — the centre's, or the domain holder's, is exactly what it cannot reach, and a scenario inside one
    site would never act. The gate camera's book of asks names the same relay; the ask goes there and back."""
    from domain.books import Books
    from domain.chain import Relay
    from domain.ingest import Asker
    from domain.scenario import Scenarios
    from domain.shared import SharedSettings, SharedView

    wall = Clock()
    fed = Federation()
    north, _ = make_cluster("north", domain=True)
    east, _ = make_cluster("east")
    fed.add(north); fed.add(east)
    signer = Signer("acme", north.vars, now=wall)
    DomainPublisher(north.vars).publish_keys(signer.tokens.keyset())
    centre = Ingest("north", CENTRE_URLS, keys=lambda: ClusterTrust(north.vars).keyset(), wall=wall)
    centre.announce(north.objects)                                     # there IS an ingest up there: the wrong one
    through = Relay(east.vars, east.objects)                           # all a camera of this site can reach
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
    relay_agent.sync()
    relay = Ingest("east", RELAY_URLS, keys=lambda: ClusterTrust(east.vars).keyset(), wall=wall)
    relay.announce(east.objects)
    SharedSettings(north.vars, north.objects, signer.tokens, wall=wall).edit(lambda s: s.update(scenarios=[
        {"when": {"camera": "SN7002", "kind": "vehicle"}, "then": {"camera": "SN7003", "action": "preset", "arg": 3}}]),
        base_rev=0, by="anna")
    books = Books(Crossings(north.vars, ReadView(fed, wall=wall), wall, issuer=signer.tokens), north.objects)

    def domain_pass():
        for d in cams.values():
            d.publish()
        for a in agents:
            a.sync()                                                   # reports into the relay
        relay_agent.sync()                                            # up in the bundle, and down the relay
        books.pass_once()
        relay_agent.sync()                                            # the new books relayed down
        for a in agents:
            a.sync()

    domain_pass(); domain_pass()

    def site_dial(url):
        if url in RELAY_URLS:
            return relay
        raise Unreachable(f"{url} is beyond the site's network")

    done = []
    ptz = CameraPusher("SN7003", cams["SN7003"].flash, site_dial, clock=wall,
                       perform=lambda action: done.append(action) or "performed")
    e = ptz.entry()
    assert e["polls_only"] and e["cluster"] == "east" and e["ingest"]["urls"] == RELAY_URLS
    assert "asks only" in ptz.pass_once([])["state"]                   # it reached its poll

    asker = Asker("SN7002", cams["SN7002"].flash, site_dial, clock=wall)
    assert [r["cluster"] for r in asker.book()["SN7003"]] == ["east"]
    left = Scenarios("SN7002", SharedView(cams["SN7002"].flash, cams["SN7002"].disk, wall), asker).on_event("vehicle")
    assert [x["state"] for x in left] == ["asked"] and left[0]["ingest"] is relay
    assert ptz.pass_once([])["asks"] == [({"action": "preset", "arg": 3}, "performed")]
    assert asker.outcome("SN7003", left[0]["ask"], left[0]["deadline"]) == "performed"


# -- a scenario between two relays: the road up through one's own relay, by event -------------------------
EAST_URLS = RELAY_URLS
WEST_URLS = ["srt://ingest.west.relay:9000"]
GATE7, PTZ7, YARD7 = "SN7102", "SN7103", "SN7104"    # the gate and a PTZ at an east site; the yard at a west site


def _two_relays(wall):
    from domain.books import Books
    from domain.chain import Relay
    from domain.ingest import Asker
    from domain.scenario import Scenarios
    from domain.shared import SharedSettings, SharedView

    fed = Federation()
    north, _ = make_cluster("north", domain=True)
    east, _ = make_cluster("east")
    west, _ = make_cluster("west")
    for c in (north, east, west):
        fed.add(c)
    signer = Signer("acme", north.vars, now=wall)
    DomainPublisher(north.vars).publish_keys(signer.tokens.keyset())
    ing = {"north": Ingest("north", CENTRE_URLS, keys=lambda: ClusterTrust(north.vars).keyset(), wall=wall),
           "east": Ingest("east", EAST_URLS, keys=lambda: ClusterTrust(east.vars).keyset(), wall=wall),
           "west": Ingest("west", WEST_URLS, keys=lambda: ClusterTrust(west.vars).keyset(), wall=wall)}
    for name, c in (("north", north), ("east", east), ("west", west)):
        ing[name].announce(c.objects)
    cams, agents, relays = {}, [], []
    for relay, serials in (("east", (GATE7, PTZ7)), ("west", (YARD7,))):
        store = east if relay == "east" else west
        through = Relay(store.vars, store.objects)                     # all a camera of that site reaches
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
    for o in relays:
        o.sync()
    SharedSettings(north.vars, north.objects, signer.tokens, wall=wall).edit(lambda s: s.update(scenarios=[
        {"when": {"camera": GATE7, "kind": "vehicle"}, "then": {"camera": YARD7, "action": "preset", "arg": 3}},
        {"when": {"camera": GATE7, "kind": "vehicle"}, "then": {"camera": PTZ7, "action": "preset", "arg": 1}}]),
        base_rev=0, by="anna")
    books = Books(Crossings(north.vars, ReadView(fed, wall=wall), wall, issuer=signer.tokens, centre="north"), north.objects)

    def domain_pass():
        for d in cams.values():
            d.publish()
        for a in agents:
            a.sync()
        for o in relays:
            o.sync()
        books.pass_once()
        for o in relays:
            o.sync()
        for a in agents:
            a.sync()

    domain_pass(); domain_pass()
    centre_up = {"on": True}

    def reach(urls, owner):
        def dial(url):
            if url in urls and (owner != "relay" or centre_up["on"]):
                return next(i for i in ing.values() if url in i.urls)
            raise Unreachable(f"{url} does not answer {owner}")
        return dial

    fwd = {"east": Forwarder("east", ing["east"], east.vars, reach(CENTRE_URLS, "relay")),
           "west": Forwarder("west", ing["west"], west.vars, reach(CENTRE_URLS, "relay"))}
    done = {PTZ7: [], YARD7: []}
    ptz = CameraPusher(PTZ7, cams[PTZ7].flash, reach(EAST_URLS, "site"), clock=wall,
                       perform=lambda a: done[PTZ7].append(a) or "performed")
    yard = CameraPusher(YARD7, cams[YARD7].flash, reach(WEST_URLS, "site"), clock=wall,
                        perform=lambda a: done[YARD7].append(a) or "performed")
    gate = Scenarios(GATE7, SharedView(cams[GATE7].flash, cams[GATE7].disk, wall),
                     Asker(GATE7, cams[GATE7].flash, reach(EAST_URLS, "site"), clock=wall))
    return ing, fwd, ptz, yard, gate, done, centre_up


def test_an_ask_to_another_relay_goes_up_through_ones_own_and_an_ask_inside_the_relay_does_not():
    """The gate camera sees only the east relay. The PTZ camera is in the same relay: its book names the east
    ingest directly, and the ask never leaves the site. The yard camera is behind the west relay: the book
    names the east ingest again, marked UP; the east forwarder takes it to the centre with the relay's own
    token for that pair, the west forwarder carries it down, and the outcome comes back hop by hop."""
    wall = Clock()
    ing, fwd, ptz, yard, gate, done, _ = _two_relays(wall)
    book = gate.asker.book()
    assert [(r["cluster"], r.get("up")) for r in book[PTZ7]] == [("east", None)]      # inside: direct
    assert [(r["cluster"], r.get("up")) for r in book[YARD7]] == [("east", "north")]  # across: up through its own
    assert list(fwd["east"].asks_book()) == [f"{YARD7}|{GATE7}"]                     # the relay may carry that pair
    assert YARD7 in fwd["west"].book()                                 # the centre has a road down to the yard

    left = {x["target"]: x for x in gate.on_event("vehicle")}
    assert {t: (x["state"], x["ingest"]) for t, x in left.items()} == {PTZ7: ("asked", ing["east"]), YARD7: ("asked", ing["east"])}
    assert ptz.pass_once([])["asks"] == [({"action": "preset", "arg": 1}, "performed")]
    assert PTZ7 not in ing["north"].cams                               # the centre never heard of the PTZ's ask

    assert fwd["east"].woken.is_set()                                  # the ask woke the east forwarder
    assert list(fwd["east"].lift().values()) == ["up"]
    fwd["west"].pass_once()                                            # the centre answers west's poll: down it goes
    assert yard.pass_once([])["asks"] == [({"action": "preset", "arg": 3}, "performed")]
    assert fwd["west"].woken.is_set()                                  # the yard's answer woke the west forwarder
    fwd["west"].lift()                                                 # …which answers the centre
    assert list(fwd["east"].lift().values()) == ["performed"]          # …and east takes the outcome back down
    x = left[YARD7]
    assert gate.asker.outcome(YARD7, x["ask"], x["deadline"]) == "performed"
    assert done == {PTZ7: [{"action": "preset", "arg": 1}], YARD7: [{"action": "preset", "arg": 3}]}


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
    assert gate.asker.outcome(YARD7, x["ask"], x["deadline"]) == "expired"
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
            out = gate.asker.outcome(YARD7, x["ask"], x["deadline"])
            _t.sleep(0.005)
        took = _t.monotonic() - t0
    finally:
        stop.set()
        for t in threads + [cam]:
            t.join(timeout=2.0)
    assert out == "performed" and done[YARD7] == [{"action": "preset", "arg": 3}]
    assert took < 0.5, f"took {took:.3f} s: something waited for a timer"


def test_a_torn_announcement_or_book_entry_is_that_ones_trouble_and_the_relay_forwards_on():
    """The eighth review's siblings, left in this module by the М12 pass: the centre's ingest announcement and the
    upstream book's own entries (`publish_upstream`), and the books the relay's agent carried (`Forwarder.book`,
    `asks_book`) were read bare — one torn document raised out of the whole pass: no token to push up re-issued, or no
    camera of the relay forwarded. A torn announcement keeps the road each entry names; a torn entry of the domain's
    book is issued anew; a torn entry the relay carried is the one it read last — each counted once (`BOOKS`)."""
    from domain.agent import UPSTREAM_PATH
    from domain.ingest import ASKS_PATH, BOOKS, INGEST
    wall = Clock()
    north, east, centre, relay, pusher, fwd, dialled, domain_pass = _chain(wall)
    north.objects.put(INGEST, b'{"cluster": "north", "urls": ')          # the centre's announcement, half written
    books = publish_upstream(domain_pass.crossings, "north", lifetime=1.0)   # (a lifetime that asks for a new token)
    assert json.loads(books["east"][SERIAL])["urls"] == CENTRE_URLS       # re-issued, on the road the entry named
    centre.announce(north.objects)
    items, idx = north.vars.get(f"{UPSTREAM_PATH}/east")
    north.vars.put(f"{UPSTREAM_PATH}/east", {**items, SERIAL: "{"}, cas=idx)   # the book's own entry, torn
    books = publish_upstream(domain_pass.crossings, "north")
    assert json.loads(books["east"][SERIAL])["token"] and f"{UPSTREAM_PATH}/east/{SERIAL}" in BOOKS.bad
    before = fwd.book()[SERIAL]
    items, idx = east.vars.get(UPSTREAM_PATH)
    east.vars.put(UPSTREAM_PATH, {**items, SERIAL: '{"urls": ["srt://'}, cas=idx)   # what the relay carried, torn
    assert fwd.book()[SERIAL] == before and f"{UPSTREAM_PATH}/{SERIAL}" in BOOKS.bad
    centre.want(SERIAL, "recorder:centre")
    assert "forwarding" in fwd.pass_once()[SERIAL]                        # the relay forwards on, by the entry read last
    road = json.dumps({"roads": [{"urls": CENTRE_URLS, "token": "t"}]})
    east.vars.put(ASKS_PATH, {"a|b": road, "c|d": "{"}, cas=east.vars.get(ASKS_PATH)[1])
    assert set(fwd.asks_book()) == {"a|b"}                                # never read whole: not a road
    east.vars.put(ASKS_PATH, {"a|b": "[", "c|d": "{"}, cas=east.vars.get(ASKS_PATH)[1])
    assert fwd.asks_book() == {"a|b": json.loads(road)}                   # torn now: the one read last


# -- the ninth review ----------------------------------------------------------------------------------------------------
def test_a_batch_whose_answer_was_lost_just_before_the_centre_restarted_is_counted_as_a_possible_hole():
    """The ninth review, a minor (and the product's sibling E): the centre keeps the batch it handed over until the relay
    says it has it — in memory. The answer to batch 3 was lost on the way down, the centre restarted, and frame 3 went
    with it: nothing anywhere counted it. The relay cannot know whether such a batch was there, but it knows the centre
    restarted — the mark's `boot` changed — and counts that as a possible hole (`holes`, in `stats`), once per restart;
    a pull whose answer is lost with no restart is handed over again and counts nothing."""
    from domain.chain import Forwarder

    def centre():
        ing = Ingest("north", CENTRE_URLS, keys=lambda: {})
        ing._check = lambda *a, **k: {}                                # (the tokens are the other tests')
        ing.subscribe("7", "up:east", maxsize=1000)
        return ing
    at = {"centre": centre()}
    relay = Ingest("east", RELAY_URLS, keys=lambda: {})
    rq = relay.subscribe("7", "recorder:east", maxsize=1000)
    fwd = Forwarder("east", relay, FakeVariables(), lambda url: at["centre"], needs=lambda ref: True)

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
            fwd._pull(ing, "7", {"token": "t"})
        except Unreachable:
            pass
        ing.pull = real
    pull(1); pull(2, lost=True); pull(4)
    assert [f["t"] for f in rq.drain()] == [1, 2, 4] and fwd.stats()["7"]["holes"] == 0   # handed over again: no hole
    pull(5, lost=True)                                                  # batch 5 handed over, its answer lost…
    at["centre"] = centre()                                             # …and the centre restarts
    pull(6); pull(7)
    assert [f["t"] for f in rq.drain()] == [6, 7]                       # 5 is gone with the centre —
    assert fwd.stats()["7"]["holes"] == 1                               # — and counted, once
