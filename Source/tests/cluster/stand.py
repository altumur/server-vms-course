"""The module's stand, traced: three servers, the real controller, workers and console, and every call they make to
the cluster's store written down in the product's own API (`tests/cluster/trace.py`).

Each SCENE is one moment of the module's story, run from nothing, and returns its trace. The lessons quote these
traces; the full ones live in `Source/traces/<scene>.txt`, and `test_stand.py` fails the day the code and a
stored trace disagree — so an example in a lesson is a record of a run, never a guess.

    python3 tests/cluster/stand.py              # print every scene
    python3 tests/cluster/stand.py --write      # regenerate Source/traces/

The stand is `tests/cluster/conftest.py`'s: one configstore state machine behind a door per role with the committed rights
file, a resource and a directory of objects on each server, processes named by their units (`w-srv-a-1`). What the
stand did to build itself — the three resources saying their doors — is not in a scene's trace.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))  # Source/

from vms import volumes  # noqa: E402
from vms.config import SPEC  # noqa: E402
from tests.cluster.conftest import Cluster, Server  # noqa: E402
from tests.cluster.trace import Call, TraceLog  # noqa: E402
from w2cplatform import host  # noqa: E402  (a controller's pass as the units run it: `host.placement_pass`)

TRACES = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "traces")
ADDRESSES = {"srv-a": "10.0.0.1", "srv-b": "10.0.0.2", "srv-c": "10.0.0.3", "srv-d": "10.0.0.4"}


class Stand(Cluster):
    """The conftest cluster, with every process's store traced under its own name and socket."""

    def __init__(self):
        log = TraceLog()
        super().__init__(log=log)
        log.roots = {self.root: "/data"}
        self.log = log
        self.store.machine.members = {n: {"raft": f"{ADDRESSES[n]}:8301", "api": f"{n}@{ADDRESSES[n]}:8300"}
                                      for n in self.servers}
        self.log.calls.clear()                        # the stand's own building is not a scene's

    def reads(self, since: int) -> int:
        return sum(1 for c in self.log.calls[since:] if c.kind == "store" and not c.write)

    def join(self, name: str, labels: str = "", via: str = "srv-a") -> Server:
        """A new server: its configstore asks a member to be added to the group (`POST /v1/join` at that member's
        mutually authenticated `-api` door, the daemon's `-join`), then its units start — the resource first."""
        ip = ADDRESSES[name]
        body = {"id": name, "raft": f"{ip}:8301", "api": f"{name}@{ip}:8300"}
        self.store.machine.members[name] = {"raft": body["raft"], "api": body["api"]}
        members = [{"id": n, **m} for n, m in sorted(self.store.machine.members.items())]
        self.log.calls.append(Call(f"configstore on {name}", f"{via}'s daemon, {via}@{ADDRESSES[via]}:8300 (mutual TLS)",
                                   "POST", "/v1/join", body, 200, {"members": members}, kind="join"))
        srv = self.servers[name] = Server(self.root, name, labels)
        self._resource(name)
        for other in self.servers.values():
            other.res._doors = None                   # the others read the doors again (every DOORS_FRESH seconds)
        return srv


# -- the scenes ------------------------------------------------------------------------------------

def worker_starts() -> str:
    """Lesson 1: the worker's unit starts on srv-a. The process claims the name its unit gives it, `w-srv-a-1`, and
    says what it is — its heartbeat a file on srv-a, not a row."""
    s = Stand()
    s.worker("srv-a", capacity=50).heartbeat_once()
    return s.log.render()


def console_creates_a_camera() -> str:
    """Lesson 2: the console writes a camera row — a number from `next_id`, then the row, both by CAS."""
    s = Stand()
    s.console().create_camera({"name": "north-gate", "source": "driverpack://acme/10.2.0.11", "labels": ["vlan:cctv-a"]})
    return s.log.render()


def two_editors_one_row() -> str:
    """Lesson 2: two consoles edit camera 1 at once. The second write carries a version that is no longer current,
    gets 409, reads again and writes on top of the first — nobody's edit is lost."""
    s = Stand()
    s.console("srv-a").create_camera({"name": "north-gate", "source": "driverpack://acme/10.2.0.11"})
    a, b = s.console("srv-a"), s.console("srv-b")
    mark = s.log.mark()
    key = SPEC.sub.config("cameras", "1")
    first = {"done": False}

    def mutate(items):
        if not first["done"]:                   # between A's read and A's write, B writes
            first["done"] = True
            b.update(1, {"events_retention_days": 30})
        items["name"] = "north-gate-2"
        return items

    a.write(key, mutate)
    return s.log.render(since=mark)


