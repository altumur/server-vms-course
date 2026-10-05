"""Who the domain's members are — decided by the registrar, read by every pass.

A box the registrar admits (Lesson 6) is added to the domain's list of members, and the next pass reads it from
its reports — nobody edits the environment of the domain's processes, nothing restarts. A member that leaves is
removed, and the next pass drops it, whatever report it left behind. Where nobody has written the list yet, the
configuration stands.
"""
import json
import urllib.error
import urllib.request

from w2cplatform.cluster.variables import FakeVariables

from w2cplatform.domain.agent import DomainAgent
from w2cplatform.domain.api import ConsoleAPI
from vms.domainpart.books import Books
from w2cplatform.domain.console import Console
from vms.domainpart.crossing import Crossings
from vms.domainpart.device import DeviceCluster, member_name
from w2cplatform.trust.enroll import Manufacturer, Pledge, Registrar
from w2cplatform.domain.federation import DomainDirectory, Federation
from w2cplatform.domain.members import Members, apply
from w2cplatform.domain.readview import ReadView
from w2cplatform.trust.signer import Signer
from w2cplatform.domain.uplink import member_copy
from tests.domain.conftest import Clock, make_cluster


def _domain(wall):
    fed = Federation()
    north, _ = make_cluster("north", domain=True)
    fed.add(north)
    signer = Signer("acme", north.vars, now=wall)
    members = Members(north.vars, wall=wall)
    return fed, north, signer, members


def _enroll(reg, vendor, serial, nonce="n1"):
    cert, key = vendor.provision(serial)
    vendor.sell(serial, "acme")
    box = Pledge(serial, cert, key, temp_credential=None)
    return reg.enroll_with_voucher(box.hello(nonce=nonce), vendor.voucher(serial, reg.id, nonce))


def test_a_box_the_registrar_admits_is_a_member_the_next_pass_reads():
    """Zero-touch enrollment of SN9001. The registrar writes the admission into the domain's list of members; the
    domain's next pass adds the camera — read from its reports — and it is on the list the console shows. The
    domain's configuration never named it."""
    wall = Clock(1000.0)
    fed, north, signer, members = _domain(wall)
    vendor = Manufacturer("vendor", now=wall)
    reg = Registrar("acme", signer, vendor.ca_cert, vendor.masa_public, now=wall, members=members,
                    cluster_of=member_name)
    _enroll(reg, vendor, "SN9001")
    assert members.names() == ["cam-SN9001"] and members.read()["members"]["cam-SN9001"]["how"] == "voucher"

    cam = DeviceCluster("SN9001", FakeVariables(), wall=wall)
    cam.boot()
    DomainAgent(cam.name, north.vars, cam.flash, now=wall, domain_objects=north.objects,
                published=cam.local_objects()).sync()
    books = Books(Crossings(north.vars, ReadView(fed, wall=wall), wall), north.objects, members=members)
    out = books.pass_once()
    assert out["members"] == {"joined": ["cam-SN9001"], "left": []}
    assert [r["ref"] for r in books.crossings.view.list()["rows"]] == ["SN9001"]
    assert books.pass_once()["members"] == {"joined": [], "left": []}          # followed once


def test_a_member_that_leaves_is_dropped_whatever_report_it_left_behind():
    wall = Clock(1000.0)
    fed, north, signer, members = _domain(wall)
    vendor = Manufacturer("vendor", now=wall)
    reg = Registrar("acme", signer, vendor.ca_cert, vendor.masa_public, now=wall, members=members,
                    cluster_of=member_name)
    _enroll(reg, vendor, "SN9002")
    cam = DeviceCluster("SN9002", FakeVariables(), wall=wall)
    cam.boot()
    DomainAgent(cam.name, north.vars, cam.flash, now=wall, domain_objects=north.objects,
                published=cam.local_objects()).sync()
    apply(fed, members, north.objects)
    assert "cam-SN9002" in fed.clusters

    assert reg.leave("SN9002", by="anna") and reg.audit[-1]["how"] == "left"
    assert apply(fed, members, north.objects) == {"joined": [], "left": ["cam-SN9002"]}
    view = ReadView(fed, wall=wall); view.refresh()
    assert view.list()["rows"] == []                                   # its last report is still there; it is not read


def test_with_no_list_written_the_configuration_stands():
    wall = Clock(1000.0)
    fed, north, signer, members = _domain(wall)
    fed.add(member_copy("cam-SN9003", north.objects, wall=wall))        # `cam-SN9003=report` in CLUSTERS
    assert apply(fed, members, north.objects) == {"joined": [], "left": []} and "cam-SN9003" in fed.clusters


