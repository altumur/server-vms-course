"""C5 accounts stay in the cluster; only granted complete book observations authenticate."""
import copy
import json
from types import SimpleNamespace
from unittest.mock import patch

from tests.vmsconftest import Box
from vms import live_accounts as la
from w2cplatform import catalog
from w2cplatform.contract import Eyes, Heartbeat
from w2cplatform.domain import bookmerge, booknames, booksecrets
from w2cplatform.domain.carry import open_row, seal_row
from w2cplatform.sealing import Sealer, seal_items
from w2cplatform.spec import BookMerge


def ring(label):
    return Sealer({label: (label.encode()*32)[:32]}, label)


def fixture(own="a", holder="holder"):
    box = Box()
    box.vars.put("domain/member", {"cluster": own})
    box.vars.put("domain/holder", {"doc": json.dumps({"holder": holder, "term": 1})})
    roster = {"doc": json.dumps({"rev": 1, "members": {name: {} for name in ("a", "b", "holder")}})}
    box.vars.put("domain/members" if own == holder else "domain/member-list", roster)
    worker = SimpleNamespace(name="g-1", vars=box.vars, objects=box.objects,
                             sealer=ring("source"), eyes=Eyes(box.clock, box.wall))
    box.objects.put("live/heartbeats/g-1", Heartbeat("g-1", box.wall()).to_bytes())
    return box, worker


def seed(box, sealer, name="wall", password="private-wall-password", disabled=False):
    path = la.ACCOUNTS+name
    box.vars.put(path, seal_items(sealer, {"doc": json.dumps({"name": name, "disabled": disabled,
        "at": box.wall(), "by": "anna"}), "password_secret": password}, path))
    return password


def book(name="wall", password="private-wall-password", *, disabled=False, missing=(), origin="a", **over):
    value = {"name": name, "to": ["a", "b", "holder"], "disabled": disabled,
             "password_secret": password, **over}
    return {"": json.dumps({"missing": list(missing)}), name: json.dumps({"missing": list(missing),
        "entries": [{"member": origin, "item": "g-1/"+name, "value": value}]})}


def test_publisher_rederives_sealed_contribution_after_restart_and_exposes_no_plaintext_in_store():
    box, worker = fixture()
    password = seed(box, worker.sealer)
    raw = box.vars.get(la.ACCOUNTS+"wall")[0]
    assert password not in json.dumps(raw)
    contribution = la.accounts(worker, [])
    assert password not in json.dumps(contribution)
    opened = open_row(worker.sealer, contribution, la.INPUT+worker.name)
    assert json.loads(opened["wall"]) == {"name": "wall", "to": ["a", "b", "holder"],
                                          "disabled": False, "password_secret": password}
    # A new gateway instance holds no account cache and still derives the same value from the durable table.
    again = SimpleNamespace(**{**vars(worker), "eyes": Eyes(box.clock, box.wall)})
    assert open_row(worker.sealer, la.accounts(again, []), la.INPUT+again.name) == opened
    worker.sealer = ring("wrong")
    assert la.accounts(worker, []) == {}                             # unreadable password is never its ciphertext


def test_publisher_elects_one_fresh_gateway_and_uses_current_holder_roster_without_old_copy():
    box, worker = fixture("holder")
    seed(box, worker.sealer)
    box.vars.put("domain/member-list", {"doc": json.dumps({"rev": 9, "members": {"stale": {}}})})
    first = open_row(worker.sealer, la.accounts(worker, []), la.INPUT+worker.name)
    assert json.loads(first["wall"])["to"] == ["a", "b", "holder"]
    box.objects.put("live/heartbeats/g-2", Heartbeat("g-2", box.wall()).to_bytes())
    worker.name = "g-2"
    assert la.accounts(worker, []) == {}
    box.clock.advance(46)
    box.objects.put("live/heartbeats/g-2", Heartbeat("g-2", box.wall()+100000).to_bytes())
    assert la.accounts(worker, [])
    box.wall.advance(1)
    box.objects.put("live/heartbeats/g-1", Heartbeat("g-1", box.wall()).to_bytes())
    assert la.accounts(worker, []) == {}
    worker.name = "g-1"
    box.vars.put("domain/members", {"doc": "{"})
    assert la.accounts(worker, []) == {}                             # stale carried list cannot replace the original


