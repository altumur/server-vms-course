"""What becomes of a slot that stopped renewing — one rule, decided by the controller from facts (`Controller.slot_fate`).

The review's eleventh pass found the console's retire door handing a hung worker's cameras to another worker while its
pipelines still wrote: two holders of cameras 1 and 3. The owner's decision (3 Oct): the operator operates SERVERS, not
workers — the worker retire door is gone — and the server's resource says in its heartbeat which workers are placed on
it (`workers`) and whose processes run (`running`), from the locks the workers hold in its tree (`Worker.present`). The
four cases: running and silent — HUNG, nothing moves (`worker.hung`), until `HUNG_MOVE_AFTER`, then it moves anyway
(`worker.hung_moved`); placed and not running, or the server silent — the units move, the slot stays; not listed at all —
the slot is released (`release_unlisted`); an older resource or a worker that never registered — what it was before. A
machine gone for good is the operator's word about the server (`POST /servers/<s>/decommission`, on the Mount), refused
while the server answers by any of three signs; the controllers carry it out (`apply_decommissions`). The product's
names (d1bc470, 83193c1) throughout.
"""
import json
import os
import urllib.request

from w2cplatform.contract import HUNG_MOVE_AFTER, SLOTS_GARBLED, ServerDecommissioned, Slot, Worker
from w2cplatform.events import ALARM
from w2cplatform.resource import Resource, workers_here
from vms.config import SPEC
from vms.controller import VmsController
from vms.worker import FakeActuator, VmsWorker
from tests.conftest import Box
from tests.test_console_gate import _call, _console
from tests.test_slot_fence import _forget_garbled


class _Said:
    """The controller's journal, as it is said: `(kind, class, fields)`."""
    def __init__(self):
        self.lines = []

    def say(self, kind, cls="observation", **fields):
        self.lines.append((kind, cls, fields))

    def kinds(self):
        return [(k, c) for k, c, _ in self.lines]


class _Site:
    """Two servers, a resource on each, a worker on each registered with its resource (`w-1` on srv-1, `w-2` on srv-2),
    four cameras placed by a pass — two on each worker — and running."""

    def __init__(self, cameras: int = 4, register: bool = True):
        self.box = box = Box()
        self.roots = {"srv-1": box.archive, "srv-2": os.path.join(box.root, "archive2")}
        os.makedirs(self.roots["srv-2"], exist_ok=True)
        self.ctl = VmsController(box.vars.as_writer("vmscontroller", SPEC.acl_controller()), box.objects, capacity=4,
                                 wall=box.wall)
        self.said = self.ctl.journal = _Said()
        self.ws = {}
        for server in ("srv-1", "srv-2"):
            w = VmsWorker(None, box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, capacity=4,
                          server=server)
            if register:
                assert w.present(self.roots[server])
            w.heartbeat_once()
            self.ws[w.name] = w
        assert sorted(self.ws) == ["w-1", "w-2"]
        self.res = {s: Resource(r, s, f"http://{s}", box.vars, box.objects, wall=box.wall) for s, r in self.roots.items()}
        self.up = {"srv-1", "srv-2"}
        self.beat()
        con = VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)
        for i in range(1, cameras + 1):
            con.create_camera({"source": f"driverpack://file/{i}.mp4"})
        self.ctl.pass_once()
        for w in self.ws.values():
            w.reconcile_once(); w.heartbeat_once()
        self.on_w1 = sorted(self.ctl.assignment("w-1").units)
        assert self.on_w1 and self.ctl.assignment("w-2").units

    def beat(self):
        for s in self.up:
            self.res[s].heartbeat()

    def tick(self, seconds: float, live=("w-2",)):
        """`seconds` pass; the workers in `live` renew and speak, the resources in `up` heartbeat."""
        self.box.clock.advance(seconds); self.box.wall.advance(seconds)
        for name in live:
            assert self.ws[name].renew_slot()
            self.ws[name].heartbeat_once()
        self.beat()

    def epoch(self, cam) -> int:
        items, _ = self.box.vars.get(SPEC.sub.epoch_key(str(cam)))
        return int((items or {}).get("epoch", 0))

    def fate(self, worker="w-1"):
        return self.ctl.slot_fate(worker, self.ctl.slots().get(worker))[0]

    def kinds(self):
        return [k for k, _ in self.said.kinds()]


