"""The request door and the reaper after the fourteenth review (`РЕВЬЮ-SERVERVMS-14.md`), each test the review's scenario:

    major 1    the same `rid` under another person's request at the door: 409 `exists`, not 202 with the stranger's row;
               the place it took in its person's ledger given back; the same request again — 202 with its row, as before
    ADR 0060   a person's ledger is `<sub>/asked/<sha>`, beside the family: a `rid` of any name is a request, and none
               reads anybody's ledger
    rid.tsv    one table of request names, the door's and `Worker.file_request`'s («Паритет»'s `testdata/rid.tsv`)
    minor 2    a request row a ledger names that does not parse: kept and counted, garbled on `/metrics`, 202 — not 500
    minor 6    an idempotency claim with no tag answers nobody: 422, not the reply of whoever it was
    minor 10   a non-finite `at` in `file_request`: `RequestRefused`, counted
    minor 12   a begun request whose mark does not read and that names no holder: past its deadline it ends `unknown`
"""
import copy
import json
import os

import yaml

from tests.conftest import TESTSUB2, Box, Served, controller, testsub2
from w2cplatform import requests
from w2cplatform.console import SpecConsole
from w2cplatform.spec import SubsystemSpec
from w2cplatform.worker import RequestRefused, Worker

TESTDATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "testdata")


def _spec(key: bool = True, per_person: bool = True):
    """testsub2 as its file says it, or — built here, the spec's bytes are «Паритет»'s — with the body's `id` naming a
    request (no `key`), as `vms.subsystem.yaml` names one, and an `id` and a `note` in its schema."""
    if key and per_person:
        return testsub2()
    testsub2()
    d = copy.deepcopy(yaml.safe_load(open(TESTSUB2)))
    r = d["requests"]
    r["schema"]["properties"].update(id={"type": "string"}, note={"type": "string"})
    if not key:
        r.pop("key")
    if not per_person:
        r.pop("per_person")
    return SubsystemSpec.from_dict(d)


def _door(spec):
    box = Box()
    ctl = controller(box, spec=spec)
    for t in ("t1", "t2"):
        ctl.create({"name": t, "of": "c1"})
    return box, ctl, SpecConsole(ctl, wall=box.wall)


def _held(box, spec, who):
    it = box.vars.get(spec.sub.asked_key(who))[0]
    return [r for r, _ in json.loads(it["asks"])] if it else []


def as_(who):
    return {"X-User": who}


class _Bare(Worker):
    def reconcile_once(self, now=None):
        return []


def _filer(box):
    """A worker of a subsystem whose spec files to testsub2 (`worker.requests`), slot `f-1`."""
    testsub2()
    spec = SubsystemSpec.from_dict({"name": "filer", "unit": {"rows": "fs", "id": "name",
                                                              "fields": {"name": {"type": "string", "required": True}}},
                                    "placement": {"capacity": {"from": "capacity", "default": 4}},
                                    "worker": {"requests": ["testsub2"]}})
    w = _Bare(spec.sub, None, box.vars, box.objects, clock=box.clock, wall=box.wall, spec=spec,
              resource_root=box.resource_root)
    w.claim_slot("f-1")
    return w