def test_reader_never_authenticates_from_local_table_or_legacy_flat_book():
    box, worker = fixture()
    seed(box, worker.sealer)
    assert la.stream_accounts(box.vars, "a", worker.sealer) == {}
    box.vars.put(la.BOOK, {"accounts_secret": json.dumps({"wall": "old-password"})})
    assert la.stream_accounts(box.vars, "a", worker.sealer) == {}
    good = book()
    box.vars.put(la.BOOK, seal_row(worker.sealer, good, la.BOOK))
    assert la.stream_accounts(box.vars, "a", worker.sealer) == {"wall": "private-wall-password"}
    for bad in (book(disabled=True), book(missing=["other"]), book(pending=True),
                book(to=["foreign"]), book(disabled=1), book(password="")):
        box.vars.put(la.BOOK, seal_row(worker.sealer, bad, la.BOOK))
        assert la.stream_accounts(box.vars, "a", worker.sealer) == {}
    bad = copy.deepcopy(good)
    item = json.loads(bad["wall"])
    item["entries"].append({**item["entries"][0], "member": "other"})
    bad["wall"] = json.dumps(item)
    box.vars.put(la.BOOK, seal_row(worker.sealer, bad, la.BOOK))
    assert la.stream_accounts(box.vars, "a", worker.sealer) == {}


def test_reader_opens_only_current_holder_result_and_is_bound_to_book_row_and_account_item():
    box, worker = fixture("a", "a")
    box.vars.put(la.BOOK, seal_row(worker.sealer, book(password="stale"), la.BOOK))
    path = la.BOOK+"/a"
    value = seal_row(worker.sealer, book(), path)
    box.vars.put(path, value)
    assert la.stream_accounts(box.vars, "a", worker.sealer) == {"wall": "private-wall-password"}
    box.vars.as_writer("domain", ["domain/*"]).delete(path)
    assert la.stream_accounts(box.vars, "a", worker.sealer) == {}
    box.vars.put(path, seal_row(worker.sealer, book(), la.BOOK))       # copied ciphertext belongs to another row
    assert la.stream_accounts(box.vars, "a", worker.sealer) == {}
    box.vars.put(path, value)
    assert la.stream_accounts(box.vars, "a", ring("wrong")) == {}


def test_secret_flow_uses_generic_book_transport_and_grants_and_unique_collision_delivers_neither():
    from w2cplatform.domain.agent import DomainPublisher
    from w2cplatform.trust.signer import DomainRoot, Signer
    box, worker = fixture()
    password = seed(box, worker.sealer)
    root = DomainRoot("accounts-test", now=box.wall)
    signer = Signer("accounts-test", box.vars, root=root, now=box.wall, sealer=worker.sealer)
    DomainPublisher(box.vars).publish_keys(root.key_set(signer.tokens.keyset(), 1))
    box.vars.put("domain/root", {"pub": root.public_bytes.hex()})
    path = la.INPUT+worker.name
    sealed = la.accounts(worker, [])
    transported = booksecrets.outgoing("a", path, sealed, box.vars, worker.sealer, box.wall())
    assert password not in json.dumps(transported) and "x25519:v1:" in json.dumps(transported)
    opened = booksecrets.incoming("a", path, transported, signer.book_key)
    rule = BookMerge(la.INPUT, "name", "unique", "to")
    merged = bookmerge.collect(rule, {"a": {path: opened}, "b": {}, "holder": {}}, ["a", "b", "holder"])
    declaration = SimpleNamespace(name="live", domain_prefix="domain/live/", domain=SimpleNamespace(
        names={"stream-accounts/": {"exclusive_with": "domain/users", "grant": "view"}},
        merged={"stream-accounts": rule}, tokens={}))
    box.vars.put("domain/grants/b", {"wall|view|": str(box.wall()+100)})
    with patch.object(catalog, "_loaded", {"live": declaration}):
        delivered = booknames.delivery(box.vars, la.BOOK+"/b", "b", merged.rows["b"], box.wall())
        denied = booknames.delivery(box.vars, la.BOOK+"/holder", "holder", merged.rows["holder"], box.wall())
        assert "wall" in delivered and set(denied) == {""}
        destination_ring = ring("destination")
        box.vars.put("domain/holder", {"doc": json.dumps({"holder": "holder", "term": 1})})
        box.vars.put(la.BOOK, booksecrets.at_rest(delivered, destination_ring, la.BOOK))
        assert password not in json.dumps(box.vars.get(la.BOOK)[0])
        assert la.stream_accounts(box.vars, "b", destination_ring) == {"wall": password}
        collision = bookmerge.collect(rule, {"a": {path: opened}, "b": {path: opened}, "holder": {}}, ["a", "b", "holder"])
        assert all(set(row) == {""} for row in collision.rows.values())
        box.vars.put(la.BOOK, collision.rows["b"])
        assert la.stream_accounts(box.vars, "b", destination_ring) == {}


