"""C2: durable CRUD queue, a signed local console, closed route set; testsub only."""
import json
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import yaml
from w2cplatform import catalog
from w2cplatform.cluster.variables import FakeVariables
from w2cplatform.console import Mount, SpecConsole
from w2cplatform.domain.api import ApiError, ConsoleAPI
from w2cplatform.domain.pending import PendingEdits, AgentConsole, apply_pending, edit_id
from w2cplatform.domain.federation import Unreachable
from w2cplatform.objects import FsObjectStore
from w2cplatform.spec import SpecController, SubsystemSpec
from w2cplatform.trust.memberkey import MemberKey, sign_request


class Clock:
    def __init__(self): self.t = 1757500000.0
    def __call__(self): return self.t


@contextmanager
def site(vars_=None, fields=None):
    raw = yaml.safe_load((Path(__file__).parent / "testdata" / "testsub.subsystem.yaml").read_text())
    raw["unit"]["fields"].update(fields or {})
    specs = [SubsystemSpec.from_dict({**json.loads(json.dumps(raw).replace("testsub/", sub+"/")), "name": sub}) for sub in ("testsub", "testsub2")]
    wall, vars_ = Clock(), FakeVariables() if vars_ is None else vars_
    key = MemberKey.load_or_make(vars_)
    vars_.put("domain/members", {"doc": json.dumps({"rev": 1, "members": {"north": {"key": key.pub, "seal": key.seal_pub}}})})
    with patch.object(catalog, "_loaded", {s.name: s for s in specs}), patch.object(catalog, "_derived", {}):
        pending = PendingEdits(vars_, wall)
        api = ConsoleAPI(None, pending=pending)
        yield SimpleNamespace(specs=specs, vars=vars_, key=key, wall=wall, pending=pending, api=api)


def raises(status, fn):
    try:
        fn()
    except ApiError as err:
        assert err.status == status, err
        return
    raise AssertionError("the operation was accepted")


def test_member_and_holder_crud_are_queued_and_restart_keeps_the_original_key():
    with site() as e:
        for s in e.specs:
            reply = e.api.queue("POST", s.name, s.rows, None, {s.domain.ref: "badge"}, "create-"+s.name, "north")
            identity = edit_id("north", "create-"+s.name)
            assert reply["kept"] == identity and reply["what"] == s.domain.ref
            assert set(e.pending.of("north")[identity]) == {"id", "what", "method", "path", "body", "key", "at"}
            again = PendingEdits(e.vars, e.wall)
            entry = again.add("north", "POST", "/"+s.name+"/"+s.rows, {s.domain.ref: "badge"}, "create-"+s.name)
            assert entry["id"] == identity
            raises(422, lambda: again.add("north", "POST", entry["path"], {s.domain.ref: "another"}, entry["key"]))
            raises(422, lambda: again.add("north", "PUT", entry["path"]+"/badge", {}, entry["key"]))


def test_refusals_happen_before_keep_and_no_secret_value_enters_a_reply():
    with site() as e:
        s = e.specs[0]
        for fields in ({"start": 4, "password_secret": "private"}, {"start": 4, "url": "rtsp://me:private@camera/live"},
                       {"worker": "w1"}, {"step": 8}):
            raises(400, lambda: e.api.queue("PUT", s.name, s.rows, "badge", fields, "bad", "north"))
        raises(400, lambda: e.api.queue("POST", s.name, s.rows, None, {}, "missing-ref", "north"))
        raises(400, lambda: e.api.queue("DELETE", s.name, s.rows, "badge", {}, "", "north"))
        raises(404, lambda: e.api.queue("DELETE", s.name, s.rows, "badge", {}, "foreign", "not-admitted"))
        assert e.pending.of("north") == {}


