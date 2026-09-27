"""Lesson 16 — a camera nobody can reach.

The camera's door is closed for good: no domain, no recorder, no gateway can open a connection to it. It
reaches out — its agent for books and reports (Lesson 10), a long poll to the recording cluster's ingest for
work, a push for media — and recording, live view and backfill all work. The stream token is the domain
signer's; the ingest checks it with the key set its own agent carried.
"""
from cluster.variables import FakeVariables

from domain.agent import ClusterTrust, DomainAgent, DomainPublisher
from domain.crossing import Crossings, resolve
from domain.device import DeviceCluster
from domain.federation import Federation, Unreachable
from domain.gateway import Gateway
from domain.ingest import LINGER, CameraPusher, Ingest, IngestLiveEndpoint, Refused, audience
from domain.readview import ReadView
from domain.signer import Signer
from domain.uplink import member_copy
from tests.conftest import Clock, make_cluster

SERIAL = "SN5001"
URLS = ["srt://srv-1.south:9000", "srt://srv-2.south:9000"]


def _site(wall, down=()):
    from vms.config import REC_SPEC
    from w2cplatform.spec import SpecController
    fed = Federation()
    north, _ = make_cluster("north", domain=True)
    south, _ = make_cluster("south")                                   # the server room that records it
    fed.add(north); fed.add(south)
    signer = Signer("acme", north.vars, now=wall)
    DomainPublisher(north.vars).publish_keys(signer.tokens.keyset())
    room_agent = DomainAgent("south", north.vars, south.vars, now=wall)
    room_agent.sync()                                                  # the room's key set: what the ingest checks with
    ingest = Ingest("south", URLS, keys=lambda: ClusterTrust(south.vars).keyset(), wall=wall)
    ingest.announce(south.objects)
    SpecController(REC_SPEC, south.vars, south.objects, wall=wall).create({"name": SERIAL, "cam": f"ref:{SERIAL}"})

    cam = DeviceCluster(SERIAL, FakeVariables(), wall=wall, pushes=True)
    cam.boot()
    cam.door_open = False                                              # nobody can open a connection to it, ever
    fed.add(member_copy(cam.name, north.objects, wall=wall))
    cam_agent = DomainAgent(cam.name, north.vars, cam.flash, now=wall, domain_objects=north.objects, published=cam.local_objects())
    cam_agent.sync()

    view = ReadView(fed, wall=wall); view.refresh()
    crossings = Crossings(north.vars, view, wall, issuer=signer.tokens)
    crossings.record(SERIAL, on="south")

    def dial(url):                                                     # the camera dialling OUT; only the ingest answers
        if url not in URLS or url in down:
            raise Unreachable(f"{url} did not answer")
        return ingest

    pusher = CameraPusher(SERIAL, cam.flash, dial, card=lambda t0, t1: [("card", t0, t1)], clock=wall)

    def domain_pass():
        view.refresh(); crossings.publish(); crossings.publish_primaries(); cam_agent.sync(); room_agent.sync()

    domain_pass()
    return fed, north, south, signer, ingest, cam, cam_agent, room_agent, crossings, pusher, domain_pass


def test_the_camera_learns_where_to_push_from_its_book_and_the_book_does_not_churn():
    wall = Clock()
    *_, ingest, cam, cam_agent, room_agent, crossings, pusher, domain_pass = _site(wall)
    e = pusher.entry()
    assert e["cluster"] == "south" and e["ingest"]["urls"] == URLS
    ingest.poll(e["ingest"]["token"], SERIAL)                          # the ingest takes the domain's token
    writes = cam.flash.writes
    for _ in range(10):
        wall.advance(30); cam.publish(); domain_pass()
    assert cam.flash.writes == writes                                  # five minutes of passes: the book did not change
    wall.advance(13 * 3600); cam.publish(); domain_pass()
    assert pusher.entry()["ingest"]["token"] != e["ingest"]["token"]  # past half its life: a new token, one write