def test_a_hung_worker_on_a_server_that_answers_keeps_its_cameras_and_no_second_holder_is_made():
    """The review's scenario: w-1's loop hangs past the stand-in, its pipelines go on recording, its server's resource
    answers. Before: the console offered retire, 202, w-2 took epoch 2 of cameras 1 and 3 — two holders. Now the
    resource names w-1's process running: HUNG — the pass moves nothing, w-2 starts nothing of w-1's, no epoch moves; the
    alarm `worker.hung` once an episode, `/servers` says `hung` and since when, `vms_workers_hung` 1. And no door does
    otherwise: there is no worker retire, and decommissioning the server is refused while it answers."""
    site = _Site()
    ctl, w2 = site.ctl, site.ws["w-2"]
    epochs = {c: site.epoch(c) for c in site.on_w1}
    site.tick(100)                                                       # w-1 hung: no renewal, no heartbeat, the lock held
    assert site.fate() == "hung"
    for _ in range(3):
        rep = ctl.pass_once()
        assert rep["ok"] and rep["workers_hung"] == ["w-1"] and rep["slots_released"] == [], rep
    assert sorted(ctl.assignment("w-1").units) == site.on_w1                 # nothing moved
    w2.reconcile_once()
    assert not set(map(str, site.on_w1)) & set(map(str, w2.actuator.running))   # w-2 records none of them
    assert {c: site.epoch(c) for c in site.on_w1} == epochs                  # nobody took a new epoch: one holder each
    assert site.ws["w-1"].actuator.running                                   # the hung process's pipelines still write
    assert site.said.kinds().count(("worker.hung", ALARM)) == 1              # said once, not every pass

    _, _, _, srv, base = _console(site.box)
    try:
        servers = _call(base, "GET", "/servers")[1]["servers"]
        row = next(w for w in servers["srv-1"]["workers"] if w["worker"] == "w-1")
        assert row["hung"] and row["hung_since"] == ctl.slots()["w-1"].until and "runs on srv-1" in row["hung_why"], row
        assert not servers["srv-1"]["decommissionable"] and "answers" in servers["srv-1"]["decommission_refusal"]
        assert _call(base, "POST", "/workers/w-1/retire", {"why": "burnt"})[0] == 404   # the worker door is gone
        st, out = _call(base, "POST", "/servers/srv-1/decommission", {"why": "burnt"}, user="anna")
        assert st == 409 and out["error"] == "server answers" and "its resource was heard" in out["detail"], out
        with urllib.request.urlopen(base + "/metrics") as r:
            text = r.read().decode()
    finally:
        srv.shutdown()
    assert "vms_workers_hung 1\n" in text
    assert ctl.decommission_requests() == {} and sorted(ctl.assignment("w-1").units) == site.on_w1


def test_a_hung_worker_past_HUNG_MOVE_AFTER_has_its_cameras_moved_with_an_alarm():
    """No hole for ever either: `HUNG_MOVE_AFTER` (fifteen minutes, as the product) past the slot's `until`, the hung
    worker's cameras move anyway — fate `hung_moved` — with the alarm `worker.hung_moved`, said once. The slot is not
    released: the process may still come back under its name."""
    site = _Site()
    ctl = site.ctl
    assert ctl.hung_move_after == HUNG_MOVE_AFTER == 900.0
    site.tick(100)
    ctl.pass_once()
    assert sorted(ctl.assignment("w-1").units) == site.on_w1
    site.tick(HUNG_MOVE_AFTER)                                               # still hung, fifteen minutes on
    assert site.fate() == "hung_moved"
    rep = ctl.pass_once()
    assert rep["workers_hung"] == [], rep
    assert ctl.assignment("w-1").units == [] and all(ctl.where(int(c)) == "w-2" for c in site.on_w1)
    assert "move anyway" in ctl.placement(int(site.on_w1[0])).reason
    assert not ctl.slots()["w-1"].released
    ctl.pass_once()
    assert site.said.kinds().count(("worker.hung_moved", ALARM)) == 1        # said once an episode


