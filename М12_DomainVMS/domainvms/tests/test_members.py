"""Who the domain's members are — decided by the registrar, read by every pass.

A box the registrar admits (Lesson 6) is added to the domain's list of members, and the next pass reads it from
its reports — nobody edits the environment of the domain's processes, nothing restarts. A member that leaves is
removed, and the next pass drops it, whatever report it left behind. Where nobody has written the list yet, the
configuration stands.
"""
import json
import urllib.error
import urllib.request

from cluster.variables import FakeVariables

from domain.agent import DomainAgent
from domain.api import ConsoleAPI
from domain.books import Books
from domain.console import Console
from domain.crossing import Crossings
from domain.device import DeviceCluster
from domain.enroll import Manufacturer, Pledge, Registrar
from domain.federation import DomainDirectory, Federation
from domain.members import Members, apply
from domain.readview import ReadView
from domain.signer import Signer
from domain.uplink import member_copy
from tests.conftest import Clock, make_cluster


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
    reg = Registrar("acme", signer, vendor.ca_cert, vendor.masa_public, now=wall, members=members)
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
    reg = Registrar("acme", signer, vendor.ca_cert, vendor.masa_public, now=wall, members=members)
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
    base = f"http://127.0.0.1:{srv.server_address[1]}/api/members"

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