def test_unreachable_waits_existing_unit_is_a_409_outcome_and_replay_does_not_apply_again():
    with site() as e:
        entry = e.pending.add("north", "POST", "/testsub/counters", {"name": "badge"}, "once")
        entries = {entry["id"]: entry}
        def unreachable(_): raise Unreachable("console off")
        assert apply_pending(entries, SimpleNamespace(apply=unreachable), e.wall()) == {}
        calls = []
        con = SimpleNamespace(apply=lambda edit: calls.append(edit) or (409, {"detail": "already exists", "password_secret": "private"}))
        out = apply_pending(entries, con, e.wall())
        assert out[entry["id"]]["status"] == 409 and "private" not in json.dumps(out)
        assert apply_pending(entries, con, e.wall(), out) == out and len(calls) == 1
        e.pending.reconcile("north", out)
        assert json.loads(e.vars.get("domain/outcomes/north")[0][entry["id"]])["status"] == 409
        assert e.pending.of("north") == {}
        reused = PendingEdits(e.vars, e.wall).add("north", "POST", entry["path"], {"name": "other"}, "once")
        assert reused["body"] == {"name": "other"}


@contextmanager
def console(e):
    objects = FsObjectStore(tempfile.mkdtemp())
    mounts = {}
    for s in e.specs:
        ctl = SpecController(s, e.vars, objects, wall=e.wall)
        mounts[s.name] = SpecConsole(ctl, wall=e.wall)
    root = mounts.pop("testsub")
    server = Mount(root, mounts).serve("127.0.0.1", 0)
    try:
        yield "http://127.0.0.1:"+str(server.server_address[1])
    finally:
        server.shutdown(); server.server_close()


def send(url, method, path, raw, key, signing_key, wall, signature_path=None, query=""):
    headers = {"Content-Type": "application/json", "Idempotency-Key": key,
        "X-Agent-Signature": sign_request(signing_key, method, signature_path or path, raw, wall())}
    req = Request(url+path+query, data=raw, method=method, headers=headers)
    try:
        with urlopen(req, timeout=5) as reply:
            return reply.status, json.loads(reply.read())
    except HTTPError as err:
        return err.code, json.loads(err.read())


def test_agent_signature_opens_only_unit_crud_and_preserves_subsystem_prefix_and_replay():
    with site() as e, console(e) as url:
        for s in e.specs:
            path = "/"+s.name+"/"+s.rows
            entry = e.pending.add("north", "POST", path, {s.domain.ref: "badge"}, "create-"+s.name)
            agent = AgentConsole(url, e.key, e.wall)
            status, result = agent.apply(entry)
            assert status == 201, (status, result)
            assert agent.apply(entry) == (status, result)
            assert send(url, "POST", path, b'{"name":"other"}', entry["key"], e.key, e.wall)[0] == 422
            assert send(url, "PUT", path+"/badge", b'{"start":4}', "edit-"+s.name, e.key, e.wall)[0] == 200
            assert send(url, "DELETE", path+"/badge", b'{}', "delete-"+s.name, e.key, e.wall)[0] == 200
            for foreign in ("/domain/placement", "/servers/s/labels", "/"+s.name+"/policy", "/"+s.name+"/requests"):
                assert send(url, "PUT", foreign, b'{}', "escape", e.key, e.wall)[0] == 403
            assert send(url, "POST", path, b'{"name":"wrong"}', "wrong-key", MemberKey.new(), e.wall)[0] == 403
            assert send(url, "POST", path, b'{"name":"wrong"}', "wrong-path", e.key, e.wall,
                        signature_path="/"+s.rows)[0] == 403
            assert send(url, "PUT", path+"/badge", b'{"password_secret":"private"}', "secret", e.key, e.wall)[0] == 400
            assert send(url, "PUT", path+"/badge", b'{"step":4}', "undeclared", e.key, e.wall)[0] == 400
        old = Clock(); old.t -= 61
        assert send(url, "POST", "/testsub/counters", b'{"name":"old"}', "old", e.key, old)[0] == 403