def test_a_dead_process_on_a_server_that_answers_has_its_cameras_moved_and_keeps_its_name():
    """Placed and not running: w-1's process ended (its lock let go), the resource still lists it among the server's
    `workers`. Fate `move`: the cameras go to w-2 once the slot is past its margin; the slot stays, lapsed — the server's
    supervisor brings the process back under its name with nothing to do. Before the margin: alive, nothing moves."""
    site = _Site()
    ctl = site.ctl
    site.ws["w-1"].absent()                                                  # the process ends
    site.tick(30)
    assert site.fate() == "alive" and ctl.pass_once()["slots_released"] == []   # its lease's end and the margin: not yet
    assert sorted(ctl.assignment("w-1").units) == site.on_w1
    site.tick(70)
    assert site.fate() == "move"
    ctl.pass_once()
    assert ctl.assignment("w-1").units == [] and all(ctl.where(int(c)) == "w-2" for c in site.on_w1)
    assert "not running" in ctl.placement(int(site.on_w1[0])).reason
    s = ctl.slots()["w-1"]
    assert s.lapsed(site.box.wall()) and not s.released


def test_a_worker_its_server_does_not_list_at_all_has_its_slot_released_journalled_and_counted():
    """The resource answers and lists w-1 nowhere in `workers` — the server does not run it any more. Fate `release`:
    the pass releases the slot (`release_unlisted`: a process under it learns the name is not its own), its cameras move
    in the same pass, `worker.released_by_controller` in the journal, `slots_released_total` 1 — counted once."""
    site = _Site()
    ctl = site.ctl
    site.ws["w-1"].absent()
    d = os.path.join(site.roots["srv-1"], ".workers")
    for f in os.listdir(d):
        os.remove(os.path.join(d, f))                                        # its registration gone from the server
    site.tick(100)
    assert site.fate() == "release"
    rep = ctl.pass_once()
    assert rep["slots_released"] == ["w-1"] and rep["slots_released_total"] == 1, rep
    assert ctl.slots()["w-1"].released and ctl.assignment("w-1").units == []
    assert all(ctl.where(int(c)) == "w-2" for c in site.on_w1)
    assert site.kinds().count("worker.released_by_controller") == 1
    assert ctl.pass_once()["slots_released_total"] == 1


def test_a_silent_server_moves_its_workers_cameras():
    """The resource on srv-1 is silent too (and it said who it runs before it went): fate `move` — under any policy now,
    where it was only `servers: distinct` with a resource required (`gone_servers`)."""
    site = _Site()
    ctl = site.ctl
    site.up.discard("srv-1")
    site.tick(100)
    assert ctl.resource_state("srv-1") == "silent" and site.fate() == "move"
    assert ctl.gone_servers() == {"w-1": "srv-1"}
    ctl.pass_once()
    assert all(ctl.where(int(c)) == "w-2" for c in site.on_w1)


def test_an_older_resource_or_an_unregistered_worker_is_judged_as_before():
    """A resource that does not say `workers`/`running` (an older build: "not said", where an empty list is a list), or a
    worker that never registered (`present` not in its heartbeat): fate `wait` — what it was before: under `servers:
    shared` a silent worker is left to its supervisor, nothing moves."""
    site = _Site()
    ctl, box = site.ctl, site.box
    site.up.discard("srv-1")
    site.tick(100)
    box.objects.put("platform/resources/srv-1/heartbeat",
                    json.dumps({"server": "srv-1", "ts": box.wall(), "url": "http://srv-1", "mirrors": {}}).encode())
    assert ctl.resource_state("srv-1") == "live" and site.fate() == "wait"
    ctl.pass_once()
    assert sorted(ctl.assignment("w-1").units) == site.on_w1

    unregistered = _Site(register=False)
    unregistered.tick(100)
    assert unregistered.fate() == "wait"
    unregistered.ctl.pass_once()
    assert sorted(unregistered.ctl.assignment("w-1").units) == unregistered.on_w1


