"""Spares and offers — how a cluster without an orchestrator gets the worker it is short of (the М11 rework; the
product's c62e236, `_notes-ru/without-an-orchestrator.md`, «Процессы»).

The controller never starts a process. After its pass has carried out the decommissions, moved what the dead slots
held and redistributed (`SpecController.offer_spares`), it counts, per label set, the units nothing live has room for
— unplaced, or still on a worker that is leaving — less the free capacity of the live workers whose labels cover the
set: `<sub>_units_short`; `ceil(short / CAPACITY)` workers, less the offers taken by a spare not heard yet (for 90 s),
is `<sub>_workers_needed`. For each it writes an OFFER: an empty slot row `<sub>/slots/<w-N>` `{holder:"", until:"0",
released:"false", gen:"0", offer:"<set>", offered_at:<ts>}`, created with `cas=0`, and removes by CAS delete the ones
not needed any more. A spare (`SPARE_FOR=<set>`, started by `w2c-spares.sh`) takes only an offer of its set, by CAS;
with none it waits holding nothing. An ordinary process never takes an offer. The console publishes the numbers on
`/metrics` without a token while the pass is at most a minute old.
"""
import json
import math
import threading
import urllib.request

from w2cplatform.contract import OFFER_GRACE, Slot, Worker, label_set
from w2cplatform import runtime
from vms.config import SPEC
from vms.controller import VmsController
from vms.worker import FakeActuator, VmsWorker
from tests.conftest import Box


def _ctl(box, capacity=2):
    return VmsController(box.vars.as_writer("vmscontroller", SPEC.acl_controller()), box.objects, capacity=capacity,
                         wall=box.wall)


def _con(box):
    return VmsController(box.vars.as_writer("console", SPEC.acl_console()), box.objects, wall=box.wall)


def _worker(box, name=None, server="srv-a", capacity=2, env=None, vars_=None):
    w = VmsWorker(name, vars_ or box.vars, box.objects, FakeActuator(), clock=box.clock, wall=box.wall,
                  capacity=capacity, server=server, archive_root=box.archive, env=env or {})
    if w.name is not None:
        w.heartbeat_once()
    return w


def _cameras(box, n, labels=None):
    con = _con(box)
    for _ in range(n):
        i = box.cameras = getattr(box, "cameras", 0) + 1                   # one channel is one camera: a source each
        con.create_camera({"source": f"driverpack://file/{i}.mp4", **({"labels": labels} if labels else {})})


def _resource(box, server: str) -> None:
    """A server's resource heartbeat: the server is there, and a spare may run on it."""
    box.objects.put(f"platform/resources/{server}/heartbeat",
                    json.dumps({"server": server, "ts": box.wall(), "url": f"http://{server}", "units": {}}).encode())


def _offers(box) -> dict:
    out = {}
    for p in box.vars.list("vms/slots/"):
        items, _ = box.vars.get(p)
        if items and "offer" in items and not items.get("holder"):
            out[p.rsplit("/", 1)[1]] = items
    return out


def test_a_shortage_writes_one_offer_per_missing_worker_in_the_products_row():
    """One worker of capacity 2, five cameras: two placed, three short — `ceil(3 / 2)` = two workers needed, two offers,
    each the product's row exactly, created with `cas=0` under the next free numbers. The pass report says the
    numbers per label set, the empty set always."""
    box = Box()
    _worker(box)
    _cameras(box, 5)
    ctl = _ctl(box)
    rep = ctl.pass_once()
    assert rep["units_short"] == {"": 3} and rep["workers_needed"] == {"": 2} and rep["spare_offers"] == {"": 2}, rep
    offers = _offers(box)
    assert sorted(offers) == ["w-2", "w-3"], offers
    assert offers["w-2"] == {"holder": "", "until": "0", "released": "false", "gen": "0", "offer": "",
                             "offered_at": str(box.wall())}
    assert ctl.pass_once()["spare_offers"] == {"": 2} and sorted(_offers(box)) == ["w-2", "w-3"]   # not written twice


