"""A unit is `<sub>/<id>`, and what it is ABOUT is its spec's word (the boundary's step 2, ГРАНИЦА-ПЛАТФОРМЫ-И-
ПОДСИСТЕМЫ.md §2.1; the keys agreed with the product).

The platform had a subsystem's field as one of its own: an index column, a query parameter, a mark's body, a
grant's scope, a field the controller kept from changing, a gate that asked a subsystem's hooks whose a row was.
Now a spec says it:

    about: {sub, field}            every unit of this subsystem is about one unit of another, named by that field
    fields.<f>.fixed: true         set at creation, never changed — the about-field is one
    rights: {unit_of: {table: f}}  a row of that table is the unit its field names

and the platform names a unit `<sub>/<id>` and nothing else: the events index's columns `unit` and `of`,
`/events?unit=`, `POST /marks {unit}`, a grant's `unit:` scope. A bare id is refused wherever a unit is named.

Everything here runs on testsub and a second subsystem invented for the purpose — no subsystem of the product is
imported (`test_boundary.py` holds this file to that).
"""
import json
import os
import tempfile
import urllib.error
import urllib.request

from w2cplatform.access import Denied
from w2cplatform.console import Mount, SpecConsole
from w2cplatform.doors import parse_ref, ref_fault, unit_ref
from w2cplatform.eventdatabase import EventIndex, MergedIndex
from w2cplatform.events import EventLog, read_bucket
from w2cplatform.objects import FsObjectStore
from w2cplatform.spec import Refused, SpecController, SubsystemSpec
from w2cplatform.variables import FileVariables

HERE = os.path.dirname(os.path.abspath(__file__))
TESTSUB = os.path.join(HERE, "testdata", "testsub.subsystem.yaml")

# A second subsystem, ABOUT testsub's counters: a tally is about one counter, and its notes (a table) are each about
# one counter too.
TALLY = {"name": "tally", "about": {"sub": "testsub", "field": "counter"},
         "unit": {"rows": "tallies", "id": "name",
                  "fields": {"name": {"type": "string", "required": True},
                             "counter": {"type": "string", "required": True, "fixed": True},
                             "labels": {"type": "list"}}},
         "tables": ["notes"], "rights": {"unit_of": {"notes": "counter"}},
         "placement": {"capacity": {"from": "capacity", "default": 4}}}


class Clock:
    def __init__(self, t): self.t = t
    def __call__(self): return self.t


def _box():
    root = tempfile.mkdtemp(prefix="about-")
    return root, FileVariables(os.path.join(root, "config")), FsObjectStore(os.path.join(root, "objects")), Clock(1_757_500_000.0)


