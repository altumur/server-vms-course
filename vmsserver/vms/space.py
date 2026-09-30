"""What the archive does when the disk is full — the recorder's answer to the
resource's one question, "free N bytes".

Retention by days is a promise to the operator: thirty days of camera 7. This
module is what happens when the promise cannot be kept, and it is deliberately
not the same thing. Three steps, in this order:

    1. give up what is not ours    a unit whose recorder now writes on another server: send it there
    2. cut above the floor         from the unit with the most days over `min_days`, oldest first —
                                   and never what somebody said to keep (`vms/keeps.py`)
    3. the ring reaches the kept   nothing else is above the floor: the oldest KEPT segment, counted
    4. say the shortfall out loud  everything on the floor and still no room: a number, not a quiet cut

Step 3 is a decision and not an accident. A keep holds footage past its days and behind everything else
the watermark can take; it does not stop the recorder. A disk is a ring, and a ring that may not overwrite
its oldest part stops recording today to protect last month. What goes is said: `kept_cut` in the report,
`pressure-kept` in the deletions journal, a warning in the log.

Step 1 is why there is no separate "evacuation" job, schedule or button. A
recording written here while the owner's server was down is not lost, not
wrong, and not urgent — the console already merges timelines across resources.
It becomes work only when the disk it sits on needs the space, and then the
server that needs it is the one that acts.

The pressure is measured by `w2cplatform.resource` (the disk, not the tree);
what to give up is decided here, because only the subsystem knows what its
files mean. Nothing in the platform deletes a segment.
"""
from __future__ import annotations

import logging
import os

from w2cplatform.console import holder_of
from w2cplatform.contract import draining
from w2cplatform.resource import resources_seen

from .archive import SUB, ArchiveResource, Manifest

log = logging.getLogger("vms.space")
MAX_SEGMENTS = 50          # one pass moves a batch, not an archive: the next pass continues
ROOM_MARGIN = 0.9          # never fill the destination's last tenth — that is its own watermark's air


# How many days of footage a unit has here, from the manifest — the operator's real answer to "how far
# back does camera 7 go", which retention_days only promises.
def depth_days(archive: ArchiveResource, unit: str, now: float) -> float:
    segs = Manifest(archive.root, unit).read()
    return (now - min(s.start for s in segs)) / 86400 if segs else 0.0


# What a unit occupies here — from the manifest's `bytes`, not from the disk. Every line already carries
# the size, so the answer costs a read of one file instead of a walk of the tree.
def unit_bytes(archive: ArchiveResource, unit: str) -> int:
    return sum(s.bytes for s in Manifest(archive.root, unit).read())


# Units on this disk whose recorder is now on ANOTHER server -> that server. No event, no outage journal,
# no "recovery mode": what is on the disk (`units()`) against who holds it (the heartbeats). The same
# comparison answers the operator's "where is camera 7's footage" and drives the evacuation below.
def foreign(archive: ArchiveResource, objects, server: str, now: float, lost_after: float = 45.0) -> dict[str, str]:
    """{unit: the server whose recorder writes it now} for units held elsewhere."""
    out = {}
    for unit in archive.units():
        found = holder_of(objects, SUB + "/", unit, now, lost_after)
        if found is None:
            continue                                            # nobody holds it: not ours to send anywhere
        where = found[1].extra.get("server")
        if where and where != server:
            out[unit] = where
    return out


# Step 1. Push a bounded batch of a foreign unit's segments to the server that writes it now, then delete
# locally only what that server's own manifest confirms it has. The deletion follows an observed fact, not
# a 204: a copy that never arrived is a copy we still hold.
#
# The destination's free space is read from its heartbeat FIRST. Evacuating onto a disk that is itself
# tight moves the problem and invites the pair to trade gigabytes back and forth; a destination with no
# room is skipped, and step 2 answers instead.
# What a destination can actually take, and why it is not `space.free`.
#
# `space` is the SUM over that server's volumes, and a sum is the one number that cannot answer this
# question. A box with one full disk and one empty one reports "half free" — and the segments land on
# ONE volume, whichever its recorder writes to. The check "the destination is tight" then silently stops
# working, and back come the two servers trading gigabytes that `ROOM_MARGIN` exists to prevent.
#
# So: the emptiest volume it names, and the sum only for a resource that names no volumes — one written
# before there were any, where the sum and the volume are the same number.
def room_on(hb: dict) -> float:
    vols = hb.get("volumes") or {}
    if vols:
        return max(float(v.get("free", 0) or 0) for v in vols.values())
    return float(hb.get("space", {}).get("free", 0) or 0)