def a_worker_may_not_write_a_camera() -> str:
    """Lesson 2: the worker's socket writes its epochs, its slot, its hold — and a camera row is a 403 from the
    store, the daemon's word by the socket it came through, not a rule in the worker's code."""
    s = Stand()
    w = s.worker("srv-a")
    mark = s.log.mark()
    try:
        w.vars.put("vms/cameras/1", {"name": "mine now"})
    except Exception:                                                    # noqa: BLE001 — the point
        pass
    return s.log.render(since=mark)


def a_server_joins() -> str:
    """Lesson 2: srv-d joins the cluster. Its configstore asks srv-a's to be added to the group and is a member before
    any process of srv-d starts; then its resource says where it answers, and its worker claims `w-srv-d-1`. Nothing
    of the other servers' was written."""
    s = Stand()
    mark = s.log.mark()
    s.join("srv-d", "vlan:cctv-b")
    w = s.worker("srv-d")
    w.heartbeat_once()
    seen = sorted(s.controller("srv-b").workers_seen())
    return (s.log.render(since=mark, kinds=("join", "store"))
            + f"\n# the controller on srv-b reads the heartbeats through srv-b's resource: {seen}\n")


def a_recorder_starts() -> str:
    """Lesson 3: the recorder's unit starts on srv-a, where the administrator declared the disks as a volume. It
    claims its name like any worker — and then takes the VOLUME, by CAS, under `rec/holds/`: the one write a
    recorder makes that a VMS worker never does."""
    s = Stand()
    # The disks, not the events archive: that is the platform's tree (WP-E), and the processes of srv-a register in it.
    disks = os.path.join(os.path.dirname(s.servers["srv-a"].archive), "disks")
    volumes.write(s.vars, {"name": "disks-a", "kind": "local", "server": "srv-a", "url": disks,
                           "quota_bytes": 4 * 10**12})
    s.log.calls.clear()
    r = s.recorder("srv-a")
    r.lease_pass(); r.heartbeat_once()
    out = s.log.render()
    r.after_stop()
    return out


def two_processes_one_name() -> str:
    """Lesson 4: two processes come up with one name — the unit restarted while the old process still lived (hung,
    stopped, out of reach of the stop), or an operator who started a second copy by hand. The second takes the name
    outright; the first finds out when it renews, and stops. One of them holds the cameras, never both."""
    s = Stand()
    s.resources_up()
    con, ctl = s.console(), s.controller()
    for i in (1, 2):
        con.create_camera({"name": f"cam-{i}", "source": f"driverpack://file/{i}.mp4"})
    a = s.worker("srv-a")
    ctl.assign(a.name, ["1", "2"])
    a.reconcile_once()
    mark = s.log.mark()
    b = s.worker("srv-a")                                              # the same name, a second process
    a.lease_pass()                                                     # the old one renews — and learns
    b.reconcile_once()
    return s.log.render(since=mark)


def _full(s, capacity=4, cameras=8):
    """Two workers of capacity 4 on srv-a and srv-b, carrying eight cameras between them."""
    s.resources_up()
    con, ctl = s.console(), s.controller("srv-b", capacity=capacity)
    for i in range(cameras):
        con.create_camera({"name": f"cam-{i + 1}", "source": f"driverpack://file/{i + 1}.mp4"})
    ws = [s.worker("srv-a", capacity=capacity), s.worker("srv-b", capacity=capacity)]
    for w in ws:
        w.heartbeat_once()
    host.placement_pass(ctl)
    for w in ws:
        w.reconcile_once(); w.heartbeat_once()
    return con, ctl, ws


def a_spare_takes_an_offer() -> str:
    """Lesson 4: the workers are full; a ninth camera waits. The controller's pass counts it short and writes an
    OFFER — an empty slot row with the label set it is for; `w2c-spares.sh` on srv-c starts a spare for that set, the
    spare takes the offer by CAS, and the camera lands on it. Then the spare is stopped in order: it releases its
    slot, and the controller moves its camera. The controller started no process. Only the writes; the reads are
    counted."""
    s = Stand()
    con, ctl, ws = _full(s)
    con.create_camera({"name": "cam-9", "source": "driverpack://file/9.mp4"})
    mark = s.log.mark()
    host.placement_pass(ctl)                                                   # full: the ninth waits — and an offer is written
    spare = s.worker("srv-c", capacity=4, spare_for="")                # `systemctl start vms-vmsworker-spare@1`, `SPARE_FOR=` in its file
    spare.heartbeat_once()
    host.placement_pass(ctl)
    spare.reconcile_once()
    spare.release_slot()                                               # `systemctl stop vms-vmsworker-spare@1`: SIGTERM
    con.delete_camera(1); con.delete_camera(2)                         # room to move into
    host.placement_pass(ctl)
    return s.log.render(since=mark, writes=True) + f"\n# … and {s.reads(mark)} GET requests, omitted\n"