def test_reader_and_publisher_need_neither_people_nor_foreign_grants_from_cluster_store():
    box, worker = fixture()
    seed(box, worker.sealer)
    accessed = []
    inner = box.vars

    class Limited:
        def get(self, path):
            accessed.append(("get", path))
            assert path in {"domain/member", "domain/holder", "domain/member-list", la.BOOK} or path.startswith(la.ACCOUNTS)
            return inner.get(path)

        def list(self, prefix):
            accessed.append(("list", prefix))
            assert prefix == la.ACCOUNTS
            return inner.list(prefix)

    worker.vars = Limited()
    assert la.accounts(worker, [])
    inner.put(la.BOOK, seal_row(worker.sealer, book(), la.BOOK))
    assert la.stream_accounts(worker.vars, "a", worker.sealer) == {"wall": "private-wall-password"}
    assert all(not path.startswith(("domain/users", "domain/grants")) for _, path in accessed)


def test_unreadable_local_record_is_not_published_as_disabled_or_as_ciphertext():
    box, worker = fixture()
    seed(box, worker.sealer)
    path = la.ACCOUNTS+"wall"
    original = box.vars.get(path)[0]
    for damaged in ({"doc": "{", "password_secret": "never-log"},
                    {**original, "password_secret": ""},
                    {**original, "doc": json.dumps({"name": "wall", "disabled": 1, "at": 2, "by": "anna"})},
                    {**original, "doc": json.dumps({"name": "foreign", "disabled": False, "at": 2, "by": "anna"})}):
        box.vars.put(path, damaged)
        assert la.accounts(worker, []) == {}
    box.vars.put(path, original)
    worker.sealer = None
    assert la.accounts(worker, []) == {}


class Console:
    def __init__(self):
        self.users, self.grants, self.calls = [], {}, []
        self.fail_put = False
        self.before_users = None

    def as_person(self, auth, by):
        def do(method, path, body=None):
            self.calls.append((auth, by, method, path, body))
            if method == "GET" and path == "/domain/users":
                if self.before_users:
                    self.before_users()
                return {"users": [{"name": name} for name in self.users]}
            if method == "GET" and path == "/domain/grants":
                return {"grants": copy.deepcopy(self.grants)}
            if method == "PUT" and path.startswith("/domain/grants/"):
                if self.fail_put:
                    from w2cplatform.domain.api import ApiError
                    raise ApiError(403, "this original person cannot revoke grants")
                self.grants[path[len("/domain/grants/"):]] = body["lines"]
                return {"ok": True}
            raise AssertionError((method, path))
        return SimpleNamespace(do=do)


def service(box, worker, console=None):
    return la.LiveAccounts(box.vars.as_writer("liveworker", [la.ACCOUNTS+"*"]), box.objects,
                           sealer=worker.sealer, console=console or Console(), wall=box.wall)


