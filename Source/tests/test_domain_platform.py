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
    from w2cplatform.domain.signer_service import Holder
    members = Members(north.vars, wall=wall, configured=lambda: ["south"], domain="north")
    con = Console(DomainDirectory(fed), view, ConsoleAPI(DomainDirectory(fed), lambda c: None), refresh_interval=60,
                  holder_objects=north.objects, holder_vars=north.vars, topology=Topology(north.vars), members=members)
    door = con.serve(port=0)
    url = f"http://127.0.0.1:{door.server_address[1]}"
    # the view is the signer's pass's to leave (ADR-0032), naming the console's address
    Holder(north.vars, north.objects, None, fed=fed, view=view, topology=Topology(north.vars), members=members,
           console_url=url, wall=wall).publish_view()
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
        assert st == 200 and d["holder"] == "north" and d["url"] == url and "topology" in d and "knocking" in d
        assert [(m["name"], m["holder"]) for m in d["members"]] == [("north", True), ("south", False)]
        st, k = get(door, "/domain/keys")
        gold = next(v for v in k["vars"] if v["key"] == "domain/testsub/badges/gold")
        assert gold["items"] == {"since": "1", "pin_secret": "***"} and any(o["key"] == "domain/view" for o in k["objects"])
        assert get(door, "/spec") == (200, {"name": "", "rows": None})
        st, m = get(door, "/mounts")
        assert m["root"] == "" and m["mounts"]["testsub"]["domain"] == {
            "keys": [{"id": "tallies", "keys": ["domain/testsub/tallies"], "prefix": "domain/testsub/tallies/"},
                     {"id": "ledger", "keys": ["domain/testsub/ledger"]}],
            "shared": ["step", "marks", "rounds"], "edit": ["start", "labels"], "view": ["start"]}
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
    from w2cplatform.domain.term import BACKUP_TAKEN, DomainHolder, exported, move_domain
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
    assert south.vars.get(BACKUP_TAKEN)[0] and south.objects.get(BACKUP_TAKEN)
    new, report = move_domain(fed, "south", signer.backup(), "acme", lambda n: fed.clusters[n].objects, wall)
    assert new.term == 2 and south.vars.get("domain/testsub/ledger")[0] == {"s1": "seen"}, report["sentence"]
    assert sorted(south.vars.list("domain/testsub/badges/")) == ["domain/testsub/badges/gold", "domain/testsub/badges/silver"]
    assert south.vars.get("domain/testsub/badges/silver")[0] == {"since": "2"}


def test_a_member_publishes_the_copy_it_took_as_backup_taken_and_nothing_under_the_old_name():
    """What a member publishes of the backup copy it took — `{rev, term, sha256}` and the document beside it — is
    `domain/backup-taken`, the product's name (one name on both sides, «Архитектор» 2026-10-06; ADR 0003: no alias).
    `domain/backup/<member>` stays the holder's pointer; no row and no object of the bare old name is written, in the
    member's store or in its report the holder reads (`term.copies`, a handover's wait)."""
    from w2cplatform.domain.agent import DomainAgent, DomainPublisher
    from w2cplatform.domain.term import BACKUP, BACKUP_TAKEN, DomainHolder, copies
    from w2cplatform.domain.uplink import _rows
    from w2cplatform.trust.signer import Signer
    assert BACKUP_TAKEN == "domain/backup-taken" and BACKUP_TAKEN in _rows() and BACKUP not in _rows()
    fed, wall = site()
    north, south = fed.clusters["north"], fed.clusters["south"]
    signer = Signer("acme", north.vars, now=wall)
    DomainPublisher(north.vars).publish_keys(signer.tokens.keyset())
    holder = DomainHolder(fed, "north", signer, 1, wall, objects=north.objects)
    holder.claim()
    holder.backup(["south"], north.objects)
    assert DomainAgent("south", north.vars, south.vars, now=wall, domain_objects=north.objects,
                       cluster_objects=south.objects, published=south.objects).sync()
    pointer = north.vars.get(f"{BACKUP}/south")[0]
    taken = south.vars.get(BACKUP_TAKEN)[0]
    assert taken and {k: taken[k] for k in ("rev", "term", "sha256")} == \
        {k: pointer[k] for k in ("rev", "term", "sha256")}, (taken, pointer)
    assert south.objects.get(BACKUP_TAKEN) == north.objects.get(pointer["object"])
    assert south.vars.get("domain/backup")[0] is None and south.objects.get("domain/backup") is None
    assert south.vars.list("domain/backup") == [BACKUP_TAKEN]
    report = holder.reported("south").vars
    assert report.get(BACKUP_TAKEN)[0] == taken and report.get("domain/backup")[0] is None
    assert copies(holder, ["south"]) == {"south": {"term": 1, "rev": int(pointer["rev"])}}


def test_a_domain_section_that_names_what_is_not_there_is_refused_when_the_spec_loads():
    """The section is read at load, and refused whole for a field the snapshot does not carry, a table that is not
    kept, a kind the platform owns, a claim the token itself writes, or a key it does not know — and for a family served
    as a table, a subject family that is not kept with its `/`, held apart from anything but the people or granted a
    word that is no grant, a token kind that says a grant (a token carries no rights), an edit of what is no field."""
    from w2cplatform import specyaml
    from w2cplatform.spec import SubsystemSpec
    base = specyaml.loads(open(TESTSUB, encoding="utf-8"))
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
    from w2cplatform import specyaml
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
    base = specyaml.loads(open(TESTSUB, encoding="utf-8"))
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


