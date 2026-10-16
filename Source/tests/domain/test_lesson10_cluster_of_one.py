"""Lesson 10 — a cluster of one.

A camera that runs the platform is a cluster of its own: one store on its flash, one writer, a unit pinned
to its hardware, no controller, no slot, its own epoch. For the domain it must be nothing special — the
directory, the read view, the agent and Lesson 9's kept edits read it exactly as they read a server room: by
the report its agent leaves in the domain holder (step 7). What IS special is small and physical: flash that
wears, and a box that is rebooted whole, which makes the order of its boot a correctness question — for the
site that reads its door, and for the domain that reads its report.
"""

from tests.catalog_fixture import isolated_catalog
from tests.member_console import device_console, admit_fixtures
from tests.domain.books_fixture import initial_books
from tests.reporting import sync as report_sync
from w2cplatform.cluster.variables import FakeVariables

from w2cplatform.domain.agent import DomainAgent, DomainPublisher
from w2cplatform.domain.api import ApiError, ConsoleAPI
from tests.domain.conftest import EmbeddedMember
from w2cplatform.domain.federation import DomainDirectory, Federation
from w2cplatform.domain.grants import Grant
from w2cplatform.domain.pending import PendingEdits
from w2cplatform.domain.federation import Unreachable
from w2cplatform.domain.readview import ReadView
from w2cplatform.domain.uplink import member_copy
from tests.domain.conftest import Clock, Running, make_cluster

SERIAL = "SN4471"


def _domain(wall, *serials):
    """A server room (М11's real controller and a worker) that holds the domain, and cameras, each its own
    cluster — read by the domain from the reports their agents leave in the room, never through a door."""
    fed = Federation()
    north, _ = make_cluster("north", domain=True)
    fed.add(north)
    room = Running(north, wall)
    room.create(101, 102)
    devices, agents = {}, {}
    for s in serials:
        d = EmbeddedMember(s, FakeVariables(), wall=wall)
        d.boot(first_name=f"gate-{s}")
        fed.add(member_copy(d.name, north.objects, wall=wall))
        agents[s] = DomainAgent(d.name, north.vars, d.flash, now=wall, console=device_console(d),
                                domain_objects=north.objects, published=d.local_objects())
        report_sync(agents[s])
        devices[s] = d
    from w2cplatform.trust.signer import Signer
    signer = Signer("acme", north.vars, now=wall)
    initial_books(fed, signer, wall, {"north": (north.vars, north.objects),
                  **{d.name: (d.flash, d.local_objects()) for d in devices.values()}})
    for agent in agents.values():
        report_sync(agent)                # initial copies settle before the quiet-day measurement
    return fed, room, devices, agents


def _no_door(name):
    raise Unreachable(f"{name} is reached only by its own agent: the edit is kept")


def _grant(fed, cluster, subject, wall, capability="edit"):
    DomainPublisher(fed.domain_holder.vars).publish_grants(cluster, [Grant(subject, capability, None, wall() + 3600)])


@isolated_catalog()
def test_the_domain_reads_a_camera_the_way_it_reads_a_server_room():
    """Nothing in the directory or the read view was written for devices. A camera publishes one heartbeat
    and one snapshot shard in the shapes a cluster publishes, and it is found by its serial — the domain's
    name for it — on a worker and a server that are both the camera itself."""
    wall = Clock()
    fed, room, devices, agents = _domain(wall, SERIAL, "SN4472")
    ans = DomainDirectory(fed, wall=wall).where(SERIAL)
    assert (ans.cluster, ans.worker, ans.server, ans.complete) == (f"cam-{SERIAL}", SERIAL, SERIAL, True)
    assert DomainDirectory(fed, wall=wall).where("101").cluster == "north"      # and the server room, unchanged

    view = ReadView(fed, wall=wall)
    view.refresh()
    mine = [r for r in view.rows() if r.cluster == f"cam-{SERIAL}"]
    assert [(r.ref, r.worker_state, r.epoch) for r in mine] == [(SERIAL, "live", 1)]


