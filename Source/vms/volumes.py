"""The archives a recording may be written into: `rec/volumes/<name>`, the
administrator's list, and the claim that makes one of them served."""
# ================================================================================================
# NOTES — what every part of this file does and why (kept beside the code, not in a separate document)
# ================================================================================================
# # volumes.py — a volume is a PLACE, declared by the operator and served by whoever takes it
#
# **Role in the module.** Until now the archives a box could write into were deployment: a directory per
# disk, an `RESOURCE_ROOT` in the unit file, an instance per volume. That works while a volume is a disk somebody
# screwed into a rack. It stops working the day a volume is a bucket: the operator creates it in the
# console, and nobody is going to edit a systemd unit for it.
#
# So a volume becomes a row — `rec/volumes/<name>`, the `tables:` grant of `rec.subsystem.yaml` — and a
# **place** in the sense placement already means (`place_by: volume`). The row is a DECLARATION: it says
# this archive should be written into. It does not say by whom, and it cannot: the row is written on a
# console, and which process serves it is a fact about the cluster at this second.
#
# That fact is a `hold` (`w2cplatform.contract`): `rec/holds/<volume>`, the same row and the same
# CAS-with-a-lease rule as a worker's slot. A recorder with no `VOLUME` pinned takes a free volume it may
# serve and becomes that volume's recorder; it renews while it runs; it lets go on an orderly stop; and if
# it dies the hold lapses and the next free recorder picks the volume up. Nobody assigns, nobody starts a
# process: the controller places recordings on the places that exist, and a place exists because somebody
# is holding it.
#
# **Who may serve what.** A local volume is a disk: only a recorder ON ITS SERVER can write to it. A
# network volume is an address: any box can, and exactly one does, because `servers: distinct` over
# `place_by: volume` means one recorder per place. That asymmetry is the whole reason `server` is a field
# here and empty for the network kind — and it is why one spare per box absorbs one NETWORK volume per
# box, not one per cluster: the spare that takes it may be anywhere.
#
# **Why `quota_bytes` and not free space.** It is the SIZE of the volume: the engine formats it as a ring of
# that many bytes, and the ring gives up its oldest minutes when it is full. `statvfs` on a bucket answers
# about the machine, not the bucket, so the number has to be given; and on a disk it is what lets one
# partition hold two volumes.
#
# **What is NOT here.** No mounting, no credentials handling beyond the `*_secret` suffix (the row names
# the key; `secrets.py` keeps it out of every reply), and no uploading: what turns a path into a bucket
# belongs to the archive, not to the list of archives.
#
# ## Public API
# - `Volume` — one row, as a frozen dataclass; `key(name)`, `refuse(fields)`, `write(vars_, fields)`,
#   `delete(vars_, name)`.
# - `declared(vars_, garbled=None)` — every volume row that parses, enabled and not; `read_volume` — one row, through
#   the one reader of rows (`VOLUMES`, `w2cplatform.rows`).
# - `servable(vols, server)` — the names a recorder on `server` may take, best first: its own disks, then
#   the network archives anybody may serve.
# - `holders(vars_, sub)` — `{volume: Slot}`: who is serving what, for the console.
# - `served(vars_, sub, now, lost_after)` — the console's view: every declared volume, its holder or None.
# ================================================================================================
from dataclasses import dataclass

from w2cplatform.contract import HOLDS, Slot, Subsystem, read_hold
from w2cplatform.rows import FIELDS as NUMBERS, PARSE_ERRORS, Table, number
from w2cplatform.secrets import hide_in_url, is_secret_field
from w2cplatform.spec import Refused

SUB = "rec"
TABLE = "volumes"
KINDS = ("local", "network", "backup", "edge", "incidents")
FIELDS = ("kind", "url", "server", "quota_bytes", "access_key", "access_secret", "enabled", "shrink_confirmed", "cam")


# The kinds that are a disk on ONE box, named in `server`. A backup volume is one when it names a server — the
# disk of a second server — and an ADDRESS any box may serve when it does not, like a network volume: a second
# storage somewhere else, which is as independent of the primary's server as a second disk is. An EDGE volume
# is the card in a camera that runs the platform: always one box, the camera itself. An INCIDENTS volume —
# where kept footage is copied to (`RecWorker.keep_pass`) — is either, like a backup one.
#
# THE CARD IS A PLACE, NOT A VOLUME OF THE ENGINE (the product's camera: its design note §12 and §14; feedback CB,
# DG). Declared here like the others — placement needs a place, the gate needs to know a recording is a standby —
# and written as nothing else is: by the camera's own recorder, as plain segment files with a byte budget
# (`vms/card.py`, `CardBuffer`), never mounted through obsd. A camera has 32 MB of memory where the engine wants
# 20–25 for a writer. `quota_bytes` is the card's budget, `url` its directory on the camera. An engine on a camera —
# a NAS, a mini-disk — would be a `local` or `network` volume like a server's, not `edge`; the course does not build it.
def on_a_box(v: "Volume") -> bool:
    return v.kind in ("local", "edge") or (v.kind in ("backup", "incidents") and bool(v.server))


