"""The VMS's schema — as a spec the platform's controller runs from
(vms.subsystem.yaml, beside this file). What this module keeps is the
Python view of the same thing, for the worker and the tests:

    vms/cameras/<id>      the row: the spec's fields, plus revision       (the controller writes)
    vms/workers/<worker>  units, rev                                      (the controller writes)
    vms/placement/<id>    worker, reason, at, rev                         (the controller writes)
    vms/retention/<id>    days — derived from events_retention_days       (the controller writes; the resource reads)
    vms/epoch/<id>        epoch                                           (a worker takes, by CAS)
    vms/devices/<device>  events, rays, relays, ptz, presets — what it says and does   (its holder, on a change)
    vms/next_id           n                                               (the controller)

A camera row is small, rare and must be consistent: raft's shape. Nothing
here is controller-derived status — that is in the worker's heartbeat.
"""
# ================================================================================================
# NOTES — what every part of this file does and why (kept beside the code, not in a separate document)
# ================================================================================================
# # config.py — the VMS's schema as the Python view over `vms.subsystem.yaml`: `SPEC`, `row()`, `items()`
#
# **Role in the module.** The schema itself is the YAML beside this file (see `vms.subsystem.yaml`), and the
# platform's `SubsystemSpec` parses it. This module loads that spec once at import and exposes the two
# conversions the worker and the tests need — a Variables row of strings to a typed camera dict, and back.
# The docstring is the VMS's key map, worth keeping in view:
#
# - `vms/cameras/<id>` — the row: the spec's fields plus `revision` (the controller writes; the console's
#   token may too).
# - `vms/workers/<worker>` — `units, rev` (the controller writes; the worker reads).
# - `vms/placement/<id>` — `worker, reason, at, rev` (the controller writes).
# - `vms/retention/<id>` — `days`, derived from `events_retention_days` (the controller writes; the
#   platform's resource job reads).
# - `vms/epoch/<id>` — `epoch` (a worker takes, by CAS).
# - `vms/next_id` — `n` (the controller).
#
# "A camera row is small, rare and must be consistent: raft's shape. Nothing here is controller-derived
# status — that is in the worker's heartbeat." Used by `worker.py` (`row` on every refresh), `controller.py`
# (`SPEC`), `console.py` via the controller, `__main__.py` (`SPEC.acl_*`, `row` in `retain`) and the tests
# (`SPEC.acl_console()` / `acl_controller()` to build the two tokens).
#
# ## Module-level names
# - `SPEC` — `SubsystemSpec.load(<this directory>/vms.subsystem.yaml)`, parsed once at import. PyYAML is
#   imported lazily inside `load`, so this is the one import in the VMS that needs it.
# - `OPERATOR_FIELDS` — `tuple(SPEC.fields)`: the field names the operator owns (`name, source, enabled,
#   retention_days, events_retention_days, priority, labels, ref`), in YAML order.
# - `FORBIDDEN_FIELDS` — an alias of `w2cplatform.spec.PLATFORM_FIELDS` (`worker, placement, epoch,
#   revision, observed_revision, phase, id`): what `SubsystemSpec.refuse` rejects in a create/update body.
#   Kept under the VMS's old name for readers of earlier lessons.
#
# ## Notes
# - Neither function filters the `deleted` marker: a row the controller marked `deleted: "true"` converts
#   like any other. `VmsWorker.refresh` checks the marker itself before calling `row`; `__main__.retain`
#   does not.
# - Changing a field's type or default is a YAML edit, not a Python one; this module has nothing to change.
# ================================================================================================
from __future__ import annotations

import os

from w2cplatform.spec import PLATFORM_FIELDS, SubsystemSpec