# -- major 1 -----------------------------------------------------------------------------------------------------------
def test_another_persons_request_under_a_taken_rid_is_409_and_gives_back_its_place():
    """boris sends `{unit: t2, id: r1}` after anna's `{unit: t1, id: r1}`: it was 202 with `queued = {unit: t1, by: anna}`
    — boris's command not filed, anna's row shown to him, a place of his quota spent until `ttl`. Now 409 `exists`, the
    row anna filed stands as it was, and boris's ledger does not count r1. anna's own retry — later, so `at` and the
    deadline the door gives differ — is the same request: 202 with her row, counted once. What is asked decides, not who
    asks it (the door's stamps `by` and `at` are left out of the comparison): boris asking for exactly what anna asked is
    the same work — one fetch of one range on the recorder, whose requests the spec's `key` names by their range."""
    spec = _spec(key=False)
    box, ctl, con = _door(spec)
    with Served(con) as call:
        a = call("POST", "/requests", {"unit": "testsub2/t1", "add": 1, "id": "r1", "note": "anna's"}, headers=as_("anna"))
        assert a[0] == 202, a
        b = call("POST", "/requests", {"unit": "testsub2/t2", "add": 9, "id": "r1", "note": "boris's"}, headers=as_("boris"))
        assert b[0] == 409 and b[1]["error"] == "exists" and "queued" not in b[1], b
        assert "different request" in b[1]["detail"] and "t1" not in json.dumps(b[1]), b
        row = box.vars.get(spec.sub.request_key("r1"))[0]
        assert (row["unit"], row["by"], row["add"]) == ("t1", "anna", "1"), row
        assert _held(box, spec, "boris") == [] and _held(box, spec, "anna") == ["r1"]
        # the same person, another value: another request too
        c = call("POST", "/requests", {"unit": "testsub2/t1", "add": 2, "id": "r1", "note": "anna's"}, headers=as_("anna"))
        assert c[0] == 409 and _held(box, spec, "anna") == ["r1"], c
        # …while what is asked decides, not who: boris asking for exactly anna's request asks for the same work — 202
        # with its row, one row, and it counts among his open requests, as it did
        f = call("POST", "/requests", {"unit": "testsub2/t1", "add": 1, "id": "r1", "note": "anna's"}, headers=as_("boris"))
        assert f[0] == 202 and f[1]["queued"]["by"] == "anna" and _held(box, spec, "boris") == ["r1"], f
        # the same request again, five seconds on: the door's `at` and its own deadline are its moments, not the request
        box.wall.advance(5)
        d = call("POST", "/requests", {"unit": "testsub2/t1", "add": 1, "id": "r1", "note": "anna's"}, headers=as_("anna"))
        assert d[0] == 202 and d[1]["queued"]["by"] == "anna" and d[1]["queued"]["at"] == row["at"], d
        assert _held(box, spec, "anna") == ["r1"]
        # …but a deadline the person gives is the request's: another one is another request
        e = call("POST", "/requests", {"unit": "testsub2/t1", "add": 1, "id": "r1", "note": "anna's",
                                       "valid_until": box.wall() + 100}, headers=as_("anna"))
        assert e[0] == 409, e


def test_a_worker_and_a_person_under_one_rid_are_both_refused_by_one_rule():
    """The review: a worker and a person under one `rid` — the worker refused with its count, the person a silent
    "success". One function judges both now (`requests.filed_already`)."""
    spec = _spec(key=False)
    box, ctl, con = _door(spec)

    w = _filer(box)
    assert w.file_request("testsub2", "shared", {"unit": "t1", "add": 1})
    with Served(con) as call:
        r = call("POST", "/requests", {"unit": "testsub2/t1", "add": 1, "id": "shared"}, headers=as_("anna"))
        assert r[0] == 409 and r[1]["error"] == "exists", r
        assert call("POST", "/requests", {"unit": "testsub2/t1", "add": 1, "id": "mine"}, headers=as_("anna"))[0] == 202
    try:
        w.file_request("testsub2", "mine", {"unit": "t1", "add": 1})
        raise AssertionError("filed over a person's request")
    except RequestRefused as e:
        assert "different request" in str(e)
    assert w.filings == {"filed": 1, "again": 0, "refused": 1}


# -- ADR 0060: the ledger beside the family ------------------------------------------------------------------------------
def test_a_rid_named_like_a_ledger_is_a_request_and_reads_nobodys_ledger():
    """minor 1 of the review, closed by ADR 0060 rather than by a prefix: a `rid` of `asks-<anna's hash>` returned anna's
    ledger (the names and ids of her requests). A ledger is `<sub>/asked/<sha>` now; such a rid is a request like any
    other, filed and answered, and anna's ledger is where it was, unread by mallory."""
    import hashlib
    spec = _spec(key=False)
    box, ctl, con = _door(spec)
    with Served(con) as call:
        assert call("POST", "/requests", {"unit": "testsub2/t1", "add": 1, "id": "secret-anna"}, headers=as_("anna"))[0] == 202
        victim = "asks-" + hashlib.sha256(b"anna").hexdigest()[:16]
        r = call("POST", "/requests", {"unit": "testsub2/t1", "add": 1, "id": victim}, headers=as_("mallory"))
        assert r[0] == 202 and r[1]["queued"]["by"] == "mallory" and "asks" not in r[1]["queued"], r
        assert "secret-anna" not in json.dumps(r[1])
    assert box.vars.list(spec.sub.asked_prefix()) == sorted([spec.sub.asked_key("anna"), spec.sub.asked_key("mallory")])
    assert _held(box, spec, "anna") == ["secret-anna"]
    assert sorted(k.rsplit("/", 1)[1] for k in box.vars.list(spec.sub.requests_prefix())) == sorted(["secret-anna", victim])
    # the ledgers are the console's: its grant writes them, a worker's and the controller's read none
    from w2cplatform.cluster.rights import roles
    acl = roles([spec], "test")
    assert f"{spec.name}/asked/*" in acl["console"]["write"]
    assert f"!{spec.name}/asked/*" in acl[f"{spec.name}worker"]["read"]
    assert f"!{spec.name}/asked/*" in acl[f"{spec.name}controller"]["read"]