def test_two_spares_racing_for_one_offer_exactly_one_takes_it_and_the_other_waits_holding_nothing():
    """Two scripts on two servers each start a spare for the one worker missing: both read the offer, both write by CAS
    — one takes the slot, the other finds no offer left and waits, nobody: no slot, no heartbeat, nothing assigned.
    The winner heartbeats, the cameras are placed on it, and `workers_needed` falls to zero."""
    box = Box()
    _worker(box)
    _cameras(box, 3)
    ctl = _ctl(box)
    assert ctl.pass_once()["workers_needed"] == {"": 1} and list(_offers(box)) == ["w-2"]
    both_read = threading.Barrier(2)

    class Racing:
        """Each spare's store: the first write to a slot waits until both have read the offer."""
        def __init__(self):
            self.waited = False

        def __getattr__(self, name):
            return getattr(box.vars, name)

        def put(self, key, items, cas=None):
            if key.startswith("vms/slots/") and not self.waited:
                self.waited = True
                both_read.wait(5)
            return box.vars.put(key, items, cas=cas)

    spares = [None, None]

    def start(i, server):
        spares[i] = _worker(box, server=server, env={"SPARE_FOR": ""}, vars_=Racing())
    threads = [threading.Thread(target=start, args=(i, s)) for i, s in enumerate(("srv-b", "srv-c"))]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)
    took = [s for s in spares if s.name is not None]
    waiting = [s for s in spares if s.name is None]
    assert len(took) == 1 and len(waiting) == 1, [(s.name, s.seeking) for s in spares]
    assert took[0].name == "w-2" and waiting[0].seeking is not None and waiting[0].slot is None
    row, _ = box.vars.get("vms/slots/w-2")
    assert row["holder"] == took[0].instance and row["offer"] == "" and _offers(box) == {}
    waiting[0].heartbeat_once()
    assert sorted(ctl.workers_seen()) == ["w-1", "w-2"]                  # the one waiting says nothing
    rep = ctl.pass_once()
    assert rep["workers_needed"] == {"": 0} and rep["units_short"] == {"": 0} and rep["unplaced"] == 0, rep
    assert ctl.assignment("w-2").units and _offers(box) == {}


def test_an_offer_not_needed_any_more_is_removed_by_the_controller():
    """The shortage goes — here a worker with room comes back — and the next pass deletes the offer, by CAS."""
    box = Box()
    _worker(box)
    _cameras(box, 3)
    ctl = _ctl(box)
    ctl.pass_once()
    assert list(_offers(box)) == ["w-2"]
    _worker(box, "w-9", server="srv-b", capacity=4)                       # room for the third camera
    rep = ctl.pass_once()
    assert rep["workers_needed"] == {"": 0} and rep["spare_offers"] == {"": 0}, rep
    assert _offers(box) == {} and box.vars.get("vms/slots/w-2")[0] is None


def test_an_ordinary_process_never_takes_an_offer():
    """A nameless process looks for a lapsed slot, then a free one, then makes one — and an offer is none of these
    (`Slot.claimable` false): it makes `w-3` beside the offer `w-2`, which stays for a spare."""
    box = Box()
    _worker(box)
    _cameras(box, 3)
    _ctl(box).pass_once()
    offer = Slot.from_items("w-2", box.vars.get("vms/slots/w-2")[0])
    assert offer.offer == "" and offer.offered() and not offer.claimable(box.wall() + 1e6)
    w = _worker(box, server="srv-b")
    assert w.name == "w-3" and list(_offers(box)) == ["w-2"]


def test_offers_are_per_label_set_and_a_spare_takes_only_its_own():
    """Cameras on `vlan:dmz` and no worker reaching it: a shortage of that set by itself, whatever room the others
    have; the empty set needs nobody. A spare for the empty set does not take the `vlan:dmz` offer; one for
    `vlan:dmz` does, and the cameras go to it — its server reaches the VLAN. (srv-c is there before it, its labels
    said by nobody yet: a server a spare of the set may run on — `test_no_offer_where_no_server_could_carry_a_spare`.)"""
    box = Box()
    _resource(box, "srv-c")
    _worker(box, capacity=4)
    _cameras(box, 2)
    _cameras(box, 2, labels=["vlan:dmz"])
    ctl = _ctl(box)
    rep = ctl.pass_once()
    assert rep["workers_needed"] == {"": 0, "vlan:dmz": 1} and rep["units_short"] == {"": 0, "vlan:dmz": 2}, rep
    assert [o["offer"] for o in _offers(box).values()] == ["vlan:dmz"]
    other = _worker(box, server="srv-b", env={"SPARE_FOR": ""})
    assert other.name is None and list(_offers(box).values())[0]["offer"] == "vlan:dmz"
    dmz = _worker(box, server="srv-c", env={"SPARE_FOR": "vlan:dmz", "LABELS": "vlan:dmz"})
    assert dmz.name == "w-2"
    dmz.heartbeat_once()
    rep = ctl.pass_once()
    assert rep["workers_needed"] == {"": 0, "vlan:dmz": 0} and sorted(ctl.assignment("w-2").units) == ["3", "4"], rep
    assert label_set("b, a,,a") == "a,b" and label_set([]) == ""