def test_a_recorder_holding_an_always_recording_gets_the_stream_the_camera_pushes():
    """The recorder wants the stream for ever, so the camera pushes for ever — and it finds the camera the
    way it found any camera of another cluster: in its own cluster's source book, which now says ingest."""
    wall = Clock()
    fed, north, south, signer, ingest, cam, *_rest, pusher, domain_pass = _site(wall)
    src = resolve(south.vars, f"ref:{SERIAL}", wall())
    assert src.live_url == f"ingest://south/{SERIAL}" and src.playback_url is None
    ingest.want(SERIAL, "recorder:r-0")
    q = ingest.subscribe(SERIAL, "recorder:r-0")
    out = pusher.pass_once(["f1", "f2"])
    assert out["pushed"] == 2 and q.drain() == ["f1", "f2"] and ingest.pushing(SERIAL)


def test_live_view_on_demand_the_camera_pushes_only_while_somebody_watches():
    """An event-recorded camera nobody watches pushes nothing. A viewer opens it: the gateway's endpoint is the
    ingest, opening it is wanting the stream, the camera learns on its poll and pushes. The viewer leaves:
    after a short linger, it stops."""
    wall = Clock()
    *_, ingest, cam, cam_agent, room_agent, crossings, pusher, domain_pass = _site(wall)
    assert pusher.pass_once(["f0"])["pushed"] == 0 and "nobody wants" in pusher.state

    ep = IngestLiveEndpoint(ingest, authorise=lambda token, camera: "anna")
    gw = Gateway("gw-1", where=lambda camera: audience("south"), endpoint=lambda w: ep)
    vq = gw.watch(SERIAL, "anna-token", "anna")
    assert pusher.pass_once(["f1", "f2"])["pushed"] == 2
    gw.pump()
    assert vq.drain() == ["f1", "f2"]

    gw.leave(SERIAL, "anna")
    assert pusher.pass_once(["f3"])["pushed"] == 1                     # the linger: a viewer who clicks back
    wall.advance(LINGER + 1)
    assert pusher.pass_once(["f4"])["pushed"] == 0


def test_backfill_and_card_playback_are_ranges_the_camera_uploads_on_request():
    """Nobody can read the card, so the recorder asks and the camera pushes — into the backfill stream, never
    the live one. The same request serves an operator who wants to see what only the card holds."""
    wall = Clock()
    *_, ingest, cam, cam_agent, room_agent, crossings, pusher, domain_pass = _site(wall)
    rid = ingest.request_range(SERIAL, 1000.0, 1600.0)
    assert ingest.answer(SERIAL, rid) is None                          # asked, not answered
    out = pusher.pass_once([])
    assert out["uploaded"] == [(1000.0, 1600.0)] and ingest.landed(SERIAL) == [(1000.0, 1600.0)]
    assert ingest.answer(SERIAL, rid) == [("card", 1000.0, 1600.0)]   # the answer to THAT request, by its id (AD)
    assert pusher.pass_once([])["uploaded"] == []                      # asked once, uploaded once


def test_the_ingest_refuses_a_token_for_another_camera_another_cluster_or_past_its_expiry():
    wall = Clock()
    fed, north, south, signer, ingest, *_ = _site(wall)
    for bad in (signer.tokens.issue("cam-SN9", 3600, now=wall(), aud=audience("south"), ref="SN9"),
                signer.tokens.issue(f"cam-{SERIAL}", 3600, now=wall(), aud=audience("east"), ref=SERIAL)):
        try:
            ingest.poll(bad, SERIAL)
            assert False
        except Refused:
            pass
    old = signer.tokens.issue(f"cam-{SERIAL}", 60, now=wall(), aud=audience("south"), ref=SERIAL)
    wall.advance(3600)
    try:
        ingest.push(old, SERIAL, ["f"])
        assert False
    except Refused as e:
        assert "expired" in str(e)


def test_one_ingest_down_the_camera_dials_the_next():
    wall = Clock()
    *_, ingest, cam, cam_agent, room_agent, crossings, pusher, domain_pass = _site(wall, down=(URLS[0],))
    ingest.want(SERIAL, "recorder:r-0")
    assert pusher.pass_once(["f"])["pushed"] == 1 and pusher.state == f"pushing to {URLS[1]}"


