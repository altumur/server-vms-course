"""What the domain reads of others — other clusters, relays, signers, members' reports, peers — is «did not answer»
or «refused», counted and named, and never an exception that stops more than its own item (the review's eighth
pass, part 4: the relay's bundle, `RecursionError`, kept edits, grants, asks, the signer's loop, the relay's age mark,
a name that is a number; and the open rest of the seventh: the trust readers, the agent's pass, the books' steps,
`identity.users`, the signer's start)."""
import json
import logging
import threading
import time

from cluster.variables import FakeVariables

from domain.agent import ClusterTrust, DomainAgent, DomainPublisher, KEYS_PATH, REVOKED_PATH, run
from domain.books import Books
from domain.chain import BUNDLE, MEMBER_SHARE, BundleView, Relay, bundle, say_seen, RELAY_SEEN
from domain.crossing import Crossings
from domain.device import DeviceCluster
from domain.federation import MEMBER_OBJECTS, DomainDirectory, Federation, Unreachable
from domain.grants import DOMAIN_GRANTS, BadName, Grant, domain_may, grants_from_items, grants_to_items, set_domain_grants
from domain.identity import IdentityStore
from domain.ingest import ASK_DEADLINE_MAX, MAX_LIVE_ASKS, Ingest, Refused, audience
from domain.pending import OUTCOMES_PATH, PendingEdits
from domain.readview import ReadView
from domain.signer import Signer
from domain.steps import Steps
from domain.tokens import RevocationList
from domain.uplink import base, member_copy, page, report
from tests.conftest import Clock, make_cluster, snapshot

SERIAL = "SN7001"


def _relay_domain(wall):
    """north holds the domain and has a camera of its own (101); east is a relay; a camera that reaches only east
    reports through it — its report travels in east's bundle."""
    fed = Federation()
    north, _ = make_cluster("north", domain=True)
    east, _ = make_cluster("east")
    fed.add(north); fed.add(east)
    snapshot(north, {101: ("w-0", "srv-1")}, ts=wall())
    snapshot(east, {201: ("w-0", "srv-2")}, ts=wall())
    signer = Signer("acme", north.vars, now=wall)
    DomainPublisher(north.vars).publish_keys(signer.tokens.keyset())
    cam = DeviceCluster(SERIAL, FakeVariables(), wall=wall, pushes=True)
    cam.boot(); cam.door_open = False
    fed.add(member_copy(cam.name, north.objects, wall=wall, via="east"))
    relay_agent = DomainAgent("east", north.vars, east.vars, now=wall, domain_objects=north.objects,
                              bundle_store=east.objects, bundle_members=[cam.name], relay_members=[cam.name])
    through = Relay(east.vars, east.objects)
    cam_agent = DomainAgent(cam.name, through.vars, cam.flash, now=wall, domain_objects=through.objects,
                            published=cam.local_objects())
    relay_agent.sync(); cam_agent.sync(); relay_agent.sync()
    return fed, north, east, cam, signer, cam_agent


class _Console:
    def __init__(self):
        self.edits = []

    def update_camera(self, camera, fields, subject):
        self.edits.append((camera, fields))
        return {"ok": True}


def test_a_torn_relay_bundle_is_its_members_silence_and_the_rest_of_the_domain_is_answered_and_its_books_written():
    """The blocker of part 4, reproduced: a torn `domain/members/<relay>/bundle` raised `JSONDecodeError` out of every
    read of a member behind that relay — `DomainDirectory.where` scans every cluster, so `/api/where` and every edit
    through the domain failed for EVERY camera of the domain, and the pass over the books raised (the signer's loop
    swallowed it; stream tokens stopped being re-issued). Now the bundle is read through the members' reader: the
    members behind the relay did not answer — named, with why, counted once — and the rest is answered and written."""
    from domain.api import ConsoleAPI
    wall = Clock(10_000.0)
    fed, north, east, cam, signer, _ = _relay_domain(wall)
    view = ReadView(fed, wall=wall); view.refresh()
    assert view.list()["complete"]
    north.objects.put(base("east") + BUNDLE, b'{"cam-SN7001": {"reported": "{\\"ts\\": ')     # half a write
    before = MEMBER_OBJECTS.counts.get("east", 0)

    d = DomainDirectory(fed, wall=wall)
    a = d.where("101")                                                  # a camera of north: raised before
    assert a.found and a.cluster == "north" and a.unreachable == [cam.name]
    console = _Console()
    api = ConsoleAPI(d, lambda name: console)
    assert api.update_camera("101", {"name": "lobby"}, "k1")["cluster"] == "north" and console.edits

    books = Books(Crossings(north.vars, view, wall, issuer=signer.tokens), north.objects)
    for _ in range(2):
        wall.advance(5); out = books.pass_once()
    assert out["failing"] == [] and {"sources", "primaries", "poll", "asks"} <= set(out)
    page_ = view.list()
    assert page_["clusters"][cam.name] == "unreachable" and "bundle cannot be read" in page_["why"][cam.name]
    assert MEMBER_OBJECTS.counts.get("east", 0) == before + 1           # once, not once per read or per pass