def a_crash_releases_nothing() -> str:
    """Lesson 4: w-srv-c-1 dies without a word. systemd starts its unit again two seconds later (`Restart=always`,
    `RestartSec=2`); in between the controller's pass finds the name still held and moves nothing, and the new
    process claims `w-srv-c-1` and finds its assignment where it left it."""
    s = Stand()
    s.resources_up()
    con, ctl = s.console(), s.controller()
    con.create_camera({"name": "cam-1", "source": "driverpack://file/1.mp4"})
    w = s.worker("srv-c"); w.heartbeat_once()
    host.placement_pass(ctl); w.reconcile_once()
    s.wall.advance(2)                                                  # it died; nobody said so; systemd waits RestartSec
    mark = s.log.mark()
    ctl.redistribute()                                                 # nothing released: nothing to move
    again = s.worker("srv-c")                                          # the same unit, a new process
    again.refresh()
    return s.log.render(since=mark)


def decommission_a_server() -> str:
    """Lesson 4 (М10A Lesson 7, step 7): srv-c burnt under w-srv-c-1, and the operator knows it will not come back.
    The operator operates SERVERS: the console writes one row, `platform/decommission/srv-c` — refused while srv-c's
    resource answers, so it is written once the resource is silent — and the controller's pass frees w-srv-c-1's slot
    itself and moves its camera to the worker that is here. Only the writes; the reads are counted."""
    s = Stand()
    s.resources_up()
    con, ctl = s.console(), s.controller()
    con.create_camera({"name": "cam-1", "source": "driverpack://file/1.mp4"})
    con.create_camera({"name": "cam-2", "source": "driverpack://file/2.mp4"})
    ws = [s.worker("srv-b"), s.worker("srv-c")]
    for w in ws:
        w.heartbeat_once()
    ctl.ensure_placed()
    s.wall.advance(100)                                                # srv-c burnt: w-srv-c-1 and its resource say nothing again
    ws[0].refresh(); ws[0].heartbeat_once()                            # w-srv-b-1 renews and says so, as every pass
    for name, r in s.resources.items():
        if name != "srv-c":
            r.heartbeat()
    mark = s.log.mark()
    con.decommission("srv-c", "anna", "srv-c burnt")                   # POST /servers/srv-c/decommission, from the page
    ctl.apply_decommissions()                                          # the controller's next pass: first this…
    ctl.redistribute()                                                 # …then what a freed slot listed moves
    return s.log.render(since=mark, writes=True) + f"\n# … and {s.reads(mark)} GET requests, omitted\n"


def what_the_spares_script_reads() -> str:
    """Lesson 4: two workers of capacity 4 carry eight cameras, a ninth waits. What the console's `/metrics` says
    without a token while the controller's pass is fresh — the four series `w2c-spares.sh` reads: how many workers
    are needed for each label set, how many units are short, how many offers wait, and what each server reaches."""
    from w2cplatform.console import SpecConsole
    s = Stand()
    con, ctl, ws = _full(s)
    con.create_camera({"name": "cam-9", "source": "driverpack://file/9.mp4", "labels": ["vlan:cctv-b"]})
    host.placement_pass(ctl)
    text = SpecConsole(s.console()).metrics_text()
    series = ("vms_workers_live", "vms_worker_load", "vms_workers_needed", "vms_units_short", "vms_spare_offers",
              "vms_server_labels")
    keep = [l for l in text.splitlines()
            if l.replace("# TYPE ", "").split("{")[0].split(" ")[0] in series]
    return "GET /metrics\n" + "\n".join(keep) + "\n"


def an_offer_withdrawn() -> str:
    """Lesson 4: an offer waits for a spare, and the shortage goes before one comes — the operator deletes a camera.
    The next pass finds the offer not needed and removes it by CAS: the version it read, so a spare that took it
    meanwhile keeps it (its write moved the version, and the delete is a 409)."""
    s = Stand()
    con, ctl, ws = _full(s)
    con.create_camera({"name": "cam-9", "source": "driverpack://file/9.mp4"})
    host.placement_pass(ctl)                                                   # the offer
    mark = s.log.mark()
    con.delete_camera(3)                                               # room again on w-srv-a-1
    host.placement_pass(ctl)
    return s.log.render(since=mark, writes=True) + f"\n# … and {s.reads(mark)} GET requests, omitted\n"


