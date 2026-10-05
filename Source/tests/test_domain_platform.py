"""The platform's domain on `testsub` alone (the boundary's «no hooks»; DOMAIN-PLATFORM.md): the domain knows the
subsystems by the `domain:` section of their specs and by nothing else. Two clusters of counters, each with the
platform's controller and a worker that holds what it is given; the domain finds a counter by the field the spec names,
lists the counters at the route the spec's row name makes, carries home the books the spec declares without reading
them, issues only the token kinds the spec declares, and backs up what the spec keeps."""
from __future__ import annotations

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TESTSUB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "testdata", "testsub.subsystem.yaml")


class Clock:
    def __init__(self, t: float = 1_757_500_000.0): self.t = t
    def __call__(self): return self.t
    def advance(self, s): self.t += s


def spec():
    from w2cplatform.spec import SubsystemSpec
    return SubsystemSpec.load(TESTSUB)                  # loaded: in this process's catalogue, as a subsystem's would be


def counter_worker(sub, vars_, objects, wall, instance: str, server: str):
    """testsub's worker, a stub: it takes each counter it was given and says so in its heartbeat."""
    from w2cplatform.contract import Worker

    class CounterWorker(Worker):
        def reconcile_once(self, now=None):
            units = self.assignment().units
            for u in units:
                if u not in self.epochs:
                    self.take_epoch(u)
            self.heartbeat([{"id": u, "name": u, "phase": "running", "position": "converged", "revision": 1,
                             "observed_revision": 1, "epoch": self.epochs.get(u, 0)} for u in units],
                           server=self.server, capacity=4, headroom=4 - len(units))
            return units

    w = CounterWorker(sub, None, vars_, objects, clock=wall, wall=wall, instance=instance)
    w.server = server
    w.claim_slot()
    return w


def cluster(name: str, wall, counters=(), holder: bool = False):
    """One cluster of counters: its own store and object store, the controller from the spec, one worker; the snapshot
    and the heartbeats published, as every cluster publishes them."""
    from w2cplatform.domain.federation import Cluster
    from w2cplatform.objects import FsObjectStore
    from w2cplatform.spec import SpecController
    from w2cplatform.variables import FileVariables
    s = spec()
    root = tempfile.mkdtemp(prefix=f"dom-{name}-")
    vars_, objects = FileVariables(os.path.join(root, "config"), volatile=True), FsObjectStore(os.path.join(root, "objects"))
    w = counter_worker(s.sub, vars_, objects, wall, f"{name}-I1", f"{name}-srv")
    w.reconcile_once()
    ctl = SpecController(s, vars_, objects, wall=wall, cluster=name)
    for c in counters:
        ctl.create({"name": c, "start": 7})
    ctl.ensure_placed()
    w.reconcile_once()
    ctl.publish_snapshot()
    return Cluster(name, vars_, objects, is_domain_holder=holder)


def site(wall=None):
    from w2cplatform.domain.federation import Federation
    wall = wall or Clock()
    fed = Federation()
    fed.add(cluster("north", wall, ("n1", "n2"), holder=True))
    fed.add(cluster("south", wall, ("s1",)))
    return fed, wall


def test_the_directory_finds_a_unit_across_clusters_by_the_field_its_spec_names():
    """`domain.ref: name` — a counter is found by its name in whichever cluster holds it, with the worker and server the
    snapshot says; a name nowhere is said to be nowhere, and a silent cluster makes the answer incomplete."""
    from w2cplatform.domain.federation import DomainDirectory
    fed, _ = site()
    d = DomainDirectory(fed)
    a = d.where("s1")
    assert a.found and a.cluster == "south" and a.sub == "testsub" and a.worker and a.server == "south-srv", a
    assert not d.where("nowhere").found and d.where("nowhere").complete
    held, down = d.holdings()
    assert sorted(held["north"][next(iter(held["north"]))]) == ["n1", "n2"] and not down


def test_the_read_view_lists_a_subsystems_units_and_the_shared_view_shows_the_fields_its_spec_declares():
    """The list of a subsystem of the directory, by its own row name; the shared view (`domain/view`) carries each
    unit's platform fields and the fields `domain.view` names — `start` here — and the tables `domain.tables` serves."""
    from w2cplatform.console import DOMAIN_VIEW
    from w2cplatform.domain.readview import ReadView
    fed, wall = site()
    view = ReadView(fed, wall=wall)
    view.refresh()
    rows = view.list(sub="testsub")["rows"]
    assert sorted(r["ref"] for r in rows) == ["n1", "n2", "s1"] and {r["sub"] for r in rows} == {"testsub"}
    north = fed.clusters["north"]
    north.vars.put("domain/testsub/ledger", {"n1": "counted"})
    view.publish(north.objects, {"testsub/ledger": north.vars.get("domain/testsub/ledger")[0]})
    shown = json.loads(north.objects.get(DOMAIN_VIEW))
    assert {u["ref"]: u.get("start") for u in shown["units"]} == {"n1": 7, "n2": 7, "s1": 7}
    assert shown["tables"] == {"testsub/ledger": {"n1": "counted"}}