def test_a_taken_offer_whose_worker_is_not_heard_counts_as_issued_for_90_s():
    """A spare took the offer and has not heartbeated yet — starting, or dead before its first word. For
    `OFFER_GRACE` (90 s) from the take it counts as a worker on its way: no second offer, no second spare. Past
    that, unheard, it is a worker that did not come, and the shortage is offered again."""
    box = Box()
    _worker(box)
    _cameras(box, 3)
    ctl = _ctl(box)
    ctl.pass_once()
    spare = Worker(SPEC.sub, None, box.vars, box.objects, clock=box.clock, wall=box.wall)
    assert spare.claim_slot(spare_for="") == "w-2"                          # took it, and never says a word
    assert OFFER_GRACE == 90.0
    for _ in range(3):
        box.clock.advance(25); box.wall.advance(25)
        box.objects.put("vms/heartbeats/w-1", box.objects.get("vms/heartbeats/w-1"))
        _worker(box, "w-1")
        rep = ctl.pass_once()
        assert rep["workers_needed"] == {"": 0} and rep["spares_starting"] == {"": 1} and _offers(box) == {}, rep
    box.clock.advance(20); box.wall.advance(20)                             # 95 s since the take
    _worker(box, "w-1")
    rep = ctl.pass_once()
    assert rep["workers_needed"] == {"": 1} and list(_offers(box)) == ["w-3"], rep


def test_the_numbers_on_metrics_without_a_token_while_the_pass_is_fresh():
    """`/metrics` (and `/live/metrics`, `/auto/metrics` — the mounts): `vms_workers_needed{labels=""}` always, a row per
    set, `vms_units_short`, `vms_spare_offers`, `vms_server_labels{server,labels,source}` — the console's row for a
    server, else its node's word. No token asked. A pass older than a minute: none of the four — a script reading a
    stale number would start processes for a shortage that may be gone."""
    from w2cplatform.spec import SpecController
    from vms.auto import AutoController
    from vms.config import LIVE_SPEC
    from vms.console import make_console
    box = Box()
    _worker(box, env={"LABELS": "vlan:a"})
    _cameras(box, 3)
    ctl = _ctl(box)
    _con(box).set_server_labels("srv-a", ["vlan:a", "vlan:b"])
    ctl.pass_once()
    live = SpecController(LIVE_SPEC, box.vars, box.objects, wall=box.wall)
    live.pass_once()
    auto = AutoController(box.vars, box.objects, wall=box.wall)
    auto.pass_once()
    m = make_console(_con(box), box.archive, box.wall, live_ctl=live, mounts={"auto": auto})
    srv = m.serve("127.0.0.1", 0)
    base = f"http://127.0.0.1:{srv.server_address[1]}"

    def page(path):
        with urllib.request.urlopen(base + path) as r:
            return r.read().decode()
    try:
        text = page("/metrics")
        assert 'vms_workers_needed{labels=""} 1\n' in text and 'vms_units_short{labels=""} 1\n' in text, text
        assert 'vms_spare_offers{labels=""} 1\n' in text
        assert 'vms_server_labels{server="srv-a",labels="vlan:a,vlan:b",source="console"} 1\n' in text
        assert 'live_workers_needed{labels=""} 0\n' in page("/live/metrics")
        assert 'auto_workers_needed{labels=""} 0\n' in page("/auto/metrics")
        box.wall.advance(61)
        stale = page("/metrics")
        assert "vms_workers_needed" not in stale and "vms_server_labels" not in stale
        assert "vms_units_unplaced" in stale                                 # the rest of the page stands
    finally:
        srv.shutdown()


def test_a_spare_waiting_for_an_offer_runs_its_loop_holding_nothing_and_takes_one_when_it_comes():
    """Started before any offer (the script raced the controller): its loop runs — passes, lease steps — with no slot,
    no heartbeat, nothing assigned and nothing fenced; the lease step after an offer appears takes it."""
    box = Box()
    _worker(box)
    spare = _worker(box, server="srv-b", env={"SPARE_FOR": ""})
    assert spare.name is None and spare.seeking is not None
    for _ in range(3):
        spare.reconcile_once(); spare.lease_pass(); spare.heartbeat_once()
    assert spare.recording_allowed and spare.pass_failures == 0 and box.vars.list("vms/slots/") == ["vms/slots/w-1"]
    assert box.objects.list("vms/heartbeats/") == ["vms/heartbeats/w-1"]
    _cameras(box, 3)
    _ctl(box).pass_once()                                                 # w-1 takes two, one is short: an offer
    spare.lease_pass()
    assert spare.name == "w-2" and spare.seeking is None
    spare.heartbeat_once()
    assert "w-2" in _ctl(box).workers_seen()