def test_holder_agent_applies_its_own_queued_edit_only_through_the_signed_console():
    from w2cplatform.domain.agent import DomainAgent
    from w2cplatform.domain.pending import _load
    with site() as e, console(e) as url:
        entry = e.pending.add("north", "POST", "/testsub/counters", {"name": "badge"}, "own-member")
        agent = DomainAgent("north", e.vars, e.vars, now=e.wall,
            console=AgentConsole(url, e.key, e.wall), key=e.key)
        assert e.vars.get("testsub/counters/badge")[0] is None
        assert agent.sync() is True
        outcomes = _load(e.vars.get("domain/outcomes")[0], "domain/outcomes")
        assert outcomes[entry["id"]]["status"] == 201
        row = e.vars.get("testsub/counters/badge")[0]
        agent.sync()
        assert e.vars.get("testsub/counters/badge")[0] == row
        e.pending.reconcile("north", outcomes)
        assert json.loads(e.vars.get("domain/outcomes/north")[0][entry["id"]])["status"] == 201
        assert e.pending.of("north") == {}
        e.wall.t += 1
        reused = e.pending.add("north", "POST", entry["path"], {"name": "other"}, entry["key"])
        agent.sync()
        latest = _load(e.vars.get("domain/outcomes")[0], "domain/outcomes")
        assert latest[reused["id"]]["status"] == 422
        assert e.vars.get("testsub/counters/other")[0] is None


def test_a_busy_member_console_keeps_the_edit_waiting_for_its_next_pass():
    with site() as e:
        entry = e.pending.add("north", "POST", "/testsub/counters", {"name": "badge"}, "busy")
        outcome = apply_pending({entry["id"]: entry}, SimpleNamespace(apply=lambda _: (503, {"detail": "busy"})), e.wall())
        assert outcome == {} and e.pending.of("north")[entry["id"]] == entry


def test_holder_collects_its_local_outcome_with_holder_rights_without_a_report_to_itself():
    from w2cplatform.domain.agent import DomainAgent
    from w2cplatform.domain.rights import agent_denials
    from w2cplatform.variables import FileVariables, Forbidden
    class UnreachableDoor:
        def answer_for(self, *args): raise Unreachable("holder takes no carry")
        def get(self, *args): raise AssertionError("holder must read its own outcome, not its report")
    with tempfile.TemporaryDirectory() as folder, site(FileVariables(folder)) as e, console(e) as url:
        e.vars.put("domain/holder", {"doc": json.dumps({"holder": "north", "term": 1})})
        edit = e.pending.add("north", "POST", "/testsub/counters", {"name": "own"}, "holder-own")
        agent_vars = e.vars.as_writer("domainagent", ["domain/*", *agent_denials(e.specs)])
        try:
            agent_vars.put("domain/pending/north", {})
        except Forbidden:
            pass
        else:
            raise AssertionError("the agent may not write the holder's queue")
        try:
            agent_vars.put("domain/outcomes/north", {})
        except Forbidden:
            pass
        else:
            raise AssertionError("the agent may not write the holder's outcome history")
        agent = DomainAgent("north", UnreachableDoor(), agent_vars, now=e.wall,
                            console=AgentConsole(url, e.key, e.wall), key=e.key)
        assert agent.sync() is False  # Unreachable carry cannot prevent applying its local queue.
        assert e.vars.get("testsub/counters/own")[0] is not None
        assert edit["id"] in e.pending.of("north")
        assert json.loads(e.vars.get("domain/outcomes")[0][edit["id"]])["status"] == 201
        assert e.vars.get("domain/outcomes/north")[0] is None
        holder_vars = e.vars.as_writer("domain", ["domain/*"])
        fed = SimpleNamespace(clusters={"north": SimpleNamespace(is_domain_holder=True, vars=UnreachableDoor())})
        PendingEdits(holder_vars, e.wall).collect(fed)
        assert e.pending.of("north") == {}
        assert e.vars.get("domain/pending")[0] is None
        history = e.vars.get("domain/outcomes/north")[0]
        assert json.loads(history[edit["id"]])["status"] == 201
        assert agent.sync() is False
        assert e.vars.get("domain/outcomes")[0] == {}
        assert e.vars.get("domain/outcomes/north")[0] == history


