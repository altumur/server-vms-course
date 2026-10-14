"""C4 camera integration: address-free sources, role credentials and scope invalidation."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import json
import os
import tempfile
import threading

from tests.vmsconftest import Box
from vms.domainpart.ingest import CameraPusher, Ingest
from vms.recording_books import Unconfirmed
from vms.recording_publication import sources
from w2cplatform.domain.topology import poll_home
from w2cplatform.trust.tokens import TokenIssuer, verify


class Site:
    def __init__(self):
        self.box, self.issuer = Box(), TokenIssuer("poll-fixture")
        self.box.vars.put("domain/member", {"cluster": "camera"})
        self.box.vars.put("domain/holder", {"doc": json.dumps({"holder": "holder", "term": 1})})
        self.policy(via={"camera": "relay"})
        self.book("relay")
        self.requests, self.dials, self.done = [], [], []
        self.before_reply = None
        self.ingests = {name: Ingest(name, ["http://"+name+"/ingest"], self.issuer.keyset,
                                    wall=self.box.wall) for name in ("relay", "centre", "holder")}
        self.door = type("Door", (), {"request": lambda _, kind, ref:
            self.request_token("cam", kind, ref, "camworker")})()
        self.pusher = self.camera()

    def policy(self, *, via=None, centre="centre"):
        self.box.vars.put("domain/member-topology", {"doc": json.dumps({
            "rev": 1, "via": via or {}, "centre": centre, "star": []})})

    def book(self, home="relay", *, urls=None, missing=(), empty=False):
        row = {"": json.dumps({"missing": list(missing)})}
        if not empty:
            row["serial"] = json.dumps({"missing": list(missing), "entries": [{"member": home,
                "item": "r-1/serial", "value": {"ref": "serial", "to": ["camera"],
                "urls": urls or ["http://"+home+"/ingest"]}}]})
        self.box.vars.put("domain/rec/polls", row)

    def request_token(self, sub, kind, ref, role, by=None, request_id=None):
        assert by is None
        home = poll_home(self.box.vars, "camera")
        self.requests.append((sub, kind, ref, role, home))
        token = self.issuer.issue("camera", 86400, now=self.box.wall(), kind=kind, ref=ref, aud=[home])
        reply = {"request_id": request_id or "local-poll", "token": token, "exp": self.box.wall()+86400}
        if self.before_reply:
            self.before_reply()
        return reply

    def dial(self, url):
        self.dials.append(url)
        return next(ing for ing in self.ingests.values() if url in ing.urls)

    def camera(self, door=None):
        return CameraPusher("serial", self.box.vars, self.dial, clock=self.box.wall, steady=self.box.clock,
                            token_requests=door or self.door,
                            perform=lambda action: self.done.append(action) or "performed")

    @contextmanager
    def role_door(self):
        from w2cplatform.console import Bounds, UnixConsoleServer
        from w2cplatform.domain.tokenrequest import WorkerTokenDoor, local_handler
        with tempfile.TemporaryDirectory(prefix="poll-role-") as directory:
            path = os.path.join(directory, "tokens.sock")
            server = UnixConsoleServer(path, local_handler(self, "camworker"), Bounds())
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                yield WorkerTokenDoor(path)
            finally:
                server.shutdown(); server.server_close(); thread.join(timeout=2)


def unconfirmed(call):
    try:
        call()
    except Unconfirmed:
        return
    raise AssertionError("a delayed or unknown route was accepted")


def claims(site, entry):
    return verify(entry["ingest"]["token_secret"], site.issuer.keyset(), now=site.box.wall(), kind="poll")


def test_unassigned_poll_source_exposes_neither_address_credentials_nor_push_and_tracks_home():
    site = Site()
    worker = type("Camera", (), {"vars": site.box.vars, "server": "srv", "wall": site.box.wall})()
    status = [{"id": "1", "ref": "serial", "polls": True, "push": True,
               "live_url": "rtsp://admin:password@private/live", "cred_secret": "password"}]
    value = json.loads(sources(worker, status)["1"])
    assert value == {"ref": "serial", "to": ["relay", "centre"], "polls": True,
                     "live_url": "", "server": "srv", "as_of": site.box.wall()}
    assert "password" not in json.dumps(value) and "private" not in json.dumps(value)
    site.policy()
    assert json.loads(sources(worker, status)["1"])["to"] == ["centre"]
    site.policy(centre=None)
    assert json.loads(sources(worker, status)["1"])["to"] == ["holder"]
    assert sources(worker, [{"id": "1", "ref": "serial", "live_url": "private", "push": True}]) == {}


def test_camera_requests_poll_through_real_role_socket_and_answers_asks_without_sending_bytes():
    site = Site()
    ing = site.ingests["relay"]
    ing.want("serial", "viewer")
    queue = ing.subscribe("serial", "viewer")
    action = {"camera": "serial", "action": "preset", "arg": 3}
    token = site.issuer.issue("gate", 60, now=site.box.wall(), kind="ask", aud=["relay"],
                              ref="serial", acts=[action])
    aid = ing.ask(token, "serial", action, site.box.wall()+30)
    with site.role_door() as door:
        pusher = site.camera(door)
        frames = [{"t": site.box.wall(), "key": True, "body": b"private-video-bytes"}]
        result = pusher.pass_once(frames)
        assert result["pushed"] == 0 and result["asks"] == [(action, "performed")]
        assert queue.drain() == [] and pusher.sent is None and pusher.delivered == []
        assert pusher.frames.piece(None, 1 << 20)[0] == frames
        assert ing.ask_outcome("serial", aid) == "performed"
        pusher.pass_once([])
        assert site.done == [action] and site.requests == [("cam", "poll", "serial", "camworker", "relay")]
        assert claims(site, pusher.entry())["aud"] == ["relay"]
        assert site.dials and set(site.dials) == {"http://relay/ingest"}
        assert "token_secret" not in json.dumps({key: site.box.vars.get(key)[0] for key in site.box.vars.list("")})


def test_home_switch_forgets_previous_route_and_credential_before_new_observation_arrives():
    site = Site()
    first = site.pusher.entry()
    tokens = [first["ingest"]["token_secret"]]
    for home, centre in (("centre", "centre"), ("holder", None)):
        site.policy(centre=centre)
        before = len(site.requests)
        unconfirmed(site.pusher.entry)                                # old publisher cannot authorize the new home
        assert len(site.requests) == before
        site.book(home)
        entry = site.pusher.entry()
        assert entry["cluster"] == home and entry["ingest"]["urls"] == ["http://"+home+"/ingest"]
        assert claims(site, entry)["aud"] == [home]
        tokens.append(entry["ingest"]["token_secret"])
    assert len(set(tokens)) == 3
    assert [request[-1] for request in site.requests] == ["relay", "centre", "holder"]


def test_holder_move_changes_fallback_home_and_invalidates_the_old_holder_credential():
    site = Site()
    site.policy(centre=None); site.book("holder")
    previous = site.pusher.entry()
    site.box.vars.put("domain/holder", {"doc": json.dumps({"holder": "new-holder", "term": 2})})
    unconfirmed(site.pusher.entry)
    site.book("new-holder")
    current = site.pusher.entry()
    assert current["cluster"] == "new-holder"
    assert claims(site, current)["aud"] == ["new-holder"]
    assert current["ingest"]["token_secret"] != previous["ingest"]["token_secret"]
    assert [request[-1] for request in site.requests] == ["holder", "new-holder"]


def test_missing_observation_opens_no_new_poll_but_established_same_scope_may_continue():
    site = Site()
    site.pusher.pass_once([])
    before = len(site.dials)
    site.book(missing=("relay",))
    fresh = site.camera()
    fresh.pass_once([])
    assert len(site.dials) == before and len(site.requests) == 1
    site.pusher.pass_once([])
    assert len(site.dials) > before and len(site.requests) == 1
    assert set(site.dials) == {"http://relay/ingest"}
    site.book(empty=True)
    assert site.pusher.entry() is None
    assert not site.pusher.polling.tokens.cached
    before = len(site.dials)
    site.book(missing=("relay",))
    site.pusher.pass_once([])
    assert len(site.dials) == before                                  # a withdrawn flow cannot be resurrected by missing


def test_late_role_reply_after_home_switch_does_not_restore_previous_home():
    site = Site()
    entered, release = threading.Event(), threading.Event()
    site.before_reply = lambda: (entered.set(), release.wait(3))
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(site.pusher.entry)
        assert entered.wait(2)
        site.policy(); site.book("centre")
        release.set()
        unconfirmed(lambda: pending.result(timeout=3))
    site.before_reply = None
    entry = site.pusher.entry()
    assert entry["cluster"] == "centre" and claims(site, entry)["aud"] == ["centre"]
    assert site.dials == []


def test_late_role_reply_after_complete_withdrawal_does_not_create_a_poll_route():
    site = Site()
    entered, release = threading.Event(), threading.Event()
    site.before_reply = lambda: (entered.set(), release.wait(3))
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(site.pusher.entry)
        assert entered.wait(2)
        site.book(empty=True)
        release.set()
        unconfirmed(lambda: pending.result(timeout=3))
    assert site.pusher.entry() is None
    assert not site.pusher.polling.tokens.cached and site.dials == []


def test_late_role_reply_after_address_change_cannot_restore_superseded_ingest():
    site = Site()
    entered, release = threading.Event(), threading.Event()
    site.before_reply = lambda: (entered.set(), release.wait(3))
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(site.pusher.entry)
        assert entered.wait(2)
        site.book(urls=["http://relay/new-ingest"])
        release.set()
        unconfirmed(lambda: pending.result(timeout=3))
    site.before_reply = None
    assert site.pusher.entry()["ingest"]["urls"] == ["http://relay/new-ingest"]
    assert site.dials == []


def test_ingest_refusal_forgets_the_poll_credential_and_next_pass_obtains_a_current_one():
    site = Site()
    token = site.pusher.entry()["ingest"]["token_secret"]
    old = verify(token, site.issuer.keyset(), now=site.box.wall(), kind="poll")
    site.ingests["relay"].revoked = lambda: {old["jti"]}
    result = site.pusher.pass_once([])                                # a refusal is retryable, never a successful poll
    assert "refused" in result["state"] and not site.pusher.polling.tokens.cached
    result = site.pusher.pass_once([])
    assert "asks only" in result["state"]
    assert len(site.requests) == 2
    assert site.pusher.entry()["ingest"]["token_secret"] != token