def any_box(v: "Volume") -> bool:
    return v.kind == "network" or (v.kind in ("backup", "incidents") and not v.server)


@dataclass(frozen=True)
class Volume:
    """One declared archive. `url` is a directory for a local volume and an
    address for a network one; `quota_bytes` is its size — the ring the engine
    formats it as."""
    name: str
    kind: str = "local"
    url: str = ""
    server: str = ""              # local: whose disk. network: empty — any box may serve it
    quota_bytes: int = 0
    access_secret: str = ""       # the `*_secret` suffix: never handed back by a console
    enabled: bool = True
    access_key: str = ""          # a bucket's key ID — which key, not the key: shown, like a camera's login
    # A quota SMALLER than the size the volume has erases its oldest footage when applied, so the recorder applies it
    # only when this says the same number — the operator's second word (`RecWorker._apply_quota`; the review's third
    # pass). Absent, the ring keeps its size and the heartbeat says why.
    shrink_confirmed: int = 0
    # An edge volume is the card IN a camera, and says which: the camera's id in this cluster's `vms/cameras`. A
    # recording is homed on a card only if it is that camera's (`must_match` on `home`): the card's recorder writes the
    # frames of its own camera's ring, whatever the recording's row says (the review's sixth pass, major).
    cam: str = ""

    @classmethod
    def from_items(cls, name: str, items: dict | None) -> "Volume":
        d = items or {}
        return cls(name, str(d.get("kind", "local")), str(d.get("url", "")), str(d.get("server", "")),
                   int(d.get("quota_bytes", 0) or 0), str(d.get("access_secret", "")),
                   str(d.get("enabled", "true")) != "false", access_key=str(d.get("access_key", "")),
                   shrink_confirmed=int(d.get("shrink_confirmed", 0) or 0), cam=str(d.get("cam", "") or ""))

    def to_items(self) -> dict:
        return {"kind": self.kind, "url": self.url, "server": self.server,
                "quota_bytes": self.quota_bytes, "access_secret": self.access_secret, "access_key": self.access_key,
                "enabled": "true" if self.enabled else "false",
                **({"shrink_confirmed": self.shrink_confirmed} if self.shrink_confirmed else {}),
                **({"cam": self.cam} if self.cam else {}),
                # the word the platform's placement reads (`affinity`): an incidents volume takes no recording
                **({"admits": "false"} if self.kind == "incidents" else {})}


def key(name: str) -> str:
    return f"{SUB}/{TABLE}/{name}"


# DECLARED BY THE PLATFORM'S RULES (the boundary's step 6). What a volume row may be — a name, a kind of five, a local
# disk naming its server, a network one naming none, a card in one camera saying which and holding no key, a size, an
# address that never carries the key to it, a key kept only for the address it was given for, an incidents volume that
# admits nobody — is `tables.volumes` in rec.subsystem.yaml, and the platform's console writes it (`tables.write_row`).
# The rules were here (`refuse`, `_kept_key`), called by the VMS's route on the console. This is the same write for the
# VMS's own code that declares one (a camera declaring its card: `card.py`) — one set of rules, the spec's.
def write(vars_, fields: dict, sealer=None) -> Volume:
    """Declare a volume, or declare it again — by the spec's rules. `sealer`: the key that seals `access_secret`."""
    from w2cplatform.tables import write_row
    from .config import REC_SPEC
    if str(fields.get("kind", "")) == "incidents":
        fields = {"admits": False, **fields}          # a place for what somebody kept: it admits no recording (`affinity`)
    name, items = write_row(REC_SPEC, TABLE, vars_, fields, "", 0.0, sealer, lambda: _recordings(vars_))
    return Volume.from_items(name, items)


def _recordings(vars_) -> list[dict]:
    out = []
    for path in vars_.list(f"{SUB}/recordings/"):
        row, _ = vars_.get(path)
        if row and row.get("deleted") != "true":
            out.append({**row, "id": path.rsplit("/", 1)[1]})
    return out