def test_a_shared_settings_edit_goes_from_the_keyless_console_to_the_signer_which_checks_and_signs_it():
    """ADR-0032: the signer performs the edit whole — a person of the domain with `admin` on it, the revision the edit
    was made against, the specs' declarations — and signs the document itself; the domain's console has no key, serves
    `GET /domain/shared` (`{doc, delivery, declared}`) from the store and hands `PUT /domain/shared` to the signer as it
    came. A stale revision (409), a field nobody declared (400: wrong by the specs alone), no token or no `admin` is
    refused and nothing is signed; there is no route that signs what it is given."""
    import threading
    import urllib.error
    import urllib.request
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from w2cplatform.domain.agent import DomainPublisher
    from w2cplatform.domain.api import ConsoleAPI
    from w2cplatform.domain.console import Console
    from w2cplatform.domain.federation import DomainDirectory
    from w2cplatform.domain.grants import Grant, set_domain_grants
    from w2cplatform.domain.readview import ReadView
    from w2cplatform.domain.shared import POINTER
    from w2cplatform.domain.signer_service import edit_shared
    from w2cplatform.trust.signer import Signer
    from w2cplatform.trust.tokens import PERSON
    fed, wall = site()
    north = fed.clusters["north"]
    signer = Signer("acme", north.vars, now=wall)
    DomainPublisher(north.vars).publish_keys(signer.tokens.keyset())
    set_domain_grants(north.vars, [Grant("anna", "admin", None, 0), Grant("vera", "view", None, 0)], wall())
    anna, vera = (signer.tokens.issue(n, 900, now=wall(), kind=PERSON) for n in ("anna", "vera"))

    def edit(token, body):
        return edit_shared(north.vars, north.objects, signer.tokens, signer.tokens.keyset(), set(), token, body, wall())
    assert edit(None, {"base_rev": 0, "shared": {"testsub": {"step": 2}}})[0] == 401
    assert edit(vera, {"base_rev": 0, "shared": {"testsub": {"step": 2}}})[0] == 403
    assert edit(anna, {"base_rev": 0, "shared": {"testsub": {"start": 2}}})[0] == 400          # not declared shared
    assert edit(anna, {"base_rev": 0, "shared": "step=2"})[0] == 400
    assert north.vars.get(POINTER)[0] is None                                                  # nothing signed
    assert edit(anna, {"base_rev": 0, "shared": {"testsub": {"step": 2, "marks": ["a"]}}}) == (200, {"rev": 1, "by": "anna"})
    assert edit(anna, {"base_rev": 0, "shared": {"testsub": {"step": 3}}})[0] == 409           # made against rev 0
    assert int(north.vars.get(POINTER)[0]["rev"]) == 1

    class SignerDoor(BaseHTTPRequestHandler):                     # the signer's PUT /api/shared, as its door runs it
        def do_PUT(self):
            raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            st, out = (edit(self.headers.get("Authorization", "")[7:] or None, json.loads(raw))
                       if self.path == "/api/shared" else (404, {"detail": "no such route"}))
            body = json.dumps(out).encode()
            self.send_response(st); self.send_header("Content-Length", str(len(body))); self.end_headers()
            self.wfile.write(body)

        def do_GET(self):                                         # `/api/holder`: a domain that holds no term
            body = json.dumps({"detail": "this domain holds no term"}).encode()
            self.send_response(404); self.send_header("Content-Length", str(len(body))); self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass
    sdoor = ThreadingHTTPServer(("127.0.0.1", 0), SignerDoor)
    threading.Thread(target=sdoor.serve_forever, daemon=True).start()
    view = ReadView(fed, wall=wall)
    view.refresh()
    con = Console(DomainDirectory(fed), view, ConsoleAPI(DomainDirectory(fed), lambda c: None), refresh_interval=60,
                  holder_vars=north.vars, signer_url=f"http://127.0.0.1:{sdoor.server_address[1]}")
    assert not any(hasattr(con, k) for k in ("signer", "issuer", "tokens", "sealer_key"))   # nothing to sign with
    door = con.serve(port=0)

    def call(method, path, body=None, token=None):
        req = urllib.request.Request(f"http://127.0.0.1:{door.server_address[1]}{path}", method=method,
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Content-Type": "application/json",
                                              **({"Authorization": f"Bearer {token}"} if token else {})})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")
    try:
        st, sh = call("GET", "/domain/shared")
        assert st == 200 and sh["doc"]["rev"] == 1 and sh["doc"]["shared"] == {"testsub": {"step": 2, "marks": ["a"]}}
        assert sh["declared"]["testsub"][:2] == [{"name": "step", "type": "int"}, {"name": "marks", "type": "list"}]
        assert sh["declared"]["testsub"][2]["name"] == "rounds" and sh["declared"]["testsub"][2]["type"] == "json"
        assert sh["declared"]["testsub"][2]["schema"]["items"]["required"] == ["counter", "every"]
        assert "south" in sh["delivery"]["behind"]
        assert call("PUT", "/domain/shared", {"base_rev": 1, "shared": {"testsub": {"marks": None}}}, anna) == \
            (200, {"rev": 2, "by": "anna"})
        assert call("PUT", "/domain/shared", {"base_rev": 1, "shared": {"testsub": {"step": 9}}}, anna)[0] == 409
        assert call("PUT", "/domain/shared", {"base_rev": 2, "shared": {"testsub": {"step": 9}}}, vera)[0] == 403
        assert call("GET", "/domain/shared")[1]["doc"]["shared"] == {"testsub": {"step": 2}}
        assert call("PUT", "/domain/sign", {"doc": {}}, anna)[0] == 404 and call("POST", "/domain/shared", {}, anna)[0] == 404
    finally:
        con.stop(door)
        sdoor.shutdown()
        sdoor.server_close()


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
    or a subsystem not on the domain, or anything beside `shared`: the edit is refused whole (400 — wrong by the specs
    on its own), nothing written. The spec refuses a shared field that is not one of the unit's, is a secret, or neither
    inherits nor is the field the page groups by."""
    from w2cplatform import specyaml
    from w2cplatform.domain.api import ApiError
    from w2cplatform.spec import SubsystemSpec
    shared, agent, ctl, con = _shared_site()
    shared.edit(lambda s: s.setdefault("shared", {}).setdefault("testsub", {}).update(step=2), base_rev=0)
    for bad in ({"testsub": {"start": 9}}, {"testsub": {"labels": ["x"]}}, {"nobody": {"step": 1}}):
        try:
            shared.edit(lambda s, bad=bad: s.update(shared=bad), base_rev=1)
            raise AssertionError(f"taken: {bad}")
        except ApiError as e:
            assert e.status == 400, e
    try:
        shared.edit(lambda s: s.update(scenarios=[]), base_rev=1)                  # nothing beside `shared`
        raise AssertionError("taken: a key beside shared")
    except ApiError as e:
        assert e.status == 400 and "settings.scenarios" in e.detail, e
    assert shared.current()[0]["rev"] == 1
    agent.sync()
    st, body = con.shared_route("testsub", {})
    assert st == 200 and sorted(body["fields"]) == ["marks", "rounds", "step"]
    assert body["fields"]["rounds"] == {"value": None, "from": None}
    assert con.shared_route("nobody", {})[0] == 404
    assert con.describe()["domain"]["shared"] == ["step", "marks", "rounds"]
    base = specyaml.loads(open(TESTSUB, encoding="utf-8"))
    for bad in (["nope"], ["start"], ["labels"]):
        try:
            SubsystemSpec.from_dict({**base, "domain": {**base["domain"], "shared": bad}})
            raise AssertionError(f"taken: {bad}")
        except ValueError:
            pass


def test_a_document_the_domain_holds_whole_is_checked_by_its_schema_at_the_signers_one_operation():
    """ADR-0010/0032: `domain.shared` carries a document of type `json` with a schema — testsub's `rounds`, no counter's
    field. The signer's `shared` is one operation over whatever the specs declare: the document is checked by its
    schema (400, the schema's words), taken as it is — a string is a string, which a schema of an array refuses (reading
    a form's text box is the page's work, the architect with «Паритет», (б)) — signed with the rest, and served at the
    cluster console's one door as it is. The operation knows no document by its name."""
    from w2cplatform.domain.agent import DomainPublisher
    from w2cplatform.domain.grants import Grant, set_domain_grants
    from w2cplatform.domain.shared import POINTER, published
    from w2cplatform.domain.signer_service import edit_shared
    from w2cplatform.trust.signer import Signer
    from w2cplatform.trust.tokens import PERSON
    shared, agent, ctl, con = _shared_site()
    north_vars, north_objects = shared.vars, shared.objects
    signer = Signer("acme", north_vars, now=shared.wall)
    DomainPublisher(north_vars).publish_keys(signer.tokens.keyset())
    set_domain_grants(north_vars, [Grant("anna", "admin", None, 0)], shared.wall())
    anna = signer.tokens.issue("anna", 900, now=shared.wall(), kind=PERSON)

    def edit(body):
        return edit_shared(north_vars, north_objects, signer.tokens, signer.tokens.keyset(), set(), anna, body,
                           shared.wall())
    for bad, words in (([{"counter": "s1"}], "every"), ([{"counter": "s1", "every": 0}], "every"),
                       ([{"counter": "s1", "every": 2, "colour": "red"}], "colour"), ({"counter": "s1"}, "array"),
                       ([{"counter": "s1", "every": "two"}], "every"), ("[{\"counter\": \"s1\", \"every\": 3}]", "array"),
                       ("not json at all", "array")):
        st, out = edit({"base_rev": 0, "shared": {"testsub": {"rounds": bad}}})
        assert st == 400 and words in out["detail"], (bad, st, out)
    assert north_vars.get(POINTER)[0] is None                                                  # nothing signed
    assert edit({"base_rev": 0, "shared": {"testsub": {"rounds": [{"counter": "s1", "every": 5}], "step": 2}}})[0] == 200
    assert edit({"base_rev": 1, "shared": {"testsub": {"rounds": [{"counter": "n1", "every": 3}]}}})[0] == 200
    assert published(north_vars, north_objects)["shared"]["testsub"] == {"rounds": [{"counter": "n1", "every": 3}], "step": 2}
    assert agent.sync()
    assert con.shared_route("testsub", {})[1]["fields"]["rounds"] == {"value": [{"counter": "n1", "every": 3}],
                                                                      "from": "domain rev 2"}
    st, _ = edit({"base_rev": 2, "shared": {"testsub": {"rounds": None}}})                     # null takes it away
    assert st == 200 and "rounds" not in published(north_vars, north_objects)["shared"]["testsub"]
    import ast
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "w2cplatform", "domain",
                            "signer_service.py"), encoding="utf-8").read()
    assert "rounds" not in src and "scenario" not in src                                       # no document by its name
    ast.parse(src)