def test_a_frame_carries_its_capture_time_and_the_ingest_moves_it_between_the_clocks_both_ways():
    """Feedback AC. The camera's clock is ninety seconds fast. Its frames arrive stamped with the camera's time;
    the ingest moves them onto the cluster's by what the camera states in every request, and a range asked on
    the cluster's clock reaches the camera on its own — and comes back on the cluster's."""
    wall = Clock()
    fast = Clock(wall() + 90)
    *_, ingest, cam, cam_agent, room_agent, crossings, pusher, domain_pass = _site(wall)
    pusher = CameraPusher(SERIAL, cam.flash, lambda url: ingest, clock=fast,
                          card=lambda t0, t1: [{"t": t0, "k": True}, {"t": t1 - 1}])
    ingest.want(SERIAL, "recorder:r-0")
    q = ingest.subscribe(SERIAL, "recorder:r-0")
    pusher.pass_once([{"t": fast(), "k": True}])
    [f] = q.drain()
    assert abs(f["t"] - wall()) < 1e-6                                 # on the cluster's clock
    rid = ingest.request_range(SERIAL, wall() - 600, wall() - 300)
    assert pusher.pass_once([])["uploaded"] == [(fast() - 600, fast() - 300)]   # on the camera's clock
    assert [round(s["t"] - wall()) for s in ingest.answer(SERIAL, rid)] == [-600, -301]   # and back


def test_the_ring_lives_on_the_camera_the_recorder_gets_it_and_the_viewer_does_not():
    """Feedback AC and AF. Nobody wants the stream, and the camera keeps the last thirty seconds. An event:
    the recorder wants it, and the first push starts with the ring — marked, with its own capture times, so
    the start of the event is not lost to the time the want took. A viewer, opened at the same moment, gets the
    live edge: the ring would be the last half-minute played fast."""
    wall = Clock()
    *_, ingest, cam, cam_agent, room_agent, crossings, pusher, domain_pass = _site(wall)
    pusher = CameraPusher(SERIAL, cam.flash, lambda url: ingest, clock=wall, ring_seconds=30)
    for _ in range(6):                                                 # a minute nobody watches: the ring keeps 30 s
        wall.advance(10); pusher.pass_once([{"t": wall()}])
    ingest.want(SERIAL, "recorder:event")
    rq = ingest.subscribe(SERIAL, "recorder:event")
    vq = ingest.subscribe(SERIAL, "viewer", edge=True)
    wall.advance(1); pusher.pass_once([{"t": wall()}])
    got = rq.drain()
    assert [f.get("ring", False) for f in got] == [True, True, True, True, False]   # 30 s of ring, then live
    assert got[0]["t"] == wall() - 31 and vq.drain() == [{"t": wall()}]


def test_the_long_poll_answers_first_holds_when_nothing_changed_and_wakes_when_a_want_runs_out():
    """Feedback AF: a camera that never polled is answered at once (version -1); the same version again is a
    poll the real ingest holds; a viewer who left wakes it at the end of the linger, not at the end of the poll."""
    wall = Clock()
    *_, ingest, cam, cam_agent, room_agent, crossings, pusher, domain_pass = _site(wall)
    token = pusher.entry()["ingest"]["token"]
    first = ingest.poll(token, SERIAL, version=-1)
    assert "held" not in first and first["push"] is False
    assert ingest.poll(token, SERIAL, version=first["version"]).get("held")
    ingest.want(SERIAL, "anna"); ingest.release(SERIAL, "anna")        # a viewer came and went
    woke = ingest.poll(token, SERIAL, version=first["version"])
    assert "held" not in woke and woke["push"] is True                 # the linger
    wall.advance(LINGER + 0.1)
    lapsed = ingest.poll(token, SERIAL, version=woke["version"])
    assert "held" not in lapsed and lapsed["push"] is False            # woken by the want running out