def test_an_old_ledger_row_in_the_family_is_neither_read_nor_carried():
    """ADR 0003: a `<sub>/requests/asks-…` row from before is a row of the family like any other — no ledger reads it,
    nothing moves it; a person's count starts in `<sub>/asked/`."""
    import hashlib
    spec = _spec()
    box, ctl, con = _door(spec)
    old = spec.sub.request_key("asks-" + hashlib.sha256(b"anna").hexdigest()[:16])
    box.vars.put(old, {"asks": json.dumps([["t1-1", box.wall()], ["t1-2", box.wall()], ["t1-3", box.wall()]]),
                       "by": "anna", "at": str(box.wall())})
    with Served(con) as call:
        assert call("POST", "/requests", {"unit": "testsub2/t1", "add": 7}, headers=as_("anna"))[0] == 202
    assert _held(box, spec, "anna") == ["t1-7"]
    assert box.vars.get(old)[0]["by"] == "anna"                                     # left as it was


# -- the rid table -------------------------------------------------------------------------------------------------------
def _rid_rows():
    out = []
    for line in open(os.path.join(TESTDATA, "rid.tsv"), encoding="utf-8"):
        line = line.rstrip("\n")
        if not line or line.startswith("#"):
            continue
        rid, verdict = line.split("\t")
        out.append((json.loads(rid), verdict))
    return out


def test_the_rid_table_is_read_by_the_door_and_by_file_request_alike():
    """«Паритет»'s `testdata/rid.tsv`, the product's byte for byte: at most 200 bytes of UTF-8, not empty, `.` or `..`, no
    `/ \\ " '`, no Cc, Zl, Zp. The door counted characters — 150 × «я» (300 bytes) went to the store and came back a 500,
    and so did `a\\u0085b`. Every row through both: the door's `id` (400 `bad id` / 202) and a worker's `file_request`
    (`RequestRefused`, counted in `filings.refused` / filed)."""
    rows = _rid_rows()
    assert len(rows) == 24 and {v for _, v in rows} == {"ok", "refused"}
    spec = _spec(key=False, per_person=False)
    box, ctl, con = _door(spec)

    w = _filer(Box())                                     # the worker files into a store of its own: the same names
    wrong = []
    with Served(con) as call:
        for i, (rid, verdict) in enumerate(rows):
            body = {"unit": "testsub2/t1", "add": i, "id": rid}
            status, reply = call("POST", "/requests", body, headers=as_("anna"), key=f"rid-{i}")
            door = "ok" if status == 202 else "refused" if (status, reply.get("error")) == (400, "bad id") else f"{status}"
            if door == "ok":
                assert reply["queued"]["id"] == (rid or f"rid-{i}"), reply      # `id: ""` is no id: the key names it
            try:
                w.file_request("testsub2", rid, {"unit": "t2", "add": i})
                worker = "ok"
            except RequestRefused:
                worker = "refused"
            want_door = "ok" if rid == "" else verdict           # …so at the door the empty one is never asked
            if door != want_door or worker != verdict:
                wrong.append((rid[:20], verdict, door, worker))
    assert not wrong, wrong
    assert w.filings["refused"] == sum(1 for _, v in rows if v == "refused")


# -- minor 2 -------------------------------------------------------------------------------------------------------------
def test_a_request_row_a_ledger_names_that_does_not_read_is_kept_and_counted_not_a_500():
    """vera's ledger reads; the row of her request `own-1` it names is torn. Past `settle` the ledger reads that row to
    keep the id — `vars.get` raised outside any `try`, and every request vera filed was a 500 until `ttl`, said nowhere.
    Now the entry stays (the row stands: it is counted towards her `per_person`), the row is counted garbled on
    `/metrics` (`console_rows_garbled{table="request_row"}`), and her request is 202, as the product answers."""
    spec = _spec(key=False)
    box, ctl, con = _door(spec)
    with Served(con) as call:
        assert call("POST", "/requests", {"unit": "testsub2/t1", "add": 1, "id": "own-1"}, headers=as_("vera"))[0] == 202
        with open(box.vars._file(spec.sub.request_key("own-1")), "wb") as f:
            f.write(b"{torn")
        box.wall.advance(spec.requests["settle"] + 1)
        r = call("POST", "/requests", {"unit": "testsub2/t1", "add": 1, "id": "own-2"}, headers=as_("vera"))
        assert r[0] == 202, r
        assert _held(box, spec, "vera") == ["own-1", "own-2"]
        lines = con.metrics_text().splitlines()
        assert 'testsub2_console_rows_garbled{table="request_row"} 1' in lines, [x for x in lines if "garbled" in x]
        assert call("POST", "/requests", {"unit": "testsub2/t1", "add": 1, "id": "own-3"}, headers=as_("vera"))[0] == 202
        r = call("POST", "/requests", {"unit": "testsub2/t1", "add": 1, "id": "own-4"}, headers=as_("vera"))
        assert r[0] == 429 and r[1]["error"] == "too many", r                    # the torn one holds its place
        lines = con.metrics_text().splitlines()
        assert 'testsub2_console_rows_garbled{table="request_row"} 1' in lines   # one row, counted once