def test_a_relay_of_an_older_build_whose_bundle_is_a_list_is_refused_by_name_and_shown():
    """The coordinator's decision on the review's question: a bundle that is a list — what an older relay wrote — is
    not parsed as a list; it is refused with a plain reason ("runs an older build; update it"), counted, and shown with
    each member behind that relay."""
    wall = Clock(10_000.0)
    fed, north, east, cam, *_ = _relay_domain(wall)
    north.objects.put(base("east") + BUNDLE, json.dumps([["cam-SN7001", {}]]).encode())
    view = ReadView(fed, wall=wall); view.refresh()
    why = view.list()["why"][cam.name]
    assert "relay east runs an older build" in why and "update it" in why
    assert "east/bundle" in MEMBER_OBJECTS.bad
    try:
        BundleView("east", north.objects).get(base(cam.name) + "reported"); raise AssertionError("must refuse")
    except Unreachable as e:
        assert "older build" in str(e)


def test_one_record_of_a_bundle_is_that_records_and_one_member_over_its_share_is_left_out_with_why():
    """Two siblings the product found: one record that does not parse rejected its relay's whole bundle; and a bundle
    bounded only as a whole let one large member crowd out the others. A record that is not a string is left out,
    counted, the member's other records read; a member whose report is over `MEMBER_SHARE` is not carried, and the
    bundle says why — the domain names it with that member, and the other member is carried whole."""
    relay = make_cluster("relay")[0].objects
    store = make_cluster("centre")[0].objects
    relay.put(base("cam-A") + "reported", b'{"ts": 1, "seq": 1}')
    relay.put(base("cam-A") + "o/vms/snapshot/w", b"x" * (MEMBER_SHARE + 1))
    relay.put(base("cam-B") + "reported", b'{"ts": 1, "seq": 1}')
    bundle("relay", ["cam-A", "cam-B"], relay, store)
    view = BundleView("relay", store)
    assert view.get(base("cam-B") + "reported") == b'{"ts": 1, "seq": 1}'
    try:
        view.get(base("cam-A") + "reported"); raise AssertionError("must say why")
    except Unreachable as e:
        assert "over the" in str(e) and "carried the others" in str(e)
    doc = json.loads(store.get(base("relay") + BUNDLE))
    doc["cam-B"]["o/vms/heartbeats/w"] = 42                             # one record that is not a string
    store.put(base("relay") + BUNDLE, json.dumps(doc).encode())
    assert view.get(base("cam-B") + "reported") == b'{"ts": 1, "seq": 1}'
    assert view.list(base("cam-B") + "o/") == [] and "relay/bundle#cam-B/o/vms/heartbeats/w" in MEMBER_OBJECTS.bad


def test_a_member_behind_a_relay_whose_bundle_is_torn_is_read_by_its_own_report_when_it_has_one():
    """A member placed behind a relay is read from the bundle AND from its own direct report (`NewerRoad`). A torn
    bundle raised out of the choice between the two — the member was silent with a good report of its own. The road
    that cannot be read is no road this pass; the other is read."""
    wall = Clock(10_000.0)
    fed, north, east, cam, *_ = _relay_domain(wall)
    report(cam.name, cam.flash, cam.local_objects(), north.objects, wall())        # the camera reached the centre itself
    north.objects.put(base("east") + BUNDLE, b"{")
    view = ReadView(fed, wall=wall); view.refresh()
    assert view.list()["clusters"][cam.name] == "ok"
    assert [r["ref"] for r in view.list()["rows"] if r["cluster"] == cam.name] == [SERIAL]


def test_json_nested_too_deep_is_a_garbled_object_and_not_a_frozen_view():
    """`RecursionError` was not one of the platform's parse errors (the review's eighth pass, major): a member's
    heartbeat or shard nested deeper than the parser goes raised it out of the read view's pass and out of
    `DomainDirectory.where` — the domain's view froze again, for every cluster. It is a parse error now
    (`rows.PARSE_ERRORS`): the object is skipped and counted, the rest is read. (Python 3.9 gives up at ten thousand
    levels; 3.14 at some two hundred thousand.)"""
    from w2cplatform.rows import PARSE_ERRORS, Table
    deep = b"[" * 300_000 + b"]" * 300_000
    assert RecursionError in PARSE_ERRORS and Table("deep", "test").read("k", lambda: json.loads(deep), "none") == "none"
    wall = Clock(10_000.0)
    fed, north, east, cam, *_ = _relay_domain(wall)
    east.objects.put("vms/heartbeats/w-9", deep)
    east.objects.put("vms/snapshot/w-9", deep)
    view = ReadView(fed, wall=wall); view.refresh()
    assert view.list()["clusters"]["east"] == "ok" and view.passes == 1
    assert DomainDirectory(fed, wall=wall).where("201").cluster == "east"