def test_the_door_serves_the_units_and_a_declared_table_and_nothing_undeclared():
    """`/api/<sub>/<rows>` is the read view of a subsystem of the directory; `/api/<sub>/<table>` a row its spec keeps
    and serves; a table no spec declares, or another subsystem's name, is no route."""
    import urllib.error
    import urllib.request
    from w2cplatform.domain.api import ConsoleAPI
    from w2cplatform.domain.console import Console
    from w2cplatform.domain.federation import DomainDirectory
    from w2cplatform.domain.readview import ReadView
    fed, wall = site()
    north = fed.clusters["north"]
    north.vars.put("domain/testsub/ledger", {"s1": "seen"})
    north.vars.put("domain/testsub/hidden", {"x": "1"})
    view = ReadView(fed, wall=wall)
    view.refresh()
    con = Console(DomainDirectory(fed), view, ConsoleAPI(DomainDirectory(fed), lambda c: None), refresh_interval=60,
                  holder_vars=north.vars)
    srv = con.serve(port=0)
    base = f"http://127.0.0.1:{srv.server_address[1]}"

    def get(path):
        try:
            with urllib.request.urlopen(base + path) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, None
    try:
        st, body = get("/api/testsub/counters")
        assert st == 200 and sorted(r["ref"] for r in body["rows"]) == ["n1", "n2", "s1"]
        assert get("/api/testsub/ledger") == (200, {"s1": "seen"})
        assert get("/api/testsub/hidden")[0] == 404 and get("/api/nobody/counters")[0] == 404
    finally:
        con.stop(srv)


def test_a_member_carries_home_the_books_its_spec_declares_and_nothing_it_does_not():
    """The holder keeps a book for each member under `domain/<sub>/<book>/<member>`; the member's agent carries its own
    home as `domain/<sub>/<book>`, as it is. A row of the domain's prefix no spec declares is not carried."""
    from w2cplatform.domain.agent import DomainAgent, DomainPublisher, per_cluster
    from w2cplatform.trust.signer import Signer
    fed, wall = site()
    north, south = fed.clusters["north"], fed.clusters["south"]
    assert "domain/testsub/tallies" in per_cluster()
    signer = Signer("acme", north.vars, now=wall)
    DomainPublisher(north.vars).publish_keys(signer.tokens.keyset())
    north.vars.put("domain/testsub/tallies/south", {"s1": json.dumps({"n": 3})})
    north.vars.put("domain/testsub/tallies/north", {"n1": json.dumps({"n": 1})})
    north.vars.put("domain/testsub/secret-plan/south", {"x": "1"})
    assert DomainAgent("south", north.vars, south.vars, now=wall).sync()
    assert south.vars.get("domain/testsub/tallies")[0] == {"s1": json.dumps({"n": 3})}
    assert south.vars.get("domain/testsub/secret-plan")[0] is None


def test_the_signer_issues_only_the_kinds_of_token_a_spec_declares_with_their_claims():
    """`domain.tokens: {tally: {lifetime: 600, claims: [counter]}}` — a tally token says its kind, lives 600 s and names a
    counter; a person's token, an undeclared kind or a claim the spec did not name is refused, and the door that takes
    tallies takes no other kind."""
    from w2cplatform.domain.declared import token_kinds
    from w2cplatform.trust.tokens import DeclaredIssuer, TokenIssuer, Undeclared, WrongKind, verify
    spec()
    t = TokenIssuer("acme")
    issuer = DeclaredIssuer(t, token_kinds())
    tok = issuer.issue("tally", "south", now=1000.0, counter="s1")
    p = verify(tok, t.keyset(), now=1000.0, kind="tally")
    assert (p["kind"], p["counter"], p["exp"] - p["iat"]) == ("tally", "s1", 600.0) and issuer.lifetime("tally") == 600.0
    for bad in (lambda: issuer.issue("person", "anna"), lambda: issuer.issue("rocket", "south"),
                lambda: issuer.issue("tally", "south", counter="s1", role="admin")):
        try:
            bad()
            raise AssertionError("an undeclared token was issued")
        except Undeclared:
            pass
    try:
        verify(tok, t.keyset(), now=1000.0, kind="person")
        raise AssertionError("a tally token passed a person's door")
    except WrongKind:
        pass