def test_a_server_is_decommissioned_only_once_it_is_silent_and_then_never_placed_on_until_it_is_brought_back():
    """The operator's word about a machine, on the Mount. While srv-1 answers — any of three signs: its resource heard, a
    worker of it heard, a slot of it renewed within the margin — 409 naming the sign, nothing written. Switched off: 202,
    `server.decommission_requested`, and the pass carries it out: w-1's slot released, its cameras moved, the mark
    `vms/decommissioned/srv-1 {asked_at, at, slots, units, holds}`, `server.decommissioned`, `servers_decommissioned_total`
    1. A process on srv-1 is refused a slot by name; a new camera is not placed there. `DELETE` brings it back
    (`server.decommission_withdrawn`), and the controller's mark goes with the request."""
    site = _Site()
    ctl, box = site.ctl, site.box
    con = VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)
    _, _, m, srv, base = _console(box)
    try:
        st, out = _call(base, "POST", "/servers/srv-1/decommission", {"why": "end of life"}, user="anna")
        assert st == 409 and "its resource was heard" in out["detail"], out           # sign 1
        site.up.discard("srv-1"); site.tick(100, live=("w-1", "w-2"))               # its resource silent, w-1 not
        st, out = _call(base, "POST", "/servers/srv-1/decommission", {})
        assert st == 409 and "w-1 holds its name" in out["detail"], out             # signs 2 and 3: it renews, it speaks
        site.ws["w-1"].absent(); site.tick(50)                                      # w-1 silent, its slot within the margin
        st, out = _call(base, "POST", "/servers/srv-1/decommission", {})
        assert st == 409 and "w-1 stopped renewing" in out["detail"], out           # sign 3: within the margin
        assert box.vars.get("platform/decommission/srv-1")[0] is None
        assert _call(base, "POST", "/servers/srv-9/decommission", {})[0] == 404       # nobody here has heard of it
        assert _call(base, "POST", "/servers/srv-1/decommission", [1])[0] == 400      # a body that is no object

        site.tick(60)                                                               # out of service, switched off
        st, out = _call(base, "POST", "/servers/srv-1/decommission", {"why": "end of life"}, user="anna")
        assert st == 202 and out["subsystems"]["vms"]["workers"] == ["w-1"], out
        assert out["subsystems"]["vms"]["units"] == site.on_w1 and "warning" not in out
        rep = ctl.pass_once()
        assert rep["servers_decommissioned"] == ["srv-1"] and rep["servers_decommissioned_total"] == 1, rep
        assert rep["slots_released"] == ["w-1"] and rep["decommission_requests_standing"] == 0
        assert ctl.slots()["w-1"].released and all(ctl.where(int(c)) == "w-2" for c in site.on_w1)
        mark = box.vars.get("vms/decommissioned/srv-1")[0]
        assert mark["slots"] == "w-1" and mark["units"] == ",".join(site.on_w1) and mark["asked_at"], mark
        assert site.kinds().count("server.decommissioned") == 1
        assert ctl.pass_once()["servers_decommissioned_total"] == 1                # carried out once
        servers = _call(base, "GET", "/servers")[1]["servers"]
        assert servers["srv-1"]["decommission"]["by"] == "anna" and servers["srv-1"]["decommissioned"]["slots"] == "w-1"
        assert not servers["srv-1"]["placeable"]

        site.up.add("srv-1"); site.beat()                                           # somebody switches it on again
        try:
            VmsWorker(None, box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, server="srv-1")
            assert False, "a process on a decommissioned server was given a slot"
        except ServerDecommissioned as e:
            assert "srv-1 is decommissioned" in str(e)
        con.create_camera({"source": "driverpack://file/5.mp4"})
        ctl.pass_once()
        assert ctl.where(5) is None                                                 # w-2 is full, srv-1 is out: 5 waits

        assert _call(base, "DELETE", "/servers/srv-1/decommission", user="anna")[0] == 200
        assert _call(base, "DELETE", "/servers/srv-1/decommission")[0] == 200       # nothing to withdraw: said, still 200
        back = VmsWorker(None, box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, capacity=4,
                         server="srv-1")
        back.heartbeat_once()
        ctl.pass_once()
        assert ctl.where(5) == back.name                                            # placeable again
        assert box.vars.get("vms/decommissioned/srv-1")[0] is None                  # the mark went with the request
    finally:
        srv.shutdown()