def test_a_shared_document_is_declared_with_its_schema_or_the_spec_does_not_load():
    """`{name, type: json, schema}` and nothing else: another type, no schema, a schema with a word the platform does not
    read, a name that is a field of the unit (a document is no unit's), a secret's name, or one name twice — refused."""
    from w2cplatform import specyaml
    from w2cplatform.spec import SubsystemSpec
    base = specyaml.loads(open(TESTSUB, encoding="utf-8"))
    d = spec().domain
    assert d.shared == ("step", "marks", "rounds") and sorted(d.documents) == ["rounds"]
    assert d.documents["rounds"].type == "json" and d.documents["rounds"].schema["maxItems"] == 16
    ok = {"name": "plan", "type": "json", "schema": {"type": "object"}}
    SubsystemSpec.from_dict({**base, "domain": {**base["domain"], "shared": ["step", ok]}})
    for bad in ({"name": "plan", "type": "list", "schema": {"type": "array"}}, {"name": "plan", "type": "json"},
                {"name": "plan", "type": "json", "schema": {"tpye": "object"}},
                {"name": "start", "type": "json", "schema": {}}, {"name": "plan_secret", "type": "json", "schema": {}},
                {"name": "plan", "type": "json", "schema": {}, "inherit": []}):
        try:
            SubsystemSpec.from_dict({**base, "domain": {**base["domain"], "shared": ["step", bad]}})
            raise AssertionError(f"taken: {bad}")
        except ValueError:
            pass
    try:
        SubsystemSpec.from_dict({**base, "domain": {**base["domain"], "shared": [ok, ok]}})
        raise AssertionError("taken: one document twice")
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