def test_the_holder_backs_up_what_a_spec_keeps_and_a_move_restores_it():
    """`domain.kept: [ledger]` — the holder's backup carries `domain/testsub/ledger` with what the domain decided; the
    member chosen to keep it carries it home; a move from the signer's backup restores it on the new holder."""
    from w2cplatform.domain.agent import DomainAgent, DomainPublisher
    from w2cplatform.domain.term import BACKUP, DomainHolder, exported, move_domain
    from w2cplatform.trust.signer import Signer
    fed, wall = site()
    north, south = fed.clusters["north"], fed.clusters["south"]
    assert "domain/testsub/ledger" in exported()
    signer = Signer("acme", north.vars, now=wall)
    DomainPublisher(north.vars).publish_keys(signer.tokens.keyset())
    north.vars.put("domain/testsub/ledger", {"s1": "seen"})
    holder = DomainHolder(fed, "north", signer, 1, wall, objects=north.objects)
    holder.claim()
    holder.backup(["south"], north.objects)
    assert DomainAgent("south", north.vars, south.vars, now=wall, domain_objects=north.objects,
                       cluster_objects=south.objects).sync()
    assert south.vars.get(BACKUP)[0] and south.objects.get(BACKUP)
    new, report = move_domain(fed, "south", signer.backup(), "acme", lambda n: fed.clusters[n].objects, wall)
    assert new.term == 2 and south.vars.get("domain/testsub/ledger")[0] == {"s1": "seen"}, report["sentence"]


def test_a_domain_section_that_names_what_is_not_there_is_refused_when_the_spec_loads():
    """The section is read at load, and refused whole for a field the snapshot does not carry, a table that is not
    kept, a kind the platform owns, a claim the token itself writes, or a key it does not know."""
    import yaml
    from w2cplatform.spec import SubsystemSpec
    base = yaml.safe_load(open(TESTSUB, encoding="utf-8"))
    for bad in ({"ref": "labels"}, {"view": ["labels"]}, {"kept": ["a"], "tables": ["b"]},
                {"tokens": {"person": {"lifetime": 1}}}, {"tokens": {"t": {"lifetime": 1, "claims": ["exp"]}}},
                {"tokens": {"t": {"lifetime": 0}}}, {"books": ["a"], "kept": ["a"]}, {"carried": ["x"]}):
        try:
            SubsystemSpec.from_dict({**base, "domain": bad})
            raise AssertionError(f"taken: {bad}")
        except ValueError:
            pass


def test_the_key_families_are_read_passed_through_spec_and_their_words_must_name_one():
    """`domain.keys` — the subsystem's key families of the domain, for a page's «keys» tab: the composition only, every
    key under the subsystem's own prefix; the words are `display.keys`, merged by id on the page. The reader takes it,
    a key falls into its family by an exact key or a prefix, `/spec` carries it as written — and a family with words in
    it, a key outside `domain/<sub>/`, a family with no key, or words for a family nobody declared are refused."""
    import yaml
    from w2cplatform.console import SpecConsole
    from w2cplatform.objects import FsObjectStore
    from w2cplatform.spec import SpecController, SubsystemSpec
    from w2cplatform.variables import FileVariables
    s = spec()
    assert [f["id"] for f in s.domain.keys] == ["tallies", "ledger"]
    assert s.domain.family_of("domain/testsub/tallies") == s.domain.family_of("domain/testsub/tallies/south") == "tallies"
    assert s.domain.family_of("domain/testsub/ledger") == "ledger" and s.domain.family_of("domain/testsub/x") is None
    root = tempfile.mkdtemp(prefix="keys-")
    ctl = SpecController(s, FileVariables(os.path.join(root, "config"), volatile=True),
                         FsObjectStore(os.path.join(root, "objects")), wall=Clock())
    got = SpecConsole(ctl, wall=Clock()).describe()
    assert got["domain"]["keys"] == [{"id": "tallies", "keys": ["domain/testsub/tallies"], "prefix": "domain/testsub/tallies/"},
                                     {"id": "ledger", "keys": ["domain/testsub/ledger"]}]
    assert got["display"]["keys"]["ledger"] == {"title": "ledger", "about": "the ledger the holder keeps for the domain",
                                                "absent": "nothing ledgered yet"}
    base = yaml.safe_load(open(TESTSUB, encoding="utf-8"))
    for bad in ([{"id": "a", "keys": ["domain/testsub/a"], "title": "A"}],          # words belong in display.keys
                [{"id": "a", "keys": ["domain/members"]}],                           # the platform's own family
                [{"id": "a", "prefix": "domain/other/"}], [{"id": "a"}],
                [{"id": "a", "keys": ["domain/testsub/a"]}, {"id": "a", "keys": ["domain/testsub/b"]}]):
        try:
            SubsystemSpec.from_dict({**base, "domain": {**base["domain"], "keys": bad}})
            raise AssertionError(f"taken: {bad}")
        except ValueError:
            pass
    for words in ({"nobody": {"title": "x"}}, {"ledger": {"title": "x", "colour": "red"}}):
        try:
            SubsystemSpec.from_dict({**base, "display": {"keys": words}})
            raise AssertionError(f"taken: {words}")
        except ValueError:
            pass


