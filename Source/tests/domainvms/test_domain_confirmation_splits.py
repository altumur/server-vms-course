"""Checks of VMS member and epoch behavior split from the platform-domain suite."""
from tests.member_console import admit_fixtures
from tests.domain.conftest import Clock, EmbeddedMember, make_cluster, make_domain
from tests.reporting import sync as report_sync
from w2cplatform.cluster.variables import FakeVariables
from w2cplatform.domain.shadow import Shadow, reports_from
from w2cplatform.domain.agent import DomainAgent, DomainPublisher
from w2cplatform.domain.pending import PendingEdits
from w2cplatform.domain.api import ApiError, ConsoleAPI
from w2cplatform.domain.federation import DomainDirectory, Federation
from w2cplatform.domain.grants import Grant
from w2cplatform.domain.readview import ReadView

SERIAL = "SN4471"

def _grant(fed, cluster, subject, wall, capability="edit"):
    DomainPublisher(fed.domain_holder.vars).publish_grants(
        cluster, [Grant(subject, capability, None, wall() + 3600)])

class Running:
    """The VMS controller and workers, reserved for tests of camera behavior."""
    def __init__(self, cluster, wall, workers=(("w-0", "srv-1"),), capacity=50):
        from vms.controller import VmsController
        from vms.worker import VmsWorker, FakeActuator
        self.c, self.wall = cluster, wall
        self.ctl = VmsController(cluster.vars, cluster.objects, capacity=capacity, wall=wall, cluster=cluster.name)
        self.workers, self.alloc = {}, 0
        for name, server in workers:
            self.alloc += 1
            env = {"SLOT_INDEX": name.split("-")[1], "SERVER_NAME": server,
                   "INSTANCE_ID": f"{cluster.name}-alloc-{self.alloc}",
                   "LABELS": ",".join(sorted(cluster.reaches))}
            worker = VmsWorker(None, cluster.vars, cluster.objects, FakeActuator(), env=env,
                               clock=wall, wall=wall, capacity=capacity)
            worker.heartbeat_once()
            self.workers[name] = worker
    def create(self, *refs, **fields):
        rows = [self.ctl.create_camera({"name": f"cam{ref}", "source": f"driverpack://file/{ref}.mp4",
                                        "ref": str(ref), **fields}) for ref in refs]
        self.ctl.ensure_placed(); self.tick()
        return [row["id"] for row in rows]
    def tick(self):
        for worker in self.workers.values():
            worker.reconcile_once(); worker.heartbeat_once()
        self.ctl.publish_snapshot()

def _device_domain(wall, *serials):
    """VMS-owned member clusters for tests of camera authorization."""
    from tests.domain.books_fixture import initial_books
    from tests.member_console import device_console
    from tests.reporting import sync as report_sync
    from w2cplatform.cluster.variables import FakeVariables
    from w2cplatform.domain.agent import DomainAgent
    from w2cplatform.domain.federation import Federation
    from w2cplatform.domain.uplink import member_copy
    from vms.camera_cluster import DeviceCluster
    from w2cplatform.trust.signer import Signer
    fed, _ = make_domain({"north": ()}, "north"); north = fed.clusters["north"]
    fed.add(north); room = Running(north, wall); room.create(101, 102)
    devices, agents = {}, {}
    for serial in serials:
        device = DeviceCluster(serial, FakeVariables(), wall=wall); device.boot(first_name=f"gate-{serial}")
        fed.add(member_copy(device.name, north.objects, wall=wall))
        agent = DomainAgent(device.name, north.vars, device.flash, now=wall, console=device_console(device),
                            domain_objects=north.objects, published=device.local_objects())
        report_sync(agent); devices[serial] = device; agents[serial] = agent
    signer = Signer("acme", north.vars, now=wall)
    initial_books(fed, signer, wall, {"north": (north.vars, north.objects),
                  **{d.name: (d.flash, d.local_objects()) for d in devices.values()}})
    for agent in agents.values(): report_sync(agent)
    return fed, room, devices, agents