SPEC = SubsystemSpec.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "vms.subsystem.yaml"))
LIVE_SPEC = SubsystemSpec.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "live.subsystem.yaml"))   # the second subsystem: live fan-outs
DET_SPEC = SubsystemSpec.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "det.subsystem.yaml"))     # the third: detectors
REC_SPEC = SubsystemSpec.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "rec.subsystem.yaml"))     # the fourth: recorders, on the archive
DETJOB_SPEC = SubsystemSpec.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "detjob.subsystem.yaml"))  # the fifth: archive scans, the first work that ends
AUTO_SPEC = SubsystemSpec.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "auto.subsystem.yaml"))  # the sixth: scenarios, the first work that READS what the others wrote
SURVEY_SPEC = SubsystemSpec.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "survey.subsystem.yaml"))  # the sixth: watching an archive we do not own
PLAYBACK_PORT = 8083     # the holder's playback surface: HTTP, because a browser must be able to seek it
LIVE_PORT_BASE = 20000       # a camera's RTP port on its worker's loopback: the RTSP fan-out's one subscriber (gstvms/livesrv.py)
SHM_DIR = "/run/vms"         # the tee's shared-memory branch: <SHM_DIR>/<cam>.shm — a subscriber on the SAME server reads it (shmsrc), no RTSP hop
RTSP_PORT = 8554             # the worker's RTSP fan-out: rtsp://<server>:8554/<cam> — what a recorder, a gateway, a detector subscribe to


def live_shm(cid, shm_dir: str = SHM_DIR) -> str:
    """The camera's shared-memory socket on its worker's server: the local fast path (shm:// scheme)."""
    return f"shm://{shm_dir}/{cid}.shm"


def device_of(source: str) -> str:
    """The thing DriverPack connects to. Cameras sharing it share one session:
    `driverpack://acme/10.0.0.50/ch/17` and `…/ch/18` are two channels of one NVR;
    a camera with an SD card is a device with one channel. Pure parsing — the
    vendor's own addressing stays opaque, only the grouping is ours."""
    from urllib.parse import urlsplit
    u = urlsplit(source)
    if u.scheme != "driverpack":
        return source
    parts = [p for p in u.path.split("/") if p]
    if u.netloc == "file":
        return "file/" + parts[0] if parts else "file"
    return f"{u.netloc}/{parts[0]}" if parts else u.netloc


# -- the device row: what the holder found the device to be -----------------------------------------------
# `vms/devices/<device>`, keyed by DEVICE and not by camera: a sixteen-channel recorder is one device and one
# set of relays, and keyed by camera the same facts would be written sixteen times. Its one writer is the
# worker that holds the device (`group_by: device` makes that one worker), and it writes only when the
# answer changes — on a camera the row is on flash, and a description does not change between passes.
#
# Why a row and not only the heartbeat: automation checks a scenario against it when the scenario is
# WRITTEN (`auto.Catalog`), and the device may be off at that moment. A heartbeat is what the device is now;
# the row is what it last was, and "the door controller has one relay" does not stop being true because the
# controller is rebooting.
DEVICES = "devices"

# What a holder writes about ANY unit it holds, whatever the device: it went quiet, a command was done to it,
# a command was refused (`VmsWorker.pump_once`, `requests`). Every unit raises these; the device adds its own.
HOLDER_EVENTS = ("command", "command.failed", "silent")


# The holder's token: the platform's grant for any worker, plus the one row it writes that is not a claim about
# itself — what a device turned out to be. Derived here, once, so the process (`__main__.worker`) and a cluster's
# policy file (М11, `test_policies`) cannot say different things.
WORKER_ACL = SPEC.sub.acl_worker() + [SPEC.sub.config(DEVICES, "*")]


def describe(caps: dict | None) -> dict | None:
    """What automation may point at on a device, from what the device said about itself (`capabilities()`):
    the kinds of event its units raise, and what it can be asked to do. `None` — the device said nothing,
    which is not the same answer as "it can do nothing"."""
    if caps is None:
        return None
    events = set(HOLDER_EVENTS) | {str(e) for e in caps.get("events", ()) if str(e)}
    if int(caps.get("rays", 0) or 0):
        events.add("io.input")                   # a contact is read as `io.input` with its port and value
    return {"events": sorted(events), "rays": int(caps.get("rays", 0) or 0), "relays": int(caps.get("relays", 0) or 0),
            "ptz": bool(caps.get("ptz")), "presets": int(caps.get("presets", 0) or 0)}