def test_a_console_request_in_flight_or_taken_over_stays_waiting_and_exists_is_terminal():
    from member_console import SignedConsole
    with site() as e, tempfile.TemporaryDirectory() as folder:
        edit = e.pending.add("north", "POST", "/testsub/counters", {"name": "one"}, "in-flight")
        signed = SignedConsole(e.specs[0], e.vars, FsObjectStore(folder), e.wall)
        raw = json.dumps(edit["body"], ensure_ascii=False, sort_keys=True).encode()
        assert signed.console.seen.claim(edit["key"], "agent:POST:" + edit["path"], raw) is None
        assert apply_pending({edit["id"]: edit}, signed, e.wall()) == {}
        assert edit["id"] in e.pending.of("north") and e.vars.get("testsub/counters/one")[0] is None
        for reason in ("in flight", "taken over"):
            response = {"detail": reason, "error": reason}
            prior = {edit["id"]: {"id": edit["id"], "status": 409, "result": response,
                                  "error": reason, "at": e.wall(), "what": edit["what"], "kept_at": edit["at"]}}
            e.pending.reconcile("north", prior)
            assert edit["id"] in e.pending.of("north")
            assert apply_pending({edit["id"]: edit}, SimpleNamespace(apply=lambda _: (409, response)), e.wall(), prior) == {}
        signed.console.seen.release(edit["key"])
        finished = apply_pending({edit["id"]: edit}, signed, e.wall())
        assert finished[edit["id"]]["status"] == 201
        e.pending.reconcile("north", finished)
        exists = e.pending.add("north", "POST", edit["path"], edit["body"], "already-there")
        result = apply_pending({exists["id"]: exists}, signed, e.wall())
        assert result[exists["id"]]["status"] == 409 and result[exists["id"]]["result"]["error"] == "exists"
        e.pending.reconcile("north", result)
        assert e.pending.of("north") == {}


def test_holder_masks_a_secret_result_even_in_an_authenticated_member_report():
    from w2cplatform.domain.carry import HolderDoor, publication_bytes
    from w2cplatform.domain.uplink import member_copy
    with site() as e, tempfile.TemporaryDirectory() as folder:
        edit = e.pending.add("north", "POST", "/testsub/counters", {"name": "one"}, "reported-secret")
        outcome = {"id": edit["id"], "status": 201, "result": {"password_secret": "private", "nested": [{"login_secret": "nested-private"}]},
                   "error": "", "at": e.wall(), "what": edit["what"], "kept_at": edit["at"]}
        pub = {"sent_at": e.wall(), "objects": {}, "rows": {}, "pages": {}, "outcomes": {edit["id"]: outcome},
               "key": e.key.pub, "seal": e.key.seal_pub}
        raw = publication_bytes(pub)
        objects = FsObjectStore(folder)
        door = HolderDoor(e.vars, objects, wall=e.wall)
        door.member("north", raw, sign_request(e.key, "POST", "/api/member/north", raw, e.wall()))
        fed = SimpleNamespace(clusters={"north": member_copy("north", objects, wall=e.wall)})
        e.pending.collect(fed)
        saved = e.vars.get("domain/outcomes/north")[0][edit["id"]]
        assert "private" not in saved
        result = json.loads(saved)["result"]
        assert result["password_secret"] == "***" and result["nested"][0]["login_secret"] == "***"
        assert e.pending.of("north") == {}


def test_console_restart_replays_its_persistent_key_and_refuses_a_changed_body():
    from w2cplatform.variables import FileVariables
    with tempfile.TemporaryDirectory() as folder, site(FileVariables(folder)) as e:
        edit = e.pending.add("north", "POST", "/testsub/counters", {"name": "durable"}, "durable-key")
        with console(e) as url:
            first = AgentConsole(url, e.key, e.wall).apply(edit)
            assert first[0] == 201
        row = e.vars.get("testsub/counters/durable")
        e.vars = FileVariables(folder)
        with console(e) as url:
            assert AgentConsole(url, e.key, e.wall).apply(edit) == first
            assert e.vars.get("testsub/counters/durable") == row
            assert AgentConsole(url, e.key, e.wall).apply({**edit, "body": {"name": "changed"}})[0] == 422
            assert e.vars.get("testsub/counters/changed")[0] is None