def delete(vars_, name: str) -> None:
    from w2cplatform.tables import delete_row
    from .config import REC_SPEC
    delete_row(REC_SPEC, TABLE, vars_, name)


# A VOLUME ROW THAT DOES NOT PARSE IS THAT VOLUME'S TROUBLE (the review's seventh pass, part 2, blocker 1). `quota_bytes:
# "1e12"` or `"64M"` in ONE row — written by hand, or by an older build — raised out of `declared`, and `declared` is
# under every recorder's lease step (`RecWorker.volume_pass`), the console's page of volumes, a camera card's look at
# its card and the scan's list of disabled volumes: every recorder of the cluster stopped heartbeating, because the
# step and the heartbeat shared a `try`. The row is skipped where volumes are listed, counted once until it parses
# again (`volumes_garbled` in a recorder's heartbeat, `rec_worker_volumes_garbled` and `rec_console_rows_garbled` on
# `/metrics`), logged once — and named: `declared(garbled=…)` collects the names for whoever must not read the
# absence as "withdrawn" (the volumes page says the row does not parse; the recorder that holds it keeps it by the row
# it read last).
VOLUMES = Table("volume", "skipped — not offered, not taken, not withdrawn from whoever holds it, until it is mended")


def read_volume(name: str, items) -> "Volume | None":
    """One declared volume, or None when its row does not parse — counted once, logged once."""
    return VOLUMES.read(key(name), lambda: Volume.from_items(name, items))


def declared(vars_, garbled: set | None = None) -> list[Volume]:
    """Every declared volume whose row parses, in name order. Includes the disabled ones: the console shows them, and
    `servable` is what filters. The names of rows that do not parse go into `garbled`, when the caller gives one."""
    out = []
    for path in sorted(vars_.list(f"{SUB}/{TABLE}/")):
        name = path[len(f"{SUB}/{TABLE}/"):]
        try:
            items, _ = vars_.get(path)                  # a file store's row that is not even JSON raises in the read itself
        except PARSE_ERRORS as e:
            VOLUMES.garbled(path, e)
            items = None
            if garbled is not None:
                garbled.add(name)
        if items:
            vol = read_volume(name, items)
            if vol is not None:
                out.append(vol)
            elif garbled is not None:
                garbled.add(name)
    return out


# What a recorder on this server may take, and in what order. Its own disks first — a local volume has
# exactly one server that can serve it, so leaving it for later risks a spare elsewhere never being able
# to help — then the network archives, which anybody can take and which are therefore the ones a spare is
# for. Disabled volumes are nobody's: the administrator turned them off.
def servable(vols: list[Volume], server: str) -> list[str]:
    mine = [v.name for v in vols if v.enabled and on_a_box(v) and v.server == server]
    net = [v.name for v in vols if v.enabled and any_box(v)]
    return mine + net


# What to offer an operator who has never declared anything. Every server whose recorder says which
# archive root it writes into, and whose resource says how big that filesystem is, and for which no local
# volume is declared yet: one proposal, named after the server, sized to the partition. A PROPOSAL and not
# a row — nothing here writes configuration on a process's behalf. The operator presses the button, and
# from that moment the disk is a volume with a number on it, which is the whole point: the number can be
# made smaller, and a second volume can have the rest.
#
# Who is live — here and in `served`'s three readers below — by what the asker saw CHANGE (`eyes`, its long-lived
# `Eyes`; the product's r29-writers2): `now - hb.ts` was the recorder's clock against the console's, with no bound ahead.
# Without eyes, `is_live` (bounded both ways). A hold is live likewise: renewed within a slot's term of the asker's clock,
# not before the `until` its holder's clock wrote (`_hold_live`).
def suggest(vars_, objects, sub: Subsystem, now: float, lost_after: float = 45.0, eyes=None) -> list[dict]:
    from w2cplatform.console import heard_live, heartbeats
    from w2cplatform.resource import resources_seen, space_total
    have = {v.server for v in declared(vars_) if on_a_box(v)}
    res = resources_seen(objects)
    out = {}
    for name, hb in heartbeats(objects, sub.name + "/").items():
        server, root = str(hb.extra.get("server", "")), str(hb.extra.get("archive", ""))
        if not server or not root or server in have or not heard_live(sub.name, name, hb, now, lost_after, eyes):
            continue
        # The size the volume HAS, from the recorder that formatted it — not the whole partition, which it shares
        # with the resource's events: declared at the partition's size, the ring would be resized past the room.
        # Through `rows.number` (the review's seventh pass): a word in one recorder's `archive_quota` raised out of the
        # whole page of volumes. Not said, the partition's size; neither said, 0, as before.
        total = number(f"{sub.heartbeat_key(name)}#archive_quota", hb.extra.get("archive_quota") or None, int, None) or \
            space_total(res, server)                     # the platform's reading of its resource (the boundary's step 5)
        out[server] = {"name": server, "kind": "local", "url": root, "server": server, "quota_bytes": total,
                       "why": "this box records here and the disk is not declared as a volume"}
    return [out[k] for k in sorted(out)]


