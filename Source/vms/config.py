"""The VMS's schema — as a spec the platform's controller runs from
(vms.subsystem.yaml, beside this file). What this module keeps is the
Python view of the same thing, for the worker and the tests:

    vms/cameras/<id>      the row: the spec's fields, plus revision       (the controller writes)
    vms/workers/<worker>  units, rev                                      (the controller writes)
    vms/placement/<id>    worker, reason, at, rev                         (the controller writes)
    vms/retention/<id>    days — derived from events_retention_days       (the console writes, with the row; the resource reads)
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
# - `vms/retention/<id>` — `days`, derived from `events_retention_days` (the console writes it with the camera's
#   row, by its own token — `SpecController.create`/`update`/`delete`; the platform's resource reads it).
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
import re
import time

from w2cplatform.doors import numeric
from w2cplatform.spec import PLATFORM_FIELDS, SubsystemSpec

SPEC = SubsystemSpec.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "vms.subsystem.yaml"))
LIVE_SPEC = SubsystemSpec.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "live.subsystem.yaml"))   # the second subsystem: live fan-outs
DET_SPEC = SubsystemSpec.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "det.subsystem.yaml"))     # the third: detectors
REC_SPEC = SubsystemSpec.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "rec.subsystem.yaml"))     # the fourth: recorders, on the archive
DETJOB_SPEC = SubsystemSpec.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "detjob.subsystem.yaml"))  # the fifth: archive scans, the first work that ends
AUTO_SPEC = SubsystemSpec.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "auto.subsystem.yaml"))  # the sixth: scenarios, the first work that READS what the others wrote
SURVEY_SPEC = SubsystemSpec.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "survey.subsystem.yaml"))  # the sixth: watching an archive we do not own


# A camera as the platform names a unit: `vms/<id>` — and `"*"`, every one, as it is (the boundary's step 2: the
# platform names units `<sub>/<id>` and nothing else; the VMS's own rows and routes name its cameras by id).
def cam_ref(cam) -> str:
    from w2cplatform.doors import unit_ref
    return "*" if str(cam) == "*" else unit_ref(SPEC.name, cam)


# …and back: the camera a reference names, None for a reference to anything else, or no reference at all.
def camera_of_ref(ref) -> str | None:
    from w2cplatform.doors import parse_ref
    got = parse_ref(ref)
    return got[1] if got is not None and got[0] == SPEC.name else None
PLAYBACK_PORT = 8083     # the holder's playback surface: HTTP, because a browser must be able to seek it
LIVE_PORT_BASE = 20000       # a camera's RTP port on its worker's loopback: the RTSP fan-out's one subscriber (gstvms/livesrv.py)
SHM_DIR = "/run/vms"         # the tee's shared-memory branch: <SHM_DIR>/<cam>.shm — a subscriber on the SAME server reads it (shmsrc), no RTSP hop
# The VMS's own paths on the box, beside the platform's (`w2cplatform.runtime`: `/data/platform`, `/etc/w2c`): its
# configuration `/etc/vms` (on an A/B box a link to `/data/vms/etc`), and the server's own volume — a ring of
# ObjectStorage, opened by the host's obsd as `vms-obsd`: the archive engine is the VMS's, so its volumes are under
# `/data/vms/obsd` (the owner, 4 October), and not beside the platform's events archive.
VMS_DATA = "/data/vms"
OWN_VOLUME = f"file://{VMS_DATA}/obsd/volume"   # a recorder with nothing declared (`ARCHIVE_VOLUME` to say another)
RTSP_PORT = 8554             # the worker's RTSP fan-out: rtsp://<server>:8554/<cam> — what a recorder, a gateway, a detector subscribe to


def live_shm(cid, shm_dir: str = SHM_DIR) -> str:
    """The camera's shared-memory socket on its worker's server: the local fast path (shm:// scheme)."""
    return f"shm://{shm_dir}/{cid}.shm"


# ONE DEVICE, ONE SPELLING (the review's eighth pass, major; a run). `device_of` took the address as it was typed, and the
# same recorder under another spelling was another device: `driverpack://ACME/10.0.0.50/ch/2`, `…/10.0.0.50:80/…`,
# `…/10.0.0.50./…` — with `admin` on a file camera of her own, a user moved it onto channel 2 of a recorder whose
# cameras were not hers (`source_cams` found no camera of "that" device), and then pulsed its relay (`device_cams`).
# So the key is canonical: the scheme and the host in lower case, a name's trailing dot gone, an address in the one
# form the resolver dials (`012.0.0.50`, `10.50`, `::ffff:10.0.0.50` are `10.0.0.50`, and `10.0.0.050` is `10.0.0.40`
# — what `inet_aton` and `ipaddress` say they are), the scheme's own port dropped (`DEFAULT_PORTS`), credentials never
# part of it. The row keeps what the
# operator typed; what is compared, grouped and keyed by is this. What syntax cannot say — a DNS name and the address
# it resolves to are one device — the device says itself, once a holder has opened it (`one_device` below).
DEFAULT_PORTS = {"driverpack": 80, "rtsp": 554, "rtsps": 322, "http": 80, "https": 443}   # driverpack: the device's web port


def _host(raw: str, scheme: str) -> str:
    """`host[:port]` in one spelling (`device_of`)."""
    import ipaddress
    import socket
    raw = raw.rsplit("@", 1)[-1]                         # credentials are not the device
    host, port = raw, ""
    if raw.startswith("["):                              # `[v6]` or `[v6]:port`
        end = raw.find("]")
        if end > 0:
            host, port = raw[1:end], (raw[end + 2:] if raw[end + 1:end + 2] == ":" else "")
    elif raw.count(":") == 1:
        host, port = raw.split(":")
    host = host.strip().lower().rstrip(".")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
        if re.fullmatch(r"(0x[0-9a-f]+|[0-9]+)(\.(0x[0-9a-f]+|[0-9]+)){0,3}", host):
            try:
                ip = ipaddress.ip_address(socket.inet_aton(host))   # `012.0.0.50`, `10.50`: what the resolver dials
            except OSError:
                ip = None
    if ip is not None:
        ip = getattr(ip, "ipv4_mapped", None) or ip
        host = str(ip) if ip.version == 4 else f"[{ip}]"
    # By `doors.numeric`, not `isdigit` + `int` (the review's tenth pass, major): `"8²".isdigit()` is true and `int`
    # raises — one camera row whose port held a superscript stopped its holder's every pass and every heartbeat, and the
    # console's every camera creation (one channel, one camera read every row). A port that is no number stays as typed: a key
    # of its own, which no holder will open — that camera's trouble, and a grant on the cluster to point one at it.
    n = numeric(port)
    if n is not None:
        port = "" if n == DEFAULT_PORTS.get(scheme) else str(n)
    return host + (f":{port}" if port else "")


# A `driverpack://` source's vendor and path, without a login a row stored before the refusals put in either (the
# product's r28-secrets2): `driverpack://acme/admin:Hun/ter2@10.0.0.5/ch/1` — a password with a `/` in it — read as
# device `acme/admin:***` with no channel, and `driverpack://admin:…@acme/10.0.0.5/ch/1` as `…@acme/…`: the channels of
# one recorder were two devices. A login ends at the last `@`, in the vendor's place or in the path; the key is the
# host after it. A file's name is a name, `@` and all.
def _vendor_and_path(u) -> tuple[str, list[str]]:
    vendor = u.netloc.rsplit("@", 1)[-1].strip().lower().rstrip(".")
    path = u.path if vendor == "file" else u.path.rsplit("@", 1)[-1]
    return vendor, [p for p in path.split("/") if p]


def device_of(source: str) -> str:
    """The thing DriverPack connects to. Cameras sharing it share one session:
    `driverpack://acme/10.0.0.50/ch/17` and `…/ch/18` are two channels of one NVR;
    a camera with an SD card is a device with one channel. Pure parsing — the
    vendor's own addressing stays opaque, only the grouping is ours — and one
    spelling for one address (`_host`)."""
    from urllib.parse import urlsplit
    from w2cplatform.secrets import SECRET_MASK, hide_in_url
    try:
        u = urlsplit(str(source).strip())
    except ValueError:                                   # `rtsp://[10.0.0.5/…`: "Invalid IPv6 URL" (the tenth pass's sweep)
        return hide_in_url(str(source))                  # not an address anybody can say the device of: as a page says it
    scheme = u.scheme.lower()
    if scheme != "driverpack":
        if not u.netloc:
            return str(source)                           # not an address: a path, a name — as it is
        # …nor are credentials in its parameters (the eleventh review, blocker 4): the key is in the heartbeat, `/devices`
        # and the log, and a row stored before the refusal named its password there.
        return hide_in_url(f"{scheme}://{_host(u.netloc, scheme)}{u.path}" + (f"?{u.query}" if u.query else ""))
    vendor, parts = _vendor_and_path(u)
    if vendor == "file":
        return "file/" + parts[0] if parts else "file"
    # …and the key as a page says an address (the thirteenth review, major 9; a run): what the cuts below leave of a row
    # stored before the refusals is still a credential in the vendor or the host — `acme:hunter2/10.0.0.5` (a password
    # where a port stands), `acme/10.0.0.5&password=hunter2` (a pair) —, and the key is in `POST /requests`,
    # `vms/requests/*`, the heartbeat and `vms/devices/<key>`. A key with none in it is the key it always was.
    said = lambda key: hide_in_url(f"{scheme}://{key}")[len(scheme) + 3:]
    if not parts:
        return said(vendor)
    # The host in the path, without what a row stored before the refusals put around it (the twelfth review's sweep):
    # a login before an `@`, a `;name=value`, a port that is no number — `acme/admin:…@10.0.0.5`, `10.0.0.5;password=…`.
    host = _host(parts[0].rsplit("@", 1)[-1].split(";", 1)[0], scheme)
    head, colon, port = host.rpartition(":")
    if colon and not host.endswith("]") and port and not port.isdigit():
        host = f"{head}:{SECRET_MASK}"
    return said(f"{vendor}/{host}")


# WHAT TWO KEYS ARE ONE DEVICE BY: the key (`device_of`), or — once a holder has opened them — what the device said it
# is (`identity` in its row, `vms/devices/<device>`: a serial number, a MAC; the driver's word). A DNS name and the
# address it resolves to are two keys and one identity. `one_device(vars_)(key)` is a token: equal tokens, one device
# for the rights asked of it. A spelling no holder has opened yet has no identity, and is its key alone until a holder
# opens it (М10B Lesson 15).
#
# A HOLDER'S WORD IS NOT A REFUSAL, AND NOT KNOWING IS A GRANT ON THE CLUSTER (the owner's decisions on the review's
# ninth pass). An identity is the driver's word, and firmware clones say the same serial number: the holder that finds
# its device's identity under another key says so and goes on (`VmsWorker.describe_devices`), it refuses nothing. So
# the bypass the eighth pass closed at the holder is closed here, where rights are asked: a camera moved onto a device
# no holder has learned the identity of — a DNS name, a spelling nothing reads as one (`010.000.000.050`, full-width
# digits), any key in the course's build, which has no device factory — needs a grant on the whole cluster
# (`vms/console.py`, `source_cams`), until a holder opens the device and says what it is. The identity groups devices
# for rights only, where two devices taken for one ask for MORE: a camera is still one channel of ONE key (the holder's
# «device busy», `VmsWorker.held_back`), so two clones' cameras are two cameras.
#
# …and across vendors: the token is the identity alone (the review's ninth pass, (д)) — one recorder under two drivers
# is one recorder, and two vendors' equal strings only ask for more.
def device_identities(vars_) -> dict[str, str]:
    prefix = SPEC.sub.config(DEVICES, "")
    out = {}
    for path in vars_.list(prefix):
        items, _ = vars_.get(path)
        ident = str((items or {}).get("identity") or "").strip()
        if ident:
            out[path[len(prefix):]] = ident
    return out


# READ BY KEY, ONCE (the review's ninth pass, minor; a count): `one_device` read every device row there is on every
# command, every move and every scenario edit — rows are never removed, and 1000 of them were 1009 reads for one press
# of a relay (in М11, a thousand reads through the store's leader). It reads the row of a device it is asked about, the first time it
# is asked, and nothing else: one instance per request, so what it says is the store's at that request.
#
# KNOWN IS NOW, NOT ONCE (the review's tenth pass, major; a run). A row says what the device under that key WAS when a
# holder last held it, and rows are never removed: `nvr50.local`, a recorder replaced since, its cameras deleted, kept
# its row `SN-OLD`; the name led to the new recorder, which the configuration holds by its address — and `admin` on
# camera 3 pointed it at `nvr50.local/ch/2` (200: "known"), the holder opened the new recorder, and camera 3 showed and
# recorded a channel of a recorder that was not hers. So a key is known while a holder that is alive HOLDS that device
# and has heard it describe itself in this process (`can` in its heartbeat's `devices`, `VmsWorker.device_status`):
# what that holder hears, it writes into the row in the same pass (`describe_devices`). A row nobody holds now is
# the past — a grant on the cluster again, as for a key nobody has opened. The heartbeats are read once a request, at
# the first `known` (`objects`; without them nothing is known).
#
# …AND "ALIVE" IS WHAT THE CONSOLE SAW CHANGE (the product's r29-writers2): the holders were judged by their `ts`
# against the console's clock — a holder dead an hour whose clock ran ahead kept its devices "known", and a box 100 s
# behind made every device it holds unknown, a grant on the cluster to move a camera within it. `eyes` — the console's
# long-lived `Eyes` — judge them (`holders(eyes=)`); without them, `is_live`.
class Devices:
    def __init__(self, vars_, objects=None, now=None, eyes=None):
        self.vars, self.ids = vars_, {}
        self.objects, self.now, self.eyes = objects, now, eyes
        self._held: set[str] | None = None

    def identity(self, key: str) -> str:
        if key not in self.ids:
            items, _ = self.vars.get(SPEC.sub.config(DEVICES, key))
            self.ids[key] = str((items or {}).get("identity") or "").strip() if isinstance(items, dict) else ""
        return self.ids[key]

    def held(self) -> set[str]:
        """The devices live holders hold and have heard describe themselves, by their heartbeats."""
        if self._held is None:
            self._held = set()
            if self.objects is not None:
                from w2cplatform.console import holders
                now = self.now() if callable(self.now) else (time.time() if self.now is None else self.now)
                for hb in holders(self.objects, SPEC.sub.name + "/", now, eyes=self.eyes).values():
                    devs = hb.extra.get("devices")
                    for d in devs if isinstance(devs, list) else ():
                        if isinstance(d, dict) and isinstance(d.get("device"), str) and d.get("can"):
                            self._held.add(d["device"])
        return self._held

    def known(self, key: str) -> bool:
        """Whether a live holder holds the device under this key now and has learned what it is."""
        return bool(self.identity(key)) and key in self.held()

    def __call__(self, key: str) -> tuple:
        ident = self.identity(key)
        return ("id", ident) if ident else ("at", key)


def one_device(vars_, objects=None, now=None, eyes=None) -> Devices:
    return Devices(vars_, objects, now, eyes)


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
# …and the same for objects: its heartbeat, and the marks it leaves before it calls a device (`vms/commands/<id>`,
# written and — when the request is gone — removed; `VmsWorker.requests`).
WORKER_OBJECTS = SPEC.sub.acl_objects_worker() + [f"{SPEC.name}/commands/*"]


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


def device_row(desc: dict, identity: str = "") -> dict:
    """The description as a row: strings, a list comma-joined — the store's shape (М10A Lesson 9). And what the device
    says it IS, when it says (`identity_of`): not a capability — it is not in `can`, it does not leave the cluster —
    but what the console tells two spellings of one device apart by (`one_device`)."""
    return {"events": ",".join(desc["events"]), "rays": str(desc["rays"]), "relays": str(desc["relays"]),
            "ptz": "true" if desc["ptz"] else "false", "presets": str(desc["presets"]),
            **({"identity": identity} if identity else {})}


# The device's own word for which device it is — `capabilities()["identity"]`: a serial number, a MAC, whatever the
# driver reads from the hardware. "" when it says nothing; a driver that cannot read one leaves its spellings to
# `device_of` alone.
def identity_of(caps: dict | None) -> str:
    return str((caps or {}).get("identity") or "").strip()[:200]


def parse_device_row(items: dict | None) -> dict | None:
    if not items:
        return None
    # The counts through `rows.number` (the review's seventh pass): a word in one device's row raised out of the
    # evaluator's whole pass (`Catalog.check`) and out of the scenario catalogue page. Not said, none.
    from w2cplatform.rows import number
    n = lambda f: number(f"vms/devices#{f}", items.get(f) or 0, int, 0)
    return {"events": [e for e in str(items.get("events", "")).split(",") if e],
            "rays": n("rays"), "relays": n("relays"), "ptz": str(items.get("ptz")) == "true", "presets": n("presets")}


def channel_of(source: str) -> str | None:
    """`driverpack://<vendor>/<host>/ch/<n>` -> "<n>"; None when the device has one channel."""
    from urllib.parse import urlsplit
    try:
        u = urlsplit(str(source))                        # `str` as `channel_key` and `device_of` read it: `5` raised here
    except ValueError:                                   # not a URL at all (`[` with no `]`): no channel to name
        return None
    vendor, parts = _vendor_and_path(u)                 # a login stored in the path is not the host (r28-secrets2)
    return parts[2] if vendor != "file" and len(parts) >= 3 and parts[1] == "ch" else None


# …and the channel as two sources are COMPARED by (the eighth pass's sibling of `device_of`): `…/ch/02` and `…/ch/2`,
# `…/CH/2` are one channel. Not what the driver is handed — that is the row's `source`, as typed. By `doors.numeric`
# (the review's tenth pass): `…/ch/①` is a channel named `①`, not a `ValueError` out of every reader of every row.
def channel_key(source: str) -> str:
    from urllib.parse import urlsplit
    try:
        u = urlsplit(str(source).strip())
    except ValueError:
        return ""
    vendor, parts = _vendor_and_path(u) if u.scheme.lower() == "driverpack" else ("", [p for p in u.path.split("/") if p])
    if vendor == "file" or u.netloc.lower() == "file" or len(parts) < 3 or parts[1].lower() != "ch":
        return ""
    n = numeric(parts[2])
    return str(n) if n is not None else parts[2]


# WHAT A NEW SOURCE MAY NOT BE (the review's tenth pass, major; the product team's sibling): a camera created or moved
# with a `source` nobody can read the device or the channel of — a port or a channel written in digits that are not
# ASCII 0–9 (`8²`, `①`, full width: `isdigit` says yes to all), a port past 65535, a host in a `[` with no `]` — was
# 200, and the row then stood in every reader. What is no address by RFC 3986 the platform refuses at the door; what
# only the VMS reads — a channel in digits that are not 0–9, a `?` in a `driverpack://` address — its holder does not
# dial and says why (`VmsWorker.held_back`; the boundary's step 6). A row stored with one is read as a key of its own by
# every parser above, and is that camera's trouble alone. None: the source may stand.
#
# …AND NO PASSWORD IN ITS WORDS (the product team's addition to the tenth round): the refusal repeated the source as
# typed, `driverpack://acme/u:hunter2@10.0.0.5:8²/…` and all, into the reply and the journal's detail. What is said is
# the source with whatever stands before an `@` hidden (`shown_source`) — and, since the eleventh review (blocker 4), the
# value of every credential parameter (`secrets.hide_in_url`: `?usr=…&pwd=…`). Since the thirteenth (major 8) the
# refusal says no address at all: `driverpack://acme/admin:Hunter2/ch/1` has its host in the path, where the hiding did
# not look, and the reply quoted the password as "the port"; what is wrong is said, the source is the caller's own and
# `shown_source` is for the log. And a `?` in a `driverpack://` source
# is refused here as `SubsystemSpec.refuse` refuses a `#`: `urlsplit` ends the path there, and `acme/cam7?@nvr50/ch/1`
# is device `cam7` to the rights and maybe `nvr50` to a driver that reads the whole string.
def shown_source(source: str) -> str:
    """The source as a refusal or a log may say it: what stands before an `@` hidden, and every credential parameter."""
    from w2cplatform.secrets import hide_in_url, hide_logins
    s = hide_logins(str(source))                     # anchored: one scan, whatever its length (the eleventh review)
    return hide_in_url(s) if "://" in s else s


def source_refusal(source: str) -> str | None:
    from urllib.parse import urlsplit
    src = str(source or "").strip()
    try:
        u = urlsplit(src)
    except ValueError:                                   # its words quote the host, a login and all (the twelfth review)
        from w2cplatform.secrets import NOT_AN_ADDRESS
        return f"the source is not an address: {NOT_AN_ADDRESS}"
    host = u.netloc
    if u.scheme.lower() == "driverpack":
        parts = [p for p in u.path.split("/") if p]
        if u.netloc.lower() == "file":
            return None                                  # a file's name, as typed: `gstvms.uri` asks the rest
        if "?" in src:
            return "the source holds '?': a device's address is vendor/host/ch/n, and what follows a '?' could name another host"
        host = parts[0] if parts else ""
        if len(parts) >= 3 and parts[1].lower() == "ch" and any(c.isdigit() and not "0" <= c <= "9" for c in parts[2]):
            return "the channel of the source is written in digits that are not 0–9: write it in plain digits"
    host = host.rsplit("@", 1)[-1]
    port = host[host.rfind("]") + 2:] if host.startswith("[") and "]:" in host else (host.split(":")[1] if host.count(":") == 1 else "")
    if port and (numeric(port) is None or not 0 < numeric(port) <= 65535):
        return "the port of the source is not a port: a number from 1 to 65535, in plain digits"
    return None


# How a holder says a request it answered, in its heartbeat's `fetched` (`VmsWorker.fetched_said`), and how the console
# matches it (`jobs.clear_requests`): the id itself when it is short and plain; else `#` and a digest of it — an id of
# 200 characters, or one with a comma (the list's separator), a quote or a control character in it, costs 21 bytes
# like any other (the review's eighth pass).
# The longest a command's argument may be — `port`, `state`, `pulse_ms`, `n`: a number or a word (the product's
# cross-check of the eleventh review: an argument had no size). The console refuses longer at its door
# (`vms/console.py`, `file_request`), the holder refuses a row that holds one anyway (`VmsWorker.perform`).
COMMAND_ARG_MAX = 32


def said_id(rid: str) -> str:
    rid = str(rid)
    if len(rid) <= 40 and not rid.startswith("#") and rid.isprintable() and not any(c in rid for c in ',"\\'):
        return rid
    import hashlib
    return "#" + hashlib.sha256(rid.encode()).hexdigest()[:20]


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


# THE DOORS ARE SHUT UNTIL SOMEBODY OPENS THEM, AND A DOOR ANNOUNCES WHAT IT BOUND (the platform review, blocker
# 1; the product's step 0, feedback BP).
#
# Nothing in this module checks who is calling — there is no authentication below М12, and that is a decision
# written down in `module-design.md`, not an oversight. What stood between a camera's live stream and anybody
# on the network was the address a door listened on, and two of them listened on every interface by default:
# the RTSP fan-out and the door to a device's own archive. They bind to loopback now. Opening one to the
# network is a setting somebody makes (`RTSP_HOST`, `PLAYBACK_HOST`), and the process says in its log that the
# door is open and asks nobody who they are.
#
# The second half is what makes the first one work. A door's address is ANNOUNCED — `live_url`, `playback_url`
# in the heartbeat — and it was always the server's name. A door bound to loopback and announced under the
# server's name is unreachable wherever that name resolves to a network address: the subscriber goes to an
# address nobody listens on. So: loopback if bound to loopback, else the server's name. And a subscriber on
# ANOTHER server that reads a loopback address knows it is not for it (`local_only`) — it does not go and
# knock on its own machine.
LOOPBACK = "127.0.0.1"


# Loopback by what the address IS, not by how it is written (the eighth pass's sweep of spellings): `LOCALHOST`,
# `localhost.`, `::ffff:127.0.0.1`, `0:0:0:0:0:0:0:1` were "beyond loopback" and announced under the server's name.
def is_loopback(host: str) -> bool:
    import ipaddress
    h = str(host or "").strip().lower().rstrip(".")
    h = h[1:-1] if h.startswith("[") and h.endswith("]") else h
    if h == "localhost" or h.endswith(".localhost"):
        return True
    try:
        ip = ipaddress.ip_address(h.split("%", 1)[0])
    except ValueError:
        return False
    return (getattr(ip, "ipv4_mapped", None) or ip).is_loopback


def announce_host(bound: str | None, server: str) -> str:
    """What a door bound to `bound` on `server` says its address is. `None` — the worker was not told what its
    door is bound to (it does not bind the fan-out itself: the actuator does) — is the server's name, as it
    always was; the PROCESS is what says loopback (`__main__`)."""
    return LOOPBACK if bound is not None and is_loopback(bound) else server


def local_only(url: str, holder_server: str, my_server: str) -> bool:
    """The address is a loopback one on another machine: announced truthfully, and not reachable from here."""
    from urllib.parse import urlsplit
    return holder_server != my_server and is_loopback(urlsplit(url).hostname or "")


def opened_beyond_loopback(what: str, host: str, log, asks: str = "") -> None:
    """Said once, at start, for a door bound beyond loopback. `asks`: what the door DOES check, when it checks
    something (the device's playback door: a console-signed address, in a gated cluster) — said instead of
    "asks nobody", which would then be untrue."""
    if not is_loopback(host):
        if asks:
            log.warning("%s is open on %s; it asks %s", what, host, asks)
        else:
            log.warning("%s is open on %s and asks nobody who they are: there is no authentication at this door — "
                        "it is for a network that is already closed", what, host)


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
