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
from w2cplatform.resource import Resource, resources_seen, workers_here
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
    `workers`. Fate `move`: the cameras go to w-2 once the slot has run out — without the margin since the owner's
    decision of 3 Oct (the test below); the slot stays, lapsed — the server's supervisor brings the process back under
    its name with nothing to do. While the slot holds: alive, nothing moves."""
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


def test_a_spare_and_the_console_judge_a_hung_worker_by_the_controllers_limit_not_their_own():
    """The product's alignment of the owner's decision: a spare asked whether a lapsed slot's worker is hung through a
    controller built in its own process — with `HUNG_MOVE_AFTER` as compiled in, while the controller read its own from
    its environment. Told an hour, the controller held w-1's cameras back at seventeen minutes and the spare took the name
    `w-1`, and the cameras with it: a second writer. Told a minute, the controller had moved them and the spare still
    would not take the name. The controller says its limit in its pass report (`hung_move_after`); the spare and the
    console's `/servers` judge by it (`published_hung_limit`)."""
    from w2cplatform.contract import published_hung_limit
    site = _Site()
    box, ctl = site.box, site.ctl
    ctl.hung_move_after = 3600.0                                             # the controller's environment: an hour
    site.tick(100)
    ctl.pass_once()
    assert published_hung_limit(box.objects, SPEC.sub) == 3600.0
    site.tick(HUNG_MOVE_AFTER)                                               # past the compiled-in fifteen minutes
    rep = ctl.pass_once()
    assert site.fate() == "hung" and rep["workers_hung"] == ["w-1"] and sorted(ctl.assignment("w-1").units) == site.on_w1
    spare = VmsWorker(None, box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, server="srv-2")
    assert spare.name == "w-3"                                               # not w-1: the controller still calls it hung
    _, _, _, srv, base = _console(box)
    try:
        row = next(w for w in _call(base, "GET", "/servers")[1]["servers"]["srv-1"]["workers"] if w["worker"] == "w-1")
    finally:
        srv.shutdown()
    assert row["hung"] and "3600 s" in row["hung_why"], row

    site = _Site()
    box, ctl = site.box, site.ctl
    ctl.hung_move_after = 60.0                                               # …and told a minute
    site.tick(100); site.tick(100)
    rep = ctl.pass_once()
    assert site.fate() == "hung_moved" and ctl.assignment("w-1").units == [], rep
    spare = VmsWorker(None, box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, server="srv-2")
    assert spare.name == "w-1"                                               # moved: the name is a lapsed one's, taken


def test_the_resource_says_which_workers_are_placed_and_which_run():
    """`workers_here`: a registration whose lock is held is in `workers` and `running`; one let go is in `workers` only; a
    newer registration under the same name replaces an old one let go; a resource heartbeat carries both, and a `ts`
    that is no finite number is no live resource heartbeat — a resource known and silent."""
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
    assert ctl.resource_state("srv-x") == "silent"                           # not live for ever: known, and not live (the twelfth pass)
    a.absent(); again.absent()


def test_a_dead_process_on_a_server_that_answers_moves_when_its_slot_runs_out_and_a_silent_server_waits_out_the_margin():
    """FAILOVER SHORTENED BY THE RESOURCE (the owner's decision, 3 Oct). The margin past a slot's `until`
    (`SLOT_LOST_AFTER`, 45 s) is for a process that may still write. When its server's resource answers and says the
    process is dead — placed, its lock let go — nothing can write: the units move the moment the slot runs out, 45 s
    after the last renewal, where they waited 90. A silent server says nothing of its processes: the margin stands —
    the slot's 45 s and 45 more."""
    site = _Site()
    ctl = site.ctl
    site.ws["w-1"].absent()                                                  # the process ends; srv-1's resource answers
    site.tick(44)
    assert site.fate() == "alive" and sorted(ctl.assignment("w-1").units) == site.on_w1   # it holds its name a second more
    site.tick(2)                                                             # 46 s: the slot ran out
    fate, server, why = ctl.slot_fate("w-1", ctl.slots()["w-1"])
    assert (fate, server) == ("move", "srv-1") and "slot ran out" in why, why
    ctl.pass_once()
    assert ctl.assignment("w-1").units == [] and all(ctl.where(int(c)) == "w-2" for c in site.on_w1)
    assert not ctl.slots()["w-1"].released                                   # the name stays, for its supervisor's restart

    silent = _Site()
    silent.up.discard("srv-1")                                               # the whole server: worker and resource
    silent.tick(46)
    assert silent.fate() == "alive"                                          # nobody can say the process is dead
    silent.tick(43)                                                          # 89 s
    assert silent.fate() == "alive"
    silent.tick(2)                                                           # 91 s: the slot's 45 and the margin's 45
    assert silent.fate() == "move"


