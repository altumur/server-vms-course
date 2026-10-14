"""C3: retained routes, ephemeral credentials and lossless token retry."""
import json
import threading

from tests.conftest import Clock
from tests.vmsconftest import Box
from vms.forwarder import Forwarder
from vms.ingest import Ingest, Refused
from vms.recording_books import Unconfirmed
from vms.role_tokens import RoleTokens
from w2cplatform.trust.tokens import TokenIssuer


def placement(box, own, *, primary="relay", copies=(), rev=1):
    box.vars.put("domain/member", {"cluster": own})
    box.vars.put("domain/placed/rec/serial", {"cluster": primary, "origin": "camera", "copies": json.dumps(list(copies)),
                                             "reason": "operator", "at": str(box.wall()), "rev": str(rev)})


def denied(call):
    try:
        call()
    except Unconfirmed:
        return
    raise AssertionError("an unconfirmed credential was accepted")


class Door:
    def __init__(self, wall, lifetime=100):
        self.wall, self.lifetime = wall, lifetime
        self.issuer, self.calls, self.failure = TokenIssuer("site"), [], False

    def request(self, kind, ref):
        self.calls.append((kind, ref))
        if self.failure:
            raise OSError("role door unavailable")
        token = self.issuer.issue("relay", self.lifetime, now=self.wall(), kind=kind, aud=["centre"], ref=ref)
        return {"request_id": "local", "token": token, "exp": self.wall() + self.lifetime}


def topology(box, *, rev=1, centre="centre", star=()):
    box.vars.put("domain/member-topology", {"doc": json.dumps({"rev": rev, "centre": centre, "star": list(star), "via": {}})})


def book(box, path, *, ref="serial", member="centre", value=None, missing=(), conflict=False):
    entries = [] if value is None else [{"member": member, "item": "r1/" + ref, "value": value}]
    if conflict:
        entries += [{"member": member, "item": "r2/" + ref, "value": value}]
    box.vars.put(path, {"": json.dumps({"missing": list(missing)}),
                        ref: json.dumps({"entries": entries, "missing": list(missing)})})


def source(box, polls=True):
    value = {"ref": "serial", "to": ["relay"], "live_url": "rtsp://camera/live", "server": "camera", "as_of": box.wall()}
    if polls:
        value["polls"] = True
    book(box, "domain/cam/sources", member="camera", value=value)


def upstream(box, *, member="centre", urls=("http://centre/ingest",), missing=(), conflict=False):
    value = {"ref": "serial", "to": ["relay"], "urls": list(urls)}
    book(box, "domain/rec/upstream", member=member, value=value, missing=missing, conflict=conflict)


class Centre:
    def __init__(self):
        self.fail, self.polls, self.frames, self.ranges, self.uploads = None, [], [], {}, []
        self.have = None

    def poll(self, token, ref, **kw):
        self.polls.append(token)
        if self.fail == "poll":
            raise Refused("retired key")
        return {"version": 1, "push": True, "ranges": dict(self.ranges)}

    def push(self, token, ref, frames):
        if self.fail == "push":
            raise Refused("revoked token")
        self.frames += frames

    def upload(self, token, ref, rid, frames, **kw):
        if self.fail == "upload":
            raise Refused("revoked token")
        self.uploads.append((rid, frames))
        self.ranges.pop(rid, None)

    def pull(self, token, ref, who, have=()):
        self.have = have
        if self.fail == "pull":
            raise Refused("revoked token")
        class Frames(list):
            have = ("boot", 2)
        return Frames(self.frames)


def fixture(*, star=False):
    box = Box()
    placement(box, "relay", primary="relay", copies=())
    topology(box, star=["relay"] if star else [])
    source(box)
    upstream(box)
    door, centre = Door(box.wall), Centre()
    local = Ingest("relay", ["http://relay/ingest"], lambda: {}, wall=box.wall)
    dialled = []
    def dial(url):
        dialled.append(url)
        return centre
    fwd = Forwarder("relay", local, box.vars, dial, token_requests=door, needs=lambda ref: True)
    fwd.tokens.clock = box.clock
    return box, fwd, door, centre, dialled


