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
    from w2cplatform.worker import Worker

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

    w = CounterWorker(sub, None, vars_, objects, clock=wall, wall=wall, instance=instance, spec=spec())
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
    assert {u["ref"]: u.get("start") for u in shown["units"]["testsub"]} == {"n1": 7, "n2": 7, "s1": 7}
    assert shown["holder"] == "north" and [m["name"] for m in shown["members"]] == ["north", "south"]
    assert shown["tables"] == {"testsub/ledger": {"n1": "counted"}}


def test_the_door_serves_the_units_and_a_declared_table_and_nothing_undeclared():
    """`/domain/<sub>/<rows>` is the read view of a subsystem of the directory; `/domain/<sub>/<table>` a row its spec keeps
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
        st, body = get("/domain/testsub/counters")
        assert st == 200 and sorted(r["ref"] for r in body["rows"]) == ["n1", "n2", "s1"]
        assert get("/domain/testsub/ledger") == (200, {"s1": "seen"})
        assert get("/domain/testsub/hidden")[0] == 404 and get("/domain/nobody/counters")[0] == 404
    finally:
        con.stop(srv)


def test_the_holders_human_routes_are_under_domain_and_a_cluster_console_hands_them_on_unrewritten():
    """One set of paths (the console module's contract, §10a): the domain's door answers `GET /domain` — the view in the
    product's shape, members a list with the holder among them, the topology, who knocks, where the door is —,
    `/domain/keys` (every `domain/` key, a secret masked), `/spec` (no root subsystem) and `/mounts` (every spec), and
    `/domain/topology`, `/domain/members`, `/domain/<sub>/<table>`; the old `/api/…` is no route (no alias). The holder's
    cluster console serves the same view at `/domain` and hands `/domain/X` to the domain's door at `/domain/X`; a
    cluster that does not hold the domain says it does not know where its door is."""
    import urllib.error
    import urllib.request
    from w2cplatform.console import Mount, SpecConsole
    from w2cplatform.domain.api import ConsoleAPI
    from w2cplatform.domain.console import Console
    from w2cplatform.domain.federation import DomainDirectory
    from w2cplatform.domain.members import Members
    from w2cplatform.domain.readview import ReadView
    from w2cplatform.domain.topology import Topology
    from w2cplatform.spec import SpecController
    fed, wall = site()
    north, south = fed.clusters["north"], fed.clusters["south"]
    north.vars.put("domain/testsub/ledger", {"s1": "seen"})
    north.vars.put("domain/testsub/badges/gold", {"since": "1", "pin_secret": "4321"})
    view = ReadView(fed, wall=wall)
    view.refresh()
    con = Console(DomainDirectory(fed), view, ConsoleAPI(DomainDirectory(fed), lambda c: None), refresh_interval=60,
                  publish_to=north.objects, holder_vars=north.vars, topology=Topology(north.vars),
                  members=Members(north.vars, wall=wall, configured=lambda: ["south"], domain="north"))
    door = con.serve(port=0)
    con.url = f"http://127.0.0.1:{door.server_address[1]}"
    con._publish_view()
    consoles = [Mount(SpecConsole(SpecController(spec(), c.vars, c.objects, wall=wall, cluster=c.name), wall=wall)).serve(port=0)
                for c in (north, south)]

    def get(srv, path):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{srv.server_address[1]}{path}") as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")
    try:
        st, d = get(door, "/domain")
        assert st == 200 and d["holder"] == "north" and d["url"] == con.url and "topology" in d and "knocking" in d
        assert [(m["name"], m["holder"]) for m in d["members"]] == [("north", True), ("south", False)]
        st, k = get(door, "/domain/keys")
        gold = next(v for v in k["vars"] if v["key"] == "domain/testsub/badges/gold")
        assert gold["items"] == {"since": "1", "pin_secret": "***"} and any(o["key"] == "domain/view" for o in k["objects"])
        assert get(door, "/spec") == (200, {"name": "domain"}) and "testsub" in get(door, "/mounts")[1]["mounts"]
        assert get(door, "/domain/testsub/ledger") == (200, {"s1": "seen"})
        assert get(door, "/domain/members")[0] == 200 and get(door, "/domain/topology")[0] == 200
        for old in ("/api/members", "/api/topology", "/api/testsub/ledger", "/api/where/s1"):
            assert get(door, old)[0] == 404, old
        here, there = consoles
        st, d = get(here, "/domain")
        assert st == 200 and d["holder"] == "north" and isinstance(d["members"], list)
        assert get(here, "/domain/topology") == get(door, "/domain/topology")
        assert get(here, "/domain/testsub/ledger") == (200, {"s1": "seen"})
        assert get(here, "/domain/where/s1")[1]["cluster"] == "south"
        assert get(here, "/domain/keys")[0] == 200
        st, d = get(there, "/domain/topology")
        assert st == 404 and d["error"] == "no domain here"
    finally:
        con.stop(door)
        for srv in consoles:
            srv.shutdown()
            srv.server_close()


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
    """`domain.kept: [ledger, badges/]` — the holder's backup carries `domain/testsub/ledger` with what the domain
    decided, and every row of the family `badges/` (`domain/testsub/badges/<name>`); the member chosen to keep it
    carries it home; a move from the signer's backup restores them on the new holder. The agent writes none of them:
    the family is denied to it row by row, as a kept row is by name."""
    from w2cplatform.domain.agent import DomainAgent, DomainPublisher
    from w2cplatform.domain.rights import agent_denials, roles
    from w2cplatform.domain.term import BACKUP, DomainHolder, exported, move_domain
    from w2cplatform.rights import allowed
    from w2cplatform.trust.signer import Signer
    fed, wall = site()
    north, south = fed.clusters["north"], fed.clusters["south"]
    assert "domain/testsub/ledger" in exported() and "domain/testsub/badges/" in exported()
    assert "!domain/testsub/badges/*" in agent_denials([spec()])
    agent = roles(specs=[spec()])["domainagent"]["write"]
    assert allowed(agent, "domain/keys") and not allowed(agent, "domain/testsub/badges/gold")
    assert not allowed(agent, "domain/testsub/ledger")
    signer = Signer("acme", north.vars, now=wall)
    DomainPublisher(north.vars).publish_keys(signer.tokens.keyset())
    north.vars.put("domain/testsub/ledger", {"s1": "seen"})
    north.vars.put("domain/testsub/badges/gold", {"since": "1"})
    north.vars.put("domain/testsub/badges/silver", {"since": "2"})
    holder = DomainHolder(fed, "north", signer, 1, wall, objects=north.objects)
    holder.claim()
    holder.backup(["south"], north.objects)
    assert DomainAgent("south", north.vars, south.vars, now=wall, domain_objects=north.objects,
                       cluster_objects=south.objects).sync()
    assert south.vars.get(BACKUP)[0] and south.objects.get(BACKUP)
    new, report = move_domain(fed, "south", signer.backup(), "acme", lambda n: fed.clusters[n].objects, wall)
    assert new.term == 2 and south.vars.get("domain/testsub/ledger")[0] == {"s1": "seen"}, report["sentence"]
    assert sorted(south.vars.list("domain/testsub/badges/")) == ["domain/testsub/badges/gold", "domain/testsub/badges/silver"]
    assert south.vars.get("domain/testsub/badges/silver")[0] == {"since": "2"}


def test_a_domain_section_that_names_what_is_not_there_is_refused_when_the_spec_loads():
    """The section is read at load, and refused whole for a field the snapshot does not carry, a table that is not
    kept, a kind the platform owns, a claim the token itself writes, or a key it does not know — and for a family served
    as a table, a subject family that is not kept with its `/`, held apart from anything but the people or granted a
    word that is no grant, a token kind that says a grant (a token carries no rights), an edit of what is no field."""
    import yaml
    from w2cplatform.spec import SubsystemSpec
    base = yaml.safe_load(open(TESTSUB, encoding="utf-8"))
    for bad in ({"ref": "labels"}, {"view": ["labels"]}, {"kept": ["a"], "tables": ["b"]},
                {"tokens": {"person": {"lifetime": 1}}}, {"tokens": {"t": {"lifetime": 1, "claims": ["exp"]}}},
                {"tokens": {"t": {"lifetime": 0}}}, {"books": ["a"], "kept": ["a"]}, {"carried": ["x"]},
                # a family (`x/`) is no table and no book's twin, and its name is a name
                {"kept": ["a/"], "tables": ["a"]}, {"books": ["a"], "kept": ["a/"]}, {"kept": ["a/b"]},
                # names: a kept family, with its `/`, apart from the people, granted one of the platform's grants
                {"kept": ["a/"], "names": {"b/": {"exclusive_with": "domain/users"}}},
                {"kept": ["a"], "names": {"a": {"exclusive_with": "domain/users"}}},
                {"kept": ["a/"], "names": {"a/": {"exclusive_with": "identity/users"}}},
                {"kept": ["a/"], "names": {"a/": {"grant": "view"}}},
                {"kept": ["a/"], "names": {"a/": {"exclusive_with": "domain/users", "grant": "root"}}},
                {"kept": ["a/"], "names": {"a/": {"exclusive_with": "domain/users", "unique": True}}},
                {"kept": ["a/"], "names": ["a/"]},
                # a token carries no rights
                {"tokens": {"t": {"lifetime": 1, "grant": "view"}}},
                # an edit names fields of the unit
                {"ref": "name", "edit": ["nope"]}):
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




def test_the_spec_reads_a_kept_family_of_subjects_their_grant_and_the_fields_an_edit_carries():
    """ADR-0031's declarations, as testsub writes them: `kept: [ledger, badges/]` (a family by its `/`), `names:
    {badges/: {exclusive_with: domain/users, grant: view}}`, `edit: [start, labels]` — and a token kind says no grant."""
    d = spec().domain
    assert d.kept == ("ledger", "badges/") and d.tables == ("ledger",)
    assert d.names == {"badges/": {"exclusive_with": "domain/users", "grant": "view"}}
    assert d.tokens["tally"] == {"lifetime": 600.0, "claims": ("counter",)}
    assert d.edit == ("start", "labels")


def _refused(write, cls, names):
    try:
        write()
    except cls as e:
        assert names in str(e), e
        return
    raise AssertionError(f"taken, though it meets {names}")


def test_a_subject_of_a_family_and_a_person_never_share_a_name_whichever_is_written_second():
    """`names.badges/.exclusive_with: domain/users` — the platform asks it of every write through its guard: a badge
    under a person's name is refused naming the person's row (the course keeps the people as `identity/users/<name>`), a
    person under a badge's name naming the badge's. A person deleted (the platform's tombstone, never refused) frees the
    name. The stores the platform's processes open are guarded (`runtime.federation_from_env`), and a subsystem's worker
    on the domain may read the people's rows and the grants the check asks."""
    from w2cplatform.domain.declared import Guarded, NameTaken, guarded
    from w2cplatform.domain.identity import IdentityStore
    from w2cplatform.domain.rights import roles
    from w2cplatform.trust.signer import Signer
    fed, wall = site()
    north = fed.clusters["north"]
    store = guarded(north.vars)
    assert guarded(store) is store
    ids = IdentityStore(Signer("acme", north.vars, now=wall), north.vars, north.objects, now=wall)
    ids.create_local("anna", "a long password 1", ["admin"])
    _refused(lambda: store.put("domain/testsub/badges/anna", {"since": "1"}), NameTaken, "identity/users/anna")
    store.put("domain/testsub/badges/bob", {"since": "1"})
    _refused(lambda: ids.create_local("bob", "a long password 2", []), NameTaken, "domain/testsub/badges/bob")
    assert north.vars.get("domain/testsub/badges/anna")[0] is None and ids.get("bob") is None
    ids.delete("anna")
    store.put("domain/testsub/badges/anna", {"since": "2"})                 # the person is gone: the name is free
    store.put("domain/testsub/ledger", {"bob": "seen"})                     # no family: not asked
    root = tempfile.mkdtemp(prefix="guard-")
    saved = {k: os.environ.get(k) for k in ("CLUSTERS", "DOMAIN_HOLDER")}
    os.environ.update({"CLUSTERS": f"north=file://{root}/config|{root}/objects", "DOMAIN_HOLDER": "north"})
    try:
        from w2cplatform.domain.runtime import federation_from_env
        opened = federation_from_env().domain_holder.vars
    finally:
        for k, v in saved.items():
            os.environ.pop(k) if v is None else os.environ.__setitem__(k, v)
    assert isinstance(opened, Guarded)
    opened.put("identity/users/dora", {"id": "dora", "kind": "local"})
    _refused(lambda: opened.put("domain/testsub/badges/dora", {"since": "1"}), NameTaken, "identity/users/dora")
    read = roles(specs=[spec()])["testsubdomain"]["read"]
    assert "identity/users/*" in read and "domain/grants/*" in read


def test_a_subject_of_a_family_is_granted_no_wider_than_its_grant_and_a_token_carries_no_rights():
    """`names.badges/.grant: view` — the grants of a cluster or of the domain may give a badge `view` and nothing wider:
    `edit` or `admin` to it is refused (`GrantTooWide`) and nothing is written, whoever writes the grants; a person of
    the same rows is granted anything. A badge made under a name already granted wider is refused too. A token kind
    declares no grant, and a tally token carries none: what its subject may do is the grants'."""
    from w2cplatform.domain.agent import DomainPublisher
    from w2cplatform.domain.declared import GrantTooWide, guarded
    from w2cplatform.domain.declared import token_kinds
    from w2cplatform.domain.grants import Grant, grants_from_items, set_domain_grants
    from w2cplatform.trust.tokens import DeclaredIssuer, TokenIssuer, verify
    fed, wall = site()
    north = fed.clusters["north"]
    store = guarded(north.vars)
    store.put("domain/testsub/badges/bob", {"since": "1"})
    until = wall() + 3600
    pub = DomainPublisher(north.vars)
    pub.publish_grants("south", [Grant("bob", "view", None, until), Grant("anna", "admin", None, until)])
    assert {(g.subject, g.capability) for g in grants_from_items(north.vars.get("domain/grants/south")[0])} == \
        {("bob", "view"), ("anna", "admin")}
    _refused(lambda: pub.publish_grants("south", [Grant("bob", "edit", "testsub/s1", until)]), GrantTooWide,
             "granted at most 'view'")
    _refused(lambda: set_domain_grants(north.vars, [Grant("anna", "admin", None, 0), Grant("bob", "admin", None, 0)],
                                       wall()), GrantTooWide, "domain/testsub/badges/bob")
    assert {g.subject for g in grants_from_items(north.vars.get("domain/grants/south")[0])} == {"bob", "anna"}
    assert north.vars.get("domain/grants/domain")[0] is None
    pub.publish_grants("north", [Grant("carl", "edit", None, until)])       # nobody's badge yet: a grant like any
    _refused(lambda: store.put("domain/testsub/badges/carl", {"since": "1"}), GrantTooWide, "grants 'carl' edit")
    spec()
    t = TokenIssuer("acme")
    p = verify(DeclaredIssuer(t, token_kinds()).issue("tally", "south", now=1000.0, counter="s1"), t.keyset(),
               now=1000.0, kind="tally")
    assert "grant" not in p and "tally" in token_kinds() and "grant" not in token_kinds()["tally"]

def test_an_edit_through_the_domains_door_carries_only_the_fields_its_spec_lets_through():
    """`edit: [start, labels]` — an edit of a member's counter through the domain's door (`PUT /domain/testsub/counters/
    <ref>`) reaches the member with those fields; one with any other (`step` here) is a 400 naming it and the list, and
    the member is not asked. An edit that names no subsystem has no list to be held to: the member's console decides."""
    import urllib.error
    import urllib.request
    from w2cplatform.domain.api import ApiError, ConsoleAPI
    from w2cplatform.domain.console import Console
    from w2cplatform.domain.federation import DomainDirectory
    from w2cplatform.domain.readview import ReadView
    fed, wall = site()
    asked = []

    class Member:
        def update_unit(self, unit, fields, subject):
            asked.append((unit, dict(fields)))
            return {"revision": 2}
    api = ConsoleAPI(DomainDirectory(fed), lambda c: Member())
    assert api.update_unit("s1", {"start": 9, "labels": ["a"]}, "k-1", sub="testsub")["cluster"] == "south"
    try:
        api.update_unit("s1", {"start": 9, "step": 2}, "k-2", sub="testsub")
        raise AssertionError("an undeclared field went through the domain")
    except ApiError as e:
        assert e.status == 400 and e.detail.startswith("step:") and "domain.edit" in e.detail, e
    api.update_unit("s1", {"step": 2}, "k-3")
    assert asked == [("s1", {"start": 9, "labels": ["a"]}), ("s1", {"step": 2})]
    view = ReadView(fed, wall=wall)
    view.refresh()
    con = Console(DomainDirectory(fed), view, api, refresh_interval=60)
    srv = con.serve(port=0)

    def put(path, body, key):
        req = urllib.request.Request(f"http://127.0.0.1:{srv.server_address[1]}{path}", json.dumps(body).encode(),
                                     {"Content-Type": "application/json", "Idempotency-Key": key}, method="PUT")
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())
    try:
        st, body = put("/domain/testsub/counters/n1", {"labels": ["b"], "name": "renamed"}, "k-4")
        assert st == 400 and body["detail"].startswith("name:"), body
        assert put("/domain/testsub/counters/n1", {"labels": ["b"]}, "k-5")[0] == 200
        assert asked[-1] == ("n1", {"labels": ["b"]}) and len(asked) == 3
    finally:
        con.stop(srv)

