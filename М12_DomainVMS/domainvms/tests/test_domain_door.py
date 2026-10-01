"""Feedback CA — the domain's door asks who is calling, and the domain's rights are the domain's own.

The first answer to "who may change the domain" was an admin of the cluster that holds it. A holder moves
(Lesson 15), and the domain's administrators would have moved with it. So the domain keeps its grants in
`domain/grants/domain`, they travel in the backup, a `GET` asks for `view`, and the last admin cannot be
taken away through the door it guards."""
import json
import urllib.error
import urllib.request

from cluster.variables import FakeVariables

from domain.api import ApiError, ConsoleAPI
from domain.console import Console
from domain.device import DeviceCluster
from domain.federation import DomainDirectory
from domain.grants import DOMAIN_GRANTS, Grant, LastAdmin, domain_may, set_domain_grants
from domain.members import Members
from domain.readview import ReadView
from domain.term import move_domain
from tests.conftest import Clock
from tests.test_lesson15_root import DOMAIN, _objects, _site


def test_a_grant_on_the_domain_is_on_the_whole_domain_and_admin_includes_view():
    v = FakeVariables()
    set_domain_grants(v, [Grant("anna", "admin", None, 0.0), Grant("boris", "view", None, 2000.0),
                          Grant("vera", "admin", 7, 0.0)], 1000.0)
    assert domain_may(v, "anna", "view", 1000.0) and domain_may(v, "anna", "admin", 10 ** 12)   # 0: never lapses
    assert domain_may(v, "boris", "view", 1000.0) and not domain_may(v, "boris", "admin", 1000.0)
    assert not domain_may(v, "boris", "view", 2000.0)                    # a number is an end
    assert not domain_may(v, "vera", "admin", 1000.0)                    # a camera is not the domain


def test_the_last_admin_is_not_taken_away():
    v = FakeVariables()
    set_domain_grants(v, [Grant("anna", "admin", None, 0.0)], 1000.0)
    for grants in ([], [Grant("anna", "view", None, 0.0)], [Grant("anna", "admin", None, 900.0)]):
        try:
            set_domain_grants(v, grants, 1000.0)
            raise AssertionError("a write that leaves no admin must be refused")
        except LastAdmin:
            pass
    assert domain_may(v, "anna", "admin", 1000.0)


def test_no_cluster_is_called_domain():
    m = Members(FakeVariables(), Clock(1000.0))
    try:
        m.add("domain", "approved by anna")
        raise AssertionError("the name is the domain's own scope")
    except ApiError as e:
        assert e.status == 400


def test_the_door_asks_for_view_to_look_and_admin_to_change():
    wall = Clock()
    fed, devices, root, holder, agents, _ = _site(wall)
    set_domain_grants(holder.vars, [Grant("anna", "admin", None, 0.0), Grant("boris", "view", None, 0.0)], wall())
    may = lambda cap: (lambda s: domain_may(holder.vars, s, cap, wall()))         # noqa: E731
    con = Console(DomainDirectory(fed), ReadView(fed, wall=wall), ConsoleAPI(DomainDirectory(fed), lambda n: None,
                  verifier=lambda t: t), refresh_interval=60, members=Members(holder.vars, wall),
                  admin=may("admin"), viewer=may("view"), publish_to=devices["cam-SN0"].disk_door())
    srv = con.serve(port=0)
    base = f"http://127.0.0.1:{srv.server_address[1]}"

    def call(path, who=None, body=None):
        req = urllib.request.Request(base + path, data=json.dumps(body).encode() if body is not None else None,
                                     method="POST" if body is not None else "GET",
                                     headers={"Authorization": f"Bearer {who}"} if who else {})
        try:
            return urllib.request.urlopen(req).status
        except urllib.error.HTTPError as e:
            return e.code
    try:
        assert call("/healthz") == 200
        assert call("/api/members") == 401 and call("/api/cameras") == 401
        assert call("/api/members", "vera") == 403
        assert call("/api/members", "boris") == 200 and call("/api/members", "anna") == 200
        assert call("/api/members", "boris", {"name": "cam-SN3"}) == 403
    finally:
        con.stop(srv)


def test_the_domains_administrators_do_not_move_with_the_holder():
    """A planned move to SN1: the domain's grants are in the backup, and anna administers the domain on SN1 —
    not whoever administers camera SN1."""
    wall = Clock()
    fed, devices, root, holder, agents, _ = _site(wall)
    set_domain_grants(holder.vars, [Grant("anna", "admin", None, 0.0)], wall())
    holder.backup(["cam-SN1"], devices["cam-SN0"].disk_door()); agents["cam-SN1"].sync()
    new, _ = move_domain(fed, "cam-SN1", root.recovery(), DOMAIN, _objects(devices), wall)
    assert new.vars.get(DOMAIN_GRANTS)[0] == holder.vars.get(DOMAIN_GRANTS)[0]
    assert domain_may(new.vars, "anna", "admin", wall())


def test_a_name_that_does_not_exist_costs_as_much_as_a_wrong_password():
    """Feedback BZ: the login door must not tell a stranger which names are real. Both refusals run scrypt once."""
    import domain.identity as ident
    calls = []
    real = ident._hash
    ident._hash = lambda pw, salt=None: (calls.append(1), real(pw, salt))[1]
    try:
        import tempfile
        from cluster.objectstore import FsObjectStore
        from domain.signer import Signer
        users = ident.IdentityStore(Signer("acme", FakeVariables(), now=Clock()), FakeVariables(),
                                    FsObjectStore(tempfile.mkdtemp()), now=Clock())
        users.create_local("alice", "secret", ["operator"])
        calls.clear()
        for uid in ("alice", "nobody"):
            try:
                users.login(uid, "wrong")
                raise AssertionError("refused")
            except ident.AuthError:
                pass
        assert len(calls) == 2                                           # one hash each, known or not
    finally:
        ident._hash = real


def test_a_devices_password_is_not_the_domains_to_carry():
    """Feedback CD: an edit for a cluster that is off is KEPT — in the holder's store, its backups, a relay's
    books — and a password there would be in the clear past the cluster's key. Refused before anything is kept."""
    api = ConsoleAPI(None, None)
    try:
        api.update_camera(7, {"name": "gate", "cred_secret": "Hunter2"}, "k1")
        raise AssertionError("refused")
    except ApiError as e:
        assert e.status == 400 and "cred_secret" in e.detail and "Hunter2" not in e.detail
    assert api._seen == {}