def test_a_slot_row_that_does_not_parse_moves_only_on_two_words_and_is_never_released():
    """The product's DZ: a slot row nobody can read is not a dead worker. With the worker's heartbeat fresh — alive,
    whatever its server's resource says: nothing moves. With the heartbeat silent AND the resource saying there is no
    such process — placed and not running, or not listed at all — the units move; the row is left as it is, not
    written over as released (`release_unlisted` releases nothing)."""
    try:
        site = _Site()
        ctl, box = site.ctl, site.box
        garbled = {"holder": "x", "until": "soon", "released": "false", "gen": "1"}
        box.vars.put("vms/slots/w-1", garbled)
        site.tick(100)
        site.ws["w-1"].heartbeat_once()                                     # the worker speaks…
        site.ws["w-1"].absent(); site.beat()                                # …and the resource says: placed, not running
        assert ctl.said_on("srv-1") == ({"w-1"}, set())                     # one word, not two
        assert ctl.slot_fate("w-1", None)[0] == "alive"
        ctl.pass_once()
        assert sorted(ctl.assignment("w-1").units) == site.on_w1

        site.tick(50)                                                        # the heartbeat silent too: two words
        assert ctl.slot_fate("w-1", None)[0] == "move"
        rep = ctl.pass_once()
        assert all(ctl.where(int(c)) == "w-2" for c in site.on_w1) and rep["slots_released"] == [], rep
        assert box.vars.get("vms/slots/w-1")[0] == garbled                   # the row as it was

        unlisted = _Site()
        unlisted.ws["w-1"].absent()
        d = os.path.join(unlisted.roots["srv-1"], ".workers")
        for f in os.listdir(d):
            os.remove(os.path.join(d, f))                                    # srv-1 does not run it at all
        unlisted.box.vars.put("vms/slots/w-1", garbled)
        unlisted.tick(100)
        fate, _, why = unlisted.ctl.slot_fate("w-1", None)
        assert fate == "move" and "does not parse" in why, why               # where a parsed row would be released
        rep = unlisted.ctl.pass_once()
        assert rep["slots_released"] == [] and unlisted.box.vars.get("vms/slots/w-1")[0] == garbled, rep
        assert all(unlisted.ctl.where(int(c)) == "w-2" for c in unlisted.on_w1)
    finally:
        _forget_garbled()


# -- the twelfth pass: two holders of the same cameras ---------------------------------------------------------------

def _two_writers(site, worker):
    """The cameras of w-1 that `worker` records while w-1's process still records them."""
    worker.reconcile_once(); worker.reconcile_once()
    return sorted(set(map(str, site.ws["w-1"].actuator.running)) & set(map(str, worker.actuator.running)))


def test_a_nameless_process_does_not_take_a_hung_workers_name_within_the_margin():
    """The review's twelfth pass, blocker 2 (`f1_spare_in_margin`): for the 45 s after a hung worker's slot ran out the
    controller says "alive" — what it started may still write — and a spare asked only "hung?": it took w-1, and cameras
    1 and 3 with it, at +46…+89 s, two writers. Now a name is given when the controller would move its units and not
    before (`Worker._held`): within the margin, and hung past it, the spare makes a slot of its own; dead, it takes it."""
    for dt in (46, 60, 89, 95, 100):
        site = _Site()
        box = site.box
        site.tick(dt)
        assert site.fate() in ("alive", "hung"), (dt, site.fate())
        spare = VmsWorker(None, box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, capacity=4,
                          server="srv-2")
        assert spare.name == "w-3" and _two_writers(site, spare) == [], dt
    site.ws["w-1"].absent(); site.beat()
    assert site.fate() == "move"
    spare = VmsWorker(None, box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, server="srv-2")
    assert spare.name == "w-1"                                               # dead: its name, and its cameras