def error(status, call):
    from w2cplatform.domain.api import ApiError
    try:
        call()
    except ApiError as fault:
        assert fault.status == status, fault
        return
    raise AssertionError("an invalid account operation succeeded")


def test_cluster_crud_keeps_password_only_in_sealed_row_and_published_disable_and_reset_survive_restart():
    box, worker = fixture()
    console = Console()
    first = service(box, worker, console)
    password = first.create("wall", "Bearer anna", "anna")
    assert len(password) == 32
    assert first.listing() == [{"name": "wall", "disabled": False, "at": box.wall(), "by": "anna"}]
    assert password not in json.dumps(first.listing())
    from w2cplatform.variables import FileVariables
    restarted_vars = FileVariables(box.vars.root, volatile=True).as_writer("liveworker", [la.ACCOUNTS+"*"])
    restarted = la.LiveAccounts(restarted_vars, sealer=worker.sealer, console=console, wall=box.wall)
    assert restarted.listing() == first.listing()
    opened = open_row(worker.sealer, la.accounts(worker, []), la.INPUT+worker.name)
    assert json.loads(opened["wall"])["password_secret"] == password
    box.wall.advance(1)
    replacement = restarted.reset_password("wall", "boris")
    assert replacement != password
    opened = open_row(worker.sealer, la.accounts(worker, []), la.INPUT+worker.name)
    assert json.loads(opened["wall"])["password_secret"] == replacement
    restarted.set_disabled("wall", True, "boris")
    opened = open_row(worker.sealer, la.accounts(worker, []), la.INPUT+worker.name)
    assert json.loads(opened["wall"])["disabled"] is True
    assert password not in json.dumps(box.vars.get(la.ACCOUNTS+"wall")[0])
    assert replacement not in json.dumps(box.vars.get(la.ACCOUNTS+"wall")[0])
    assert console.calls == [("Bearer anna", "anna", "GET", "/domain/users", None)]


def test_create_checks_people_local_row_and_partial_foreign_book_but_does_not_claim_global_uniqueness():
    box, worker = fixture()
    console = Console(); console.users = ["anna"]
    accounts = service(box, worker, console)
    error(409, lambda: accounts.create("anna", "Bearer op", "op"))
    accounts.create("local", "Bearer op", "op")
    error(409, lambda: accounts.create("local", "Bearer op", "op"))
    box.vars.put(la.BOOK, seal_row(worker.sealer, book(name="foreign", origin="b", missing=["holder"]), la.BOOK))
    error(409, lambda: accounts.create("foreign", "Bearer op", "op"))
    box.vars.put(la.BOOK, {"": '{"missing":["b"]}'})
    assert accounts.create("new", "Bearer op", "op")                 # partial check, no distributed reservation
    for name in ("", ".", "..", "a/b", "a:b", "break-glass", "a\n", "a|b"):
        error(400, lambda: accounts.create(name, "Bearer op", "op"))
    error(400, lambda: accounts.set_disabled("new", 1, "op"))
    error(404, lambda: accounts.reset_password("absent", "op"))
    unsealed = la.LiveAccounts(box.vars, console=console, wall=box.wall)
    error(503, lambda: unsealed.create("no-ring", "Bearer op", "op"))


def test_delete_revokes_only_matching_grant_lines_through_local_console_as_original_person_then_removes_row():
    box, worker = fixture()
    console = Console()
    accounts = service(box, worker, console)
    accounts.create("wall", "Bearer anna", "anna")
    own = {"subject": "wall", "cap": "view", "scope": "unit:cam/7", "until": box.wall()+50}
    other = {"subject": "anna", "cap": "admin", "scope": "*", "until": box.wall()+100}
    console.grants = {"a": [own, other], "b": [own], "holder": [other]}
    assert accounts.delete("wall", "Bearer boris", "boris") == ["a", "b"]
    assert console.grants == {"a": [other], "b": [], "holder": [other]}
    assert box.vars.get(la.ACCOUNTS+"wall")[0] is None
    assert [(auth, by, method, path) for auth, by, method, path, _ in console.calls[-3:]] == [
        ("Bearer boris", "boris", "GET", "/domain/grants"),
        ("Bearer boris", "boris", "PUT", "/domain/grants/a"),
        ("Bearer boris", "boris", "PUT", "/domain/grants/b")]
    error(404, lambda: accounts.delete("wall", "Bearer boris", "boris"))