def _domain(clk):
    """The identity-grant fixture used by the VMS member-mark check."""
    from w2cplatform.domain.agent import KEYS_PATH
    from w2cplatform.trust.signer import Signer
    fed, links = make_domain({"north": (), "south": ()}, "north")
    dc = fed.domain_holder
    return fed, links, dc, Signer("acme", dc.vars, now=clk)

def _site(wall, nets=("vlan:a", "vlan:a", "vlan:b")):
    """Camera-owned member devices and their alarm cards for the ingest-liveness check."""
    import tempfile
    from vms.camera_cluster import DeviceCluster
    from w2cplatform.domain.alarms import Card, ReportedDoor, pages
    from w2cplatform.domain.federation import Federation
    from w2cplatform.domain.uplink import member_copy
    from w2cplatform.domain.agent import DomainAgent
    from tests.reporting import sync as report_sync
    from w2cplatform.cluster.variables import FakeVariables
    fed = Federation(); north, _ = make_domain({"north": ()}, "north"); north = north.clusters["north"]
    fed.add(north); devices, cards, agents = {}, {}, {}
    for i, net in enumerate(nets):
        device = DeviceCluster(f"SN{i}", FakeVariables(), wall=wall, reaches=(net,)); device.boot()
        fed.add(member_copy(device.name, north.objects, wall=wall, reaches=(net,)))
        devices[device.name] = device
        agents[device.name] = DomainAgent(device.name, north.vars, device.flash, now=wall,
                    domain_objects=north.objects, published=device.local_objects(),
                    pages=lambda d=device: pages(cards[d.name], wall()))
        cards[device.name] = Card("cam", tempfile.mkdtemp(prefix="card-"), on_alarm=agents[device.name].wake)
    def report(skip=()):
        for name, agent in agents.items():
            if devices[name].door_open and name not in skip: report_sync(agent)
    report()
    return fed, north, devices, cards, agents, report, lambda name: ReportedDoor(name, north.objects, wall=wall)

def test_the_report_from_what_clusters_publish():
    """Two real clusters; the domain placed 1 and 2 in north and nothing in
    south. The shadow reads heartbeats and cam/epoch/* — never a controller."""
    fed, links = make_domain({"north": (), "south": ()}, "north"); wall = Clock()
    n = Running(fed.clusters["north"], wall); n.create(1, 2)
    s = Running(fed.clusters["south"], wall); s.create(3)
    reports, epochs, down = reports_from(fed)
    assert down == [] and sorted(r.cluster for r in reports) == ["north", "south"] and epochs[("north", "1")] == 1
    placed = {"1": "north", "2": "north"}                                       # the domain's placements, by its refs
    r = Shadow().compare(placed, epochs, reports, now=wall())
    assert r.count("unmanaged") == 1 and r.findings[-1].where == "south/w-0" and r.findings[-1].unit == "3"   # south runs a camera the domain never placed
    links["south"].up = False
    reports, epochs, down = reports_from(fed)
    assert down == ["south"] and all(r.cluster == "north" for r in reports)       # a silent cluster is named, not counted as clean

def test_one_garbled_epoch_row_is_skipped_and_the_report_of_every_cluster_stands():
    """The review's sixth pass, the reading side of «one camera's garbled epoch stops everybody»: `reports_from`
    read every `cam/epoch/<id>` of every cluster bare, and one row with a word for a number — in one cluster —
    raised out of the shadow report of the whole domain. The row is skipped; that camera's worker is taken at its
    word, and the other cameras and clusters are compared as before."""
    fed, links = make_domain({"north": (), "south": ()}, "north"); wall = Clock()
    n = Running(fed.clusters["north"], wall); n.create(1, 2)
    s = Running(fed.clusters["south"], wall); s.create(3)
    fed.clusters["north"].vars.put("cam/epoch/2", {"epoch": "two"})              # a hand edit
    reports, epochs, down = reports_from(fed)
    assert down == [] and sorted(r.cluster for r in reports) == ["north", "south"]
    assert epochs[("north", "1")] == 1 and ("north", "2") not in epochs and epochs[("south", "3")] == 1
    r = Shadow().compare({"1": "north", "2": "north", "3": "south"}, epochs, reports, now=wall())
    assert not r.count("stale_epoch") and not r.findings                        # nothing invented about camera 2