def test_a_spare_that_cannot_ask_whether_the_holder_is_gone_leaves_the_name_alone():
    """Blocker 2's second half (`f6_hung_fail_open`): a store that raised while the spare asked was "not hung" — it took
    the hung worker's name. Now a question that cannot be asked is "not known": the name stays, the spare makes its own."""
    site = _Site()
    box = site.box
    site.tick(100)
    assert site.fate() == "hung"
    real = box.objects.list

    def failing(prefix, *a, **k):
        if prefix.startswith("platform/resources"):
            raise OSError(5, "I/O error")
        return real(prefix, *a, **k)
    box.objects.list = failing
    try:
        spare = VmsWorker(None, box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, capacity=4,
                          server="srv-2")
    finally:
        box.objects.list = real
    assert spare.name == "w-3" and _two_writers(site, spare) == []


def test_a_garbled_slot_row_of_a_hung_worker_is_not_taken_when_it_stands_still():
    """Major 4 (`f2_garbled_hung`): a hung worker's slot row torn — it stands still, its holder is hung — and a seeking
    process that watched it a term took it, and the units, past `slot_fate`. Now the stood-still row is taken only
    where the controller would move its units: hung, it is left; the process makes a slot of its own."""
    try:
        site = _Site()
        box, ctl = site.box, site.ctl
        box.vars.put("vms/slots/w-1", {"holder": site.ws["w-1"].instance, "until": "torn", "released": "false",
                                       "gen": "1"})
        site.tick(100)
        assert ctl.slot_fate("w-1", None)[0] == "hung"
        seeker = VmsWorker(None, box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, capacity=4,
                           server="srv-2")
        assert seeker.name == "w-3"                                          # first look: the row noted, not taken
        site.tick(seeker.slot_ttl + seeker.HOLD_SKEW + 1, live=("w-2", "w-3") if "w-3" in site.ws else ("w-2",))
        assert seeker.renew_slot()
        seeker.slot = None
        assert seeker.claim_slot() != "w-1" and ctl.slot_fate("w-1", None)[0] == "hung"
        assert _two_writers(site, seeker) == []
    finally:
        _forget_garbled()


def test_what_the_resource_cannot_read_of_its_workers_is_not_taken_for_their_end():
    """Blocker 3 (`f3_resource_cannot_look`, `probe_presence_json`): a resource that answers and could not read who runs
    on it said "not listed" — a directory that does not list, a lock that does not open, a live lock whose `.json` is
    absent, torn, names no subsystem or nobody — and the hung w-1's slot was released, its cameras given to w-2 while it
    wrote them, in each case. Now what is not read is said (`presence_error`, `presence_unread`), a live holder is
    matched by its lock's own name (`running_instances`), and nothing of it releases or moves: hung, or `unsure`."""
    import builtins, glob
    for mode in ("no listing", "lock does not open", "json absent", "json torn", "json without sub", "json nobody"):
        site = _Site()
        ctl, res = site.ctl, site.res["srv-1"]
        d = os.path.join(site.roots["srv-1"], ".workers")
        for p in glob.glob(os.path.join(d, "*.json")):
            if mode == "json absent":
                os.remove(p)
            elif mode == "json torn":
                open(p, "w").write('{"sub": "vms", "na')
            elif mode == "json without sub":
                open(p, "w").write(json.dumps({"name": "w-1", "pid": 1}))
            elif mode == "json nobody":
                open(p, "w").write(json.dumps({"sub": "vms", "name": "", "pid": 1}))
        site.tick(100)                                                       # w-1 hung, its lock held
        real = builtins.open
        if mode == "no listing":
            os.chmod(d, 0)
        elif mode == "lock does not open":
            def no_lock(path, *a, **k):
                if isinstance(path, str) and path.endswith(".lock") and "rb" in (a[0] if a else k.get("mode", "r")):
                    raise OSError(24, "Too many open files")
                return real(path, *a, **k)
            builtins.open = no_lock
        try:
            hb = res.heartbeat()
        finally:
            builtins.open = real
            os.chmod(d, 0o755)
        fate, _, why = ctl.slot_fate("w-1", ctl.slots()["w-1"])
        assert fate in ("hung", "unsure"), (mode, fate, why, hb.get("workers"), hb.get("presence_unread"))
        rep = ctl.pass_once()
        assert rep["slots_released"] == [] and sorted(ctl.assignment("w-1").units) == site.on_w1, (mode, rep)
        site.ws["w-2"].reconcile_once()
        assert not set(map(str, site.on_w1)) & set(map(str, site.ws["w-2"].actuator.running)), mode
        if fate == "unsure":
            assert rep["workers_unjudged"] == ["w-1"] and rep["units_unjudged"] == len(site.on_w1), (mode, rep)
            assert ("worker.unjudged", ALARM) in site.said.kinds(), mode