def _http(base, method, path, body=None, token=None):
    _http.n = getattr(_http, "n", 0) + 1
    headers = {"Idempotency-Key": f"k-{_http.n}", "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(base + path, method=method, headers=headers,
                                 data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null")


class Grants:
    """An `Access` with no cryptography: a token is a name, a grant is `(capability, unit or None, labels)` — units
    named as the platform names them. Every question it is asked is kept, to say which unit the gate asked about."""
    def __init__(self, grants):
        self.grants, self.asked = grants, []

    def who(self, token):
        if token not in self.grants:
            raise Denied(401, "nobody's token")
        return {"sub": token}

    def may(self, payload, capability, unit, labels):
        self.asked.append((capability, unit, tuple(labels)))
        rank = {"view": 0, "edit": 1, "admin": 2}
        mine = self.grants[payload["sub"]]
        if unit is None and capability == "view":
            return bool(mine)
        return any(rank[c] >= rank[capability] and ((set(lab) <= set(labels)) if lab else u in (unit, None))
                   for c, u, lab in mine)


# -- the names ------------------------------------------------------------------------------------------------------

def test_a_unit_is_named_sub_slash_id_and_a_bare_id_names_nothing():
    """`<sub>/<id>`, one string: the id has no `/` of its own, neither half is empty, neither is a path."""
    assert unit_ref("testsub", "c1") == "testsub/c1" and parse_ref("testsub/c1") == ("testsub", "c1")
    assert parse_ref("other/a-b") == ("other", "a-b") and parse_ref("tally/7") == ("tally", "7")
    for bad in ("c1", "7", "", "/c1", "testsub/", "testsub/a/b", "../c1", "testsub/..", None, 7, ["testsub/c1"]):
        assert parse_ref(bad) is None and ref_fault(bad), bad


# -- the spec ---------------------------------------------------------------------------------------------------------

def test_about_names_another_subsystem_and_a_fixed_field_of_the_row_and_nothing_else_loads():
    """`about:` is `{sub, field}` — another subsystem, a field of this row that says `fixed: true` — and `rights.unit_of`
    names this spec's own tables. Anything else is refused when the spec is loaded, not when a gate reads a row by it."""
    spec = SubsystemSpec.from_dict(TALLY)
    assert (spec.about_sub, spec.about_field, spec.unit_of) == ("testsub", "counter", {"notes": "counter"})
    assert spec.fields["counter"].fixed and not spec.fields["name"].fixed
    assert spec.of_row({"counter": "c1"}) == "testsub/c1" and spec.of_row({"counter": ""}) == "" and spec.of_row(None) == ""
    assert spec.of_row({"counter": "testsub/c1"}) == "testsub/c1"            # a value written as a reference stays
    assert spec.table_unit("notes", {"counter": "c2"}) == ("testsub/c2", True)
    assert spec.table_unit("notes", {}) == ("", True) and spec.table_unit("volumes", {"counter": "c2"}) == ("", False)
    assert SubsystemSpec.load(TESTSUB).about_sub == ""                      # about nothing but itself

    def refused(change, why):
        d = json.loads(json.dumps(TALLY))
        change(d)
        try:
            SubsystemSpec.from_dict(d)
        except ValueError as e:
            assert why in str(e), (why, str(e))
        else:
            raise AssertionError(f"loaded: {why}")
    refused(lambda d: d["unit"]["fields"]["counter"].pop("fixed"), "fixed: true")
    refused(lambda d: d["about"].update(field="nope"), "about.field names no field")
    refused(lambda d: d["about"].update(sub="tally"), "another subsystem")
    refused(lambda d: d.update(about="testsub"), "`about:` is")
    refused(lambda d: d["about"].update(sub="../x"), "`about:` is")
    refused(lambda d: d["rights"]["unit_of"].update(volumes="counter"), "not one of its tables")
    refused(lambda d: d.update(rights={"colour": {}}), "`rights:` takes")
    refused(lambda d: d["unit"]["fields"]["counter"].update(fixed="yes"), "`fixed` is true or false")


def test_a_fixed_field_does_not_change_and_a_deleted_name_comes_back_only_with_the_same_value():
    """The rule the controller kept for one subsystem's field by its name is now `fixed: true` in any spec: an edit that
    changes it is refused, the same value is no change (a page sends the whole form), and a name deleted and created
    again about another unit is refused — whatever was written under the name is still the first one's."""
    root, vars_, objects, wall = _box()
    con = SpecController(SubsystemSpec.from_dict(TALLY), vars_.as_writer("console", SubsystemSpec.from_dict(TALLY).acl_console()),
                         objects, wall=wall)
    con.create({"name": "t1", "counter": "c1"})
    assert con.update("t1", {"counter": "c1", "labels": ["x"]})["labels"] == ["x"]
    try:
        con.update("t1", {"counter": "c2"}); raise AssertionError("moved to another counter")
    except Refused as e:
        assert "`counter` is fixed" in str(e)
    con.delete("t1")
    try:
        con.create({"name": "t1", "counter": "c2"}); raise AssertionError("the name came back about another counter")
    except Refused as e:
        assert "was counter c1's" in str(e)
    assert con.create({"name": "t1", "counter": "c1"})["revision"] > 1     # …and about the same one, it comes back


# -- the line and the index -------------------------------------------------------------------------------------------

def test_a_line_says_what_its_unit_is_about_as_a_reference_or_not_at_all():
    """`of` is the index's second column: the log's (`EventLog(of=)`) unless the line names its own, a reference either
    way — a bare id or a number there is refused where the line is written — and an empty one is not written."""
    root = tempfile.mkdtemp(prefix="of-")
    p = EventLog(root, "tally", "t1", 1, of="testsub/c1").append(10.0, "seen")
    q = EventLog(root, "tally", "t1", 1, of="testsub/c1").append(11.0, "seen", of="testsub/c9")
    r = EventLog(root, "tally", "t2", 1).append(12.0, "seen", of="")
    assert [e.get("of") for e in read_bucket(p)] == ["testsub/c1", "testsub/c9"] and p == q
    assert "of" not in read_bucket(r)[0]
    for bad in ("c1", 7, "testsub/a/b"):
        try:
            EventLog(root, "tally", "t1", 1).append(13.0, "seen", of=bad); raise AssertionError(f"took of={bad!r}")
        except ValueError as e:
            assert "<sub>/<id>" in str(e)


def test_a_query_for_a_unit_answers_its_own_lines_and_those_of_every_unit_about_it():
    """`query(unit="testsub/c1")`: testsub's own lines of c1, and the lines of tallies about c1 — whatever they are
    named; nothing of c2's, nothing of a tally about c2. Every row says its own unit and what it is about as
    references. With `subsystem`, only that subsystem's rows of it. A bare id is refused: whose `c1` would it be?"""
    root = tempfile.mkdtemp(prefix="index-")
    EventLog(root, "testsub", "c1", 1).append(100.0, "counted", n=1)
    EventLog(root, "testsub", "c2", 1).append(101.0, "counted", n=2)
    EventLog(root, "tally", "lobby", 1, of="testsub/c1").append(102.0, "tallied")
    EventLog(root, "tally", "other", 1, of="testsub/c2").append(103.0, "tallied")
    db = EventIndex(root, "srv-1", wall=Clock(200.0))
    rows = db.query(0, 1e12, unit="testsub/c1")["events"]
    assert [(e["unit"], e["of"], e["kind"]) for e in rows] == [("testsub/c1", "", "counted"), ("tally/lobby", "testsub/c1", "tallied")]
    assert [e["unit"] for e in db.query(0, 1e12, unit="testsub/c1", subsystem="tally")["events"]] == ["tally/lobby"]
    assert [e["unit"] for e in db.query(0, 1e12, unit="tally/other")["events"]] == ["tally/other"]
    assert len(db.query(0, 1e12)["events"]) == 4
    # a unit read once and found about another is passed by without being read again
    reads = []
    real = db._lines
    db._lines = lambda path: reads.append(path) or real(path)
    db.query(0, 1e12, unit="testsub/c1")
    assert not any("/other/" in p for p in reads), reads
    for bad in ("c1", "7", "testsub/"):
        try:
            db.query(0, 1e12, unit=bad); raise AssertionError(f"answered unit={bad!r}")
        except ValueError as e:
            assert "<sub>/<id>" in str(e)


def test_the_merge_refuses_a_bare_unit_before_it_asks_anybody():
    """The merge reads a resource's refusal as "did not answer": a caller's bare id would come back as an outage that
    never happened. Refused here, the same words as the index's."""
    asked = []
    m = MergedIndex(FsObjectStore(tempfile.mkdtemp(prefix="merge-")), fetch=lambda url, p: asked.append(p) or {"events": []})
    try:
        m.query(0, 1e12, unit="c1"); raise AssertionError("asked with a bare id")
    except ValueError as e:
        assert "<sub>/<id>" in str(e) and asked == []


# -- the console --------------------------------------------------------------------------------------------------------

def _consoles(access=None):
    """A process that fronts testsub at `/` and tally at `/tally`, its index over one tree, its journal beside it —
    and, for tally's table of notes, the route a subsystem would add (`extra`): the platform serves no table."""
    root, vars_, objects, wall = _box()
    tree = os.path.join(root, "events")
    base_spec, tally_spec = SubsystemSpec.load(TESTSUB), SubsystemSpec.from_dict(TALLY)
    acl = base_spec.acl_console() + tally_spec.acl_console()
    ctl = SpecController(base_spec, vars_.as_writer("console", acl), objects, wall=wall)
    tally = SpecController(tally_spec, vars_.as_writer("console", acl), objects, wall=wall)

    def notes(h, method, path, q):
        if method == "POST" and path == "/notes":
            body = json.loads(h.rfile.read(int(h.headers.get("Content-Length", 0))) or b"{}")
            tally.vars.put(tally_spec.sub.config("notes", body["id"]), {"counter": body["counter"]})
            return 201, {"note": body["id"]}
        if method == "DELETE" and path.startswith("/notes/"):
            tally.vars.delete(tally_spec.sub.config("notes", path.split("/")[2]))
            return 200, {"deleted": True}
        return None
    root_con = SpecConsole(ctl, marks_root=tree, index=EventIndex(tree, "srv-1", wall=wall), wall=wall)
    tally_con = SpecConsole(tally, index=root_con.index, wall=wall, extra=notes)
    tally_con.EDIT_ROUTES = SpecConsole.EDIT_ROUTES + ("/notes",)
    tally_con.ID_ROUTES = ("notes",)
    m = Mount(root_con, {"tally": tally_con})
    if access is not None:
        for c in (root_con, tally_con):
            c.gate.impl = access
    srv = m.serve("127.0.0.1", 0)
    return srv, f"http://127.0.0.1:{srv.server_address[1]}", ctl, tally, tree, root_con


def test_events_and_marks_name_a_unit_as_sub_slash_id_and_a_bare_id_is_400():
    """`GET /events?unit=testsub/c1` — its own lines and a tally's about it; `POST /marks {unit: "testsub/c1"}` — the
    console's line, about that unit (`of`), found by the same query. A bare id is 400 at both, and so is a mark that
    names no unit: the console names a unit `<sub>/<id>`, and its old field of one subsystem's is gone with the
    numeric rule."""
    srv, base, ctl, tally, tree, con = _consoles()
    try:
        assert _http(base, "POST", "/counters", {"name": "c1"})[0] == 201     # through the door: a journal line
        tally.create({"name": "lobby", "counter": "c1"})
        EventLog(tree, "testsub", "c1", 1).append(con.wall() - 30, "counted")
        EventLog(tree, "tally", "lobby", 1, of="testsub/c1").append(con.wall() - 20, "tallied")
        st, out = _http(base, "POST", "/marks", {"unit": "testsub/c1", "note": "look"})
        assert st == 201, out
        st, out = _http(base, "GET", "/events?unit=testsub/c1")
        assert st == 200 and [(e["kind"], e["unit"].split("/")[0], e["of"]) for e in out["events"]] == [
            ("counted", "testsub", ""), ("tallied", "tally", "testsub/c1"), ("mark", "console", "testsub/c1")], out
        assert _http(base, "GET", "/tally/events?unit=testsub/c1&subsystem=tally")[1]["events"][0]["unit"] == "tally/lobby"
        for path in ("/events?unit=c1", "/events?unit=7", "/events?unit=testsub/c1/x"):
            st, out = _http(base, "GET", path)
            assert st == 400 and "<sub>/<id>" in json.dumps(out), (path, st, out)
        for body in ({"unit": "c1", "note": "x"}, {"note": "x"}, {"unit": 7}):
            st, out = _http(base, "POST", "/marks", body)
            assert st == 400, (body, st, out)
        # the journal says what a line is about as `sub` and `target`: `of` is the index's column
        made = [e for e in _http(base, "GET", "/events?subsystem=audit")[1]["events"] if e["kind"] == "unit.created"]
        assert made and all(e["sub"] in ("testsub", "tally") and e["of"] == "" for e in made), made
        # …and `/spec` says what a subsystem's units are about, and which fields are fixed
        spec = _http(base, "GET", "/tally/spec")[1]
        assert spec["about"] == {"sub": "testsub", "field": "counter"}
        assert [f["name"] for f in spec["fields"] if f.get("fixed")] == ["counter"]
    finally:
        srv.shutdown(); srv.server_close()


def test_a_grant_on_a_unit_takes_in_the_units_about_it_and_the_labels_are_the_about_units():
    """The gate asks about a unit with what it is about (`about`): a grant on testsub/c1 sees and edits tally/lobby,
    which is about c1, and nothing about c2; a grant by labels is matched against c1's labels, not the tally's own
    (which say where it runs). On `/events` the same: a line is its own unit's and its about-unit's."""
    access = Grants({"ann": [("admin", "testsub/c1", ())], "bob": [("view", None, ("floor-1",))],
                     "cat": [("view", "tally/lobby", ())], "root": [("admin", None, ())]})
    srv, base, ctl, tally, tree, con = _consoles(access)
    try:
        ctl.create({"name": "c1", "labels": ["floor-1"]}); ctl.create({"name": "c2", "labels": ["floor-2"]})
        tally.create({"name": "lobby", "counter": "c1", "labels": ["floor-2"]})
        tally.create({"name": "yard", "counter": "c2", "labels": ["floor-1"]})
        EventLog(tree, "tally", "lobby", 1, of="testsub/c1").append(con.wall() - 20, "tallied")
        EventLog(tree, "tally", "yard", 1, of="testsub/c2").append(con.wall() - 10, "tallied")
        # ann holds c1: the tally about c1 is hers to see and to change; the one about c2 is not
        listed = _http(base, "GET", "/tally/tallies", token="ann")[1]
        assert [r["id"] for r in listed["configured"]] == ["lobby"]
        assert _http(base, "PUT", "/tally/tallies/lobby", {"labels": ["x"]}, token="ann")[0] == 200
        assert _http(base, "PUT", "/tally/tallies/yard", {"labels": ["x"]}, token="ann")[0] == 403
        assert ("admin", "tally/yard", ("floor-2",)) in access.asked                 # asked with c2's labels…
        assert ("admin", "testsub/c2", ("floor-2",)) in access.asked                 # …and of c2, what it is about
        assert [e["unit"] for e in _http(base, "GET", "/events", token="ann")[1]["events"]] == ["tally/lobby"]
        # bob's grant is by labels: the about-unit's — c1's floor-1 — not lobby's own floor-2
        assert [r["id"] for r in _http(base, "GET", "/tally/tallies", token="bob")[1]["configured"]] == ["lobby"]
        assert [e["unit"] for e in _http(base, "GET", "/events", token="bob")[1]["events"]] == ["tally/lobby"]
        # cat holds the tally itself: that one, and not the counter it is about
        assert [r["id"] for r in _http(base, "GET", "/tally/tallies", token="cat")[1]["configured"]] == ["lobby"]
        assert [r["id"] for r in _http(base, "GET", "/counters", token="cat")[1]["configured"]] == []
        assert [e["unit"] for e in _http(base, "GET", "/events?kind=tallied", token="root")[1]["events"]] == ["tally/lobby", "tally/yard"]
    finally:
        srv.shutdown(); srv.server_close()


def test_a_row_of_a_table_is_its_units_and_whoever_writes_it_needs_that_unit():
    """`rights.unit_of`: a note is the counter's its `counter` names. Writing one needs the route's capability on that
    counter — asked of nobody wider when the request names no unit of its own — and lifting one is asked of the
    counter the STORED note names, whatever the request says."""
    access = Grants({"ann": [("edit", "testsub/c1", ())], "root": [("admin", None, ())]})
    srv, base, ctl, tally, tree, con = _consoles(access)
    try:
        ctl.create({"name": "c1"}); ctl.create({"name": "c2"})
        assert _http(base, "POST", "/tally/notes", {"id": "n1", "counter": "c1"}, token="ann")[0] == 201
        assert _http(base, "POST", "/tally/notes", {"id": "n2", "counter": "c2"}, token="ann")[0] == 403
        assert _http(base, "POST", "/tally/notes", {"id": "n2", "counter": "c2"}, token="root")[0] == 201
        assert _http(base, "DELETE", "/tally/notes/n2", token="ann")[0] == 403          # the stored note is c2's
        assert ("edit", "testsub/c2", ()) in access.asked
        assert _http(base, "DELETE", "/tally/notes/n1", token="ann")[0] == 200
        assert tally.vars.get("tally/notes/n2")[0] is not None and tally.vars.get("tally/notes/n1")[0] is None
    finally:
        srv.shutdown(); srv.server_close()


def test_the_resources_door_takes_a_unit_as_sub_slash_id_and_refuses_a_bare_one():
    """`GET <resource>/events?unit=` — what the merge asks — the same rule: a reference, else 400."""
    from w2cplatform.resource import Resource, serve as serve_resource
    root, vars_, objects, wall = _box()
    tree = os.path.join(root, "events")
    EventLog(tree, "testsub", "c1", 1).append(wall() - 10, "counted")
    EventLog(tree, "tally", "lobby", 1, of="testsub/c1").append(wall() - 5, "tallied")
    res = Resource(tree, "srv-1", "", vars_, objects, wall=wall)
    res.index = EventIndex(tree, "srv-1", wall=wall)
    srv = serve_resource(res, "127.0.0.1", 0)
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        st, out = _http(base, "GET", "/events?unit=testsub/c1")
        assert st == 200 and [e["unit"] for e in out["events"]] == ["testsub/c1", "tally/lobby"]
        assert _http(base, "GET", "/events?unit=c1")[0] == 400
    finally:
        srv.shutdown(); srv.server_close()
