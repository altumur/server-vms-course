"""Ordinary recorder reads and archive planning from C2 observations (ADR-0074)."""
from __future__ import annotations
import json
import time
from dataclasses import dataclass
from vms.archive import subtract
from w2cplatform.domain.federation import Unreachable, _names, a_heartbeat, published
from w2cplatform.rows import PARSE_ERRORS
from w2cplatform.domain.memberbook import read as member_book

class NotResolvable(Exception):
    pass


@dataclass
class Source:
    ref: str
    cluster: str
    live_url: str
    coverage: dict | None
    age: float
    backups: list = None              # М11 lesson 1: backups of this camera on another server — cluster, recording, url, coverage


# The recorder's side, in the recording cluster: `ref:<serial>` against this cluster's own copy of the book.
# Any other source is this cluster's own and is found as it always was — in its own heartbeats.
# The recorder asks it for each recording of such a camera on every pass (`RecWorker.source`), and reads the book once a
# pass for all of them (`resolve_in`, over the pass's look); the product's `ResolveRef` and `sourceIn`.
def resolve(cluster_vars, source: str, now: float) -> Source | None:
    if not str(source).startswith("ref:"):
        return None
    from .recording_books import Unconfirmed, source as source_fact, read, recording_value
    from .recording_publication import member
    from w2cplatform.domain.placement import placed
    ref = str(source)[4:]
    try:
        assignment = placed(cluster_vars, "rec", ref)
        own = member(cluster_vars)
        if assignment is None or own not in (assignment["cluster"], *assignment["copies"]):
            raise Unconfirmed("this cluster is not assigned to receive this source")
        fact = source_fact(member_book(cluster_vars, "domain/cam/sources", own), ref)
        if fact.member != assignment["origin"]:
            raise Unconfirmed("source origin does not match placement")
        observations = read(member_book(cluster_vars, "domain/rec/primaries", own), ref)
        card, backups = None, []
        for observation in observations.entries:
            if observation.member in observations.missing:
                continue
            value = recording_value(observation.value)
            if value["role"] == "card" and observation.member == assignment["origin"]:
                card = value.get("coverage")
            if value["role"] == "backup" and observation.member in assignment["copies"] \
                    and value.get("coverage") and value.get("peer_url"):
                backups.append({"cluster": observation.member, "recording": value["recording"],
                                "url": value["peer_url"], "coverage": value["coverage"]})
        return Source(ref, fact.member, fact.value["live_url"], card,
                      max(0.0, now - fact.value["as_of"]), backups)
    except (ValueError, TypeError, KeyError) as error:
        raise NotResolvable(str(error)) from None


# What to fetch from the card: what the book says it holds, minus what we hold, bounded as М10B's recorder
# bounds it (not older than our own volume keeps, not fresher than `settle`) — and then checked against
# what the device says NOW. The book is as old as its last carry; a card is a ring, and the oldest hour it
# listed may have been overwritten since. A range the card no longer has is dropped with its reason — a
# retry would ask the same card the same question.
def plan_backfill(src: Source, ours: list[tuple[float, float]], now: float, keep_days: float, settle: float,
                  ask_device) -> tuple[list[tuple[float, float]], list[tuple[tuple[float, float], str]]]:
    if not src.coverage:
        return [], []
    want = (max(float(src.coverage["from"]), now - keep_days * 86400), min(float(src.coverage["to"]), now - settle))
    if want[1] <= want[0]:
        return [], []
    holes = subtract(want, ours)
    if not holes:
        return [], []
    card = ask_device()                                  # {"from", "to"} — the card, now
    fetch, dropped = [], []
    for h in holes:
        lo, hi = max(h[0], float(card["from"])), min(h[1], float(card["to"]))
        if hi > lo:
            fetch.append((lo, hi))
        for gone in subtract(h, [(lo, hi)] if hi > lo else []):
            dropped.append((gone, "no longer on the card"))
    return fetch, dropped