def test_a_worker_that_cannot_write_its_name_beside_its_lock_says_so_and_tries_again():
    """Blocker 3's other half: `_say_present` on ENOSPC only logged, and the `.json` stayed absent or naming nobody. Now
    the heartbeat says it (`presence_unsaid`), the controller counts it (`workers_presence_unsaid`) and judges the
    worker "unsure" — never released, never moved by the resource's word — and the next heartbeat writes it again."""
    site = _Site()
    w1, ctl = site.ws["w-1"], site.ctl
    f, d, _ = w1._presence
    w1._presence = (f, d, None)                                              # what it is called must be said again…
    real = os.replace

    def full(src, dst):
        if str(dst).startswith(d):
            raise OSError(28, "No space left on device")
        return real(src, dst)
    os.replace = full                                                        # …and the archive's volume is full
    try:
        w1.heartbeat_once()
    finally:
        os.replace = real
    hb = ctl._heard("w-1")
    assert "No space left" in hb.extra["presence_unsaid"]
    assert ctl.pass_once()["workers_presence_unsaid"] == ["w-1"]
    for p in os.listdir(d):
        if p.endswith(".json"):
            os.remove(os.path.join(d, p))                                    # the resource reads no name for its lock
    site.tick(100)
    assert site.fate() in ("hung", "unsure") and ctl.pass_once()["slots_released"] == []
    w1.heartbeat_once()                                                      # room again: said, and the mark gone
    assert "presence_unsaid" not in ctl._heard("w-1").extra
    assert any(p.endswith(".json") for p in os.listdir(d))


def test_the_resources_pulse_during_a_long_pass_says_who_runs_now():
    """Blocker 4 (`p8_pulse_stale_running`): the pulse of a long pass sent the heartbeat of the pass's start again with
    the time moved on — `workers`/`running` as they were. w-1 restarted after the pass began and froze: by the old list
    it was "placed, not running", and its slot was freed while its new process held its lock. Now every pulse looks
    again (`presence_here`): the restarted, frozen w-1 is running — hung, nothing moves."""
    import time
    site = _Site()
    box, ctl, res = site.box, site.ctl, site.res["srv-1"]
    res.clock, res.PULSE_SECONDS = box.clock, 0.02
    site.ws["w-1"].absent()
    res.heartbeat()                                                          # the pass begins: w-1 placed, not running
    seen = {}

    class Slow:
        def pass_(self, now):
            again = VmsWorker("w-1", box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall,
                              server="srv-1")                               # restarted under its name…
            assert again.present(site.roots["srv-1"])
            again.heartbeat_once()
            box.wall.advance(100); box.clock.advance(100)                    # …and frozen, while the pass runs on
            site.res["srv-2"].heartbeat()
            time.sleep(0.2)
            seen["fate"] = ctl.slot_fate("w-1", ctl.slots()["w-1"])[0]
            seen["running"] = resources_seen(box.objects)["srv-1"].get("running")
            seen["keep"] = again
            return {}
    res.register("slow", Slow())
    res.pass_()
    assert seen["running"] == {"vms": ["w-1"]} and seen["fate"] == "hung", seen
    seen["keep"].absent()