def test_one_members_unparsable_outcome_leaves_the_other_members_edits_reconciled():
    """`PendingEdits.collect` read each member's outcomes whole: `{"cam1": "applied"}` from one member (not JSON) raised
    on every pass, and the members after it were never reconciled — an applied edit stayed "waiting". Each item is
    read alone now, each member in its own try; and an item of the domain's own row that does not parse is kept as
    it was by a write about another camera."""
    fed = Federation()
    north, _ = make_cluster("north", domain=True); a, _ = make_cluster("cam-A"); b, _ = make_cluster("cam-B")
    for c in (north, a, b):
        fed.add(c)
    pending = PendingEdits(north.vars, wall=Clock())
    pending.add("cam-A", "1", {"name": "x"}, {"name": "old"}, "anna")
    e = pending.add("cam-B", "1", {"name": "y"}, {"name": "old"}, "anna")
    a.vars.put(OUTCOMES_PATH, {"1": "applied"})
    b.vars.put(OUTCOMES_PATH, {"1": json.dumps({"rev": e["rev"], "applied": ["name"]})})
    pending.collect(fed); pending.collect(fed)
    assert pending.of("cam-B") == {} and "1" in pending.of("cam-A")
    assert "cam-A/domain/outcomes#1" in MEMBER_OBJECTS.bad
    items, idx = north.vars.get("domain/pending/cam-A")
    north.vars.put("domain/pending/cam-A", {**items, "9": "{torn"}, cas=idx)
    pending.add("cam-A", "2", {"name": "z"}, {"name": "old"}, "anna")
    assert north.vars.get("domain/pending/cam-A")[0]["9"] == "{torn"                # not dropped by a write about camera 2


def test_a_pipe_in_a_name_is_refused_where_it_is_made_and_a_stored_one_closes_no_door():
    """`|` in a user's name split a grant into four: every grant of the row went with it, the domain's door answered
    500 to everyone, the admin included, and the command that mends grants raised the same way. The coordinator's
    decision: `|`, `"` and control characters are not allowed in a user's name — refused where a user is made and
    wherever a grant is written. A row that holds one anyway is read item by item: that item is not a grant, counted
    once; the others are read; and the mending command writes the row without it."""
    from domain.agent import GRANTS_PATH
    wall = Clock()
    north, _ = make_cluster("north", domain=True)
    ids = IdentityStore(Signer("acme", north.vars, now=wall), north.vars, north.objects, now=wall)
    for bad in ("acme|ivan", 'say"hi', "two\nlines", "tab\tbed"):
        for make in (lambda u: ids.create_local(u, "pw", []), lambda u: ids.create_federated(u, "sub", [])):
            try:
                make(bad); raise AssertionError(f"{bad!r} must be refused")
            except BadName:
                pass
        try:
            grants_to_items([Grant(bad, "view", None, 0.0)]); raise AssertionError("must refuse")
        except BadName:
            pass
    try:
        grants_to_items([Grant("anna", "view", None, 0.0, labels=("floor,1",))]); raise AssertionError("must refuse")
    except BadName:
        pass
    north.vars.put(DOMAIN_GRANTS, {"root|admin|": "0.0", "acme|ivan|view|": "0.0", "anna|view|": "nan"})
    for _ in range(2):
        assert domain_may(north.vars, "root", "admin", wall())
    assert not domain_may(north.vars, "anna", "view", wall())             # `nan` never lapsed: not a grant
    assert {f"{DOMAIN_GRANTS}#acme|ivan|view|", f"{DOMAIN_GRANTS}#anna|view|"} <= {k for k in __import__(
        "domain.grants", fromlist=["GRANTS"]).GRANTS.bad}
    have = grants_from_items(north.vars.get(DOMAIN_GRANTS)[0], DOMAIN_GRANTS)
    set_domain_grants(north.vars, have + [Grant("anna", "view", None, 0.0)], wall())   # what `python -m domain.grants` does
    assert sorted(north.vars.get(DOMAIN_GRANTS)[0]) == ["anna|view|", "root|admin|"]
    south, _ = make_cluster("south")
    south.vars.put(GRANTS_PATH, {"anna|edit|7": str(wall() + 60), "x|y|z|w": "1"})
    assert [(g.subject, g.camera) for g in ClusterTrust(south.vars).grants()] == [("anna", 7)]