def test_restart_between_outcome_write_and_queue_removal_preserves_the_result_and_other_edits():
    with site() as e:
        edit = e.pending.add("north", "PUT", "/testsub/counters/one", {"start": 7}, "one")
        other = e.pending.add("north", "DELETE", "/testsub/counters/two", {}, "two")
        items, idx = e.vars.get("domain/pending/north")
        e.vars.put("domain/pending/north", {**items, "torn": "{bad"}, cas=idx)
        result = apply_pending({edit["id"]: edit}, SimpleNamespace(apply=lambda _: (200, {"revision": 2})), e.wall())
        put = e.vars.put
        def fail_removal(path, *args, **kwargs):
            if path == "domain/pending/north": raise Unreachable("crash before removal")
            return put(path, *args, **kwargs)
        with patch.object(e.vars, "put", fail_removal):
            try: e.pending.reconcile("north", result)
            except Unreachable: pass
            else: raise AssertionError("the crash was not exercised")
        assert edit["id"] in e.pending.of("north")
        assert json.loads(e.vars.get("domain/outcomes/north")[0][edit["id"]]) == result[edit["id"]]
        PendingEdits(e.vars, e.wall).reconcile("north", result)
        assert edit["id"] not in e.pending.of("north") and other["id"] in e.pending.of("north")
        assert e.vars.get("domain/pending/north")[0]["torn"] == "{bad"


def test_bad_outcome_does_not_close_a_waiting_edit_and_zero_status_has_the_declared_type():
    with site() as e:
        edit = e.pending.add("north", "PUT", "/testsub/counters/one", {"step": 7, "start": 4}, "shape")
        assert edit["what"] == "start,step"
        outcome = {"id": edit["id"], "status": 0, "result": None, "error": "not asked", "at": e.wall(), "what": "start,step", "kept_at": edit["at"]}
        for fields in ({"status": True}, {"what": ["start", "step"]}, {"at": "100"}, {"status": 503}):
            e.pending.reconcile("north", {edit["id"]: {**outcome, **fields}})
            assert edit["id"] in e.pending.of("north")
        e.pending.reconcile("north", {edit["id"]: outcome})
        assert e.pending.of("north") == {}
        assert json.loads(e.vars.get("domain/outcomes/north")[0][edit["id"]]) == outcome


def test_domain_http_queues_all_three_operations_and_refuses_missing_key_before_storage():
    from http.server import ThreadingHTTPServer
    from w2cplatform.domain.console import Console
    with site() as e:
        domain = Console(None, None, e.api, pending=e.pending, holder_vars=e.vars)
        server = ThreadingHTTPServer(("127.0.0.1", 0), domain.handler())
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = "http://127.0.0.1:" + str(server.server_address[1])
        def call(method, path, body, key=None):
            headers = {"Content-Type": "application/json"}
            if key is not None: headers["Idempotency-Key"] = key
            req = Request(url + path, method=method, data=json.dumps(body).encode(), headers=headers)
            try:
                with urlopen(req, timeout=5) as response: return response.status, json.load(response)
            except HTTPError as err: return err.code, json.load(err)
        try:
            assert call("POST", "/domain/testsub/counters", {"cluster": "north", "name": "one"})[0] == 400
            assert e.pending.of("north") == {}
            for sub in ("testsub", "testsub2"):
                for method, path, body in (
                    ("POST", "/domain/"+sub+"/counters", {"cluster": "north", "name": "one"}),
                    ("PUT", "/domain/"+sub+"/counters/one?cluster=north", {"start": 7}),
                    ("DELETE", "/domain/"+sub+"/counters/one?cluster=north", {})):
                    status, result = call(method, path, body, sub+method)
                    assert status == 202, (status, result)
                    edit = e.pending.of("north")[result["kept"]]
                    assert edit["method"] == method and edit["path"].startswith("/"+sub+"/counters")
                    assert "cluster" not in edit["body"]
            assert e.vars.get("testsub/counters/one")[0] is None
            assert call("POST", "/domain/testsub/counters", {"cluster": "outsider", "name": "one"}, "outsider")[0] == 404
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=5)