def test_a_controller_started_after_a_server_died_moves_its_cameras():
    """Blocker 5 (`p1_fresh_reader`): srv-1 went whole — its worker, its resource, and (as in М11, where they are files on
    it) both their heartbeats. A controller that had heard srv-1 moved its cameras; one started after it read nothing:
    "never said which server", `wait` for ever, no sign. Now the store keeps what outlives the server — the server in the
    slot row (`Slot.server`), and when its resource last said it is there (`at` on its door row) — and the fresh
    controller judges the two silences: the cameras move. A slot it still cannot judge is counted and an alarm."""
    site = _Site()
    box = site.box
    assert box.vars.get("vms/slots/w-1")[0]["server"] == "srv-1"
    assert box.vars.get("platform/doors/srv-1")[0]["at"]
    site.up.discard("srv-1")
    site.tick(100)
    for key in ("vms/heartbeats/w-1", "platform/resources/srv-1/heartbeat"):
        box.objects.delete(key)                                              # gone with the server
    fresh = VmsController(box.vars.as_writer("vmscontroller", SPEC.acl_controller()), box.objects, capacity=4,
                          wall=box.wall)
    fresh.journal = _Said()
    assert fresh.resource_state("srv-1") == "silent"
    fate, server, why = fresh.slot_fate("w-1", fresh.slots()["w-1"])
    assert (fate, server) == ("move", "srv-1"), why
    fresh.pass_once()
    assert all(fresh.where(int(c)) == "w-2" for c in site.on_w1)

    lost = _Site()                                                           # …and where even the store says nothing
    lost.up.discard("srv-1")
    lost.tick(100)
    lost.box.vars.delete("platform/doors/srv-1")
    lost.box.objects.delete("platform/resources/srv-1/heartbeat")
    lost.box.objects.delete("vms/heartbeats/w-1")
    rep = lost.ctl.pass_once()
    assert lost.fate() == "wait" and sorted(lost.ctl.assignment("w-1").units) == lost.on_w1
    assert rep["workers_unjudged"] == ["w-1"] and rep["units_unjudged"] == len(lost.on_w1), rep
    assert lost.said.kinds().count(("worker.unjudged", ALARM)) == 1
    lost.ctl.pass_once()
    assert lost.said.kinds().count(("worker.unjudged", ALARM)) == 1         # once an episode


def test_a_resource_whose_door_cannot_be_reached_is_not_a_silent_server():
    """Major 9 (`p6` door_down): the resource is alive, only its door is closed to the controller — its heartbeat seen
    ageing. "Silent", the hung worker's cameras moved and a nameless process took its name. Now the resource's own row
    in the store (`at`, every `ALIVE_EVERY`) is the second opinion: fresh, the server is `unreachable` — `unsure`, nothing
    moves, the name stays, and decommissioning it is refused."""
    site = _Site()
    box, ctl = site.box, site.ctl
    stale = box.objects.get("platform/resources/srv-1/heartbeat")
    site.tick(100)                                                           # w-1 hung; srv-1's resource beats…
    box.objects.put("platform/resources/srv-1/heartbeat", stale)             # …and is seen as it was 100 s ago
    assert ctl.resource_state("srv-1") == "unreachable"
    assert site.fate() == "unsure"
    ctl.pass_once()
    assert sorted(ctl.assignment("w-1").units) == site.on_w1
    spare = VmsWorker(None, box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, capacity=4,
                      server="srv-2")
    assert spare.name == "w-3" and _two_writers(site, spare) == []
    refusal, _ = ctl.decommission_refusal("srv-1")
    assert refusal and "said it is there" in refusal, refusal
    site.up.discard("srv-1"); site.tick(60)                                  # really gone now: both stale
    box.objects.put("platform/resources/srv-1/heartbeat", stale)
    assert ctl.resource_state("srv-1") == "silent" and site.fate() == "move"