def test_an_ask_whose_deadline_or_camera_clock_is_not_a_number_is_refused_and_the_ceiling_holds():
    """A deadline of `nan` passed every check and failed every comparison: never counted against `MAX_LIVE_ASKS`,
    never expired — two thousand asks at a ceiling of sixteen. A deadline or a camera clock that is not a finite
    number is refused, so is a deadline further ahead than `ASK_DEADLINE_MAX` (the product: `within` had no bound),
    and the ceiling counts what is left."""
    wall = Clock(10_000.0)
    south, _ = make_cluster("south")
    signer = Signer("acme", south.vars, now=wall)
    DomainPublisher(south.vars).publish_keys(signer.tokens.keyset())
    ing = Ingest("south", ["srt://south:9000"], keys=lambda: ClusterTrust(south.vars).keyset(), wall=wall)
    acts = [{"action": "preset", "arg": i} for i in range(40)]
    token = signer.tokens.issue("cam-GATE", 3600, now=wall(), aud=audience("south"), ask="SN5", by="GATE", acts=acts, kind="ask")
    for deadline, camera_now in ((float("nan"), None), (float("inf"), None), ("soon", None),
                                 (wall() + ASK_DEADLINE_MAX + 60, None), (wall() + 10, float("nan"))):
        for i in range(3):
            try:
                ing.ask(token, "SN5", acts[i], deadline, camera_now=camera_now); raise AssertionError("must refuse")
            except Refused:
                pass
    assert sum(len(c.asks) for c in ing.cams.values()) == 0
    for i in range(MAX_LIVE_ASKS):
        ing.ask(token, "SN5", acts[i], wall() + 30)
    try:
        ing.ask(token, "SN5", acts[MAX_LIVE_ASKS], wall() + 30); raise AssertionError("the ceiling must hold")
    except Refused as e:
        assert "ceiling" in str(e)
    try:
        ing.poll(signer.tokens.issue("cam-SN5", 60, now=wall(), aud=audience("south"), ref="SN5", kind="stream"), "SN5",
                 camera_now=float("nan")); raise AssertionError("a camera clock of nan must be refused")
    except Refused:
        pass


def test_the_signers_loop_runs_each_step_and_says_the_one_that_failed_once():
    """The signer's loop was `except Exception: pass` (the review's eighth pass, major): the blocker's books stopped in
    silence, and a failed publication of the identity set skipped the pruning behind it. Each is a step of its own now:
    the one that raises is logged once until it works again, counted, named on `/healthz`; the others run."""
    from domain.signer_service import signer_steps
    said, ran = [], []

    class Catch(logging.Handler):
        def emit(self, record):
            said.append(record.getMessage())

    class Ids:
        def publish(self):
            raise ValueError("a torn object")

    class Revoked:
        def prune(self, now):
            ran.append("pruned")

    class BooksStub:
        def pass_once(self):
            ran.append("books")

    log = logging.getLogger("test.signer"); h = Catch(); log.addHandler(h)
    try:
        loop = Steps("domain signer", 5.0, log)
        for _ in range(3):
            loop.run(*signer_steps(Ids(), Revoked(), BooksStub()))
    finally:
        log.removeHandler(h)
    assert ran == ["pruned", "books"] * 3
    assert len([m for m in said if "publishing the identity set failed" in m]) == 1
    assert loop.said() == {"step_failures": 3, "failing": ["publishing the identity set"]}


def test_a_torn_age_mark_of_a_relay_is_written_whole_again_and_a_failing_agent_pass_does_not_spin():
    """`say_seen` read the old mark before writing the new one: one torn mark raised on every pass and was never
    written again — the cameras behind the relay never learnt how current their books were; and the agent's loop,
    its pass raising, ran again at once (twenty passes a second). The mark is written whole, counted on from the
    clock; a camera that cannot read it knows nothing (`seen() is None`); and the loop waits its interval after a
    pass that raised."""
    east, _ = make_cluster("east")
    east.objects.put(RELAY_SEEN, b'{"n": ')
    assert Relay(east.vars, east.objects).vars.seen() is None
    mark = say_seen(east.objects, 900.0, 1000.0)
    assert mark == {"n": 1_000_000, "age": 100.0} and Relay(east.vars, east.objects).vars.seen() == mark
    assert say_seen(east.objects, 900.0, 1001.0)["n"] == 1_000_001

    class Raising:
        cluster, URGENT_GAP, last_synced, passes = "east", 1.0, None, 0
        woken = threading.Event()

        def due(self):
            return False

        def sync(self):
            self.passes += 1
            raise ValueError("a torn mark")

    agent, stop = Raising(), threading.Event()
    t = threading.Thread(target=run, args=(agent, 30.0, stop), daemon=True); t.start()
    time.sleep(0.5); stop.set(); agent.woken.set(); t.join(2)
    assert agent.passes == 1                                           # not one every 50 ms


def test_a_name_that_is_not_a_string_stops_no_search_and_a_camera_claimed_twice_is_contested():
    """`{"id": 2, "name": 42}` in one worker's heartbeat broke `GET /api/cameras?q=` for every operator
    (`r.name.lower()`); and a member naming another's camera made `where` raise — a 500 on `/api/where/<ref>`. The name
    is read as text; the camera claimed twice is an answer that names both and is not complete."""
    from tests.conftest import heartbeat
    wall = Clock(10_000.0)
    fed, north, east, cam, *_ = _relay_domain(wall)
    east.objects.put("vms/heartbeats/w-0", json.dumps({"worker": "w-0", "ts": wall(), "server": "srv-2",
                                                         "status": [{"id": 2, "name": 42, "ref": "201"}]}).encode())
    heartbeat(north, "w-0", [101], ts=wall())
    view = ReadView(fed, wall=wall); view.refresh()
    assert view.list(q="42")["total"] == 1 and view.list(q="lobby")["total"] == 0
    snapshot(east, {101: ("w-0", "srv-2")}, ts=wall())                  # east names north's camera
    view.refresh()
    for a in (DomainDirectory(fed, wall=wall).where("101"), view.where("101")):
        assert a.contested == ["east", "north"] and not a.complete and not a.found