def who_may_write_what() -> str:
    """Lesson 5: every process of the cluster tries one write that is its own and one that is not, through the socket
    its unit can open. The rights are the committed rights file (`deploy/cluster/configstore-rights.json`), generated from the
    spec (`acl_worker`, `acl_controller`, `acl_console`); the 403 is the daemon's."""
    s = Stand()
    tries = [
        ("vmsworker", "vmsworker w-srv-a-1 on srv-a", [("vms/epoch/7", {"epoch": "1"}),
                                                       ("vms/placement/7", {"worker": "w-srv-a-1"})]),
        ("recworker", "recworker r-srv-a-1 on srv-a", [("rec/holds/disks-a", {"holder": "srv-a:4102"}),
                                                       ("rec/recordings/7", {"cam": "7"})]),
        ("vmscontroller", "vmscontroller on srv-a", [("vms/placement/7", {"worker": "w-srv-a-1", "reason": "…"}),
                                                     ("vms/cameras/7", {"name": "moved"})]),
        ("console", "console on srv-a", [("vms/cameras/7", {"name": "north-gate"}),
                                         ("vms/workers/w-srv-a-1", {"units": "7"})]),
        ("resource", "resource on srv-a", [("platform/doors/srv-a", {"url": "http://srv-a:8090", "since": "0"}),
                                           ("vms/cameras/7", {"name": "mine"})]),
    ]
    for role, who, writes in tries:
        v = s.door(role, who)
        for key, items in writes:
            try:
                v.put(key, items)
            except Exception:                                            # noqa: BLE001 — the 403 is the point
                pass
    return s.log.render()


def _host(url: str) -> str:
    return url.split("//", 1)[1].split("/", 1)[0].split(":", 1)[0]


def _json(obj) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False, indent=2)


def _two_silences(s, dead: str = "srv-a", down: bool = True) -> None:
    """`dead` goes: its processes and its resource say nothing again — and, `down`, nothing on it answers, its files
    with it. Then the slot's 45 s, the margin's 45 s past them, and three of the controller's pass: the others renew
    and heartbeat on the way."""
    s.servers[dead].down = down
    for step in (30, 30, 33):
        s.wall.advance(step)
        for name, srv in s.servers.items():
            if name != dead:
                srv.res.heartbeat()
        for w in getattr(s, "alive", []):
            w.lease_pass(); w.heartbeat_once()


def an_edit_during_the_failover() -> str:
    """Lesson 6: srv-a dies under w-srv-a-1; while nobody runs camera 1, the operator renames it; when the controller
    moves it to w-srv-b-1, the camera starts there with the new name. Nothing was published for this to work — the
    edit is in the store. Only the writes."""
    s = Stand()
    s.resources_up()
    con, ctl = s.console("srv-b"), s.controller("srv-b")
    con.create_camera({"name": "before", "source": "driverpack://file/1.mp4", "labels": ["vlan:cctv-a"]})
    a, b = s.worker("srv-a"), s.worker("srv-b")
    for w in (a, b):
        w.heartbeat_once()
    host.placement_pass(ctl); a.reconcile_once(); ctl.workers_seen()
    s.alive = [b]
    mark = s.log.mark()
    s.servers["srv-a"].down = True
    s.wall.advance(20)
    con.update_camera(1, {"name": "edited during the failover"})       # while nobody runs it
    _two_silences(s)
    host.placement_pass(ctl)
    b.reconcile_once()
    return (s.log.render(since=mark, writes=True)
            + f"\n# … and {s.reads(mark)} GET requests, omitted\n# w-srv-b-1 runs camera 1 as {b.rows[0]['name']!r}\n")