def test_failed_grant_revocation_preserves_account_for_an_authorized_retry():
    box, worker = fixture()
    console = Console(); accounts = service(box, worker, console)
    accounts.create("wall", "Bearer anna", "anna")
    console.grants = {"a": [{"subject": "wall", "cap": "view", "scope": "*", "until": box.wall()+50}]}
    console.fail_put = True
    error(403, lambda: accounts.delete("wall", "Bearer guest", "guest"))
    assert accounts.listing()[0]["name"] == "wall"
    console.fail_put = False
    assert accounts.delete("wall", "Bearer anna", "anna") == ["a"]


def test_racing_local_creators_keep_one_password_and_never_overwrite_the_first_account():
    import threading
    from concurrent.futures import ThreadPoolExecutor
    from w2cplatform.domain.api import ApiError
    box, worker = fixture()
    console = Console()
    barrier = threading.Barrier(2)
    console.before_users = lambda: barrier.wait(timeout=3)
    accounts = service(box, worker, console)
    with ThreadPoolExecutor(max_workers=2) as pool:
        attempts = [pool.submit(accounts.create, "wall", "Bearer anna", "anna") for _ in range(2)]
        passwords, conflicts = [], []
        for attempt in attempts:
            try:
                passwords.append(attempt.result(timeout=4))
            except ApiError as fault:
                conflicts.append(fault.status)
    assert len(passwords) == 1 and conflicts == [409]
    opened = open_row(worker.sealer, box.vars.get(la.ACCOUNTS+"wall")[0], la.ACCOUNTS+"wall")
    assert opened["password_secret"] == passwords[0]


def test_bad_clock_or_unreadable_people_list_never_creates_or_overwrites_an_account():
    box, worker = fixture()
    console = Console(); accounts = service(box, worker, console)
    console.as_person = lambda auth, by: SimpleNamespace(do=lambda *args: {"users": "not a list"})
    error(503, lambda: accounts.create("wall", "Bearer anna", "anna"))
    assert box.vars.get(la.ACCOUNTS+"wall")[0] is None
    accounts = service(box, worker)
    accounts.create("wall", "Bearer anna", "anna")
    before = box.vars.get(la.ACCOUNTS+"wall")[0]
    accounts.wall = lambda: float("nan")
    error(503, lambda: accounts.reset_password("wall", "anna"))
    assert box.vars.get(la.ACCOUNTS+"wall")[0] == before
    error(503, lambda: accounts.set_disabled("wall", True, "anna"))
    assert box.vars.get(la.ACCOUNTS+"wall")[0] == before


def test_admin_can_reset_or_delete_a_valid_account_without_opening_its_previous_password():
    box, worker = fixture()
    console = Console(); old = service(box, worker, console)
    original_password = old.create("wall", "Bearer anna", "anna")
    new_ring = ring("replacement")
    repair = la.LiveAccounts(box.vars.as_writer("liveworker", [la.ACCOUNTS+"*"]), sealer=new_ring,
                             console=console, wall=box.wall)
    assert repair.listing()[0]["name"] == "wall"
    error(503, lambda: repair.set_disabled("wall", True, "anna"))
    new_password = repair.reset_password("wall", "anna")
    assert new_password != original_password
    worker.sealer = new_ring
    opened = open_row(new_ring, la.accounts(worker, []), la.INPUT+worker.name)
    assert json.loads(opened["wall"])["password_secret"] == new_password
    no_ring = la.LiveAccounts(box.vars.as_writer("liveworker", [la.ACCOUNTS+"*"]), console=console, wall=box.wall)
    assert no_ring.delete("wall", "Bearer anna", "anna") == []
    assert box.vars.get(la.ACCOUNTS+"wall")[0] is None