def test_a_cluster_whose_trust_rows_do_not_parse_answers_503_with_why_and_its_agent_mends_them():
    """The trust readers (the seventh review left them open): a key set or a revocation list in a cluster's store that
    did not parse raised out of every request. Now the door says "nobody can be checked" with a 503; one entry of the
    revocation list that does not parse stays revoked and the rest is read; and the agent's next pass writes the key
    set again from the domain's — a key set from the domain that does not parse is refused and the one carried
    before is held, and the pass goes on to its report."""
    from domain.access import ClusterAccess
    from w2cplatform.access import Denied
    wall = Clock(10_000.0)
    fed, north, east, cam, signer, cam_agent = _relay_domain(wall)
    token = signer.tokens.issue("anna", 600, now=wall(), kind="person")
    access = ClusterAccess(east.vars, wall=wall)
    assert access.who(token)["sub"] == "anna"
    good, idx = east.vars.get(KEYS_PATH)
    east.vars.put(KEYS_PATH, {"current": "k", "key:k": "not hex"}, cas=idx)
    try:
        access.who(token); raise AssertionError("must say it cannot check")
    except Denied as e:
        assert e.status == 503 and "domain/keys" in e.why
    agent = DomainAgent("east", north.vars, east.vars, now=wall)
    assert agent.sync() and access.who(token)["sub"] == "anna"          # mended by the next pass
    rl = RevocationList.from_items({"jtis": "aaa:2000.5,bbb:then,ccc"})
    assert rl.entries["aaa"] == 2000.5 and rl.entries["bbb"] == float("inf") and rl.jtis == {"aaa", "bbb", "ccc"}
    _, idx = north.vars.get(KEYS_PATH)
    north.vars.put(KEYS_PATH, {"current": "k", "key:k": "zz"}, cas=idx)   # the domain's own key set, torn
    wall.advance(10)
    assert agent.sync() and agent.keys.startswith("refused: the domain's key set does not parse")   # …and the pass went on
    assert access.who(token)["sub"] == "anna"                          # the one carried before is held


def test_the_agents_pass_goes_on_past_a_row_of_the_domain_that_does_not_parse_and_leaves_its_report():
    """The agent's pass (the seventh review left it open): a kept edit, a holder record or a pointer from the domain
    that did not parse raised out of the pass — and the report, the member's sign of life, was not written; the domain
    called a member silent whose only trouble was a row the domain wrote. Each is refused in its own step now, said
    once in the log, and the report goes."""
    from domain.shared import POINTER
    from domain.term import HOLDER
    wall = Clock(10_000.0)
    north, _ = make_cluster("north", domain=True)
    signer = Signer("acme", north.vars, now=wall)
    DomainPublisher(north.vars).publish_keys(signer.tokens.keyset())
    cam = DeviceCluster(SERIAL, FakeVariables(), wall=wall)
    cam.boot()
    agent = DomainAgent(cam.name, north.vars, cam.flash, now=wall, console=cam.local_console(), current=cam.current,
                        domain_objects=north.objects, cluster_objects=cam.local_objects(), published=cam.local_objects())
    assert agent.sync()
    north.vars.put(f"domain/pending/{cam.name}", {SERIAL: "{torn", "other": json.dumps({"rev": 1, "fields": 3})})
    north.vars.put(HOLDER, {"doc": "{torn"})
    north.vars.put(POINTER, {"object": "shared/rev-1", "term": "one", "rev": "1", "sha256": "x"})
    before = json.loads(north.objects.get(base(cam.name) + "reported"))["seq"]
    wall.advance(10)
    assert agent.sync()
    assert agent.holder.startswith("refused") and agent.shared.startswith("refused")
    assert json.loads(north.objects.get(base(cam.name) + "reported"))["seq"] == before + 1


def test_one_users_record_that_does_not_parse_stops_neither_the_publication_nor_a_federated_login():
    """`identity.users` (the seventh review left it open): one torn user record raised out of `users()` — the
    identity set was never published again, and no federated user could log in. That record is skipped, counted;
    the others are published and log in."""
    wall = Clock()
    north, _ = make_cluster("north", domain=True)
    ids = IdentityStore(Signer("acme", north.vars, now=wall), north.vars, north.objects, now=wall)
    ids.create_federated("bob", "bob@corp", ["admin"])
    north.vars.put("identity/users/eve", {"id": "eve", "kind": "local", "created": "yesterday"})
    assert [u.id for u in ids.users()] == ["bob"] and ids.publish(force=True)
    assert ids.login_federated({"sub": "bob@corp"})