def a_timeline_across_two_volumes() -> str:
    """Lesson 6: camera 7 was recorded into srv-a's volume under epoch 3 until the failure, then into srv-b's under
    epoch 4. The console's timeline asks every live recorder's archive door; srv-a's recorder goes silent and its
    volume is NAMED unavailable; it comes back and nothing was rebuilt. Not a store trace: what the recorders say
    of their volumes, then what `/timeline/7` answers, three times."""
    from vms.footage import footage_routes
    from tests.cluster.conftest import footage
    s = Stand()
    t = s.wall()
    s.vars.put("rec/epoch/7", {"epoch": "4"})                          # the recording's writer is e4 now
    recs = {}
    for server, epoch, spans in (("srv-a", 3, ((t - 1200, t - 900), (t - 600, t - 450))), ("srv-b", 4, ((t - 300, t),))):
        r = s.recorder(server)
        r.lease_pass()
        for a, b in spans:
            footage(r.store, "7", epoch, a, b, step=10, seal=False)
        r.store.seal(); r.serve_archive(); r.heartbeat_once()
        recs[server] = r
    out = ["# what each recorder says of its volume (its heartbeat, the door's address left out)"]
    for server, r in recs.items():
        hb = r.heartbeat_extra()
        out.append(f"{r.name} on {server}: volume {hb['volume']!r}, archive {hb['archive']!r}, writer {hb['writer']}")
    ctl = s.controller()
    routes = footage_routes(ctl.objects, ctl.vars, ctl.wall, eyes=ctl.eyes)     # the recording's holder's door (step 6)
    keep = ("start", "end", "epoch", "fenced", "recording", "recorder", "volume", "media")

    def ask():
        _, body = routes(None, "GET", "/door/timeline/7", {"from": t - 2000, "to": t})
        if isinstance(body, list):
            return [{k: sp[k] for k in keep} for sp in body]
        return {**body, "segments": [{k: sp[k] for k in keep} for sp in body["segments"]]}
    out += ["", "# GET /timeline/7 — both recorders answer", _json(ask())]
    s.wall.advance(60); recs["srv-b"].heartbeat_once()
    out += ["", "# srv-a's recorder has been silent for 60 s", _json(ask())]
    recs["srv-a"].heartbeat_once()
    out += ["", "# srv-a is back — its volume with it", _json(ask())]
    for r in recs.values():
        r.after_stop()
    return s.log._clean("\n".join(out)) + "\n"


def objects_across_servers() -> str:
    """Lesson 6: objects are files on each server. The worker on srv-a puts its heartbeat — a file on srv-a, no store
    write; the controller on srv-b reads it through srv-b's resource, which asks the others (`scope=cluster`, the
    freshest copy by `written`); a mark before a device command is created ONCE across the cluster, so it is a row
    (`cas: ""`). Then srv-a goes down: the resource names it missing, and the reader answers with what it last heard."""
    s = Stand()
    s.log.objects = True
    w = s.worker("srv-a")
    ctl = s.controller("srv-b")
    mark = s.log.mark()
    w.heartbeat_once()
    seen = ctl.workers_seen()
    made = w.objects.put_new("vms/commands/r-17", b'{"instance": "srv-a:4101"}')
    s.servers["srv-a"].down = True
    later = ctl.workers_seen()
    keep = ("objects", "file", "store")
    calls = [c for c in s.log.calls[mark:] if c.who.startswith(("vmsworker", "vmscontroller")) and c.kind in keep
             and (c.kind != "store" or "commands" in c.target or "commands" in str(c.body))]
    s.log.calls[mark:] = calls
    return (s.log.render(since=mark)
            + f"\n# workers_seen() on srv-b = {sorted(seen)}; the mark made: {made}"
            + f"\n# srv-a down: the resource on srv-b names it missing ({ctl.objects.missing}); "
            + f"workers_seen() = {sorted(later)}, by what srv-b's reader heard last\n")


def _events_site():
    from tests.cluster.test_lesson3_events import _observe
    s = Stand()
    t = s.wall() - 7200
    _observe(s, "srv-a", "vms", "7", 3, t + 12, "motion", zone="gate")          # the VMS worker, camera 7, before the failover
    _observe(s, "srv-a", "vms", "7", 3, t + 40, "silent")
    _observe(s, "srv-b", "vms", "7", 4, t + 1205, "motion")                      # after it: next epoch, other server
    _observe(s, "srv-c", "det", "d-12", 1, t + 30, "person", of="vms/7", cam=7, score=0.9)  # a detector ABOUT camera 7, on a GPU server
    _observe(s, "srv-a", "vms", "7", 3, t + 6800, "motion")                      # in srv-a's OPEN bucket
    return s, t


def _merged(s):
    from w2cplatform.eventdatabase import MergedIndex

    def fetch(url, p):
        name = _host(url)
        if s.servers[name].down:
            raise ConnectionError(name)
        return s.resources[name].index.query(float(p["from"]), float(p["to"]), p.get("kind"), p.get("subsystem"), p.get("unit"), limit=int(p.get("limit", 1000)))
    m = MergedIndex(s.objects, fetch=fetch, wall=s.wall)
    m.SEEN_FOR = 0.0          # the stand moves only its wall: each query reads the resources afresh, as two queries a minute apart do
    return m


def _short(q) -> dict:
    keep = ("t", "subsystem", "unit", "of", "kind", "server", "epoch", "fenced")
    return {"state": q["state"], "events": [{k: e[k] for k in keep if k in e} for e in q["events"]]}


