"""The scenario language, and where it is checked.

`auto.subsystem.yaml` says a scenario has a `when`, a `within` and a `then`.
The platform checks that those are JSON and small and stops there, because a
generic loader that validated a trigger would be a generic loader that knows
what a trigger is. Everything else is `vms/auto.py`, and it runs at the door —
while the operator is still looking at what they typed, which is the only
moment the answer is cheap.
"""
import json

from w2cplatform.spec import Refused, SubsystemSpec
from vms.auto import ACTIONS, AutoController, fires, refuse_scenario
from vms.config import AUTO_SPEC
from tests.conftest import Box, door_site


DOOR = {"name": "door-on-badge",
        "when": [{"sub": "vms", "kind": "io.input", "unit": "12", "match": {"port": "1", "value": "closed"}},
                 {"sub": "det", "kind": "motion", "unit": "7-motion"}],
        "within": 30,
        "then": [{"sub": "vms", "action": "output", "unit": "12", "port": 2, "pulse_ms": 500},
                 {"sub": "rec", "action": "record", "cam": "7", "minutes": 10, "archive": "cold"}]}


def _con(box):
    door_site(box)                                   # the door, the lobby and its detector exist
    return AutoController(box.vars.as_writer("console", AUTO_SPEC.acl_console()), box.objects, wall=box.wall)


def test_a_scenario_is_a_row_and_its_shapes_survive_the_round_trip():
    """JSON in the row, structure out of it. The fifth subsystem needed the type
    and none of the four before it did: a scenario's triggers are a LIST OF
    SHAPES, and flattening that into fields would cap it at one trigger or
    invent `when_1_sub` — a schema pretending not to be one."""
    box = Box()
    con = _con(box)
    row = con.create(DOOR)

    assert row["id"] == "door-on-badge"
    back = con.unit("door-on-badge")
    assert back["when"][0]["match"] == {"port": "1", "value": "closed"}      # parsed, not a string
    assert back["then"][1]["minutes"] == 10
    assert back["within"] == 30 and back["rate_per_minute"] == 6             # the default ceiling is on

    stored, _ = box.vars.get("auto/scenarios/door-on-badge")                 # …and in the store it is text
    assert json.loads(stored["when"])[1]["kind"] == "motion"


def test_what_the_platform_checks_and_what_it_does_not():
    """The line, in two assertions. JSON and a ceiling are the platform's; what
    a trigger MEANS is the subsystem's."""
    box = Box(); con = _con(box)

    try:
        con.create({**DOOR, "name": "broken", "when": "{not json"})
        raise AssertionError("a `json` field took something that is not JSON")
    except Refused as e:
        assert "not JSON" in str(e)

    try:
        con.create({**DOOR, "name": "huge", "when": [{"sub": "vms", "kind": "x", "match": {"a": "b" * 5000}}]})
        raise AssertionError("a single field ate the row's ceiling")
    except Refused as e:
        assert "ceiling" in str(e)

    # …and the platform would happily have taken this one: it is valid JSON and small
    assert AUTO_SPEC.fields["when"].type == "json"
    try:
        con.create({**DOOR, "name": "nonsense", "when": [{"sub": "vms", "kind": "io.input", "colour": "red"}],
                    "within": 0})
        raise AssertionError("a trigger with an invented key was accepted")
    except Refused as e:
        assert "no key 'colour'" in str(e)


def test_every_refusal_says_what_would_be_right():
    """A refusal that names only what is wrong makes the operator guess. These
    are read by somebody mid-edit, so each one carries the alternative."""
    box = Box(); con = _con(box)
    cases = [
        ({"when": DOOR["when"], "within": 0}, "within how many seconds"),
        ({"when": [DOOR["when"][0]], "within": 30}, "with one trigger there is nothing to window"),
        ({"when": [], "within": 0}, "non-empty list"),
        ({"then": [{"sub": "vms", "action": "reboot", "unit": "1"}]}, "this course files"),
        ({"then": [{"sub": "rec", "action": "record", "cam": "7"}]}, "needs 'minutes'"),
        ({"then": [{"sub": "vms", "action": "output", "unit": "1", "port": 1, "volume": "x"}]}, "no field 'volume'"),
        ({"when": [{"sub": "vms"}], "within": 0}, "names the subsystem it watches"),
        ({"rate_per_minute": 9999}, "between 1 and 600"),
    ]
    for i, (patch, want) in enumerate(cases):
        try:
            con.create({**DOOR, "name": f"bad{i}", **patch})
            raise AssertionError(f"accepted {patch}")
        except Refused as e:
            assert want in str(e), (patch, str(e))