def test_a_server_whose_resource_was_never_heard_is_decommissioned_with_a_warning():
    """No resource ever heard on srv-3: whether the machine is off cannot be told, and the operator's word is taken — 202,
    with `warning`; `/servers` says `decommission_warning` before."""
    site = _Site()
    box = site.box
    w3 = VmsWorker(None, box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, server="srv-3")
    w3.heartbeat_once()
    site.tick(100)
    _, _, _, srv, base = _console(box)
    try:
        servers = _call(base, "GET", "/servers")[1]["servers"]
        assert servers["srv-3"]["decommissionable"] and "never heard" in servers["srv-3"]["decommission_warning"]
        st, out = _call(base, "POST", "/servers/srv-3/decommission", {"why": "gone"})
        assert st == 202 and "never heard" in out["warning"], out
    finally:
        srv.shutdown()


def test_the_rule_lives_in_one_place():
    """The move off a dead worker, releasing a slot and a decommission all read `slot_fate`: change it, and every one of
    them follows — what the owner decides next is one function."""
    site = _Site()
    ctl = site.ctl
    site.up.discard("srv-1")
    site.tick(100)
    row = site.box.vars.get("vms/slots/w-1")[0]
    for fate, moves, releases, refused in (("hung", {}, [], False), ("wait", {}, [], False),
                                           ("move", {"w-1": "srv-1"}, [], False), ("hung_moved", {"w-1": "srv-1"}, [], False),
                                           ("release", {}, ["w-1"], False), ("alive", {}, [], True)):
        site.box.vars.put("vms/slots/w-1", row)                              # the slot as it was: lapsed, held
        ctl.slot_fate = lambda w, s, fate=fate: (fate, "srv-1", fate) if w == "w-1" else ("alive", "", "")
        assert ctl.gone_servers() == moves, fate
        assert sorted(ctl.release_unlisted()["released"]) == releases, fate
        assert (ctl.decommission_refusal("srv-1")[0] is not None) == refused, fate


def test_a_slot_until_infinity_is_that_slots_trouble_alone():
    """The review's regression: `until: "Infinity"` read as a lease for ever, and `int(until - now)` raised past what
    `/servers` and the pass caught — no answer, and the pass stopped at its first step. Now the row does not parse:
    skipped and counted, `/servers` answers (`slot_garbled`, `slot_until: null`), the pass runs, and the other slots are
    judged as ever. `NaN` and a word the same."""
    site = _Site()
    ctl, box = site.ctl, site.box
    w9 = Worker(SPEC.sub, "w-9", box.vars, box.objects, clock=box.clock, wall=box.wall)
    w9.heartbeat([], server="srv-2")
    try:
        for bad in ("Infinity", "NaN", "soon"):
            box.vars.put("vms/slots/w-9", {"holder": "x", "until": bad, "released": "false", "gen": "1"})
            rep = ctl.pass_once()
            assert rep["ok"], rep
            assert "w-9" not in ctl.slots() and SLOTS_GARBLED.get("vms")
        _, _, _, srv, base = _console(box)
        try:
            st, out = _call(base, "GET", "/servers")
            assert st == 200, out
            row = next(w for w in out["servers"]["srv-2"]["workers"] if w["worker"] == "w-9")
            assert row["slot_garbled"] and row["slot_until"] is None, row
        finally:
            srv.shutdown()
        site.ws["w-1"].absent(); site.tick(100)
        assert site.fate() == "move"
        ctl.pass_once()
        assert all(ctl.where(int(c)) == "w-2" for c in site.on_w1)
    finally:
        _forget_garbled()