def test_role_cache_uses_steady_time_and_never_extends_a_failed_refresh():
    wall, steady = Clock(1000), Clock(100)
    door = Door(wall)
    tokens = RoleTokens("recworker", door, clock=steady)
    first = tokens.get("upstream", "serial", (1,))
    wall.advance(-50000)
    assert tokens.get("upstream", "serial", (1,)) == first and len(door.calls) == 1
    steady.advance(75)
    door.failure = True
    assert tokens.get("upstream", "serial", (1,)) == first
    steady.advance(16)
    denied(lambda: tokens.get("upstream", "serial", (1,)))
    denied(lambda: tokens.get("upstream", "serial", (2,)))
    assert tokens.cached == {}


def test_late_reply_cannot_resurrect_a_forgotten_or_changed_scope():
    for change_scope in (False, True):
        started, release = threading.Event(), threading.Event()
        door = Door(Clock())
        real = door.request
        def held(kind, ref):
            reply = real(kind, ref)
            started.set()
            assert release.wait(2), "test did not release the role reply"
            return reply
        door.request = held
        tokens = RoleTokens("recworker", door, clock=Clock())
        results = []
        def request():
            try:
                results.append(tokens.get("upstream", "serial", (1,)))
            except Unconfirmed:
                results.append("unconfirmed")
        t = threading.Thread(target=request)
        t.start()
        assert started.wait(2)
        tokens.forget("upstream", "serial")
        if change_scope:
            door.request = real
            current = tokens.get("upstream", "serial", (2,))
        release.set()
        t.join(2)
        assert not t.is_alive() and results == ["unconfirmed"]
        if change_scope:
            assert tokens.cached[("upstream", "serial")][1] == current
        else:
            assert not tokens.cached


def test_role_cache_refuses_malformed_or_outlived_reply():
    for value in (None, [], {}, {"token": []}, {"token": "x", "exp": 100},
                  {"token": "x.W10.x", "exp": float("inf")}):
        door = type("BadDoor", (), {"request": lambda self, *args: value})()
        tokens = RoleTokens("recworker", door, clock=Clock())
        denied(lambda: tokens.get("upstream", "serial", (1,)))
        assert not tokens.cached
    wall, steady = Clock(), Clock()
    door = Door(wall)
    real = door.request
    def delayed(*args):
        reply = real(*args)
        steady.advance(1000)
        return reply
    door.request = delayed
    tokens = RoleTokens("recworker", door, clock=steady)
    denied(lambda: tokens.get("upstream", "serial", (1,)))
    assert not tokens.cached


def test_conflicting_missing_and_torn_facts_hold_only_a_working_route():
    for damage in ("missing", "conflict", "torn", "no-source"):
        box, fwd, door, centre, dialled = fixture()
        fwd.pass_once()
        assert centre.polls and "serial" in fwd.queues
        if damage == "missing":
            upstream(box, missing=["centre"])
        elif damage == "conflict":
            upstream(box, conflict=True)
        elif damage == "torn":
            box.vars.put("domain/rec/upstream", {"serial": "{"})
        else:
            book(box, "domain/cam/sources", missing=["camera"])
        fwd.pass_once()
        assert len(centre.polls) == 2 and len(door.calls) == 1
        fresh = Forwarder("relay", fwd.local, box.vars, lambda url: (_ for _ in ()).throw(AssertionError("new dial")),
                          token_requests=door)
        assert fresh.book() == {} and len(door.calls) == 1


def test_explicit_poll_withdrawal_cannot_revive_after_a_missing_source():
    box, fwd, door, centre, dialled = fixture()
    fwd.pass_once()
    source(box, polls=False)
    fwd.pass_once()
    assert not fwd.queues and not fwd._routes and not fwd.tokens.cached
    # Ending a forwarder subscription retains the existing ingest linger, then releases the want.
    box.wall.advance(fwd.local.linger + .01)
    assert not fwd.local.wanted("serial")
    book(box, "domain/cam/sources", missing=["camera"])
    fwd.pass_once()
    assert len(centre.polls) == 1 and len(door.calls) == 1 and not fwd._routes