def test_an_edit_is_checked_as_the_scenario_it_would_become():
    """The likelier of the two doors: the scenario that runs the site was
    written months ago and is being adjusted at speed. Validating the half being
    sent would pass anything; the check is on the row as it would end up."""
    box = Box(); con = _con(box)
    con.create(DOOR)

    try:
        con.update("door-on-badge", {"when": [DOOR["when"][0]]})       # one trigger, and `within` still 30
        raise AssertionError("an edit left the scenario unrunnable")
    except Refused as e:
        assert "nothing to window" in str(e)

    con.update("door-on-badge", {"when": [DOOR["when"][0]], "within": 0})   # both together: fine
    assert con.unit("door-on-badge")["within"] == 0


def test_matching_is_equality_and_nothing_else():
    """The evaluator's half of the language, beside the validation on purpose:
    two files would drift, and the drift would look like a scenario that never
    fires — the hardest kind of bug to see, because nothing happens."""
    ev = {"subsystem": "vms", "unit": "vms/12", "kind": "io.input", "t": 100.0, "port": "1", "value": "closed"}
    assert fires({"sub": "vms", "kind": "io.input"}, ev)
    assert fires({"sub": "vms", "kind": "io.input", "unit": "12"}, ev)
    assert fires({"sub": "vms", "kind": "io.input", "match": {"port": 1}}, ev)       # numbers compare as text
    assert not fires({"sub": "det", "kind": "io.input"}, ev)
    assert not fires({"sub": "vms", "kind": "motion"}, ev)
    assert not fires({"sub": "vms", "kind": "io.input", "unit": "13"}, ev)
    assert not fires({"sub": "vms", "kind": "io.input", "match": {"value": "open"}}, ev)
    assert not fires({"sub": "vms", "kind": "io.input", "match": {"nothing": "x"}}, ev)


def test_the_catalogue_is_the_boundary():
    """What automation may ask for is narrower than what the subsystems can do,
    and the narrow list is the point: every entry is a request somebody has to
    have written a performer for."""
    assert set(ACTIONS) == {("vms", "output"), ("vms", "preset"), ("rec", "record"), ("det", "detect"), ("det", "scan")}
    for (sub, action), spec in ACTIONS.items():
        assert spec["need"], f"{sub}.{action} names no required field"

    # the snapshot leaves the cluster, and what a site pulses is nobody's business up there
    assert AUTO_SPEC.snapshot == ["name", "enabled"]
    assert "when" not in AUTO_SPEC.snapshot and "then" not in AUTO_SPEC.snapshot


def test_the_spec_says_nothing_about_doors():
    """The subsystem is domain from the first word, and the platform stays where
    it was: the spec it loads has fields, types and a placement policy, and not
    one line of it means anything about sensors."""
    d = SubsystemSpec.load(AUTO_SPEC.path) if hasattr(AUTO_SPEC, "path") else AUTO_SPEC
    assert d.requires == "resource" and d.servers == "shared"
    assert [f.type for f in (d.fields[n] for n in ("when", "then"))] == ["json", "json"]


# -- the catalogue is not the device: what the units raise and can do ----------------------------------
def _held(box, key_source, **devkw):
    """The holder of one device, with the token a worker actually gets — its epochs, its slot, and what it
    found the device to be."""
    from vms.config import SPEC as VMS, WORKER_ACL
    from vms.controller import VmsController
    from vms.worker import FakeActuator, FakeDevice, VmsWorker
    from w2cplatform.contract import Heartbeat
    con = VmsController(box.vars.as_writer("console", VMS.acl_console()), box.objects, wall=box.wall)
    have = next((c for c in con.cameras() if c.get("source") == key_source), None)   # a restart: the camera is there already
    cid = (have or con.create_camera({"name": "lobby", "source": key_source}))["id"]
    box.objects.put(VMS.sub.heartbeat_key("w-1"), Heartbeat("w-1", box.wall(), [], {"server": "srv-a", "capacity": 50,
                                                                                    "headroom": 50}).to_bytes())
    box.objects.put("platform/resources/srv-a/heartbeat",
                    json.dumps({"server": "srv-a", "ts": box.wall(), "url": "http://srv-a", "units": {}}).encode())
    ctl = VmsController(box.vars.as_writer("vmscontroller", VMS.acl_controller()), box.objects, wall=box.wall)
    ctl.ensure_placed()
    token = box.vars.as_writer("vmsworker", WORKER_ACL)
    w = VmsWorker("w-1", token, box.objects, FakeActuator(), clock=box.clock, wall=box.wall, server="srv-a", env={},
                  archive_root=box.archive, device_factory=lambda key: FakeDevice(key, channels=["1"], **devkw))
    return w, cid