def holders(vars_, sub: Subsystem, garbled: set | None = None) -> dict[str, Slot]:
    """`{volume: Slot}` from `rec/holds/*` — who took what, lapsed holds included. A row that does not parse is not
    in it (`contract.read_hold`: one garbled hold failed the whole list — the review's sixth pass); its volume's name
    goes into `garbled`, when the caller gives one."""
    out = {}
    prefix = f"{sub.name}/holds/"
    for path in sorted(vars_.list(prefix)):
        name = path[len(prefix):]
        try:
            items, _ = vars_.get(path)                  # a file store's row that is not even JSON raises in the read itself
            slot = read_hold(path, name, items)
        except PARSE_ERRORS as e:
            HOLDS.garbled(path, e)
            slot = None
        if slot is not None:
            out[name] = slot
        elif garbled is not None:
            garbled.add(name)
    return out


# The console's answer to "what archives are there, and is anybody writing into them". A volume whose
# hold is lapsed or released reads as UNSERVED, with the reason — that is the state an operator has to
# see, because `home: <that volume>` is a preference and would otherwise put the footage somewhere else
# without a word. `wanted`/`serving` is the same arithmetic one line up: how many processes the declared
# list needs, and how many of them exist.
def _hold_live(sub: Subsystem, name: str, slot, now: float, eyes) -> bool:
    if slot is None or slot.released or slot.holder == "":
        return False
    if eyes is None:
        return now <= slot.until
    from w2cplatform.contract import SLOT_TERM
    return eyes.age(sub.hold_key(name), (slot.holder, slot.until, slot.gen)) <= SLOT_TERM


def served(vars_, sub: Subsystem, now: float, lost_after: float = 45.0, objects=None, eyes=None) -> dict:
    garbled, unread = set(), set()
    vols, held = declared(vars_, unread), holders(vars_, sub, garbled)
    broken = _unwritable(objects, sub, now, lost_after, eyes) if objects is not None else {}
    writing = _writing(objects, sub, now, lost_after, eyes) if objects is not None else {}
    refusing = _refusing(objects, sub, now, lost_after, eyes) if objects is not None else {}
    rows = []
    for v in vols:
        slot = held.get(v.name)
        live = _hold_live(sub, v.name, slot, now, eyes)
        err = broken.get(v.name) if live else None
        # The rule at the source — and the url as a page may say it (`hide_in_url`; the twelfth review, major 15): a row
        # declared before `refuse` saw `?X-Amz-Credential=…`, `?secret=…` or `KEY:SECRET@` stood on `/volumes` as stored.
        row = {k: hide_in_url(x) for k, x in v.to_items().items() if not is_secret_field(k)}
        why = (None if live and not err else
               f"held by {slot.holder}, which cannot write there: {err}" if err else
               "disabled by the administrator" if not v.enabled else
               f"its hold row ({sub.name}/holds/{v.name}) does not parse, so no recorder can take it: mend the row or "
               f"delete it" if v.name in garbled else
               "declared, and no recorder has taken it" if slot is None or slot.holder == "" else
               "the recorder that held it let go" if slot.released else
               "the recorder that held it went silent")
        if why and v.enabled and not err and v.name in refusing:
            why += "; " + "; ".join(refusing[v.name])   # …and the recorders that will not take it say why not
        rows.append({**row, "name": v.name, "served_by": slot.holder if live and not err else None,
                     "writing": writing.get(v.name) if live and not err else None, "why": why})
    # A declaration whose row does not parse is on the page as what it is — named, with what to do — and counted as
    # wanted: somebody declared it, and nobody can tell whether it is enabled. Its holder, if a recorder still holds
    # it, is shown; it writes by the row it read last (`RecWorker.volume_pass`).
    for name in sorted(unread):
        slot = held.get(name)
        live = _hold_live(sub, name, slot, now, eyes)
        rows.append({"name": name, "served_by": slot.holder if live else None, "writing": None, "garbled": True,
                     "why": f"its row ({key(name)}) does not parse, so no recorder takes it and the console cannot show "
                            f"it: mend the row — declare the volume again — or delete it"
                            + (f"; {slot.holder} still holds it and writes by the row it read last" if live else "")})
    rows.sort(key=lambda r: r["name"])
    wanted = len([v for v in vols if v.enabled]) + len(unread)
    return {"volumes": rows, "wanted": wanted, "serving": len([r for r in rows if r["served_by"]])}