def events_merged() -> str:
    """Lesson 7: each resource reads its OWN tree where it lies; the console holds nothing and merges theirs,
    fencing by the epochs only the cluster's rows know. A silent resource is named, not guessed."""
    s, t = _events_site()
    rs = s.resources_up()
    out = ["# each resource's index: what its own tree holds, from its directories alone — nothing rebuilt"]
    for name in rs:
        out.append(f"{name}: {rs[name].index.listing()}")
    m = _merged(s)
    out += ["", "# GET /events?unit=vms/7 on the console — merged from every live resource",
            _json(_short(m.query(t, t + 7200, unit="vms/7", current_epochs={("vms", "7"): 4})))]
    s.wall.advance(60); rs["srv-b"].heartbeat(); rs["srv-c"].heartbeat()
    out += ["", "# srv-a has been silent for 60 s", _json(_short(m.query(t, t + 7200, unit="vms/7", current_epochs={("vms", "7"): 4})))]
    return "\n".join(out) + "\n"


def the_events_mirror() -> str:
    """Lesson 7: the storage knob's events row — one row in the store. Each resource copies its CLOSED buckets to the
    next live resource; srv-a goes silent and its events come from srv-b's copy, saying so; srv-a returns with an
    empty disk and pulls its buckets home."""
    import shutil
    from w2cplatform.resource import MIRROR_KEY
    s, t = _events_site()
    rs = s.resources_up()
    out = [f"# knob off: srv-a pass -> mirrored {rs['srv-a'].pass_()['mirrored']}"]
    s.vars.put(MIRROR_KEY, {"enabled": "true", "copies": "1"})
    out.append('# the knob: POST /v1/write {"op": "put", "key": "platform/mirror", "items": {"enabled": "true", '
               '"copies": "1"}}')
    for name in rs:
        r = rs[name].pass_()
        out.append(f"{name} pass -> mirrored {r['mirrored']} to {r['peers']}")
    for r in rs.values():
        r.heartbeat()
    for name in rs:
        out.append(f"{name} index -> {rs[name].index.listing()}")
    m = _merged(s)
    out += ["", "# srv-a answers: its own events, the open bucket included", _json(_short(m.query(t, t + 7200, unit="vms/7")))]
    s.wall.advance(60); rs["srv-b"].heartbeat(); rs["srv-c"].heartbeat()
    out += ["", "# srv-a silent: its closed buckets, from srv-b's copy", _json(_short(m.query(t, t + 7200, unit="vms/7")))]
    shutil.rmtree(s.servers["srv-a"].archive); os.makedirs(s.servers["srv-a"].archive)
    rs["srv-a"].heartbeat()
    out += ["", f"# srv-a back with an EMPTY disk: restore -> {rs['srv-a'].restore()}"]
    rs["srv-a"].heartbeat()
    out += [_json(_short(m.query(t, t + 7200, unit="vms/7")))]
    return "\n".join(out) + "\n"


def _recording(s, n=3):
    """Lesson 8's starting point: w-srv-a-1 holds cameras 1..n under epoch 1, w-srv-b-1 is there with room, the
    servers' resources alive, the controller on srv-b has heard everybody."""
    s.resources_up()
    con, ctl = s.console("srv-b"), s.controller("srv-b")
    for i in range(n):
        con.create_camera({"name": f"cam-{i + 1}", "source": f"driverpack://file/{i + 1}.mp4", "labels": ["vlan:cctv-a"]})
    a = s.worker("srv-a")
    a.heartbeat_once(); host.placement_pass(ctl); a.reconcile_once(); a.heartbeat_once()
    b = s.worker("srv-b"); b.heartbeat_once()
    ctl.workers_seen(); ctl.failover_seconds()
    s.alive = [b]
    return ctl, a, b


def pull_the_power() -> str:
    """Lesson 8: srv-a dies at t=0 — its processes, its resource, its disks. Nothing restarts anything elsewhere: the
    controller on srv-b sees the two silences — the slot of w-srv-a-1 out by 45 s more, and srv-a's resource silent —
    and moves the cameras by assignment to w-srv-b-1, which takes the next epoch for each and starts them. Only the
    writes."""
    s = Stand()
    ctl, a, b = _recording(s)
    mark = s.log.mark()
    _two_silences(s)
    host.placement_pass(ctl)
    b.reconcile_once(); b.heartbeat_once()
    return (s.log.render(since=mark, writes=True)
            + f"\n# … and {s.reads(mark)} GET requests, omitted"
            + f"\n# 93 s after the power went: w-srv-b-1 runs {sorted(b.actuator.running)} under epochs "
            + f"{dict(sorted(b.actuator.epochs.items()))}; where(1..3) = {[ctl.where(i) for i in (1, 2, 3)]}\n")