def test_the_holder_says_what_its_device_raises_and_can_do_once():
    """Only the process that opened the device knows it has one contact, two relays and its own motion
    analytics. It writes that where automation reads it — `vms/devices/<device>`, keyed by device — and
    writes it ONCE: on a camera the row is on flash, and a description does not change between passes. The
    same description leaves the cluster in the heartbeat, per camera (`can`), for a domain to read."""
    box = Box()
    w, cid = _held(box, "driverpack://acme/10.0.0.77/ch/1", rays=1, relays=2, presets=5, events=("motion",))
    w.refresh()
    row, idx = box.vars.get("vms/devices/acme/10.0.0.77")
    assert row == {"events": "command,command.failed,io.input,motion,silent", "rays": "1", "relays": "2",
                   "ptz": "true", "presets": "5"}
    assert w.describe_devices() == 0                                    # memory, not the store: nothing again
    w.reconcile_once(); w.heartbeat_once()
    from w2cplatform.contract import Heartbeat
    hb = Heartbeat.from_bytes(box.objects.get("vms/heartbeats/w-1"))
    st = next(s for s in hb.status if s["id"] == cid)
    assert st["can"]["relays"] == 2 and "motion" in st["can"]["events"]
    assert hb.extra["devices"][0]["can"]["presets"] == 5

    w.release_slot()                                                    # a restart: a fresh memory…
    again, _ = _held(box, "driverpack://acme/10.0.0.77/ch/1", rays=1, relays=2, presets=5, events=("motion",))
    again.refresh()
    assert box.vars.get("vms/devices/acme/10.0.0.77")[1] == idx         # …compared with the store: not rewritten


def test_a_scenario_is_checked_against_what_the_units_are():
    """The catalogue says what automation may ask for; the device rows say what THIS unit raises and can do.
    Each of these passed the language and would have been accepted before — and never fired, or been refused
    by the holder at three in the morning. Now each is refused while the operator is looking at it, with
    what would be right. The first is the trigger this lesson printed: a detector is named by its unit."""
    box = Box(); con = _con(box)
    cases = [
        ({"when": [{"sub": "det", "kind": "motion", "unit": "7"}], "within": 0},
         "there is no detector 7 — a detector is named by its unit: 7-motion (camera 7's)"),
        ({"when": [{"sub": "vms", "kind": "motoin", "unit": "7"}], "within": 0},
         "camera 7 does not raise 'motoin' — it raises command, command.failed, motion, silent"),
        ({"when": [{"sub": "vms", "kind": "io.input", "unit": "12", "match": {"port": "2"}}], "within": 0},
         "camera 12 has 1 input(s), not port 2"),
        ({"when": [{"sub": "det", "kind": "lpr", "unit": "7-motion"}], "within": 0},
         "detector 7-motion raises motion, not 'lpr'"),
        ({"when": [{"sub": "vms", "kind": "io.input", "unit": "99"}], "within": 0}, "there is no camera 99"),
        ({"then": [{"sub": "vms", "action": "output", "unit": "12", "port": 3}]}, "camera 12 has 2 relay(s), not port 3"),
        ({"then": [{"sub": "vms", "action": "output", "unit": "7", "port": 1}]}, "camera 7 has no relays"),
        ({"then": [{"sub": "vms", "action": "preset", "unit": "12", "n": 1}]}, "camera 12 has no telemetry"),
        ({"then": [{"sub": "vms", "action": "preset", "unit": "7", "n": 9}]}, "camera 7 has 5 preset(s), not 9"),
        ({"then": [{"sub": "rec", "action": "record", "cam": "99", "minutes": 10}]}, "there is no camera 99 to record"),
    ]
    for i, (patch, want) in enumerate(cases):
        try:
            con.create({**DOOR, "name": f"bad{i}", **patch})
            raise AssertionError(f"accepted {patch}")
        except Refused as e:
            assert want in str(e), (patch, str(e))
    con.create({**DOOR, "then": DOOR["then"] + [{"sub": "vms", "action": "preset", "unit": "7", "n": 3}]})   # fits