def test_two_ingests_of_one_cluster_pass_the_stream_to_each_other():
    """Feedback AG. The book lists both ingests of the recording cluster; the camera pushes to the first that
    answers; the recorder holding the recording is on the other server. A want at either counts at both, and the
    ingest with a subscriber and no camera takes the stream from the one that has it. A range asked there is
    answered there."""
    wall = Clock()
    fed, north, south, signer, ingest, cam, *_rest, pusher, domain_pass = _site(wall)
    keys = lambda: ClusterTrust(south.vars).keyset()
    a = Ingest("south", URLS, keys=keys, wall=wall, name=URLS[0], peers=lambda: [b])
    b = Ingest("south", URLS, keys=keys, wall=wall, name=URLS[1], peers=lambda: [a])
    by_url = {URLS[0]: a, URLS[1]: b}
    pusher = CameraPusher(SERIAL, cam.flash, lambda url: by_url[url], clock=wall, card=lambda t0, t1: [("card", t0, t1)])
    b.want(SERIAL, "recorder:srv-2")                                   # the recorder is on the second server
    rq = b.subscribe(SERIAL, "recorder:srv-2")
    assert pusher.pass_once(["x1", "x2"])["pushed"] == 2 and pusher.state == f"pushing to {URLS[0]}"
    b.pump()
    assert rq.drain() == ["x1", "x2"]
    rid = b.request_range(SERIAL, 100.0, 200.0)
    pusher.pass_once([])                                               # asked at b, polled and answered at a
    assert b.answer(SERIAL, rid) == [("card", 100.0, 200.0)]


# -- asks between cameras: a scenario's action, fast, over the long poll ------------------------------------
GATE = "SN5002"                                                        # the gate camera: its event asks the yard camera


def _two(wall):
    from domain.ingest import Asker, publish_asks
    fed, north, south, signer, ingest, cam, cam_agent, room_agent, crossings, pusher, domain_pass = _site(wall)
    gate = DeviceCluster(GATE, FakeVariables(), wall=wall, pushes=True)
    gate.boot(); gate.door_open = False
    fed.add(member_copy(gate.name, north.objects, wall=wall))
    gate_agent = DomainAgent(gate.name, north.vars, gate.flash, now=wall, domain_objects=north.objects,
                             published=gate.local_objects())
    gate_agent.sync()
    done = []

    def perform(action):
        if action.get("preset") not in (1, 2, 3):
            return f"refused: no preset {action.get('preset')}"
        done.append(action)
        return "performed"

    pusher.perform = perform
    scenarios = [{"trigger": GATE, "target": SERIAL, "actions": [{"preset": 3}, {"preset": 9}]}]

    def asks_pass():
        domain_pass(); publish_asks(crossings, scenarios); gate_agent.sync()

    asks_pass()
    asker = Asker(GATE, gate.flash, lambda url: ingest if url in URLS else (_ for _ in ()).throw(Unreachable(url)),
                  clock=wall)
    return ingest, pusher, asker, done, asks_pass, signer, crossings, north


def test_a_scenario_between_two_unreachable_cameras_acts_within_one_poll():
    """"Vehicle at the gate: the yard camera to preset 3." Neither camera can be dialled. The gate camera leaves
    the ask at the ingest that records the yard camera — its book says where, with a token to ask — and the
    ask wakes the yard camera's held poll: done on the next answer, not on an agent's pass."""
    wall = Clock()
    ingest, pusher, asker, done, *_ = _two(wall)
    book = asker.book()
    assert [r["urls"] for r in book[SERIAL]] == [URLS]              # one road: the room that records it
    e = pusher.entry()["ingest"]
    held = ingest.poll(e["token"], SERIAL, version=ingest.poll(e["token"], SERIAL)["version"])
    assert held.get("held")                                            # the yard camera is waiting, nothing new
    ing, aid = asker.ask(SERIAL, {"preset": 3}, within=10)
    woken = ingest.poll(e["token"], SERIAL, version=held["version"])
    assert not woken.get("held") and [a["action"] for a in woken["asks"].values()] == [{"preset": 3}]
    out = pusher.pass_once([])
    assert out["asks"] == [({"preset": 3}, "performed")] and done == [{"preset": 3}]
    assert ing.ask_outcome(SERIAL, aid) == "performed"
    assert pusher.pass_once([])["asks"] == []                          # done once