def test_assignment_or_topology_changes_invalidate_before_missing_fallback():
    for change in ("revision", "withdrawal", "cluster", "centre", "mode", "torn-policy"):
        box, fwd, door, centre, dialled = fixture()
        fwd.pass_once()
        upstream(box, missing=["centre"])
        if change == "revision":
            placement(box, "relay", primary="relay", copies=(), rev=2)
        elif change == "withdrawal":
            box.vars.as_writer("domainagent", ["domain/*"]).delete("domain/placed/rec/serial")
        elif change == "cluster":
            placement(box, "relay", primary="other", copies=(), rev=2)
        elif change == "centre":
            topology(box, rev=2, centre="other")
        elif change == "mode":
            topology(box, rev=2, star=["relay"])
        else:
            box.vars.put("domain/member-topology", {"doc": "{"})
        fwd.pass_once()
        assert len(centre.polls) == 1 and not fwd._routes and not fwd.tokens.cached and not fwd.queues


def test_wrong_origin_empty_urls_and_unknown_topology_cannot_start_a_route():
    for damage in ("origin", "urls", "topology"):
        box, fwd, door, centre, dialled = fixture()
        if damage == "origin":
            upstream(box, member="stranger")
        elif damage == "urls":
            upstream(box, urls=[])
        else:
            topology(box, rev=0)
        assert fwd.book() == {} and not door.calls and not dialled


def test_metadata_and_restart_do_not_obtain_or_restore_tokens():
    box, fwd, door, centre, dialled = fixture()
    fwd.book(authorize=False)
    fwd.restore_up()
    fwd.stats()
    assert not door.calls and not fwd.tokens.cached
    fwd.pass_once()
    assert len(door.calls) == 1
    fresh = Forwarder("relay", fwd.local, box.vars, fwd.dial, token_requests=door)
    assert not fresh.tokens.cached
    assert all("token_secret" not in str(box.vars.get(key)[0]) for key in box.vars.list(""))


def test_refused_poll_forgets_the_token_and_retries_through_role_door():
    box, fwd, door, centre, dialled = fixture()
    centre.fail = "poll"
    fwd.pass_once()
    assert not fwd.tokens.cached and not fwd._active
    centre.fail = None
    fwd.pass_once()
    assert len(door.calls) == 2 and len(centre.polls) == 2 and "serial" in fwd._active


def test_refused_drained_push_survives_token_outage_then_sends_every_frame():
    box, fwd, door, centre, dialled = fixture()
    fwd.pass_once()
    frames = [{"t": box.wall(), "key": True, "body": "a"}, {"t": box.wall() + .01, "key": False, "body": "b"}]
    fwd.local.inject("serial", frames)
    centre.fail = "push"
    fwd.pass_once()
    assert fwd.unsent["serial"] == frames and not centre.frames and not fwd.tokens.cached
    door.failure = True
    fwd.pass_once()
    assert fwd.unsent["serial"] == frames and "serial" in fwd.queues and not centre.frames
    door.failure, centre.fail = False, None
    fwd.pass_once()
    assert centre.frames == frames and not fwd.unsent.get("serial") and len(door.calls) == 3


def test_refused_upload_is_not_acknowledged_and_retries_with_a_current_token():
    box, fwd, door, centre, dialled = fixture()
    centre.ranges["range-1"] = {"from": 1, "to": 2, "recording": "recording-9"}
    fwd.archive = lambda ref, lo, hi, recording=None: [(ref, lo, hi, recording)]
    centre.fail = "upload"
    fwd.pass_once()
    assert centre.ranges and not centre.uploads and not fwd.tokens.cached
    centre.fail = None
    fwd.pass_once()
    assert centre.uploads == [("range-1", [("serial", 1, 2, "recording-9")])] and not centre.ranges
    assert len(door.calls) == 2


def test_refused_pull_does_not_advance_batch_or_inject_frames():
    box, fwd, door, centre, dialled = fixture(star=True)
    queue = fwd.local.subscribe("serial", "recorder:test", maxsize=10)
    centre.frames = [{"t": box.wall(), "key": True}]
    centre.fail = "pull"
    fwd.pass_once()
    assert not fwd.pulled and not queue.drain() and not fwd.tokens.cached
    centre.fail = None
    fwd.pass_once()
    assert fwd.pulled["serial"] == ("boot", 2) and queue.drain() == centre.frames and len(door.calls) == 2