def test_the_name_comes_from_the_unit_and_a_spare_has_none():
    """Product P4: the unit says the name — `Environment=WORKER_NAME=w-%l-1`, one per server and role — read by every
    role after its own `<ROLE>_NAME`; else `SLOT_INDEX`; else a free slot, a lapsed one first. A spare
    (`SPARE_FOR`) takes an offer and nothing else, whatever name it was handed."""
    assert runtime.slot({"WORKER_NAME": "w-srv-a-1"}) == "w-srv-a-1"
    assert runtime.slot({"WORKER_NAME": "r-srv-a-1"}, "RECORDER_NAME", "r") == "r-srv-a-1"
    assert runtime.slot({"RECORDER_NAME": "r-2", "WORKER_NAME": "x"}, "RECORDER_NAME", "r") == "r-2"
    assert runtime.slot({"SLOT_INDEX": "3"}, "GATEWAY_NAME", "g") == "g-3" and runtime.slot({}) is None
    assert runtime.spare_for({}) is None and runtime.spare_for({"SPARE_FOR": ""}) == ""
    box = Box()
    w = _worker(box, env={"WORKER_NAME": "w-srv-a-1"})
    assert w.name == "w-srv-a-1"
    spare = _worker(box, server="srv-b", env={"WORKER_NAME": "w-srv-b-1", "SPARE_FOR": ""})
    assert spare.name is None and box.vars.get("vms/slots/w-srv-b-1")[0] is None
    assert math.ceil(3 / 2) == 2


# -- the twelfth round's «Вопросы»: offers only where a spare could carry units ----------------------------------------

class _Said:
    def __init__(self):
        self.lines = []

    def say(self, kind, cls="observation", **fields):
        self.lines.append((kind, cls))


def test_no_offer_where_no_server_could_carry_a_spare():
    """«Вопросы» 4 (found rebuilding three-cameras, by runs): offers were written for a label set no server reaches — they
    hung, never taken, and the number said a worker was needed for ever. Now, where every server known says what it
    reaches and none reaches the set, no offer is written: the shortage stays counted, `spares_withheld` says why (on
    `/metrics` too), and the alarm `spares.no_server` goes once. A server that comes to reach it gets the offer."""
    from w2cplatform.events import ALARM
    box = Box()
    _resource(box, "srv-a")
    _worker(box, capacity=4)
    _cameras(box, 2, labels=["vlan:dmz"])
    ctl = _ctl(box)
    ctl.journal = said = _Said()
    _con(box).set_server_labels("srv-a", ["vlan:lan"])
    for _ in range(2):
        rep = ctl.pass_once()
        assert rep["units_short"]["vlan:dmz"] == 2 and rep["workers_needed"]["vlan:dmz"] == 0, rep
        assert "reaches vlan:dmz" in rep["spares_withheld"]["vlan:dmz"] and _offers(box) == {}, rep
    assert said.lines.count(("spares.no_server", ALARM)) == 1
    _resource(box, "srv-d")
    _con(box).set_server_labels("srv-d", ["vlan:dmz"])
    rep = ctl.pass_once()
    assert rep["workers_needed"]["vlan:dmz"] == 1 and "vlan:dmz" not in rep["spares_withheld"], rep
    assert [o["offer"] for o in _offers(box).values()] == ["vlan:dmz"]


def test_under_distinct_servers_a_spare_is_offered_only_where_it_would_not_idle():
    """«Вопросы» 2: under `servers: distinct` a spare started on a server that already has its worker idles by policy;
    the camera stayed unplaced, `workers_needed` stayed 1, and the next pass offered again — spares raised on every
    server, each idle. Now only a server with no worker of the subsystem counts as room for a spare: with none, nothing
    is offered and the reason is said; a third server arriving gets exactly one offer."""
    box = Box()
    for server in ("srv-a", "srv-b"):
        _resource(box, server)
        _worker(box, server=server, capacity=2)
    _cameras(box, 5)
    ctl = _ctl(box)
    _con(box).set_policy({"servers": "distinct"})
    assert ctl.policy()["servers"] == "distinct"
    rep = ctl.pass_once()
    assert rep["units_short"] == {"": 1} and rep["workers_needed"] == {"": 0} and _offers(box) == {}, rep
    assert "distinct" in rep["spares_withheld"][""], rep
    _resource(box, "srv-c")
    rep = ctl.pass_once()
    assert rep["workers_needed"] == {"": 1} and len(_offers(box)) == 1 and rep["spares_withheld"] == {}, rep


def test_the_shortage_is_counted_by_what_the_workers_announce_not_the_controllers_fallback():
    """«Вопросы» 3: workers were counted by the controller's own `CAPACITY` (2 here) while every worker of the role says
    4 — two offers for four cameras where one spare carries them. Now the count is by the smallest capacity the live
    workers of the set announce (a spare is started like them, and says the same); the fallback only with none live."""
    box = Box()
    _worker(box, capacity=4)
    _cameras(box, 8)
    rep = _ctl(box, capacity=2).pass_once()
    assert rep["units_short"] == {"": 4} and rep["workers_needed"] == {"": 1}, rep