def test_an_ask_dies_at_its_deadline_and_a_camera_that_was_off_never_does_it_late():
    """Unlike an edit (Lesson 9), an ask is not kept: the yard camera was off for a minute, the ask said "within
    ten seconds" — when it polls again there is nothing, and the gate camera reads "expired"."""
    wall = Clock()
    ingest, pusher, asker, done, *_ = _two(wall)
    ing, aid = asker.ask(SERIAL, {"preset": 3}, within=10)
    wall.advance(60)                                                   # the yard camera was off
    assert pusher.pass_once([])["asks"] == [] and done == []
    assert ing.ask_outcome(SERIAL, aid) == "expired"


def test_a_refused_action_is_answered_and_only_a_scenario_gives_the_right_to_ask():
    wall = Clock()
    ingest, pusher, asker, done, asks_pass, signer, crossings, north = _two(wall)
    ing, aid = asker.ask(SERIAL, {"preset": 9}, within=10)
    pusher.pass_once([])
    assert ing.ask_outcome(SERIAL, aid) == "refused: no preset 9" and done == []
    try:
        asker.ask("SN9999", {"preset": 1}, within=10)                  # no scenario ties them: no book entry
        assert False
    except Refused:
        pass
    push = pusher.entry()["ingest"]["token"]                           # a push token is not a token to ask
    for bad in (push, signer.tokens.issue(GATE, 60, now=wall(), aud=audience("south"), ask="SN9999")):
        try:
            ingest.ask(bad, SERIAL, {"preset": 1}, wall() + 10)
            assert False
        except Refused:
            pass


# -- end to end: the scenario from the shared document to the camera that acts ------------------------------
PTZ = "SN5003"                                                         # a PTZ camera kept for live view: nobody records it
NORTH_URLS = ["srt://ingest.north:9000"]


def _scenario_site(wall, scenarios):
    from domain.books import Books
    from domain.ingest import Asker
    from domain.scenario import Scenarios
    from domain.shared import SharedSettings, SharedView
    fed, north, south, signer, ingest, cam, cam_agent, room_agent, crossings, pusher, _ = _site(wall)
    home = Ingest("north", NORTH_URLS, keys=lambda: ClusterTrust(north.vars).keyset(), wall=wall)
    home.announce(north.objects)                                       # the domain's cluster: every camera reaches it

    def member(serial):
        d = DeviceCluster(serial, FakeVariables(), wall=wall, pushes=True)
        d.boot(); d.door_open = False
        fed.add(member_copy(d.name, north.objects, wall=wall))
        a = DomainAgent(d.name, north.vars, d.flash, now=wall, domain_objects=north.objects, cluster_objects=d.disk,
                        published=d.local_objects())
        return d, a

    gate, gate_agent = member(GATE)
    ptz, ptz_agent = member(PTZ)
    shared = SharedSettings(north.vars, north.objects, signer.tokens, wall=wall)
    shared.edit(lambda s: s.update(scenarios=scenarios), base_rev=0, by="anna")
    books = Books(crossings, north.objects)
    agents = (cam_agent, room_agent, gate_agent, ptz_agent)

    def domain_pass():
        for d in (cam, gate, ptz):
            d.publish()
        for a in agents:
            a.sync()                                                   # reports up
        books.pass_once()                                              # the signer's pass: every book
        for a in agents:
            a.sync()                                                   # books down

    domain_pass()
    ingests = {u: ingest for u in URLS} | {u: home for u in NORTH_URLS}

    def dial(url):
        if url not in ingests:
            raise Unreachable(f"{url} did not answer")
        return ingests[url]

    done = {SERIAL: [], PTZ: []}
    pusher.perform = lambda action: done[SERIAL].append(action) or "performed"
    ptz_pusher = CameraPusher(PTZ, ptz.flash, dial, clock=wall, perform=lambda action: done[PTZ].append(action) or "performed")
    gate_scenarios = Scenarios(GATE, SharedView(gate.flash, gate.disk, wall), Asker(GATE, gate.flash, dial, clock=wall))
    return (shared, books, domain_pass, gate, ptz, home, ingest, pusher, ptz_pusher, gate_scenarios, done)