def test_scope_changed_during_role_reply_or_held_poll_cannot_start_transport():
    for when in ("token", "poll"):
        box, fwd, door, centre, dialled = fixture()
        target = door if when == "token" else centre
        method = "request" if when == "token" else "poll"
        real = getattr(target, method)
        def changed(*args, **kw):
            reply = real(*args, **kw)
            placement(box, "relay", primary="other", copies=(), rev=2)
            return reply
        setattr(target, method, changed)
        fwd.pass_once()
        assert not fwd.local.wanted("serial") and not fwd.queues and not centre.frames
        if when == "token":
            assert not dialled
        fwd.pass_once()
        assert not fwd.tokens.cached and not fwd._routes


def test_daemon_outage_keeps_retry_state_and_explicit_stop_ends_subscription():
    box, fwd, door, centre, dialled = fixture()
    fwd.pass_once()
    frames = [{"t": box.wall(), "key": True, "body": "kept"}]
    fwd.unsent["serial"] = frames
    fwd.tokens.forget("upstream", "serial")
    door.failure = True
    outage, retried, closed = threading.Event(), threading.Event(), threading.Event()
    real_request, real_push, real_release = door.request, centre.push, fwd.local.release
    def request(*args):
        if door.failure:
            outage.set()
        return real_request(*args)
    def push(*args):
        real_push(*args)
        retried.set()
    def release(ref, who):
        real_release(ref, who)
        if ref == "serial" and who == fwd.up:
            closed.set()
    door.request, centre.push, fwd.local.release = request, push, release
    stop = threading.Event()
    previous_threads = {t.ident for t in threading.enumerate()}
    threads = fwd.serve(stop, period=.01, stream_every=.01)
    try:
        assert outage.wait(2), "daemon did not try its role door"
        assert fwd.unsent["serial"] == frames and "serial" in fwd.queues
        door.failure = False
        fwd.woken.set()
        assert retried.wait(2), "daemon did not retry after role recovery"
        assert centre.frames == frames
        source(box, polls=False)
        fwd.woken.set()
        assert closed.wait(2), "withdrawn subscription stayed alive"
        assert not fwd.queues and not fwd._routes and not fwd.tokens.cached
    finally:
        stop.set()
        fwd.woken.set()
        fwd.pending.set()
        for t in threads + [t for t in threading.enumerate() if t.name == "fwd-serial" and t.ident not in previous_threads]:
            t.join(2)
            assert not t.is_alive(), "test left a forwarder thread alive"


def test_changing_urls_of_the_same_centre_preserves_unacknowledged_frames():
    box, fwd, door, centre, dialled = fixture()
    fwd.pass_once()
    frames = [{"t": box.wall(), "key": True, "body": "unacknowledged"}]
    fwd.unsent["serial"] = frames
    queue = fwd.queues["serial"]
    upstream(box, urls=["http://centre/new"])
    fwd.pass_once()
    assert centre.frames == frames and fwd.queues["serial"] is queue
    assert dialled[-1] == "http://centre/new" and len(door.calls) == 2


def test_scope_change_during_a_role_reply_forgets_its_orphaned_cache_immediately():
    box, fwd, door, centre, dialled = fixture()
    real = door.request
    def changed(*args):
        reply = real(*args)
        source(box, polls=False)
        return reply
    door.request = changed
    fwd.pass_once()
    assert not dialled and not fwd.tokens.cached


def test_refused_carried_answer_refreshes_credential_without_changing_ask_format():
    box, fwd, door, centre, dialled = fixture()
    real_poll = centre.poll
    def poll(*args, **kw):
        return {**real_poll(*args, **kw), "asks": {"ask-1": {"deadline": box.wall()+60}}}
    centre.poll = poll
    answered = []
    def answer(token, ref, aid, outcome):
        if not answered:
            answered.append("refused")
            raise Refused("retired key")
        answered.append((ref, aid, outcome))
    centre.answer_ask = answer
    fwd.local.carry_ask = lambda *args: None
    fwd.local.ask_outcome = lambda *args: "performed"
    fwd.pass_once()
    assert not fwd.tokens.cached and ("serial", "ask-1") in fwd.carried
    fwd.pass_once()
    assert answered == ["refused", ("serial", "ask-1", "performed")]
    assert not fwd.carried and len(door.calls) == 2