def test_a_device_nobody_has_held_is_not_refused_and_a_scenario_that_stops_fitting_says_so():
    """Two answers the door cannot give. A camera added this minute, whose device no holder has opened yet,
    has said nothing — and "unknown" is not "cannot": the scenario is accepted and the evaluator names what it
    could not check, on every pass. And a scenario that fitted when it was written can stop fitting: the
    lobby camera replaced by one without a telemetry. The evaluator checks again every pass and says so."""
    from w2cplatform.contract import requests_acl
    from vms.autoworker import AutoWorker
    box = Box(); con = _con(box)
    box.vars.put("vms/cameras/20", {"id": "20", "name": "gate", "source": "driverpack://acme/10.0.0.20/ch/1"})
    gate = {"name": "gate-to-lobby", "when": [{"sub": "vms", "kind": "io.input", "unit": "20"}], "within": 0,
            "then": [{"sub": "vms", "action": "preset", "unit": "7", "n": 3}]}
    con.create(gate)                                                   # accepted: camera 20 has said nothing yet
    AutoController(box.vars.as_writer("autocontroller", AUTO_SPEC.acl_controller()), box.objects,
                   wall=box.wall).assign("a-1", ["gate-to-lobby"])

    class _Quiet:
        def query(self, *a, **kw): return {"events": [], "state": "live", "truncated": False}
    w = AutoWorker("a-1", box.vars.as_writer("autoworker", AUTO_SPEC.sub.acl_worker() + requests_acl("vms", "rec")),
                   box.objects, index=_Quiet(), clock=box.clock, wall=box.wall, server="srv-a", archive_root=box.archive, env={})
    w.reconcile_once()
    st = w.status()[0]
    assert st["unchecked"] == ["camera 20 has not said what it raises — its device has not been held yet; "
                               "'io.input' is not checked"] and "unfit" not in st

    box.vars.put("vms/devices/acme/10.0.0.20", {"events": "command,command.failed,io.input,silent", "rays": "2",
                                                "relays": "0", "ptz": "false", "presets": "0"})   # held, at last
    box.vars.put("vms/devices/acme/10.0.0.77", {"events": "command,command.failed,silent", "rays": "0",
                                                "relays": "0", "ptz": "false", "presets": "0"})   # the lobby, replaced
    w.reconcile_once()
    st = w.status()[0]
    assert "unchecked" not in st and st["unfit"] == ["camera 7 has no telemetry: it cannot go to a preset"]


def test_the_form_is_built_from_the_catalogue():
    """One answer with both halves: what automation may ask for, and per unit what it raises and can do. The
    page offers camera 12's kinds and camera 7's five presets from it; a camera nobody has held says `can:
    null`, and the page offers a free field for it."""
    from vms.console import auto_routes
    box = Box(); con = _con(box)
    box.vars.put("vms/cameras/20", {"id": "20", "name": "gate", "source": "driverpack://acme/10.0.0.20/ch/1"})
    code, cat = auto_routes(con)(None, "GET", "/catalog", {})
    assert code == 200 and set(cat["actions"]) == {"vms.output", "vms.preset", "rec.record", "det.detect", "det.scan"}
    assert cat["vms"]["12"]["can"]["relays"] == 2 and "io.input" in cat["vms"]["12"]["can"]["events"]
    assert cat["vms"]["7"]["can"]["presets"] == 5 and cat["vms"]["20"]["can"] is None
    assert cat["det"] == {"7-motion": {"cam": "7", "raises": ["motion"]}}
    assert list(cat["vms"]) == ["7", "12", "20"]                        # numeric ids in numeric order


def test_the_pages_scenario_form_takes_its_subsystem_from_the_spec_and_names_none_of_its_own():
    """The page is the platform's (`w2cplatform/console.html`), and its scenario form said `vms` itself: the units
    from `catalog.vms`, the trigger `vms|<unit>|<kind>`, the action `{sub: 'vms', …}` — a page over another root
    subsystem would have offered nothing and filed actions for a subsystem it does not show (the course's decision on
    the platform's names). Now the form takes the root console's `spec.name`, and the catalogue keys the units by
    that same name — the two halves agree, and the page's code names no subsystem in that form."""
    import os
    import re
    from vms.config import SPEC
    from vms.console import auto_routes
    page = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "w2cplatform",
                             "console.html"), encoding="utf-8").read()
    form = page.split("// -- automation:", 1)[1].split("// -- the administrator's knob", 1)[0]
    assert "catalog[spec.name]" in form and "sub: spec.name" in form and "${spec.name}|${current}|" in form
    assert not re.search(r"catalog\.vms|'vms'|`vms\|", form), "the form names a subsystem of its own"
    box = Box(); con = _con(box)
    code, cat = auto_routes(con)(None, "GET", "/catalog", {})
    assert code == 200 and isinstance(cat.get(SPEC.name), dict)          # what the form reads, by the spec's name