def evacuate(archive: ArchiveResource, objects, peers, server: str, need: int, now: float,
             lost_after: float = 45.0, max_segments: int = MAX_SEGMENTS, vars_=None) -> dict:
    """Send foreign units home, delete what the destination confirms."""
    seen, freed, moved, skipped = resources_seen(objects), 0, 0, {}
    drains = draining(vars_) if vars_ is not None else ""
    for unit, to in sorted(foreign(archive, objects, server, now, lost_after).items()):
        if freed >= need:
            break
        hb = seen.get(to)
        if hb is None or now - float(hb["ts"]) > lost_after:
            skipped[unit] = f"{to} silent"
            continue
        if to == drains:                                         # about to stop: do not hand it gigabytes first
            skipped[unit] = f"{to} draining"
            continue
        room = room_on(hb) * ROOM_MARGIN
        man = Manifest(archive.root, unit)
        segs = sorted(man.read(), key=lambda s: (s.start, s.epoch))
        sent, size = [], 0
        for s in segs:
            if freed + size >= need or len(sent) >= max_segments:
                break
            if size + s.bytes > room:
                skipped[unit] = f"{to} has no room"
                break
            try:
                with open(os.path.join(archive.root, s.path), "rb") as f:
                    peers.put_raw(hb["url"], f"segment/{s.path}", f.read(), {"X-Segment": s.line()})
            except (OSError, IOError) as e:                      # noqa: BLE001 — a peer that stopped answering mid-batch
                skipped[unit] = str(e)
                break
            sent.append(s); size += s.bytes
        if not sent:
            continue
        there = confirmed(peers, hb["url"], unit)
        keep, gone = [], 0
        for s in segs:
            if s in sent and s.path in there:
                archive.remove(s, "moved", now, to=to)           # not lost: it is there, and the journal says where
                gone += s.bytes; moved += 1
            else:
                keep.append(s)
        if gone:
            man.rewrite(keep)
            freed += gone
    return {"freed": freed, "moved": moved, **({"skipped": skipped} if skipped else {})}


# What the destination says it has: the paths in ITS manifest for this unit. A read, over the same route
# the console uses to draw a timeline — nothing was added for the sake of the check.
def confirmed(peers, url: str, unit: str) -> set[str]:
    try:
        body = peers.get_raw(url, f"manifest/{unit}").decode()
    except (OSError, IOError):                                   # unreachable now: confirm nothing, delete nothing
        return set()
    from .archive import Segment
    return {Segment.from_line(l).path for l in body.splitlines() if l.strip()}


# Step 2. Cut from whoever has the most days over the floor, oldest segment first, one at a time so the
# choice is made again after every deletion — the unit that was deepest stops being deepest, and the loss
# spreads instead of falling on one camera.
#
# Not "the oldest segments on the resource": that empties the camera with the longest retention, which is
# the one the operator cared most about. Not "the biggest file": that empties the camera with the highest
# bitrate, which is usually the same camera.
#
# `spans_of(unit)` is what somebody said to keep of that unit. Kept segments are not candidates and do not
# count towards a unit's depth: a camera whose only footage over the floor is kept has nothing to give.
def cut(archive: ArchiveResource, need: int, now: float, min_days: float, spans_of=None) -> dict:
    """Free `need` bytes from the unit with the most slack over the floor."""
    from .keeps import held
    spans_of = spans_of or (lambda unit: [])
    freed, removed = 0, 0
    while freed < need:
        best, slack, oldest = None, 0.0, None
        for unit in archive.units():
            spans = spans_of(unit)
            free = [s for s in Manifest(archive.root, unit).read() if not held(spans, s.start, s.end)]
            if not free:
                continue
            first = min(free, key=lambda s: (s.start, s.epoch))
            over = (now - first.start) / 86400 - min_days
            if over > slack:
                best, slack, oldest = unit, over, first
        if best is None:
            break                                                # everything that is not kept is on the floor
        man = Manifest(archive.root, best)
        archive.remove(oldest, "pressure", now)
        man.rewrite([s for s in man.read() if s != oldest])
        freed += oldest.bytes; removed += 1
    # Step 3: the ring. Still short, and what is left over the floor is kept. The oldest kept segment on the
    # disk goes — whichever unit it is, because "oldest" is the only order a ring has.
    kept_cut = 0
    while freed < need:
        oldest = None
        for unit in archive.units():
            spans = spans_of(unit)
            for s in Manifest(archive.root, unit).read():
                if held(spans, s.start, s.end) and (now - s.start) / 86400 > min_days \
                        and (oldest is None or (s.start, s.epoch) < (oldest.start, oldest.epoch)):
                    oldest = s
        if oldest is None:
            break
        man = Manifest(archive.root, oldest.unit)
        archive.remove(oldest, "pressure-kept", now)
        man.rewrite([s for s in man.read() if s != oldest])
        freed += oldest.bytes; kept_cut += 1
    if kept_cut:
        log.warning("the disk is full and nothing else is above the floor: %d KEPT segment(s) were cut, oldest "
                    "first — export what must outlive the disk", kept_cut)
    return {"freed": freed, "removed": removed + kept_cut, **({"kept_cut": kept_cut} if kept_cut else {})}