@isolated_catalog()
def test_a_shard_from_an_older_build_shows_no_secret_and_no_password_in_an_address():
    """vmsserver's eleventh review, blocker 4, defence in depth: a member's shard written by an older build — before the
    cluster hid credentials in its snapshot — carried `cred_secret` and `source: …?pwd=…`, and the domain's read view
    kept and showed them as written. The view drops `*_secret` fields and hides credentials in addresses on read."""
    import json
    wall = Clock()
    fed, room, devices, agents = _domain(wall, SERIAL)
    d = devices[SERIAL]
    row = {**d.row(), "worker": SERIAL, "server": SERIAL, "cred_secret": "Hunter2",
           "source": "http://10.0.0.5/videostream.cgi?usr=admin&pwd=Hunter2"}
    d.ram.put(f"cam/snapshot/{SERIAL}", json.dumps({"cluster": d.name, "worker": SERIAL, "ts": wall(),
                                                    "cameras": [row]}).encode())     # as an older build wrote it
    report_sync(agents[SERIAL])
    view = ReadView(fed, wall=wall)
    view.refresh()
    shown = json.dumps(view.configured[f"cam-{SERIAL}"])
    assert "Hunter2" not in shown and "cred_secret" not in shown and "usr=admin&pwd=***" in shown, shown




@isolated_catalog()
def test_a_day_of_heartbeats_costs_the_flash_nothing():
    """A heartbeat every ten seconds is 8640 writes a day. On a server's disk that is nothing; on a
    camera's flash, over years, it is the camera. So what changes every few seconds lives in RAM — the agent
    reports it from there, and the site reads it through the door; flash takes the epoch, the row, and what
    the agent carries when it changes."""
    wall = Clock()
    fed, room, devices, agents = _domain(wall, SERIAL)
    d = devices[SERIAL]
    _grant(fed, d.name, "anna", wall)
    agent = DomainAgent(d.name, fed.domain_holder.vars, d.flash, now=wall)
    after_boot = d.flash.writes
    for i in range(8640):                                # one day, a heartbeat every 10 s
        wall.advance(10)
        d.publish()
        if i % 3 == 0:
            report_sync(agent)                                 # and the agent every 30 s
    assert after_boot == 3 + 5                           # epoch, unit, identity; roster and four cam/rec book copies
    assert d.flash.writes - after_boot == 1              # the grants, once, when they arrived — and nothing else


@isolated_catalog()
def test_nothing_places_a_pinned_unit_so_nothing_a_placer_writes_is_there():
    """The camera IS the unit. Its store holds its row, its epoch, and what the agent carried — `domain/*`.
    No slot, no assignment, no snapshot written by a controller: not forbidden, simply absent, because
    nobody's job is to write them."""
    wall = Clock()
    fed, room, devices, agents = _domain(wall, SERIAL)
    d = devices[SERIAL]
    _grant(fed, d.name, "anna", wall)
    report_sync(DomainAgent(d.name, fed.domain_holder.vars, d.flash, now=wall))
    assert d.flash.list("") == ["cam/cameras/1", "cam/epoch/1", "domain/cam/sources", "domain/grants",
                                "domain/member-key", "domain/member-list",
                                "domain/rec/polls", "domain/rec/primaries", "domain/rec/upstream"]




@isolated_catalog()
def test_the_door_opens_after_the_first_publish_not_before():
    """A camera is rebooted whole, which a server cluster never is. For the seconds between power and the
    first publish its RAM is empty — and a door open in those seconds says "I hold no cameras", a COMPLETE
    answer that whoever reads it must believe: a recorder of the site looking for its source would conclude
    the camera "is not anywhere". Closed until the publish, the same seconds are a camera that did not answer.
    The domain reads the report, not the door, and the same rule holds there: no report before the first
    publish (`test_uplink`) — so the domain keeps the camera's last report, and an edit is kept."""
    wall = Clock()
    fed, room, devices, agents = _domain(wall, SERIAL)
    d = devices[SERIAL]
    site = Federation()                                              # what the site reads: the camera's door
    site.add(d.cluster())

    # the wrong order, by hand: power, the door, and nothing published yet
    d.power_off(); d.ram = type(d.ram)(); d.door_open = True
    ans = DomainDirectory(site, wall=wall).where(SERIAL)
    assert not ans.found and ans.complete                            # "not anywhere", and believed

    # the right order: the door is closed while it boots, so the same moment is "did not answer"
    d.power_off()
    assert not DomainDirectory(site, wall=wall).where(SERIAL).complete

    # the domain meanwhile: the last report, and an edit kept for the agent to take home
    view = ReadView(fed, wall=wall)
    view.refresh()
    admit_fixtures(fed.domain_holder.vars, fed.clusters)
    api = ConsoleAPI(DomainDirectory(fed, wall=wall), pending=PendingEdits(fed.domain_holder.vars, wall),
                     last_known=view.last_known)
    assert api.update_unit(SERIAL, {"enabled": False}, idempotency_key="k2", sub="cam")["kept"]

    # …and `boot` keeps that order: the door is still shut while the first publish is being made
    shut_during_publish = []
    publish = d.publish
    d.publish = lambda: (shut_during_publish.append(not d.door_open), publish())
    d.boot()
    assert shut_during_publish == [True] and d.door_open