def test_a_signer_whose_key_row_does_not_parse_does_not_start_and_does_not_make_new_keys():
    """The product's sibling: a signer that took a row it could not read for "no keys" would make new ones and write
    them over — orphaning every member. A row that is there and does not parse stops the start with what to do; the
    row is left as it was. A torn revocation list does not stop it: entry by entry, the torn one kept revoked."""
    from domain.signer_service import revocations
    v = FakeVariables()
    v.put("domain/signer", {"ca_key": "zz", "ca_cert": "x", "token_key": "y", "kid": "k"})
    try:
        Signer("acme", v); raise AssertionError("must not start")
    except RuntimeError as e:
        assert "do not parse" in str(e)
    assert v.get("domain/signer")[0]["ca_key"] == "zz"
    v.put(REVOKED_PATH, {"jtis": "a:1e12,b:"})
    assert revocations(v).jtis == {"a", "b"}

    class Odd:                                                         # a row of another shape altogether
        def get(self, path):
            return ["a:1e12"], 1
    assert revocations(Odd()).jtis == set()


def test_a_member_page_with_a_bad_line_or_a_report_mark_past_any_number_stops_no_list():
    """Minors of part 4: an alarm line `{"t": "x"}` from one camera raised out of the domain's whole list of alarms;
    `"seq": 1e999` in a report mark raised `OverflowError` before the next report was written. The line is that
    line's — left out, counted; the mark is written whole again, counted on from the clock."""
    wall = Clock(10_000.0)
    north, _ = make_cluster("north", domain=True)
    b = base("cam-X")
    north.objects.put(b + "reported", json.dumps({"ts": wall(), "seq": 1}).encode())
    north.objects.put(b + "p/alarms", json.dumps({"from": 0, "to": wall(), "events": [
        {"t": "x", "kind": "door"}, 5, {"t": wall() - 1, "kind": "motion"}]}).encode())
    p = page("cam-X", "alarms", north.objects, wall=wall)
    assert [e["kind"] for e in p["events"]] == ["motion"] and "cam-X/p/alarms#line" in MEMBER_OBJECTS.bad
    cam = DeviceCluster("SNX", FakeVariables(), wall=wall); cam.boot(); cam.publish()
    north.objects.put(base(cam.name) + "reported", b'{"ts": 1, "seq": 1e999}')
    report(cam.name, cam.flash, cam.local_objects(), north.objects, wall())
    assert json.loads(north.objects.get(base(cam.name) + "reported"))["seq"] == int(wall() * 1000)


def test_a_camera_whose_description_is_words_stops_no_book_and_reads_as_not_said():
    """`int(can.get("presets"))` on "five" and `can_a['events']` on a description that is not one raised out of the
    pass over the books — every camera's books with it. A description that is not one says nothing: the camera
    reads as one that has not said, and `misfit` reads a count that is a word as none."""
    from domain.scenario import misfit
    assert misfit("cam", {"ptz": True, "presets": "five"}, {"action": "preset", "arg": 3}) is None
    assert misfit("cam", {"relays": "two"}, {"action": "output", "arg": 1}) == "cam has no relays"


# -- the ninth review: М12's own lists of exceptions, the books' reads, the grants' old names, a worker named by a list --

def test_a_camera_id_of_1e400_in_a_members_copy_freezes_no_list_and_no_view_of_the_domain():
    """`{"id": 1e400}` in one member's snapshot: `int(inf)` raised `OverflowError`, which the read view's own list of
    exceptions left out — `rows()`, `list()`, `publish()` raised, `GET /api/cameras` was a 500 for everyone and the
    domain's view was frozen at its last publish. The view reads with `PARSE_ERRORS`: that row is left out, counted,
    and the rest of the domain is listed and published."""
    wall = Clock(10_000.0)
    fed, north, east, cam, *_ = _relay_domain(wall)
    east.objects.put("vms/snapshot/w-9", json.dumps({"cluster": "east", "worker": "w-9", "ts": wall(),
                                                     "cameras": [{"id": 1e400, "ref": "299"}]}).encode())
    view = ReadView(fed, wall=wall); view.refresh()
    listed = {r["ref"] for r in view.list()["rows"]}
    assert {"101", "201"} <= listed and "299" not in listed
    assert {"101", "201"} <= {u["ref"] for u in view.publish(north.objects)["units"]}
    assert "east/vms/snapshot#inf" in MEMBER_OBJECTS.bad


def test_one_heartbeat_whose_worker_is_a_list_is_that_heartbeats_and_not_the_whole_member_unreachable():
    """`"worker": ["w-1"]` passed the check (`str(hb["worker"])`) and was the key itself — unhashable — so
    `heartbeats()` raised, and the whole member read as unreachable for one heartbeat. A worker's name is a string:
    that heartbeat is skipped, counted, and the member's other workers are read."""
    from tests.conftest import heartbeat
    wall = Clock(10_000.0)
    fed, north, east, cam, *_ = _relay_domain(wall)
    heartbeat(east, "w-0", [201], ts=wall(), server="srv-2")
    east.objects.put("vms/heartbeats/w-1", json.dumps({"worker": ["w-1"], "ts": wall(), "status": []}).encode())
    view = ReadView(fed, wall=wall); view.refresh()
    assert "east" not in view.cluster_down_since and ("east", "w-0") in view.snapshots
    assert "east/vms/heartbeats/w-1" in MEMBER_OBJECTS.bad