# The primary is back, and everything is taken home (М11 lesson 1, two servers). While it was not writing, TWO
# backups wrote: the card in the camera, and the backup recording on the other server — both `when: offline`,
# both started by the same book of primaries. Now the primary closes its holes from them, and only inside what it
# records (М10B lesson 26: between its first and last visible second, not fresher than `settle`):
#
#     first   the other server's backup — on the site's LAN, copied as it was recorded, and not over the
#             camera's uplink, which live video needs
#     then    the card, for what the backup does not have — the seconds before the camera switched its stream,
#             a backup that failed too — asked of the device NOW, as Lesson 13 asks (a card is a ring)
#
# Returns what to fetch, each range with where from, and what nobody has, with why.
def plan_takeback(src: Source, ours: list[tuple[float, float]], now: float, keep_days: float, settle: float,
                  ask_device=None) -> tuple[list[tuple[tuple[float, float], str]], list[tuple[tuple[float, float], str]]]:
    if not ours:
        return [], []
    lo, hi = max(ours[0][0], now - keep_days * 86400), min(ours[-1][1], now - settle)
    if hi <= lo:
        return [], []
    holes = subtract((lo, hi), ours)
    fetch, missing = [], []
    for b in src.backups or []:
        span = (float(b["coverage"]["from"]), float(b["coverage"]["to"]))
        rest = []
        for h in holes:
            got = (max(h[0], span[0]), min(h[1], span[1]))
            if got[1] > got[0]:
                fetch.append((got, f"backup:{b['cluster']}"))
            rest += subtract(h, [got] if got[1] > got[0] else [])
        holes = rest
    if holes and src.coverage:
        card = ask_device() if ask_device else src.coverage
        for h in holes:
            got = (max(h[0], float(card["from"])), min(h[1], float(card["to"])))
            if got[1] > got[0]:
                fetch.append((got, "card"))
            missing += [(g, "on no backup and no longer on the card") for g in subtract(h, [got] if got[1] > got[0] else [])]
    else:
        missing += [(h, "on no backup, and the camera has no card") for h in holes]
    return sorted(fetch), missing


# -- a standby that PULLS: one stream, when the primary does not take it (М11 lesson 1) ---------------------
# A camera the second server takes itself — RTSP, over the camera's door, which is open to the site: where
# pulling works at all. Nobody pushes, so the standby asks the camera for its stream — and only when the
# primary does not take it: COLD, not on hold, so the camera serves one session, not two. How it knows, two ways,
# neither the domain:
#
#     our camera     ask the CAMERA who takes its stream (`camera_taken`): the same door it would pull from,
#                    nothing new to reach, and a partition between the servers opens no second session. What it
#                    cannot see: a recorder that holds its session and writes nothing
#     any camera     watch the primary's recorder through its server's door (`neighbour_writes`) — site traffic
#                    between servers — and sees "running" or not. It needs the servers to SEE each other: one that
#                    cannot tell "dead" from "out of sight" opens a second session and keeps it — two recordings,
#                    safe, but not one stream. Servers that cannot see each other take cameras that push
def neighbour_writes(objects, recording: str, now: float, lost_after: float = 45.0) -> bool:
    """Whether the primary's recorder, read through its server's door, says the recording is running."""
    try:
        for key in objects.list("rec/heartbeats/"):
            hb = published("neighbour", key, objects.get(key), a_heartbeat) or {}   # one torn heartbeat says nothing
            if not hb or now - float(hb.get("ts", 0)) > lost_after:
                continue
            if any(str(st.get("id")) == recording and st.get("phase") == "running" for st in hb.get("status", [])):
                return True
    except Unreachable:
        return False                                     # the server does not answer: it writes nothing we know of
    return False


def camera_taken(door_objects, serial: str, me: str) -> bool | None:
    """Whether anyone but `me` takes the camera's stream, as the camera says through its door. None: the camera
    does not answer — then there is nothing to pull either."""
    try:
        raw = door_objects.get(f"cam/heartbeats/{serial}")
    except Unreachable:
        return None
    # a list of names, checked as one (`_names`, the ninth review's sibling of `_urls`): `list("srv-b")` passed a string
    # as its letters, and every letter is "someone but me" — the standby read the camera as taken and never pulled
    hb = published("camera", f"cam/heartbeats/{serial}", raw, lambda v: _names(v.get("taken_by", [])), None)
    if raw and hb is None:
        return None                                      # what the camera said cannot be read: nothing known, change nothing
    return any(t != me for t in (hb or {}).get("taken_by", []))


class ColdStandby:
    """`primary_writes() -> bool | None` — `neighbour_writes` or `camera_taken`, bound; None: cannot tell, change
    nothing. `open()` / `close()` a session with the camera; `pass_once()` opens it when the primary does not
    write and closes it when the primary is back — a minute later, so the two archives overlap (М10B lesson 26)
    and the primary's takeback finds the seam on both sides."""

    OVERLAP = 60.0

    def __init__(self, primary_writes, open_, close, wall=time.time):
        self.primary_writes, self.open, self.close, self.wall = primary_writes, open_, close, wall
        self.pulling, self._back_since = False, None

    def pass_once(self) -> str:
        now = self.wall()
        writes = self.primary_writes()
        if writes is None:
            return "pulling" if self.pulling else "cold: cannot tell"
        if not writes:
            self._back_since = None
            if not self.pulling:
                self.open(); self.pulling = True
                return "pulling: the primary does not write"
            return "pulling"
        if self.pulling:
            self._back_since = self._back_since or now
            if now - self._back_since >= self.OVERLAP:
                self.close(); self.pulling = False
                return "closed: the primary writes again"
            return "pulling: the overlap"
        return "cold: the primary writes"