# `{volume: why}` for the volumes a live recorder is holding and cannot write into.
#
# This is the third state, and it exists because the first two hid the worst failure there is. A hold is
# fresh, so the console counted the volume served; no footage was being written; every number on the
# screen was green. A declaration can name a path that is not there, a mount that went away or a bucket
# nobody can reach, and none of that is visible in the row — only the process that opened it knows, so
# the process says so (`volume_error` in its heartbeat) and this reads it.
def _unwritable(objects, sub: Subsystem, now: float, lost_after: float, eyes=None) -> dict[str, str]:
    from w2cplatform.console import heard_live, heartbeats
    out = {}
    for name, hb in heartbeats(objects, sub.name + "/").items():
        if not heard_live(sub.name, name, hb, now, lost_after, eyes):
            continue                                    # a silent recorder's last word is not news about a volume
        vol, err = str(hb.extra.get("volume", "")), str(hb.extra.get("volume_error", ""))
        if vol and err:
            out[vol] = err
    return out



# `{volume: ["<recorder> does not take it: <why>"]}` for the volumes a live recorder REFUSES — handed back for
# refusing writes, given up for an engine that stopped answering, or not taken at all because its host's engine cannot
# serve it safely (`refused` in the recorder's heartbeat; the review's sixth pass). An unserved volume used to read
# "no recorder has taken it" and nothing more, with the reason only in a heartbeat's JSON.
def _refusing(objects, sub: Subsystem, now: float, lost_after: float, eyes=None) -> dict[str, list[str]]:
    from w2cplatform.console import heard_live, heartbeats
    out: dict[str, list[str]] = {}
    for name, hb in sorted(heartbeats(objects, sub.name + "/").items()):
        if not heard_live(sub.name, name, hb, now, lost_after, eyes):
            continue
        refused = hb.extra.get("refused")
        for vol, why in sorted((refused if isinstance(refused, dict) else {}).items()):
            out.setdefault(str(vol), []).append(f"{name} does not take it: {why}")
    return out


# `{volume: what the console says}` for the volumes whose live holder reports its writer stuck or losing
# (Lesson 10, feedback U). Served, and not writing well: a different sentence from "cannot write there".
def _writing(objects, sub: Subsystem, now: float, lost_after: float, eyes=None) -> dict[str, str]:
    from w2cplatform.console import heard_live, heartbeats
    from .writerwatch import describe
    out = {}
    for name, hb in heartbeats(objects, sub.name + "/").items():
        if not heard_live(sub.name, name, hb, now, lost_after, eyes):
            continue
        try:                                            # one recorder's `writer` that is not what it says: that recorder's
            vol, said = str(hb.extra.get("volume", "")), describe(hb.extra.get("writer") or {})
        except PARSE_ERRORS as e:
            NUMBERS.garbled(f"{sub.heartbeat_key(name)}#writer", e)
            continue
        if vol and said:
            out[vol] = said
    return out


# -- the standby archives (М10B Lesson 26) ------------------------------------------------------------
# Two kinds of volume hold a second recording of a camera, and the primary closes its gaps from either — a link
# that dropped, the seconds its recorder took to move — the way Lesson 16 closes them from a device's archive,
# except that this archive is OURS: a recording, in a volume, served by a recorder's door.
#
#     edge     the card in the camera itself. Written by the camera's own recorder from its own ring: no
#              network between them, so it records whatever the network does. Not a volume of the engine — the
#              camera's buffer of plain files (`vms/card.py`); read by ASKING the camera for a range
#              (`RecWorker.card_range`), never through a door
#     backup   a second server's disk (or an address). Its stream comes over the network — and a camera that
#              pushes sends it there only when its primary does not take it (М11 lesson 1, М12 lesson 16)
#
# Inside a cluster they are the same rules — a filter for placement, `when: offline`, a source for the primary
# — so everything here takes both. They are named apart because across clusters they behave apart, and because
# they are written and read apart: the engine and a door for a backup, the card's buffer and a range answer for an edge.
STANDBY = ("backup", "edge")