# -- minor 6 -------------------------------------------------------------------------------------------------------------
def test_an_idempotency_claim_that_says_no_caller_answers_nobody():
    """A claim with no `sub` and no `digest` — a branch for claims written before tags — matched anybody: a row put under
    `<sub>/idem/<key>` answered any caller's retry with its reply. No console writes such a claim; one is refused, 422
    `key reused`, and nothing is written (ADR 0003)."""
    spec = _spec(key=False)
    box, ctl, con = _door(spec)
    box.vars.put(f"{spec.name}/idem/K-old", {"state": "done", "status": 202, "at": box.wall(),
                                             "body": json.dumps({"queued": {"id": "x", "by": "admin"}})})
    with Served(con) as call:
        r = call("POST", "/requests", {"unit": "testsub2/t1", "add": 1, "id": "y"}, headers=as_("mallory"), key="K-old")
        assert r[0] == 422 and r[1]["error"] == "key reused", r
        assert box.vars.get(spec.sub.request_key("y"))[0] is None
        # a claim this console makes carries its tag, and its retry is answered as before
        a = call("POST", "/requests", {"unit": "testsub2/t1", "add": 1, "id": "z"}, headers=as_("anna"), key="K-new")
        assert a[0] == 202 and call("POST", "/requests", {"unit": "testsub2/t1", "add": 1, "id": "z"},
                                    headers=as_("anna"), key="K-new") == a


# -- minor 10 ------------------------------------------------------------------------------------------------------------
def test_a_non_finite_moment_is_refused_and_counted():
    """`file_request(..., at=nan)` raised a bare `ValueError` from `number_text` — not `RequestRefused`, not counted, and
    the autoworker's scenario stood `waiting` on it. Now it is refused like any filing that may not be, and counted."""
    box = Box()
    testsub2()

    w = _filer(box)
    for bad in (float("nan"), float("inf"), "soon", 10 ** 400, True):
        try:
            w.file_request("testsub2", "r", {"unit": "t1", "add": 1}, at=bad)
            raise AssertionError(f"filed at {bad!r:.20}")
        except RequestRefused as e:
            assert "finite number" in str(e)
    assert w.filings == {"filed": 0, "again": 0, "refused": 5} and box.vars.list("testsub2/requests/") == []
    assert w.file_request("testsub2", "r", {"unit": "t1", "add": 1}, at=box.wall() - 3)


# -- minor 12 ------------------------------------------------------------------------------------------------------------
def test_a_begun_request_whose_mark_does_not_read_ends_unknown_past_its_deadline():
    """A request row with a deadline, its mark torn (or naming no instance), no holder: `said = {}`, begun, and
    `_holder_still_there({})` is "still there" — five hours on the row stood. An unreadable mark is nobody's: past the
    deadline the row is deleted by CAS, counted `unknown`, and `complete_mark` writes `unknown` over the torn mark by the
    index it read — whoever asked reads an outcome."""
    spec = testsub2()
    box = Box()
    ctl = controller(box, spec=spec)
    now = box.wall()
    for rid, mark in (("torn", b"{not json"), ("nameless", json.dumps({"unit": "t1", "at": now}).encode()),
                      ("list", b"[1, 2]")):
        box.vars.put(spec.sub.request_key(rid), {"unit": "t1", "add": "1", "at": str(now), "by": "anna",
                                                 "valid_until": str(now + 10)})
        box.objects.put(spec.sub.command_key(rid), mark)
    was = requests.unknown.get(spec.name, 0)
    requests.clear_requests(ctl, sweep=True)
    assert len(box.vars.list(spec.sub.requests_prefix())) == 3                    # not past the deadline yet: they wait
    box.wall.advance(10 + requests.REAP_AFTER + 1)
    requests.clear_requests(ctl, sweep=True)
    assert box.vars.list(spec.sub.requests_prefix()) == []
    assert requests.unknown.get(spec.name, 0) == was + 3
    for rid in ("torn", "nameless", "list"):
        m = json.loads(box.objects.get(spec.sub.command_key(rid)))
        assert m["outcome"] == "unknown" and "does not read" in m["error"], (rid, m)