def one_silence_or_two() -> str:
    """Lesson 8: a hang — w-srv-a-1 silent, its process running (registered with srv-a's resource, its lock held), the
    resource alive — moves nothing: the unit is systemd's to start again (its watchdog), and its process comes back
    under the same name. A dead server — two silences: the slot, and the resource on its server — is a fact the
    controller acts on."""
    s = Stand()
    ctl, a, b = _recording(s)
    rs = s.resources
    s.wall.advance(2 * 45 + 3); b.lease_pass(); b.heartbeat_once()
    for r in rs.values():
        r.heartbeat()
    crash = s.log.mark()
    one = (ctl.gone_servers(), ctl.redistribute())
    fate = ctl.slot_fate("w-srv-a-1", ctl.slots()["w-srv-a-1"])[0]
    after_crash = s.log.mark()
    s.wall.advance(2 * 45 + 3); b.lease_pass(); b.heartbeat_once(); rs["srv-b"].heartbeat(); rs["srv-c"].heartbeat()
    gone = ctl.gone_servers()
    mark = s.log.mark()
    ctl.redistribute()
    b.reconcile_once()
    writes_in_crash = sum(1 for c in s.log.calls[crash:after_crash] if c.write)
    return (f"# a hang — w-srv-a-1 silent, its process running, srv-a's resource alive: gone_servers() = {one[0]}, "
            f"redistribute() = {one[1]}, fate: {fate!r}, writes: {writes_in_crash}\n"
            f"# the power pull — w-srv-a-1 AND srv-a's resource silent: gone_servers() = {gone}\n\n"
            + s.log.render(since=mark, writes=True))


def the_old_instance_wakes_up() -> str:
    """Lesson 9: srv-a was not dead — cut off from the others, or paused. The controller moved its cameras to w-srv-b-1
    under epoch 2; srv-a comes back with w-srv-a-1 still holding three cameras under epoch 1. Its next lease pass finds
    every epoch moved on; it stops them, and its assignment says they are not its any more."""
    s = Stand()
    ctl, a, b = _recording(s)
    _two_silences(s)
    host.placement_pass(ctl); b.reconcile_once(); b.heartbeat_once()
    s.servers["srv-a"].down = False
    mark = s.log.mark()
    lost = a.lease_pass()                                              # kill -CONT, or the network back
    a.reconcile_once()
    a.heartbeat_once()
    return (s.log.render(since=mark)
            + f"\n# a.lease_pass() lost {lost}; running {sorted(a.actuator.running)}; its assignment now "
            + f"{a.assignment().units}; its name is still its own: {a.name}\n")


def a_reassignment_is_not_a_zombie() -> str:
    """Lesson 9: the controller moves camera 2 from w-srv-a-1 to w-srv-b-1. w-srv-a-1 loses the lease on 2 exactly as
    a zombie would — and one read of its assignment tells it this is a move: it lets 2 go and keeps 1 and 3."""
    s = Stand()
    ctl, a, b = _recording(s)
    mark = s.log.mark()
    ctl.move(2, b.name, "operator: srv-b sees that VLAN")
    b.reconcile_once()
    lost = a.lease_pass()
    a.reconcile_once()
    return (s.log.render(since=mark)
            + f"\n# a.lease_pass() lost {lost}; a.writing_allowed = {a.writing_allowed}; running {sorted(a.actuator.running)}\n")


def _labelled_workers(s):
    """Lesson 10's cluster: srv-a reaches vlan:cctv-a, srv-b both, srv-c vlan:cctv-b — one worker on each."""
    s.resources_up()
    ws = {srv: s.worker(srv, capacity=10) for srv in ("srv-a", "srv-b", "srv-c")}
    for w in ws.values():
        w.heartbeat_once()
    return ws


def placement_under_labels() -> str:
    """Lesson 10: four cameras, each saying which network it is on. The controller places each on a worker
    whose server reaches it, by the workers' own capacity, and writes the server into the reason; the one
    nothing reaches is named with its labels."""
    s = Stand()
    _labelled_workers(s)
    con, ctl = s.console(), s.controller()
    for name, labels in (("a", ["vlan:cctv-a"]), ("b", ["vlan:cctv-b"]), ("ab", ["vlan:cctv-a", "vlan:cctv-b"]), ("x", ["vlan:cctv-x"])):
        con.create_camera({"name": name, "source": f"driverpack://file/{name}.mp4", "labels": labels})
    mark = s.log.mark()
    ctl.ensure_placed()
    return (s.log.render(since=mark, writes=True)
            + f"\n# unplaceable() = {ctl.unplaceable()}\n")