def test_a_recorders_archive_url_that_is_a_list_stops_no_source_book_and_a_string_of_urls_takes_no_road_away():
    """Two reads of another cluster's data in the books, not through the one reader: the backup's recorder publishing
    `archive_url` as a list raised in `.rstrip` out of the whole `sources` step — no book written for any camera;
    and an ingest announcing `urls` as a STRING passed `list(...)` as its letters, and the book of primaries handed
    the camera a string for a road. Now the url is that heartbeat's trouble — no backup archive from it, counted —
    and the string is an announcement that does not parse: the road the book already held stays."""
    from domain.agent import PRIMARIES_PATH, SOURCES_PATH
    from domain.ingest import INGEST
    from w2cplatform.contract import Heartbeat, Subsystem
    from tests.test_two_servers import A_URLS, SERIAL as SN, _office
    wall = Clock()
    o = _office(wall)
    o.b.objects.put(Subsystem("rec").heartbeat_key("r-b"), Heartbeat("r-b", wall(), [
        {"id": f"{SN}-copy", "cam": f"ref:{SN}", "enabled": True, "phase": "running",
         "coverage": {"from": wall() - 60, "to": wall()}}], {"archive_url": ["http://srv-b:9100/"]}).to_bytes())
    books = o.crossings.publish()
    entry = json.loads(books["srv-a"][SN])
    assert "backups" not in entry and json.loads(o.b.vars.get(f"{SOURCES_PATH}/srv-a")[0][SN]) == entry
    assert any(k.endswith("#archive_url") for k in MEMBER_OBJECTS.bad)
    o.a.objects.put(INGEST, json.dumps({"cluster": "srv-a", "urls": "srt://srv-a:9000", "ts": wall()}).encode())
    o.crossings.publish_primaries()
    said = json.loads(o.b.vars.get(f"{PRIMARIES_PATH}/{o.cam.name}")[0][SN])
    assert said["ingest"]["urls"] == A_URLS                               # the road it had, not a string


def test_a_camera_that_says_who_takes_its_stream_as_a_string_is_not_read_as_its_letters():
    """The sibling of the string of urls: `taken_by: "srv-b"` passed `list(...)` as letters, every letter is somebody
    else, and the standby `srv-b` read the camera as taken by another and never pulled. A list of names, or nothing
    known (None: change nothing)."""
    from domain.crossing import camera_taken

    class Door:
        def __init__(self, said):
            self.said = said

        def get(self, key):
            return json.dumps({"taken_by": self.said}).encode()
    assert camera_taken(Door("srv-b"), "SN1", "srv-b") is None
    assert camera_taken(Door(["srv-b"]), "SN1", "srv-b") is False and camera_taken(Door(["srv-a"]), "SN1", "srv-b") is True


def test_an_old_name_with_a_quote_blocks_no_write_of_grants_and_a_new_one_is_still_refused():
    """A grant to `say"hi`, written before `"` was refused, read as a grant and was carried into every rewrite of its row,
    which raised: revoking `mallory` (deleting the user) was refused, and the command that mends the grants failed the
    same way. A rewrite leaves such a grant out — counted, with why and what to do — and writes the rest; a NEW grant
    under such a name is still refused, and an admin left out is no admin."""
    from domain.grants import GRANTS, LastAdmin
    wall = Clock()
    north, _ = make_cluster("north", domain=True)
    ids = IdentityStore(Signer("acme", north.vars, now=wall), north.vars, north.objects, now=wall)
    ids.create_local("mallory", "pw", [])
    north.vars.put(DOMAIN_GRANTS, {"root|admin|": "0.0", 'say"hi|view|': "0.0", "mallory|view|": "0.0"})
    ids.delete("mallory")                                                # the revocation goes through
    assert sorted(north.vars.get(DOMAIN_GRANTS)[0]) == ["root|admin|"]
    assert f'{DOMAIN_GRANTS}#say"hi|view|' in GRANTS.bad
    have = grants_from_items(north.vars.get(DOMAIN_GRANTS)[0], DOMAIN_GRANTS)
    set_domain_grants(north.vars, have + [Grant("anna", "view", None, 0.0)], wall())   # the mending command
    assert sorted(north.vars.get(DOMAIN_GRANTS)[0]) == ["anna|view|", "root|admin|"]
    try:
        set_domain_grants(north.vars, have + [Grant('new"one', "view", None, 0.0)], wall()); raise AssertionError("must refuse")
    except BadName:
        pass
    north.vars.put(DOMAIN_GRANTS, {'old"admin|admin|': "0.0", "anna|view|": "0.0"})
    try:
        set_domain_grants(north.vars, grants_from_items(north.vars.get(DOMAIN_GRANTS)[0]), wall()); raise AssertionError
    except LastAdmin:
        pass
    north.vars.put("domain/grants/south", {'say"hi|view|7': "1.0"})     # a cluster's row, published again
    DomainPublisher(north.vars).publish_grants("south", [Grant('say"hi', "view", 7, 1.0), Grant("anna", "view", 7, 2.0)])
    assert north.vars.get("domain/grants/south")[0] == {"anna|view|7": "2.0"}