def test_a_worker_clock_ahead_does_not_hold_its_cameras_without_limit():
    """Major 17: srv-1 off, and its worker's last words dated an hour ahead — the slot's `until` and the heartbeat's
    `ts`. The move waited the hour and decommissioning answered 409; `until` 1e308 was "alive" for ever. Now a slot
    dated further ahead than one term (`SLOT_AHEAD`) is no lease to read, a heartbeat past `FUTURE_TOLERANCE` is not
    heard, and the skew is counted: the server's two silences move the cameras as for any other worker."""
    from w2cplatform.contract import SKEW_MAX
    for until in (3600.0, 1e308):
        site = _Site()
        box, ctl = site.box, site.ctl
        row = dict(box.vars.get("vms/slots/w-1")[0])
        hb = json.loads(box.objects.get("vms/heartbeats/w-1"))
        site.up.discard("srv-1")
        row["until"] = box.wall() + until
        box.vars.put("vms/slots/w-1", row)
        hb["ts"] = box.wall() + 3600
        box.objects.put("vms/heartbeats/w-1", json.dumps(hb).encode())
        site.tick(100)
        assert site.fate() == "move", until
        assert ctl.decommission_refusal("srv-1")[0] is None
        assert SKEW_MAX.get("vms", 0) > 1000
        ctl.pass_once()
        assert all(ctl.where(int(c)) == "w-2" for c in site.on_w1), until


def test_the_decommission_door_reads_its_body_as_every_door_and_a_refusal_is_journalled():
    """The review's twelfth pass, minors: the decommission door read its body bare — `Content-Length: -1` held the
    thread 30 s and answered 503 "the store did not take it", 20 MB was read whole — and its 409 was a log line only.
    Now the body goes through `read_body` (400 at once, 413 past the limit), and a refusal is `server.decommission_refused`
    in the journal with its reason; a hung worker moved past the limit is counted (`workers_hung_moved_total`)."""
    import http.client
    import time
    from w2cplatform.eventdatabase import EventIndex
    site = _Site()
    box = site.box
    _, _, _, srv, base = _console(box)
    try:
        host, port = srv.server_address[:2]
        for length, want in (("-1", 400), (str(20 << 20), 413)):
            c = http.client.HTTPConnection(host, port, timeout=10)
            t0 = time.monotonic()
            c.putrequest("POST", "/servers/srv-1/decommission")
            c.putheader("Content-Type", "application/json"); c.putheader("Content-Length", length)
            c.endheaders()
            r = c.getresponse()
            assert r.status == want and time.monotonic() - t0 < 5, (length, r.status)
            c.close()
        st, out = _call(base, "POST", "/servers/srv-1/decommission", {"why": "burnt"}, user="anna")
        assert st == 409
    finally:
        srv.shutdown()
    kinds = [e["kind"] for e in EventIndex(box.archive, "srv-1", wall=box.wall).query(0, box.wall() + 1)["events"]]
    assert "server.decommission_refused" in kinds, kinds
    site.tick(100); site.ctl.pass_once()
    site.tick(HUNG_MOVE_AFTER)
    assert site.ctl.pass_once()["workers_hung_moved_total"] == 1
    assert site.ctl.pass_once()["workers_hung_moved_total"] == 1                # counted once an episode


def test_a_resource_heartbeat_that_does_not_parse_is_a_silent_server_not_an_unknown_one():
    """The review's twelfth pass, minor (a regression for NaN): a known resource whose heartbeat says `ts: NaN` was
    "unknown" — `wait` for ever, its server's cameras recorded by nobody. Now a heartbeat there that does not parse is a
    resource known and not live: silent, and the two silences move the cameras — unless its row in the store says it
    is there (`unreachable`)."""
    site = _Site()
    box = site.box
    site.up.discard("srv-1")
    site.tick(100)
    box.objects.put("platform/resources/srv-1/heartbeat",
                    b'{"server": "srv-1", "ts": NaN, "url": "http://srv-1", "mirrors": {}}')
    box.vars.delete("platform/doors/srv-1")
    box.objects.delete("vms/heartbeats/w-1")
    site.ctl.resource_state("srv-1")                                         # read once: the heartbeat counted as garbled
    assert site.ctl.resource_state("srv-1") == "silent" and site.fate() == "move"