def test_a_refusal_is_409_when_it_depends_on_rows_that_exist_and_400_when_the_request_is_wrong_by_the_spec():
    """The architect's rule for the codes, at the doors: a person under the name of a subject of a family (testsub's
    badge `bob`) is a conflict with a row that exists — 409 at the signer's people; a grant to the badge wider than
    the family's declared `grant: view` is wrong by the spec on its own — 400 at the domain console's
    `PUT /domain/grants/<cluster>`, nothing written. A grant within it goes through."""
    from w2cplatform.domain.agent import DomainPublisher
    from w2cplatform.domain.api import ConsoleAPI
    from w2cplatform.domain.console import Console
    from w2cplatform.domain.declared import guarded
    from w2cplatform.domain.federation import DomainDirectory
    from w2cplatform.domain.grants import Grant, grants_from_items, set_domain_grants
    from w2cplatform.domain.identity import IdentityStore
    from w2cplatform.domain.readview import ReadView
    from w2cplatform.domain.signer_service import Holder
    from w2cplatform.trust.signer import Signer
    from w2cplatform.trust.tokens import PERSON, RevocationList
    fed, wall = site()
    north = fed.clusters["north"]
    spec()
    guarded(north.vars).put("domain/testsub/badges/bob", {"since": "1"})
    signer = Signer("acme", north.vars, now=wall)
    DomainPublisher(north.vars).publish_keys(signer.tokens.keyset())
    set_domain_grants(north.vars, [Grant("anna", "admin", None, 0.0)], wall())
    h = Holder(north.vars, north.objects, signer, ids=IdentityStore(signer, north.vars, north.objects, publish_floor=0,
               now=wall), revoked=RevocationList(), wall=wall)
    anna = signer.tokens.issue("anna", 900, now=wall(), kind=PERSON)
    st, out = h.people("POST", "users", anna, {"name": "bob", "password": "a long password"})
    assert st == 409 and "domain/testsub/badges/bob" in out["detail"], out
    con = Console(DomainDirectory(fed), ReadView(fed, wall=wall), ConsoleAPI(DomainDirectory(fed), lambda c: None),
                  refresh_interval=60, holder_vars=north.vars)
    door = con.serve(port=0)
    base = f"http://127.0.0.1:{door.server_address[1]}"
    try:
        st, out = _call(base, "PUT", "/domain/grants/south", {"lines": [{"subject": "bob", "cap": "edit", "scope": "*"}]})
        assert st == 400 and "granted at most 'view'" in out["detail"], out
        assert north.vars.get("domain/grants/south")[0] is None                       # nothing written
        assert _call(base, "PUT", "/domain/grants/south", {"lines": [{"subject": "bob", "cap": "view", "scope": "*"}]})[0] == 200
        assert [(g.subject, g.capability) for g in grants_from_items(north.vars.get("domain/grants/south")[0])] == \
            [("bob", "view")]
    finally:
        con.stop(door)