def backups(vars_) -> set[str]:
    """The names of the enabled standby volumes — backup and edge."""
    return {v.name for v in declared(vars_) if v.kind in STANDBY and v.enabled}


# -- where kept footage goes (feedback BH; the product's design) -----------------------------------------------
# A volume is a ring, and a ring cannot spare a range: what somebody said to KEEP is overwritten with the rest
# when its turn comes. So a keep is not a flag on footage in place — it is a COPY, into a volume of its own kind,
# `incidents`, which only keeps go into. The recorder that holds it copies every keep's minutes out of whichever
# recorder's door holds them (`RecWorker.keep_pass`), and nothing is ever recorded into it: it is a place for
# evidence, not a place to put a camera (`admits: false` in its row, read by the platform's `affinity`).
def incidents(vars_) -> set[str]:
    """The names of the enabled incidents volumes."""
    return {v.name for v in declared(vars_) if v.kind == "incidents" and v.enabled}


def edges(vars_) -> set[str]:
    """The names of the enabled edge volumes — cards in cameras."""
    return {v.name for v in declared(vars_) if v.kind == "edge" and v.enabled}


def is_backup(row: dict, vars_=None, names: set[str] | None = None) -> bool:
    """Is this recording a backup copy — homed on a backup volume?"""
    names = backups(vars_) if names is None else names
    return str(row.get("home") or "") in names


# -- what the platform reads of these rows, instead of the VMS's code (the boundary's step 6) ----------------------------
# Three rules about a recording and its volume were the VMS's code called inside the platform's controller — an admit,
# a near rank, a refusal of a row. They are declarations now, in the specs, and these rows are what the platform reads:
#
#     a standby is a filter     `home` is a preference everywhere else, and for a backup or edge volume that is wrong in
#                               both directions (М10B Lesson 26): a primary moved onto the backup while its server
#                               rebooted is ONE copy where the operator paid for two, and a backup moved off it is no
#                               copy at all. `placement.affinity` in rec.subsystem.yaml: an enabled backup or edge row
#                               (`strict`) binds the recordings homed on it, and takes no other
#     incidents take nobody     a place for what somebody kept, never one to record into: its row says `admits: false`
#                               (`Volume.to_items`), and the platform reads that word, not the kind
#     beside the standby        a camera with two recordings has its worker beside the BACKUP one, which must survive the
#                               primary's server: `near.prefer` in vms.subsystem.yaml (`home.kind`, through `ref`)
#     a card is its camera's    `home: {ref: rec/volumes, must_match: {cam: cam}}`: the platform refuses a recording of
#                               another camera homed on a card (the review's sixth pass, major — through a scenario's
#                               `record` with `archive: card2` as much as an operator's PUT); and a row that does not
#                               parse is no row to point at. The other order — a card declared as another camera's under
#                               a name recordings are homed on already — is `write` above.
#
# A row that does not parse is not "no volume" (the review's seventh pass): `volume_named` raises `Unreadable` for it —
# the console's gate asks whose card a volume is through it (`vms/console.py`, `volume_cam`).
class Unreadable(Refused):
    """The volume's row does not parse."""


def volume_named(vars_, name: str) -> "Volume | None":
    items, _ = vars_.get(key(name))
    if not items:
        return None
    vol = read_volume(name, items)
    if vol is None:
        raise Unreadable(f"volume {name}'s row ({key(name)}) does not parse: mend it — declare the volume again — first")
    return vol


# What two sources are the same camera by, for the RIGHTS a move asks (`vms/console.py`, `source_cams`): the device and
# the channel on it, as the holder groups them (`config.device_of`, `channel_key`) — `…/ch/2` and `…/ch/2/` are one
# channel; so are `…/10.0.0.50:80/ch/02` and `…/10.0.0.50/ch/2` (the review's eighth pass: one device, one spelling).
# By the KEY, not by what the device says it is (the owner's decision on the ninth pass: a serial number is not unique).
# Whether a channel is TAKEN is no longer asked here: the platform refuses the same address in its one spelling
# (`source: {unique: canonical}`), and the twin only the VMS can see — `…/ch/02` beside `…/ch/2` — is the holder's to
# find (`VmsWorker`, «device busy» in its heartbeat; the owner's decision on the boundary's step 6).
def source_key(source: str) -> tuple:
    from .config import channel_key, device_of
    return device_of(str(source)), channel_key(str(source))