def test_the_epoch_grows_on_every_boot_and_the_archive_path_carries_it():
    """There is no second instance for the epoch to fence. It is still taken, by the camera, from its flash,
    on every boot — because the archive and the event buckets carry it, and footage from after a reboot
    must never land in the directory of footage from before it."""
    d = EmbeddedMember(SERIAL, FakeVariables(), wall=Clock())
    assert d.boot() == 1 and d.rec_prefix() == f"rec/{SERIAL}/e1/"
    d.power_off()
    assert d.boot() == 2 and d.rec_prefix() == f"rec/{SERIAL}/e2/"
    assert d.row()["ref"] == SERIAL and d.row()["revision"] == 1              # the row was made once, at the FIRST boot

def test_an_edit_from_the_domain_is_the_cameras_own_console_deciding():
    """The domain keeps the edit (Lesson 9) — it opens no connection to a member — and the camera's own agent
    takes it home, where the camera's console checks the subject against the grants ITS agent carried, when it
    applies it. A camera writes its own row, always; the domain owns nothing. A refused edit comes back in the
    report, said."""
    wall = Clock()
    fed, room, devices, agents = _device_domain(wall, SERIAL)
    d = devices[SERIAL]
    _grant(fed, d.name, "anna", wall)
    report_sync(agents[SERIAL])
    view = ReadView(fed, wall=wall)
    view.refresh()
    admit_fixtures(fed.domain_holder.vars, fed.clusters)
    pending = PendingEdits(fed.domain_holder.vars, wall)
    api = ConsoleAPI(DomainDirectory(fed, wall=wall), verifier=lambda token: token, pending=pending,
                     last_known=view.last_known)

    assert api.update_unit(SERIAL, {"enabled": False}, idempotency_key="k1", token="anna", sub="cam")["kept"]
    report_sync(agents[SERIAL])
    assert d.row()["enabled"] is False and d.row()["revision"] == 2
    pending.collect(fed)
    assert pending.of(d.name) == {}

    # Human grants remain enforced by the device's human console, separately
    # from the local agent signature authorised by the domain admin.
    try:
        d._update(1, {"enabled": True}, "boris")
        raise AssertionError("a person without a grant edited the camera")
    except ApiError as err:
        assert err.status == 403 and "grant" in err.detail
    assert d.row()["enabled"] is False

def test_a_kept_edit_reaches_a_real_camera_when_it_boots():
    """Lesson 9, end to end, on a device: the camera goes off, the edit is kept beside its grants, the camera
    boots, its agent carries the edit home and its console applies it as the operator, and the domain clears
    what landed."""
    wall = Clock()
    fed, room, devices, agents = _device_domain(wall, SERIAL)
    d = devices[SERIAL]
    _grant(fed, d.name, "anna", wall)
    agent = agents[SERIAL]
    report_sync(agent)
    view = ReadView(fed, wall=wall)
    view.refresh()
    admit_fixtures(fed.domain_holder.vars, fed.clusters)
    pending = PendingEdits(fed.domain_holder.vars, wall)
    api = ConsoleAPI(DomainDirectory(fed, wall=wall), verifier=lambda token: token,
                     pending=pending, last_known=view.last_known)

    d.power_off()
    view.refresh()
    assert api.update_unit(SERIAL, {"enabled": False}, idempotency_key="k1", token="anna", sub="cam")["kept"]
    wall.advance(3600)
    _grant(fed, d.name, "anna", wall)                    # grants are renewed while it is off; they expire otherwise
    d.boot()
    report_sync(agent)
    assert d.row()["enabled"] is False
    pending.collect(fed)
    assert pending.of(d.name) == {}