def test_a_garbled_slot_row_nobody_touches_for_a_term_can_be_claimed_again():
    """The product's cross-check: a slot row that does not parse was nobody's for ever — no claim took it, and the
    units assigned to its name with it. A seeking process that has watched it stand still (the same revision) for the
    slot's term and `HOLD_SKEW` takes it, under the generation the row still says, plus one. A row that changes in
    between (its holder renews it) is not taken."""
    box = Box()
    box.vars.put("vms/slots/w-1", {"holder": "x", "until": "soon", "released": "false", "gen": "7"})
    try:
        w = Worker(SPEC.sub, None, box.vars, box.objects, clock=box.clock, wall=box.wall)
        idx = box.vars.get("vms/slots/w-1")[1]
        assert not w._garbled_stale("w-1", idx)                              # first look: from now
        box.clock.advance(w.slot_ttl + w.HOLD_SKEW - 1)
        box.vars.put("vms/slots/w-1", {"holder": "x", "until": "later", "released": "false", "gen": "7"})   # it moved
        assert not w._garbled_stale("w-1", box.vars.get("vms/slots/w-1")[1])
        box.clock.advance(w.slot_ttl + w.HOLD_SKEW + 1)                      # and stood still a whole term since
        assert w.claim_slot() == "w-1"
        s = Slot.from_items("w-1", box.vars.get("vms/slots/w-1")[0])
        assert s.holder == w.instance and s.gen == 8
    finally:
        _forget_garbled()


def test_a_spare_does_not_take_the_name_of_a_hung_worker_and_takes_a_dead_ones():
    """The sibling of the review's blocker by another door: a nameless process claims a lapsed slot first — its
    assignment is waiting — and with the name it takes the units. A hung worker's name (its process runs on a server
    that answers) is not taken: the spare makes a new slot. A dead worker's is, as ever."""
    site = _Site()
    box = site.box
    site.tick(100)
    assert site.fate() == "hung"
    spare = VmsWorker(None, box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, server="srv-2")
    assert spare.name == "w-3"                                               # not w-1: its process still runs
    site.ws["w-1"].absent()
    site.beat()
    assert site.fate() == "move"
    other = VmsWorker(None, box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, server="srv-2")
    assert other.name == "w-1"                                               # dead: its name, and what it was assigned


def test_the_resource_says_which_workers_are_placed_and_which_run():
    """`workers_here`: a registration whose lock is held is in `workers` and `running`; one let go is in `workers` only; a
    newer registration under the same name replaces an old one let go; a resource heartbeat carries both, and a `ts`
    that is no finite number is no resource heartbeat at all."""
    box = Box()
    root = box.archive
    a = Worker(SPEC.sub, "w-1", box.vars, box.objects, clock=box.clock, wall=box.wall)
    b = Worker(SPEC.sub, "w-2", box.vars, box.objects, clock=box.clock, wall=box.wall)
    assert a.present(root) and b.present(root)
    assert workers_here(root) == ({"vms": ["w-1", "w-2"]}, {"vms": ["w-1", "w-2"]})
    b.absent()
    assert workers_here(root) == ({"vms": ["w-1", "w-2"]}, {"vms": ["w-1"]})
    again = Worker(SPEC.sub, "w-2", box.vars, box.objects, clock=box.clock, wall=box.wall)
    assert again.present(root)
    assert workers_here(root) == ({"vms": ["w-1", "w-2"]}, {"vms": ["w-1", "w-2"]})
    assert len([f for f in os.listdir(os.path.join(root, ".workers")) if f.endswith(".lock")]) == 2   # the old one removed
    hb = Resource(root, "srv-1", "http://srv-1", box.vars, box.objects, wall=box.wall).heartbeat()
    assert hb["workers"] == {"vms": ["w-1", "w-2"]} and hb["running"] == {"vms": ["w-1", "w-2"]}
    ctl = VmsController(box.vars, box.objects, wall=box.wall)
    assert ctl.said_on("srv-1") == ({"w-1", "w-2"}, {"w-1", "w-2"})
    box.objects.put("platform/resources/srv-x/heartbeat",
                    b'{"server": "srv-x", "ts": Infinity, "url": "", "mirrors": {}}')
    assert ctl.resource_state("srv-x") == "unknown"                          # not live for ever
    a.absent(); again.absent()