def test_a_token_whose_header_or_key_id_is_not_what_a_token_holds_is_refused_and_not_a_500():
    """Before the signature, everything in a token is a stranger's: a header that is a list (`.get`), a `kid` that is
    a list (unhashable in `kid in keys`), JSON nested ten thousand deep, a signature that is not base64, a token that
    is not a string — each raised past the door's `TokenError` and answered 500. Each is "not a token" now."""
    from domain.tokens import TokenError, _b64, kid_of, verify
    signer = Signer("acme", FakeVariables(), now=lambda: 1000.0)
    ks = signer.tokens.keyset()
    good = signer.tokens.issue("anna", 60, now=1000.0)
    h, p, s = good.split(".")
    for bad in (_b64(b"[1]") + "." + p + "." + s, _b64(b'{"kid": ["x"]}') + "." + p + "." + s,
                _b64(b"[" * 10000) + "." + p + "." + s, h + "." + p + ".%%é", 7):
        try:
            verify(bad, ks, now=1000.0); raise AssertionError(f"{bad!r:.40} must be refused")
        except TokenError:
            pass
    assert kid_of(_b64(b"[" * 10000) + ".x.y") is None and verify(good, ks, now=1000.0)["sub"] == "anna"


def test_one_status_entry_that_is_not_numbers_stops_no_shadow_report():
    """The shadow report read every running entry of every heartbeat bare: `id: "seven"` raised out of the report for
    every cluster of the domain. That entry is left out, counted; the others are reported."""
    from domain.shadow import reports_from
    from tests.conftest import heartbeat
    wall = Clock(10_000.0)
    fed, north, east, cam, *_ = _relay_domain(wall)
    heartbeat(north, "w-0", [101], ts=wall())
    east.objects.put("vms/heartbeats/w-0", json.dumps({"worker": "w-0", "ts": wall(), "server": "srv-2", "status": [
        {"id": "seven", "phase": "running"}, {"id": 201, "phase": "running", "ref": "201", "epoch": 1}]}).encode())
    reports, _, _ = reports_from(fed)
    by = {(r.cluster, r.worker): r for r in reports}
    assert [c[0] for c in by[("east", "w-0")].cameras] == ["201"] and "east/vms/heartbeats/w-0#seven" in MEMBER_OBJECTS.bad


def test_an_ask_whose_deadline_has_passed_is_refused_and_one_askers_outcomes_are_bounded_without_crowding_out_another():
    """The ninth review, a minor, run as its probe ran it: 20 000 asks with `deadline = now − 1` were taken — a deadline
    already past was never a live ask, so `MAX_LIVE_ASKS` never counted it — each became an "expired" outcome kept for
    `REMEMBER`, and every ask swept all of them: 27.5 s of the ingest's CPU. A deadline that has passed is refused now;
    an asker that lets its asks run out as fast as it may keeps at most `OUTCOMES_KEPT` outcomes at a camera, the
    oldest forgotten first; and another asker's outcome is not pushed out by it."""
    from domain.ingest import OUTCOMES_KEPT
    wall = Clock(10_000.0)
    south, _ = make_cluster("south")
    signer = Signer("acme", south.vars, now=wall)
    DomainPublisher(south.vars).publish_keys(signer.tokens.keyset())
    ing = Ingest("south", ["srt://south:9000"], keys=lambda: ClusterTrust(south.vars).keyset(), wall=wall)
    acts = [{"action": "preset", "arg": i} for i in range(MAX_LIVE_ASKS)]

    def token(by):
        return signer.tokens.issue(f"cam-{by}", 3600, now=wall(), aud=audience("south"), ask="SN5", by=by, acts=acts,
                                   kind="ask")
    flood, other = token("GATE"), token("YARD")
    for deadline in (wall() - 1, wall()):
        try:
            ing.ask(flood, "SN5", acts[0], deadline); raise AssertionError("a deadline that has passed must be refused")
        except Refused as e:
            assert "passed" in str(e)
    assert ing.cams.get("SN5") is None or not ing.cams["SN5"].asks
    kept = ing.ask(other, "SN5", acts[0], wall() + 1)                     # another asker's ask, expired like the rest
    for _ in range(40):                                                   # sixteen live asks at a time, run out, again
        for i in range(MAX_LIVE_ASKS):
            ing.ask(flood, "SN5", acts[i], wall() + 1)
        wall.advance(2)
    assert ing.ask_outcome("SN5", kept) == "expired"                      # not crowded out by 640 of GATE's
    outcomes = ing.cams["SN5"].outcomes
    assert sum(1 for v in outcomes.values() if v[2] == "GATE") == OUTCOMES_KEPT and len(outcomes) == OUTCOMES_KEPT + 1