def test_a_leave_from_the_domain_console_admins_only():
    wall = Clock(1000.0)
    fed, north, signer, members = _domain(wall)
    members.add("cam-SN9004", "approved by anna", serial="SN9004")
    view = ReadView(fed, wall=lambda: 1000.0)
    con = Console(DomainDirectory(fed), view, ConsoleAPI(DomainDirectory(fed), lambda n: None, verifier=lambda t: t),
                  refresh_interval=0.05, members=members, admin=lambda s: s == "anna")
    srv = con.serve(port=0)
    base = f"http://127.0.0.1:{srv.server_address[1]}/domain/members"

    def delete(name, token):
        req = urllib.request.Request(f"{base}/{name}", method="DELETE", headers={"Authorization": f"Bearer {token}"})
        try:
            return urllib.request.urlopen(req).status
        except urllib.error.HTTPError as e:
            return e.code

    try:
        assert list(json.load(urllib.request.urlopen(base))["members"]) == ["cam-SN9004"]
        assert delete("cam-SN9004", "boris") == 403
        assert delete("cam-SN9004", "anna") == 200 and members.names() == []
        assert delete("cam-SN9004", "anna") == 404                    # not a member any more
    finally:
        con.stop(srv)


# -- feedback AN ----------------------------------------------------------------------------------------------
def test_the_first_write_carries_the_configuration_so_no_configured_member_becomes_a_stranger():
    """SN9005 was named in the configuration (`cam-SN9005=report`). The registrar admits SN9006 — the list's first
    write. Had it written only the newcomer, the next pass would have dropped SN9005 as one that left."""
    wall = Clock(1000.0)
    fed, north, signer, _ = _domain(wall)
    fed.add(member_copy("cam-SN9005", north.objects, wall=wall))
    members = Members(north.vars, wall=wall, configured=lambda: ["cam-SN9005"], domain="north")
    vendor = Manufacturer("vendor", now=wall)
    reg = Registrar("acme", signer, vendor.ca_cert, vendor.masa_public, now=wall, members=members,
                    cluster_of=member_name)
    _enroll(reg, vendor, "SN9006")
    doc = members.read()["members"]
    assert sorted(doc) == ["cam-SN9005", "cam-SN9006"] and doc["cam-SN9005"]["how"] == "configuration"
    assert apply(fed, members, north.objects) == {"joined": ["cam-SN9006"], "left": []}


def test_the_domains_own_cluster_is_neither_admitted_nor_removed():
    from w2cplatform.domain.api import ApiError
    wall = Clock(1000.0)
    fed, north, signer, _ = _domain(wall)
    members = Members(north.vars, wall=wall, domain="north")
    for act in (lambda: members.add("north", "approved by anna"), lambda: members.remove("north")):
        try:
            act()
            raise AssertionError("the domain's holder")
        except ApiError as e:
            assert e.status == 400


def test_a_cluster_that_knocks_is_named_and_accepted_from_the_console():
    """SN9007 reports into the domain's store and is not on the list — admitted by nobody, or left and still
    reporting. It is not read; it is named, with when it last reported. An admin accepts it; the next pass
    reads it."""
    wall = Clock(1000.0)
    fed, north, signer, _ = _domain(wall)
    members = Members(north.vars, wall=wall, domain="north")
    members.add("cam-SN9001", "voucher", serial="SN9001")
    cam = DeviceCluster("SN9007", FakeVariables(), wall=wall)
    cam.boot()
    DomainAgent(cam.name, north.vars, cam.flash, now=wall, domain_objects=north.objects, published=cam.local_objects()).sync()
    assert apply(fed, members, north.objects)["joined"] == ["cam-SN9001"] and "cam-SN9007" not in fed.clusters

    view = ReadView(fed, wall=lambda: 1000.0)
    con = Console(DomainDirectory(fed), view, ConsoleAPI(DomainDirectory(fed), lambda n: None, verifier=lambda t: t),
                  refresh_interval=60, members=members, admin=lambda s: s == "anna", publish_to=north.objects)
    srv = con.serve(port=0)
    base = f"http://127.0.0.1:{srv.server_address[1]}/domain/members"
    try:
        body = json.load(urllib.request.urlopen(base))
        assert [(k["name"], k["reported"]) for k in body["knocking"]] == [("cam-SN9007", 1000.0)]
        req = urllib.request.Request(base, data=json.dumps({"name": "cam-SN9007"}).encode(), method="POST",
                                     headers={"Authorization": "Bearer boris"})
        try:
            urllib.request.urlopen(req); raise AssertionError("boris is no admin")
        except urllib.error.HTTPError as e:
            assert e.code == 403
        req = urllib.request.Request(base, data=json.dumps({"name": "cam-SN9007"}).encode(), method="POST",
                                     headers={"Authorization": "Bearer anna"})
        assert urllib.request.urlopen(req).status == 200
        assert members.read()["members"]["cam-SN9007"]["how"] == "accepted by anna"
        assert json.load(urllib.request.urlopen(base))["knocking"] == []
    finally:
        con.stop(srv)
    assert apply(fed, members, north.objects)["joined"] == ["cam-SN9007"]