SCENARIOS = [{"when": {"camera": GATE, "kind": "vehicle"}, "then": {"camera": PTZ, "action": "preset", "arg": 3}},
             {"when": {"camera": GATE, "kind": "vehicle"}, "then": {"camera": SERIAL, "action": "preset", "arg": 1, "within": 10}}]


def test_a_scenario_in_the_shared_document_acts_on_two_cameras_one_recorded_and_one_not():
    """The operator writes two scenarios into the shared document. The domain's pass over the books makes the
    gate camera a trigger with two targets: the yard camera, at the room that records it, and the PTZ camera
    nobody records — at the domain's own ingest, which the domain gave it to poll, because otherwise an ask
    for it would have nowhere to wait. The gate camera sees a vehicle; both act, each on its next poll."""
    wall = Clock()
    shared, books, domain_pass, gate, ptz, home, ingest, pusher, ptz_pusher, gate_scenarios, done = _scenario_site(wall, SCENARIOS)
    assert ptz_pusher.entry()["polls_only"] and ptz_pusher.entry()["ingest"]["urls"] == NORTH_URLS
    assert ptz_pusher.pass_once(["f"])["pushed"] == 0 and "asks only" in ptz_pusher.state   # never told to push

    assert gate_scenarios.on_event("motion") == []                    # no scenario for that event
    left = gate_scenarios.on_event("vehicle")
    assert [(x["target"], x["state"]) for x in left] == [(PTZ, "asked"), (SERIAL, "asked")]
    assert ptz_pusher.pass_once([])["asks"] == [({"action": "preset", "arg": 3}, "performed")]
    assert pusher.pass_once([])["asks"] == [({"action": "preset", "arg": 1}, "performed")]
    assert done == {PTZ: [{"action": "preset", "arg": 3}], SERIAL: [{"action": "preset", "arg": 1}]}
    by_target = {x["target"]: x for x in left}
    assert by_target[PTZ]["ingest"] is home and home.ask_outcome(PTZ, by_target[PTZ]["ask"]) == "performed"
    assert ingest.ask_outcome(SERIAL, by_target[SERIAL]["ask"]) == "performed"


def test_the_books_do_not_churn_and_a_scenario_taken_out_takes_the_right_with_it():
    wall = Clock()
    shared, books, domain_pass, gate, ptz, *_rest, gate_scenarios, done = _scenario_site(wall, SCENARIOS)
    writes = (gate.flash.writes, ptz.flash.writes)
    for _ in range(10):
        wall.advance(30); domain_pass()
    assert (gate.flash.writes, ptz.flash.writes) == writes            # five minutes of passes: no book rewritten

    rev = shared.current()[0]["rev"]
    shared.edit(lambda s: s.update(scenarios=[]), base_rev=rev, by="anna")
    domain_pass()
    assert gate_scenarios.on_event("vehicle") == []                   # the document no longer says so…
    assert gate_scenarios.asker.book() == {}                           # …and the book no longer lets it
    try:
        gate_scenarios.asker.ask(PTZ, {"action": "preset", "arg": 3}, within=10)
        assert False
    except Refused:
        pass


# -- asks under pressure: the token names the action, one gust is one ask, and memory is not a log -----------
def test_the_token_names_the_actions_and_one_camera_cannot_flood_an_ingest():
    """The scenario says preset 3 and preset 9: the token to ask says so too, and preset 4 is refused at the
    ingest — before the yard camera hears of it. A token for twenty presets still holds at most sixteen live
    asks at one ingest: a ceiling, not a queue."""
    from domain.ingest import MAX_LIVE_ASKS
    wall = Clock()
    ingest, pusher, asker, done, asks_pass, signer, crossings, north = _two(wall)
    try:
        asker.ask(SERIAL, {"preset": 4}, within=10)
        assert False
    except Refused as e:
        assert "not {'preset': 4}" in str(e)
    wide = signer.tokens.issue(GATE, 600, now=wall(), aud=audience("south"), ask=SERIAL, by=GATE,
                               acts=[{"preset": i} for i in range(20)])
    for i in range(MAX_LIVE_ASKS):
        ingest.ask(wide, SERIAL, {"preset": i}, wall() + 30)
    try:
        ingest.ask(wide, SERIAL, {"preset": 19}, wall() + 30)
        assert False
    except Refused as e:
        assert "ceiling" in str(e)