def test_an_old_outcome_cannot_settle_a_reused_key_before_the_new_member_pass():
    from w2cplatform.domain.agent import DomainAgent
    from w2cplatform.domain.pending import _load
    with site() as e, console(e) as url:
        first = e.pending.add("north", "POST", "/testsub/counters", {"name": "one"}, "reused")
        agent = DomainAgent("north", e.vars, e.vars, now=e.wall, console=AgentConsole(url, e.key, e.wall), key=e.key)
        agent.sync()
        old = _load(e.vars.get("domain/outcomes")[0], "outcomes")
        e.pending.reconcile("north", old)
        assert e.pending.of("north") == {}
        e.wall.t += 1
        second = e.pending.add("north", "POST", first["path"], {"name": "two"}, "reused")
        assert second["id"] == first["id"] and second["at"] != first["at"]
        e.pending.reconcile("north", old)
        assert e.pending.of("north")[second["id"]] == second
        # The clocks do not agree: correlation is an echo, never a time ordering.
        e.wall.t -= 600
        agent.sync()
        fresh = _load(e.vars.get("domain/outcomes")[0], "outcomes")
        assert fresh[second["id"]]["kept_at"] == second["at"]
        assert fresh[second["id"]]["status"] == 422
        e.pending.reconcile("north", fresh)
        assert e.pending.of("north") == {}
        assert e.vars.get("testsub/counters/two")[0] is None


def test_an_outcome_without_kept_at_is_refused_without_a_compatibility_reader():
    with site() as e:
        edit = e.pending.add("north", "PUT", "/testsub/counters/one", {"start": 7}, "missing-echo")
        outcome = apply_pending({edit["id"]: edit}, SimpleNamespace(apply=lambda _: (200, {})), e.wall())
        del outcome[edit["id"]]["kept_at"]
        e.pending.reconcile("north", outcome)
        assert edit["id"] in e.pending.of("north")
        calls = []
        replayed = apply_pending({edit["id"]: edit}, SimpleNamespace(apply=lambda _: calls.append(1) or (200, {})), e.wall(), outcome)
        assert calls == [1] and replayed[edit["id"]]["kept_at"] == edit["at"]


def test_restarted_domain_gives_a_reused_key_a_distinct_marker_at_equal_or_reversed_clocks():
    import math
    from w2cplatform.domain.pending import _load
    from w2cplatform.variables import FileVariables
    for change in (0, -600):
        with tempfile.TemporaryDirectory() as folder, site(FileVariables(folder)) as e, console(e) as url:
            first = e.pending.add("north", "POST", "/testsub/counters", {"name": "one"}, "same-key")
            own_console = AgentConsole(url, e.key, e.wall)
            old = apply_pending({first["id"]: first}, own_console, e.wall())
            assert old[first["id"]]["status"] == 201
            e.pending.reconcile("north", old)
            e.wall.t += change
            restarted = PendingEdits(FileVariables(folder), e.wall)
            second = restarted.add("north", "POST", first["path"], {"name": "two"}, "same-key")
            assert second["at"] == math.nextafter(first["at"], math.inf)
            e.wall.t -= 60
            assert restarted.add("north", "POST", second["path"], second["body"], "same-key") == second
            restarted.reconcile("north", old)
            assert restarted.of("north")[second["id"]] == second
            fresh = apply_pending({second["id"]: second}, own_console, e.wall(), old)
            assert fresh[second["id"]]["kept_at"] == second["at"] and fresh[second["id"]]["status"] == 422
            restarted.reconcile("north", fresh)
            assert restarted.of("north") == {} and e.vars.get("testsub/counters/two")[0] is None
            saved = _load(FileVariables(folder).get("domain/outcomes/north")[0], "outcomes")
            third = PendingEdits(FileVariables(folder), e.wall).add("north", "POST", first["path"], {"name": "three"}, "same-key")
            assert third["at"] == math.nextafter(saved[first["id"]]["kept_at"], math.inf)