def device_row(desc: dict) -> dict:
    """The description as a row: strings, a list comma-joined — the store's shape (М10A Lesson 9)."""
    return {"events": ",".join(desc["events"]), "rays": str(desc["rays"]), "relays": str(desc["relays"]),
            "ptz": "true" if desc["ptz"] else "false", "presets": str(desc["presets"])}


def parse_device_row(items: dict | None) -> dict | None:
    if not items:
        return None
    return {"events": [e for e in str(items.get("events", "")).split(",") if e],
            "rays": int(items.get("rays") or 0), "relays": int(items.get("relays") or 0), "ptz": str(items.get("ptz")) == "true",
            "presets": int(items.get("presets") or 0)}


def channel_of(source: str) -> str | None:
    """`driverpack://<vendor>/<host>/ch/<n>` -> "<n>"; None when the device has one channel."""
    from urllib.parse import urlsplit
    u = urlsplit(source)
    parts = [p for p in u.path.split("/") if p]
    return parts[2] if u.netloc != "file" and len(parts) >= 3 and parts[1] == "ch" else None


# A port an instance was told, where `auto` (or `0`) means "ask the operating system for a free one".
#
# A door with a number baked into a TEMPLATE is a door only one instance can open. `vmsworker@w-1` and
# `vmsworker@w-2` on one box are the ordinary way to use capacity — and the second one binds the same
# 8554, dies, and `Restart=always` raises it every two seconds until morning. Nothing in the system needs
# the number to be 8554: every subscriber reads the address out of the heartbeat, which is what the
# heartbeat is for. So the number may be zero, and what gets published is what the OS gave.
def port_of(value, default: int) -> int:
    v = str(value if value is not None else "").strip().lower()
    if v in ("auto", "0"):
        return 0
    return int(v) if v else int(default)


def playback_url(server: str, cid, port: int = PLAYBACK_PORT) -> str:
    """Where a camera's OWN archive is served from — the holder's playback surface.
    HTTP, not the RTSP fan-out: a browser has to seek inside it, and the recorder
    fetches ranges from the same door. The port is the one this holder BOUND."""
    return f"http://{server}:{port}/playback/{cid}"


def live_url(server: str, cid, port: int = RTSP_PORT) -> str:
    """Where a camera's stream is served from: the worker's RTSP fan-out. In the
    heartbeat, so a subscriber needs only the heartbeat — on any server, at
    whatever port this worker's fan-out ended up on."""
    return f"rtsp://{server}:{port}/{cid}"


# `REC_SPEC.row(items)` with `id` as the camera number: the recorder's reconciler wants an int id like the
# worker's, and a recording is named by its camera.
def rec_row(items: dict) -> dict:
    """The recorder's row, with `id` left exactly as the spec made it.

    It used to read `r["id"] = int(r["cam"])` — and that one line was the whole of "a recording is named
    by its camera", hidden in a parser rather than declared in the YAML. With it gone the two identities
    are separate everywhere: `id` is WHICH RECORDING (its epoch, its slot, its tree), `cam` is WHOSE
    FAN-OUT to subscribe to. The spec said `id: cam` for a long time and they were the same string; the
    difference the line made was that this was the spec's statement and nothing else's — which is why
    `id: name` cost no Python here when a second archive made a camera's recordings two."""
    return REC_SPEC.row(items)
OPERATOR_FIELDS = tuple(SPEC.fields)
FORBIDDEN_FIELDS = PLATFORM_FIELDS


# `SPEC.row(items)`: Variables items (all strings) to a typed dict with `id`, every spec field (its default
# if absent) and `revision` (default 1). The worker calls it on each camera row named by its assignment;
# `retain` calls it on every row under `vms/cameras/`.
def row(items: dict) -> dict:
    return SPEC.row(items)


# `SPEC.items(row_)`: the inverse, everything as strings (`bool` → `"true"/"false"`, lists comma-joined).
# The controller uses the spec's method directly; this wrapper exists for symmetry and for the tests.
def items(row_: dict) -> dict:
    return SPEC.items(row_)

from . import volumes as _volumes  # noqa: E402,F401  — registers the backup volume's placement rules (Lesson 26)