def test_twenty_events_in_a_minute_are_six_asks_and_identical_live_asks_are_one():
    """Leaves in the wind: the gate camera sees a "vehicle" every three seconds for a minute. The scenario's
    ceiling (six a minute, the product's default) lets six through; the ingest folds an ask identical to one
    still alive into that one: while the PTZ camera is between polls, one ask waits for it, not six."""
    wall = Clock()
    shared, books, domain_pass, gate, ptz, home, ingest, pusher, ptz_pusher, gate_scenarios, done = _scenario_site(wall, SCENARIOS)
    seen = []
    for i in range(20):
        seen += gate_scenarios.on_event("vehicle")
        if i == 5:                                                     # the sixth, fifteen seconds in
            assert len(home.cams[PTZ].asks) == 1
        wall.advance(3)
    for target in (PTZ, SERIAL):
        mine = [x for x in seen if x["target"] == target]
        assert sum(x["state"] == "asked" for x in mine) == 6
        assert sum(x["state"].startswith("over its ceiling of 6/min") for x in mine) == 14
    assert len({x["ask"] for x in seen if x["target"] == PTZ and "ask" in x}) == 1       # within 30 s: one ask
    assert len({x["ask"] for x in seen if x["target"] == SERIAL and "ask" in x}) == 2    # within 10 s: two


def test_an_ingest_that_restarted_knows_nothing_and_the_asker_says_so_after_the_deadline():
    """Asks live in the ingest's memory. The ingest restarts with one in it: the yard camera never hears of it,
    and the gate camera, asking the roads again, is told nothing — until the deadline and a grace have passed,
    when "nobody knows" becomes an answer: lost, not late. Outcomes that were answered are kept a quarter of an
    hour for the asker, then forgotten."""
    from domain.ingest import ANSWER_GRACE, REMEMBER
    wall = Clock()
    ingest, pusher, asker, done, *_ = _two(wall)
    ing, aid = asker.ask(SERIAL, {"preset": 3}, within=10)
    deadline = wall() + 10
    fresh = Ingest("south", URLS, keys=ingest.keys, wall=wall)         # the same addresses, a new process
    asker.dial = pusher.dial = lambda url: fresh
    assert pusher.pass_once([])["asks"] == [] and done == []
    assert asker.outcome(SERIAL, aid, deadline) is None                # not yet: it may still come
    wall.advance(10 + ANSWER_GRACE + 1)
    assert asker.outcome(SERIAL, aid, deadline).startswith("unknown")

    ing, aid = asker.ask(SERIAL, {"preset": 3}, within=10)
    pusher.pass_once([])
    assert asker.outcome(SERIAL, aid, wall() + 10) == "performed"
    wall.advance(REMEMBER + 1)
    pusher.pass_once([])                                               # a poll, and the ingest forgets what it kept
    assert fresh.ask_outcome(SERIAL, aid) is None