def test_no_readable_saved_outcome_uses_only_the_domains_own_seconds():
    with site() as e:
        key = "unreadable-outcome"
        identity = edit_id("north", key)
        good = {"id": identity, "status": 200, "result": {}, "error": "", "what": "start",
                "at": e.wall(), "kept_at": e.wall()}
        malformed = ["{torn", "null", "[]", "{}"]
        malformed += [json.dumps({**good, "kept_at": value}) for value in (True, False, "1757500000", None, float("nan"), float("inf"), 10**400)]
        malformed += [json.dumps({**good, "status": True}), json.dumps({**good, "id": "another-edit"})]
        for raw in [None, *malformed]:
            e.vars.put("domain/outcomes/north", {} if raw is None else {identity: raw})
            entry = PendingEdits(e.vars, e.wall).add("north", "PUT", "/testsub/counters/one", {"start": 7}, key)
            assert entry["at"] == e.wall() and type(entry["at"]) is float
            e.vars.put("domain/pending/north", {})


def test_domain_backup_restore_keeps_completed_outcomes_and_distinct_markers_after_a_move():
    from w2cplatform.domain.agent import DomainAgent, DomainPublisher
    from w2cplatform.domain.carry import open_row
    from w2cplatform.domain.federation import Cluster, Federation
    from w2cplatform.domain.pending import _load
    from w2cplatform.domain.term import BACKUP_TAKEN, DomainHolder, move_domain
    from w2cplatform.trust.signer import Signer
    for change in (0, -600):
        with site() as e, console(e) as url, tempfile.TemporaryDirectory() as folder:
            objects = {name: FsObjectStore(folder + "/" + name) for name in ("north", "south")}
            south = FakeVariables()
            south_key = MemberKey.load_or_make(south)
            fed = Federation()
            fed.add(Cluster("north", e.vars, objects["north"], is_domain_holder=True))
            fed.add(Cluster("south", south, objects["south"]))
            signer = Signer("queue-move", e.vars, now=e.wall)
            DomainPublisher(e.vars).publish_keys(signer.tokens.keyset())
            holder = DomainHolder(fed, "north", signer, 1, wall=e.wall, objects=objects["north"])
            holder.claim()
            first = e.pending.add("north", "POST", "/testsub/counters", {"name": "one"}, "moved-key")
            own_console = AgentConsole(url, e.key, e.wall)
            outcome = apply_pending({first["id"]: first}, own_console, e.wall())
            assert outcome[first["id"]]["status"] == 201
            outcome[first["id"]]["result"]["password_secret"] = "private"
            e.pending.reconcile("north", outcome)
            outcome_path = "domain/outcomes/north"
            stored = e.vars.get(outcome_path)[0]
            old = _load(stored, outcome_path)
            assert "private" not in json.dumps(stored) and old[first["id"]]["result"]["password_secret"] == "***"
            exported = holder.export()
            holder.backup(["south"], objects["north"])
            keeper = DomainAgent("south", e.vars, south, now=e.wall, domain_objects=objects["north"],
                                 cluster_objects=objects["south"], key=south_key)
            assert keeper.sync() and south.get(BACKUP_TAKEN)[0] is not None
            moved, _ = move_domain(fed, "south", signer.backup(), "queue-move", objects.__getitem__, wall=e.wall)
            assert moved.term == 2 and moved.restored_from == {"term": 1, "rev": 1}
            restored_outcomes = south.get(outcome_path)[0]
            e.wall.t += change
            pending = PendingEdits(south, e.wall)
            second = pending.add("north", "POST", first["path"], {"name": "two"}, first["key"])
            pending.reconcile("north", old)
            assert second["id"] in pending.of("north"), "the new holder settled a new edit with the old member outcome"
            assert second["at"] > first["at"]
            fresh = apply_pending({second["id"]: second}, own_console, e.wall(), old)
            assert fresh[second["id"]]["status"] == 422 and fresh[second["id"]]["kept_at"] == second["at"]
            pending.reconcile("north", fresh)
            assert pending.of("north") == {} and e.vars.get("testsub/counters/two")[0] is None
            assert open_row(signer.backup_sealer(), exported[outcome_path], outcome_path) == stored
            assert restored_outcomes == stored
            backup = json.loads(objects["south"].get(BACKUP_TAKEN))
            assert open_row(signer.backup_sealer(), backup["state"][outcome_path], outcome_path) == stored
            assert "private" not in json.dumps(backup["state"][outcome_path])