# -- the fifth operation: the domain moved onto a member, on the NEW holder, by the recovery file ---------------------
def _call(base, method, path, body=None, token=None):
    import urllib.error
    import urllib.request
    req = urllib.request.Request(base + path, data=json.dumps(body).encode() if body is not None else None, method=method,
                                 headers={"Content-Type": "application/json",
                                          **({"Authorization": f"Bearer {token}"} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def _moving_site(root=None):
    """testsub's site with a term: north holds the domain — its signer's own root, or one `root` issued (Lesson 15,
    step 9) — keeps a ledger, and south keeps its backup. Then SOUTH's signer, as it runs on a member: its own process,
    its own store (a signer of its own, made at its start as on any box), the domain as south reads it — south the
    would-be holder, north one of the clusters it reaches — and a console beside it. Returns
    `(north_holder, south, holder, console, signer_url, console_url, lines, wall, stop)`."""
    from w2cplatform.console import open_doors
    from w2cplatform.domain.agent import DomainAgent, DomainPublisher
    from w2cplatform.domain.api import ConsoleAPI
    from w2cplatform.domain.console import Console
    from w2cplatform.domain.federation import Cluster, DomainDirectory, Federation
    from w2cplatform.domain.identity import IdentityStore
    from w2cplatform.domain.readview import ReadView
    from w2cplatform.domain.signer_service import Holder
    from w2cplatform.domain.term import DomainHolder, install
    from w2cplatform.trust.signer import Signer
    from w2cplatform.trust.tokens import RevocationList
    fed, wall = site()
    north, south = fed.clusters["north"], fed.clusters["south"]
    if root is None:
        signer = Signer("acme", north.vars, now=wall)
        DomainPublisher(north.vars).publish_keys(signer.tokens.keyset())
        north_holder = DomainHolder(fed, "north", signer, 1, wall, objects=north.objects)
        north_holder.claim()
    else:
        north_holder = install(fed, "north", "acme", root, wall, objects=north.objects)
    north.vars.put("domain/testsub/ledger", {"s1": "seen"})
    north_holder.backup(["south"], north.objects)
    assert DomainAgent("south", north.vars, south.vars, now=wall, domain_objects=north.objects,
                       cluster_objects=south.objects).sync()
    mine = Federation()
    mine.add(Cluster("south", south.vars, south.objects, is_domain_holder=True))
    mine.add(Cluster("north", north.vars, north.objects))
    lines = []

    class Lines:
        def say(self, kind, cls="observation", **fields):
            lines.append((kind, fields))
    own = Signer("acme", south.vars, now=wall)                  # what any box's signer makes at its start
    holder = Holder(south.vars, south.objects, own, ids=IdentityStore(own, south.vars, south.objects, publish_floor=0,
                    now=wall), revoked=RevocationList(), fed=mine, journal=Lines(), signer_url="http://south.site:8445",
                    wall=wall)
    srv = open_doors("127.0.0.1", 0, holder.handler(), unix_env="DW_NO_SUCH_SOCKET", say=False)
    signer_url = f"http://127.0.0.1:{srv.server_address[1]}"
    con = Console(DomainDirectory(mine), ReadView(mine, wall=wall), ConsoleAPI(DomainDirectory(mine), lambda c: None),
                  refresh_interval=60, holder_vars=south.vars, signer_url=signer_url)
    door = con.serve(port=0)

    def stop():
        con.stop(door)
        srv.shutdown()
    return north_holder, south, holder, con, signer_url, f"http://127.0.0.1:{door.server_address[1]}", lines, wall, stop


def test_a_move_is_made_on_the_new_holder_by_its_signer_through_the_door_and_checked_by_the_recovery_file():
    """ADR-0032's fifth operation: north is gone, and the operator moves the domain onto south — at SOUTH's door,
    `POST /domain/move {recovery}` (`w2cctl domain move` calls that door; there is no second road), handed to south's
    signer, which checks the file — not a grant: the holder that kept the grants is the one that is gone — and makes
    the move (`term.move_domain`). A file that is not this domain's is 403, a body that is not the move's 400, a theft
    answered by the signer's backup 400 (it holds the stolen keys themselves); then the move: term 2 on south, the
    ledger the spec keeps restored, the record saying where south's signer answers, a line of the journal — and a second
    move is 409: south holds the domain."""
    import tempfile
    from w2cplatform import w2cctl
    from w2cplatform.trust.signer import Signer
    from w2cplatform.cluster.variables import FakeVariables
    north_holder, south, holder, con, signer_url, base, lines, wall, stop = _moving_site()
    d = tempfile.mkdtemp(prefix="recovery-")
    right, wrong = os.path.join(d, "right.json"), os.path.join(d, "wrong.json")
    open(right, "wb").write(north_holder.signer.backup())
    open(wrong, "wb").write(Signer("acme", FakeVariables(), now=wall).backup())
    try:
        assert w2cctl.move(base, wrong)[0] == 403                                    # not this domain's signer
        assert w2cctl.main(["domain", "move", base, wrong]) == 1
        assert _call(base, "POST", "/domain/move", {})[0] == 400
        assert _call(base, "POST", "/domain/move", {"recovery": open(right).read(), "stolen": "yes"})[0] == 400
        st, out = w2cctl.move(base, right, stolen=True)
        assert st == 400 and "recovery file" in out["detail"], out
        assert south.vars.get("domain/testsub/ledger")[0] is None and holder.term is None   # nothing moved yet
        assert w2cctl.main(["domain", "move", base, right]) == 0
        assert holder.term.term == 2 and holder.term.name == "south" and holder.signer is holder.term.signer
        assert south.vars.get("domain/testsub/ledger")[0] == {"s1": "seen"}
        said = _call(signer_url, "GET", "/api/holder")[1]
        assert said["term"] == 2 and said["record"]["holder"] == "south" and said["record"]["url"] == "http://south.site:8445"
        assert lines[-1][0] == "domain.moved" and lines[-1][1]["term"] == 2 and lines[-1][1]["target"] == "south"
        st, out = w2cctl.move(base, right)
        assert st == 409 and "south holds the domain at term 2" in out["detail"], out
        assert holder.hand_to is not None                                            # its own root: it can hand on
    finally:
        stop()


def test_after_a_theft_the_move_through_the_door_drops_the_old_keys_and_a_wrong_root_is_refused():
    """Lesson 15, step 9, through the door: the root is off the holder, north is stolen, and the operator moves the
    domain onto south with the root's recovery file, saying so (`stolen`). Another root's file is 403 — no member holds
    a key set it signed. The move gives south keys of its own, the root signs the next key set without north's token
    key, and south's signer signs the people's tokens with the new key from then on."""
    from w2cplatform.domain.agent import ClusterTrust
    from w2cplatform.trust.signer import DomainRoot
    from w2cplatform.trust.tokens import TokenError, verify
    wall = Clock()
    root = DomainRoot("acme", now=wall)
    north_holder, south, holder, con, signer_url, base, lines, wall, stop = _moving_site(root)
    old_kid = north_holder.signer.tokens.kid
    stolen_token = north_holder.signer.tokens.issue("mallory", 900, now=wall(), kind="person")
    try:
        st, out = _call(base, "POST", "/domain/move", {"recovery": DomainRoot("acme", now=wall).recovery().decode(),
                                                       "stolen": True})
        assert st == 403 and "not this domain's recovery file" in out["detail"], out
        st, out = _call(base, "POST", "/domain/move", {"recovery": root.recovery().decode(), "stolen": True})
        assert st == 200 and out["term"] == 2 and out["stolen"] and out["keys_rev"] > 1, out
        keys = ClusterTrust(south.vars).keyset()
        assert keys.rev == out["keys_rev"] and old_kid not in keys.keys
        try:
            verify(stolen_token, keys, now=wall())
            raise AssertionError("the stolen key must be refused")
        except TokenError:
            pass
        assert holder.ids.signer is holder.signer and holder.signer.tokens.kid in keys.keys
        assert holder.hand_to is None                                                # an issued signer: the file moves it
        assert lines[-1][1]["stolen"] is True
    finally:
        stop()


# -- the cluster console's doors of a move, to processes (contract §10a; «Архитектор» 2026-10-06) ----------------------
def _signed_get(base, path, headers):
    import urllib.error
    import urllib.request
    try:
        with urllib.request.urlopen(urllib.request.Request(base + path, headers=headers), timeout=30) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def _signed_post(base, path, headers, body=None):
    import urllib.error
    import urllib.request
    req = urllib.request.Request(base + path, data=json.dumps(body or {}).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


class _SignerHere:
    """`SIGNER_URL` of this "box" for as long as a test needs it: where a cluster's console hands `/api/prepare` and
    `/api/take`."""
    def __init__(self, url): self.url, self.saved = url, os.environ.get("SIGNER_URL")
    def __enter__(self): os.environ["SIGNER_URL"] = self.url
    def __exit__(self, *a): os.environ.pop("SIGNER_URL") if self.saved is None else os.environ.__setitem__("SIGNER_URL", self.saved)


def _members_site(wall):
    """north holds term 1 (its signer's own root) and keeps a ledger; south and east are members admitted with keys;
    south keeps north's backup, and its agent carried home the list of members with it."""
    from w2cplatform.domain.agent import DomainAgent, DomainPublisher
    from w2cplatform.domain.members import Members
    from w2cplatform.domain.term import DomainHolder
    from w2cplatform.trust.memberkey import MemberKey
    from w2cplatform.trust.signer import Signer
    fed, wall = site(wall)
    north, south = fed.clusters["north"], fed.clusters["south"]
    signer = Signer("acme", north.vars, now=wall)
    DomainPublisher(north.vars).publish_keys(signer.tokens.keyset())
    north_holder = DomainHolder(fed, "north", signer, 1, wall)
    north_holder.claim()
    skey, ekey = MemberKey.load_or_make(south.vars), MemberKey.new()
    Members(north.vars, wall).add("south", "voucher", key=skey.pub, seal=skey.seal_pub)
    Members(north.vars, wall).add("east", "voucher", key=ekey.pub, seal=ekey.seal_pub)
    north.vars.put("domain/testsub/ledger", {"s1": "seen"})
    north_holder.backup(["south"], north.objects)
    for name, c in (("north", north), ("south", south)):          # the holder's own agent too: its cluster's list
        assert DomainAgent(name, north.vars, c.vars, now=wall, domain_objects=north.objects,
                           cluster_objects=c.objects).sync()
    return fed, wall, north_holder, signer, skey, ekey


def _cluster_console(c, wall):
    from w2cplatform.console import Mount, SpecConsole
    from w2cplatform.spec import SpecController
    srv = Mount(SpecConsole(SpecController(spec(), c.vars, c.objects, wall=wall, cluster=c.name), wall=wall)).serve(port=0)
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def _member_signer(fed, wall, consoles=None):
    """south's signer, as it runs on a member: its own store, a signer of its own made at its start."""
    from w2cplatform.console import open_doors
    from w2cplatform.domain.federation import Cluster, Federation
    from w2cplatform.domain.signer_service import Holder
    from w2cplatform.trust.signer import Signer
    north, south = fed.clusters["north"], fed.clusters["south"]
    mine = Federation()
    mine.add(Cluster("south", south.vars, south.objects, is_domain_holder=True))
    mine.add(Cluster("north", north.vars, north.objects))
    holder = Holder(south.vars, south.objects, Signer("acme", south.vars, now=wall), fed=mine,
                    signer_url="http://south.site:8445", wall=wall, consoles=consoles)
    srv = open_doors("127.0.0.1", 0, holder.handler(), unix_env="DW_NO_SUCH_SOCKET", say=False)
    return holder, srv, f"http://127.0.0.1:{srv.server_address[1]}"


def test_a_clusters_console_says_held_to_anybody_the_backup_to_a_member_and_prepare_to_the_holder_alone():
    """south's console, to processes: `/api/held` to anybody — exactly `{cluster, holder, term, keys, backup: {term, rev}}`,
    the record and the key set south holds, signed, and which backup copy it keeps (term and rev), never its content;
    `/api/backup` only to a member that signs its ask with the key it was admitted
    with (unsigned 401, a name off the list 403, a member's name with another key 401, east itself 200); `/api/prepare`
    handed to south's signer, which prepares only for the holder of the current term — north's token key; unsigned,
    a member's key: 403. The old doors `/domain/held`, `/domain/prepare` are no doors of a process (no alias, ADR 0003)."""
    from w2cplatform.trust.memberkey import MemberKey
    from w2cplatform.domain.term import backup_message, prepare_message
    fed, wall, north_holder, signer, skey, ekey = _members_site(None)
    srv, console = _cluster_console(fed.clusters["south"], wall)
    holder, ssrv, signer_url = _member_signer(fed, wall)
    try:
        st, said = _signed_get(console, "/api/held", {})
        assert st == 200 and sorted(said) == ["backup", "cluster", "holder", "keys", "term"], said
        assert said["cluster"] == "south" and said["holder"]["holder"] == "north" and said["term"] == 1
        assert said["keys"]["current"] == signer.tokens.kid and said["backup"] == {"term": 1, "rev": 1}   # its pair, no content
        for path in ("/domain/held", "/domain/prepare"):
            assert _signed_get(console, path, {})[0] in (401, 404), path      # a person's route, no process door
            assert _signed_get(signer_url, path, {})[0] == 404, path

        def ask(member, key):
            at = wall()
            return _signed_get(console, "/api/backup", {"X-W2C-Member": member, "X-W2C-Time": f"{at:.3f}",
                                                        "X-W2C-Signature": key.sign(backup_message("south", member, at))})
        assert _signed_get(console, "/api/backup", {})[0] == 401
        assert ask("mallory", MemberKey.new())[0] == 403
        assert ask("east", MemberKey.new())[0] == 401
        st, got = ask("east", ekey)
        assert st == 200 and int(got["pointer"]["rev"]) == 1 and json.loads(got["backup"])["rev"] == 1, got

        def prepare(sign_with):
            at = wall()
            return _signed_post(console, "/api/prepare", {"X-W2C-Time": f"{at:.3f}",
                                                          "X-W2C-Signature": sign_with(prepare_message("south", at))})
        assert _signed_post(console, "/api/prepare", {})[0] == 404                # no signer on this box: said
        with _SignerHere(signer_url):
            assert _signed_post(console, "/api/prepare", {})[0] == 403
            assert prepare(ekey.sign)[0] == 403                                    # a member is not the holder
            st, pubs = prepare(lambda m: north_holder.signer.tokens.key.sign(m).hex())
            assert st == 200 and len(pubs["seal"]) == 64, pubs
            assert prepare(skey.sign)[0] == 403                                    # nor is south itself
    finally:
        for s in (srv, ssrv):
            s.shutdown()
            s.server_close()


def test_a_planned_handover_over_the_doors_is_taken_by_the_target_onto_its_own_store():
    """north hands the domain to south over the doors alone (`asked_to_take`): south's console hands prepare and take
    to south's signer, which checks north's signature and grant, opens north's keys with the key it prepared, reads
    north over north's console (`/api/held`, and `/api/backup` signed with south's member key) and moves the domain
    onto its OWN store. north writes nothing of south's: every write into south's store is south's signer's or south's
    agent's. north reads the term south claimed and steps down; a second take is refused."""
    import threading
    import time
    from w2cplatform.domain.agent import DomainAgent
    from w2cplatform.domain.signer_service import asked_to_take
    from w2cplatform.domain.term import HOLDER, handover
    fed, wall, north_holder, signer, skey, ekey = _members_site(time.time)
    north, south = fed.clusters["north"], fed.clusters["south"]
    nsrv, ncon = _cluster_console(north, wall)
    srv, console = _cluster_console(south, wall)
    holder, ssrv, signer_url = _member_signer(fed, wall, consoles={"north": ncon})
    by_north, carrying = [], threading.Event()
    put = south.vars.put

    def watched(path, items, cas=None):
        if threading.current_thread() is threading.main_thread() and not carrying.is_set():
            by_north.append(path)                       # the main thread is north's, but for south's agent below
        return put(path, items, cas)
    south.vars.put = watched

    def carry_to():
        carrying.set()
        try:
            DomainAgent("south", north.vars, south.vars, now=wall, domain_objects=north.objects,
                        cluster_objects=south.objects).sync()
        finally:
            carrying.clear()
    try:
        with _SignerHere(signer_url):
            new, report = handover(north_holder, "south", lambda n: fed.clusters[n].objects, carry_to,
                                   asked_to_take(console, "south", north_holder, signer))
            assert new is None and report["term"] == 2 and report["planned"], report
            assert by_north == [], by_north
            assert north_holder.deposed_by["holder"] == "south" and north_holder.deposed_by["term"] == 2
            rec = json.loads(south.vars.get(HOLDER)[0]["doc"])
            assert rec["holder"] == "south" and rec["term"] == 2 and holder.term.term == 2
            assert south.vars.get("domain/testsub/ledger")[0] == {"s1": "seen"}
            try:
                asked_to_take(console, "south", north_holder, signer)()
                raise AssertionError("south holds the domain: nothing is taken twice")
            except RuntimeError as e:
                assert "did not prepare (409" in str(e), e
    finally:
        south.vars.put = put
        for s in (nsrv, srv, ssrv):
            s.shutdown()
            s.server_close()


# -- the witness: a member matched by its own name, the field that carries it declared ---------------------------------
def test_a_witness_names_a_member_by_the_field_that_carries_its_name_and_the_spec_must_declare_it_fixed():
    """`domain.witness: {report, member_field}` — testsub2's `{report: seen, member_field: of}`: the witness objects are
    `testsub2/seen/*`, and the field is the unit's, declared `fixed: true` (ADR-0010). A spec whose witness names no
    field, a field that is not the unit's, one that is not fixed, or the bare family of before, does not load. The domain
    matches a member by its own name — no `ref_of` handed in: one a witness heard of after its last report is
    `not_reporting`, another is `silent`."""
    from w2cplatform import specyaml
    from w2cplatform.domain import declared
    from w2cplatform.domain.alarms import DomainAlarms
    from w2cplatform.spec import SubsystemSpec
    t2 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "testdata", "testsub2.subsystem.yaml")
    s2 = SubsystemSpec.load(t2)
    assert (s2.domain.witness, s2.domain.member_field) == ("seen", "of")
    assert "testsub2/seen/" in declared.witnesses()
    base = specyaml.loads(open(t2, encoding="utf-8"))
    for bad in ("seen", {"report": "seen"}, {"report": "seen", "member_field": "nope"},
                {"report": "seen", "member_field": "mode"}, {"report": "Seen!", "member_field": "of"},
                {"report": "seen", "member_field": "of", "via": "x"}):
        try:
            SubsystemSpec.from_dict({**base, "domain": {**base["domain"], "witness": bad}})
            raise AssertionError(f"taken: {bad}")
        except ValueError:
            pass
    fed, wall = site()
    north = fed.clusters["north"]

    class Silent:                                             # each member's door: its last report, an hour old
        def __init__(self, name):
            self.name = name

        def alarms(self, since, until, limit):
            from w2cplatform.domain.federation import Unreachable
            raise Unreachable(self.name)

        def last(self, since, until, limit):
            return {"events": [], "truncated": False, "known_until": wall() - 3600}
    north.objects.put("testsub2/seen/w-1", json.dumps({"ts": wall(), "cluster": "north",
                                                       "units": {"south": 5.0, "s1": 1.0}}).encode())
    SubsystemSpec.load(t2)
    out = DomainAlarms(fed, Silent, wall).list(since=wall() - 7200)
    assert out["members"]["south"]["alive_at"] == wall() - 5 and out["members"]["south"]["alive_via"] == "north"
    assert [e["kind"] for e in out["events"] if e["member"] == "south"] == ["not_reporting"]
    assert DomainAlarms(fed, Silent, wall).alive_at("s1") == (wall() - 1, "north")    # by name, whatever it names
    assert DomainAlarms(fed, Silent, wall).alive_at("nobody") is None