# -- cameras only: asks through the domain camera, and after it moves -----------------------------------------
def test_cameras_only_asks_go_through_the_domain_camera_and_follow_it_when_the_domain_moves():
    """No server: the domain runs on SN0 (Lesson 15), and SN0 runs a light ingest — polls and asks, no streams.
    Every camera polls it, as it takes everything else from it. The gate camera SN1 asks the PTZ camera SN2
    through it. SN0 dies: asks stop, like edits of the shared settings — nothing to wait for, "not asked".
    The operator re-hosts on SN3; its first pass over the books names its own ingest, the agents carry the
    books home, and the same scenario acts again. The shared document comes back with the domain, from a
    member's copy: the book of asks is built from its scenarios."""
    from domain.books import Books
    from domain.ingest import Asker
    from domain.scenario import Scenarios
    from domain.shared import SharedSettings, SharedView
    from domain.term import DomainHost, rehost
    from tests.test_lesson15_domain_of_one import _agent, _objects

    wall = Clock()
    fed, devices = Federation(), {}
    for i in range(4):
        d = DeviceCluster(f"SN{i}", FakeVariables(), wall=wall, pushes=True)
        d.boot()
        devices[d.name] = d
        fed.add(d.cluster(domain=i == 0))
    home = fed.clusters["cam-SN0"].vars
    signer = Signer("acme", home, now=wall)
    offline = signer.backup()                                          # Lesson 7: the key, kept beyond the host
    DomainPublisher(home).publish_keys(signer.tokens.keyset())
    host = DomainHost(fed, "cam-SN0", signer, term=1, wall=wall)
    host.claim()
    SharedSettings(home, devices["cam-SN0"].disk_door(), signer.tokens, wall=wall).edit(lambda s: s.update(scenarios=[
        {"when": {"camera": "SN1", "kind": "vehicle"}, "then": {"camera": "SN2", "action": "preset", "arg": 3}}]),
        base_rev=0, by="anna")

    urls, ingests = {"cam-SN0": ["srt://sn0.site:9000"], "cam-SN3": ["srt://sn3.site:9000"]}, {}

    def light_ingest(name, vars_):                                     # on the domain camera: asks only
        ingests[name] = Ingest(name, urls[name], keys=lambda: ClusterTrust(vars_).keyset(), wall=wall)
        ingests[name].announce(fed.clusters[name].objects)

    def dial(url):
        for name, i in ingests.items():
            if url in urls[name] and devices[name].door_open:
                return i
        raise Unreachable(f"{url} did not answer")

    def settle(host_name, issuer):                                     # the host's pass over the books, agents both sides
        live = [n for n in devices if n != host_name and devices[n].door_open]
        agents = [_agent(fed, devices, n, host_name, wall) for n in live]
        books = Books(Crossings(fed.clusters[host_name].vars, ReadView(fed, wall=wall), wall, issuer=issuer),
                      devices[host_name].disk_door())
        for n in live:
            devices[n].publish()
        for a in agents:
            a.sync()
        books.pass_once()
        for a in agents:
            a.sync()

    light_ingest("cam-SN0", home)
    settle("cam-SN0", signer.tokens)
    done = []
    ptz = CameraPusher("SN2", devices["cam-SN2"].flash, dial, clock=wall, perform=lambda a: done.append(a) or "performed")
    gate = Scenarios("SN1", SharedView(devices["cam-SN1"].flash, devices["cam-SN1"].disk, wall),
                     Asker("SN1", devices["cam-SN1"].flash, dial, clock=wall))
    assert ptz.entry()["cluster"] == "cam-SN0" and "asks only" in ptz.pass_once([])["state"]
    [x] = gate.on_event("vehicle")
    assert x["state"] == "asked" and x["ingest"] is ingests["cam-SN0"]
    assert ptz.pass_once([])["asks"] == [({"action": "preset", "arg": 3}, "performed")]

    host.backup(["cam-SN1", "cam-SN3"], devices["cam-SN0"].disk_door())
    for n in ("cam-SN1", "cam-SN3"):
        _agent(fed, devices, n, "cam-SN0", wall).sync()               # the backup, carried
    devices["cam-SN0"].power_off()                                     # the domain camera is gone
    wall.advance(15)
    [x] = gate.on_event("vehicle")
    assert x["state"] == "no ingest answered: not asked"               # stopped, with the rest of the domain

    new, report = rehost(fed, "cam-SN3", offline, "acme", _objects(devices), wall)
    assert report["shared_from"] == "cam-SN3"                          # the document, from the new host's own copy
    light_ingest("cam-SN3", new.vars)
    settle("cam-SN3", new.signer.tokens)
    assert ptz.entry()["cluster"] == "cam-SN3" and [r["cluster"] for r in gate.asker.book()["SN2"]] == ["cam-SN3"]
    wall.advance(15)
    [x] = gate.on_event("vehicle")
    assert x["state"] == "asked" and x["ingest"] is ingests["cam-SN3"]
    assert ptz.pass_once([])["asks"] == [({"action": "preset", "arg": 3}, "performed")]
    assert len(done) == 2