def test_a_marker_that_cannot_grow_to_another_finite_number_is_not_persisted():
    import sys
    with site() as e:
        key = "finite-ceiling"
        identity = edit_id("north", key)
        e.vars.put("domain/outcomes/north", {identity: json.dumps({"id": identity, "status": 200, "result": {}, "error": "",
                    "at": e.wall(), "what": "start", "kept_at": sys.float_info.max})})
        try:
            e.pending.add("north", "PUT", "/testsub/counters/one", {"start": 7}, key)
        except ValueError:
            pass
        else:
            raise AssertionError("a non-finite Edit.at must not be stored")
        assert e.pending.of("north") == {}


def test_a_reused_key_with_a_new_operation_after_the_backup_is_stranded_exactly():
    from w2cplatform.domain.term import exported, stranded
    with site() as e:
        first = e.pending.add("north", "POST", "/testsub/counters", {"name": "one"}, "same-key-after-backup")
        snapshot = {path: e.vars.get(path)[0] for prefix in exported() for path in e.vars.list(prefix)}
        outcome = apply_pending({first["id"]: first}, SimpleNamespace(apply=lambda _: (201, {"name": "one"})), e.wall())
        e.pending.reconcile("north", outcome)
        second = e.pending.add("north", "POST", first["path"], {"name": "two"}, first["key"])
        assert second["id"] == first["id"] and second["body"] != first["body"] and second["at"] != first["at"]
        assert stranded(e.vars, snapshot) == [["domain/pending/north", second["id"],
                                               json.dumps(second, ensure_ascii=False, sort_keys=True)]]


def test_a_stranded_edit_is_resubmitted_as_the_original_crud_with_the_same_key():
    import io
    from w2cplatform.domain.console import Console
    with site() as e:
        old = Console(None, None, e.api, signer_url="http://old-holder")
        calls = []
        class Reply(io.BytesIO):
            status = 202
        def answer(request, **kwargs):
            if isinstance(request, str):
                assert request == "http://new-holder/api/holder"
                return Reply(b'{"console":"http://new-console"}')
            calls.append(request)
            return Reply(b'{"kept":"edit","cluster":"north"}')
        for method, route, body in (("POST", "/testsub/counters", {"name": "one"}),
                                    ("PUT", "/testsub/counters/one", {"start": 7}),
                                    ("DELETE", "/testsub/counters/one", {})):
            entry = e.pending.add("north", method, route, body, "stranded-"+method)
            item = {"path": "domain/pending/north", "key": entry["id"], "value": json.dumps(entry)}
            old.ask_signer = lambda *args: (200, {"deposed_by": {"holder": "south", "term": 2, "url": "http://new-holder"}, "stranded": [item]})
            with patch("urllib.request.urlopen", answer):
                status, reply = old.stranded_apply({"path": item["path"], "key": item["key"]}, "person-token")
            assert status == 202 and reply["kept"]
            request = calls[-1]
            assert request.method == method and request.get_header("Idempotency-key") == entry["key"]
            assert request.get_header("Authorization") == "Bearer person-token"
            assert request.full_url == "http://new-console/domain" + route + ("" if method == "POST" else "?cluster=north")
            assert json.loads(request.data) == ({**body, "cluster": "north"} if method == "POST" else body)


def test_domain_rejects_wrong_field_types_and_schema_before_persisting_an_edit():
    with site(fields={"budget": {"type": "int", "schema": {"minimum": 1}}}) as e:
        # The same declared domain.edit set, extended by this test's own spec.
        for schema in e.specs:
            schema.domain.edit = tuple(schema.domain.edit) + ("budget",)
        for number, value in enumerate((0, 1.5, "yes", True, None)):
            raises(400, lambda: e.api.queue("PUT", "testsub", e.specs[0].rows, "1",
                                          {"budget": value}, str(number), "north"))
            assert e.pending.of("north") == {}
        reply = e.api.queue("PUT", "testsub", e.specs[0].rows, "1", {"budget": 2}, "valid", "north")
        assert reply["kept"] in e.pending.of("north")