def two_controllers_one_camera() -> str:
    """Lesson 10: a controller runs on every server, and two may place at once. Controller B places camera 1 between
    controller A's read and A's write. A's CAS fails; A reads again, finds a worker already named, and ADOPTS B's
    decision — it writes nothing more. One camera, one worker, whichever controller got there."""
    s = Stand()
    _labelled_workers(s)
    s.console().create_camera({"name": "gate", "source": "driverpack://file/gate.mp4", "labels": ["vlan:cctv-a"]})
    a, b = s.controller("srv-a"), s.controller("srv-b")
    put = a.vars.put
    first = {"done": False}

    def racing_put(path, items, cas=None):
        if path == "vms/placement/1" and not first["done"]:
            first["done"] = True
            b.place(1)                                               # B gets there between A's read and A's write
        return put(path, items, cas)
    a.vars.put = racing_put
    mark = s.log.mark()
    a.place(1)
    return (s.log.render(since=mark, writes=True) + f"\n# … and {s.reads(mark)} GET requests, omitted"
            + f"\n# where(1) = {a.where(1)}; placement reason: {a.placement(1).reason!r}\n")


def where_is_camera_7() -> str:
    """Lesson 10: the cluster's directory is one scan of one store. Nine cameras, nine answers, one scan."""
    from w2cplatform.cluster.directory import Directory
    s = Stand()
    _labelled_workers(s)
    con, ctl = s.console(), s.controller()
    for i in range(9):
        con.create_camera({"name": f"cam-{i + 1}", "source": f"driverpack://file/{i + 1}.mp4"})
    ctl.ensure_placed()
    mark = s.log.mark()
    d = Directory(s.door("console", "console on srv-a"), "vms", ttl=5.0, clock=s.clock)
    answers = {i: d.where(i) for i in range(1, 10)}
    return s.log.render(since=mark) + f"\n# where(1..9) = {answers}; scans = {d.scans}\n"


def the_snapshot() -> str:
    """Lesson 10: the one thing that leaves the cluster — a copy of the rows, one object per worker, with an age.
    Objects are files: the shards are written on the controller's server, and the trace shows them as files."""
    s = Stand()
    _labelled_workers(s)
    con, ctl = s.console(), s.controller()
    ctl.cluster = "north"
    for name in ("gate", "yard", "dock"):
        con.create_camera({"name": name, "source": f"driverpack://file/{name}.mp4"})
    ctl.ensure_placed()
    s.log.objects = True
    mark = s.log.mark()
    ctl.publish_snapshot()
    shards = {k: len(ctl.objects.local.get(k) or b"") for k in ctl.objects.local.list("vms/snapshot/")}
    return (s.log.render(since=mark, kinds=("file",))
            + f"\n# on srv-a, /data/platform/objects: {shards}\n")


SCENES = {"01-worker-starts": worker_starts,
          "02-console-creates-a-camera": console_creates_a_camera,
          "02-two-editors-one-row": two_editors_one_row,
          "02-a-worker-may-not-write-a-camera": a_worker_may_not_write_a_camera,
          "02-a-server-joins": a_server_joins,
          "03-a-recorder-starts": a_recorder_starts,
          "04-two-processes-one-name": two_processes_one_name,
          "04-a-spare-takes-an-offer": a_spare_takes_an_offer,
          "04-a-crash-releases-nothing": a_crash_releases_nothing,
          "04-decommission-a-server": decommission_a_server,
          "04-what-the-spares-script-reads": what_the_spares_script_reads,
          "04-an-offer-withdrawn": an_offer_withdrawn,
          "05-who-may-write-what": who_may_write_what,
          "06-an-edit-during-the-failover": an_edit_during_the_failover,
          "06-a-timeline-across-two-volumes": a_timeline_across_two_volumes,
          "06-objects-across-servers": objects_across_servers,
          "07-events-merged": events_merged,
          "07-the-events-mirror": the_events_mirror,
          "08-pull-the-power": pull_the_power,
          "08-one-silence-or-two": one_silence_or_two,
          "09-the-old-instance-wakes-up": the_old_instance_wakes_up,
          "09-a-reassignment-is-not-a-zombie": a_reassignment_is_not_a_zombie,
          "10-placement-under-labels": placement_under_labels,
          "10-two-controllers-one-camera": two_controllers_one_camera,
          "10-where-is-camera-7": where_is_camera_7,
          "10-the-snapshot": the_snapshot}


def main() -> None:
    write = "--write" in sys.argv
    only = [a for a in sys.argv[1:] if not a.startswith("--")]
    if write:
        os.makedirs(TRACES, exist_ok=True)
    for name, scene in SCENES.items():
        if only and not any(o in name for o in only):
            continue
        text = scene()
        if write:
            with open(os.path.join(TRACES, name + ".txt"), "w", encoding="utf-8") as f:
                f.write(text)
        else:
            print(f"==== {name}\n{text}")


if __name__ == "__main__":
    main()