def _shared_site():
    """testsub's site with the shared document: north holds it, south's agent carried it, south's console reads it."""
    from w2cplatform.console import SpecConsole
    from w2cplatform.domain.agent import DomainAgent, DomainPublisher
    from w2cplatform.domain.shared import SharedSettings
    from w2cplatform.spec import SpecController
    from w2cplatform.trust.signer import Signer
    fed, wall = site()
    north, south = fed.clusters["north"], fed.clusters["south"]
    signer = Signer("acme", north.vars, now=wall)
    DomainPublisher(north.vars).publish_keys(signer.tokens.keyset())
    shared = SharedSettings(north.vars, north.objects, signer.tokens, wall=wall)
    agent = DomainAgent("south", north.vars, south.vars, now=wall, domain_objects=north.objects, cluster_objects=south.objects)
    ctl = SpecController(spec(), south.vars, south.objects, wall=wall, cluster="south")
    return shared, agent, ctl, SpecConsole(ctl, wall=wall)


def test_a_shared_field_takes_the_domains_value_where_the_unit_set_none_and_a_union_adds_to_its_own():
    """`domain.shared: [step, marks]` — the domain holds a value for each; the platform resolves them (no subsystem's
    route): a counter that set no step takes the domain's, one that did keeps its own, and nobody above means the
    spec's `inherit`; `marks` merges by union — the domain's AND the counter's own. Served at the cluster console's
    one door, `GET /domain/shared/testsub`, from the copy this cluster's agent carried and verified."""
    shared, agent, ctl, con = _shared_site()
    ctl.create({"name": "s2", "step": 3, "marks": ["mine"]})
    assert con.shared_route("testsub", {})[1]["fields"]["step"] == {"value": 1, "from": "spec", "inherit": 1}
    shared.edit(lambda s: s.setdefault("shared", {}).setdefault("testsub", {}).update(step=5, marks=["site"]), base_rev=0)
    assert agent.sync() and agent.shared == "took rev 1"
    st, body = con.shared_route("testsub", {})
    assert st == 200 and body["rev"] == 1
    assert body["fields"]["step"] == {"value": 5, "from": "domain rev 1", "inherit": 1}
    assert body["fields"]["marks"] == {"value": ["site"], "from": "domain rev 1", "inherit": [], "merge": "union"}
    s1 = con.shared_route("testsub", {"unit": "s1"})[1]["fields"]
    s2 = con.shared_route("testsub", {"unit": "s2"})[1]["fields"]
    assert (s1["step"]["value"], s1["step"]["from"]) == (5, "domain rev 1")
    assert (s2["step"]["value"], s2["step"]["from"]) == (3, "unit")
    assert (s2["marks"]["value"], s2["marks"]["from"]) == (["mine", "site"], "unit + domain rev 1")
    assert con.shared_route("testsub", {"unit": "nobody"})[0] == 404


def test_the_shared_door_gives_only_declared_fields_and_an_edit_of_an_undeclared_one_is_refused():
    """The door answers the fields `domain.shared` names and nothing else — not `start`, not `labels`, whatever the
    document holds; a subsystem that shares nothing is a 404; and the document never takes a field nobody declared,
    or a subsystem not on the domain: the edit is refused whole, nothing written. The spec refuses a shared field that
    is not one of the unit's, is a secret, or neither inherits nor is the field the page groups by."""
    import yaml
    from w2cplatform.domain.api import ApiError
    from w2cplatform.spec import SubsystemSpec
    shared, agent, ctl, con = _shared_site()
    shared.edit(lambda s: s.setdefault("shared", {}).setdefault("testsub", {}).update(step=2), base_rev=0)
    for bad in ({"testsub": {"start": 9}}, {"testsub": {"labels": ["x"]}}, {"nobody": {"step": 1}}):
        try:
            shared.edit(lambda s, bad=bad: s.update(shared=bad), base_rev=1)
            raise AssertionError(f"taken: {bad}")
        except ApiError as e:
            assert e.status == 409, e
    assert shared.current()[0]["rev"] == 1
    agent.sync()
    st, body = con.shared_route("testsub", {})
    assert st == 200 and sorted(body["fields"]) == ["marks", "step"]
    assert con.shared_route("nobody", {})[0] == 404
    assert con.describe()["domain"]["shared"] == ["step", "marks"]
    base = yaml.safe_load(open(TESTSUB, encoding="utf-8"))
    for bad in (["nope"], ["start"], ["labels"]):
        try:
            SubsystemSpec.from_dict({**base, "domain": {**base["domain"], "shared": bad}})
            raise AssertionError(f"taken: {bad}")
        except ValueError:
            pass

