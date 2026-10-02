"""Lesson 13 — a stream from another cluster.

A camera that is its own cluster still wants a server to record it: the card in it holds days, the server's
volume holds months, and the card is in the camera a thief takes with him. The server's recorder does what
it always does — pulls RTSP, writes its volume, closes gaps from the device's own archive (М10B Lessons
15–16). What changes is only where it FINDS the camera. In one cluster it found the holder's `live_url`,
`playback_url` and `coverage` in its own cluster's heartbeats. This camera's heartbeat is in the camera's
cluster, which the recorder cannot read and must not depend on.

So the domain — which reads every member — publishes a SOURCE BOOK per recording cluster: for each camera
of another cluster that this one records, where it was last seen, and when. The cluster's agent carries it
home, as it carries grants. The recorder resolves `ref:<serial>` against its own cluster's copy, so a
recording goes on with the domain switched off, from the address last carried.

    data crosses    footage and coverage go from the camera's cluster to the server's
    work does not   the recorder stays in the server cluster; the camera learns of no server; no row, no
                    epoch and no request is written into the camera's cluster by anyone but itself
    one consumer    a camera serves one live session and one backfill (М10B Lesson 15). Which cluster
                    records it is therefore a DOMAIN decision, stored, one per camera — the same shape as
                    Lesson 1's placement, and refused the same way when a second cluster asks
    a hint          what the book says about the card is as old as the book. The device is asked again
                    before a range is fetched, and a range the card no longer holds is dropped, not retried

    domain/crossings            in the domain holder: {ref: the cluster that records it}
    domain/sources/<cluster>    in the domain holder: that cluster's source book
    domain/sources              in the recording cluster: its agent's copy
    domain/primaries/<cluster>  in the domain holder: the camera cluster's book of primaries
    domain/primaries            in the camera's cluster: its agent's copy, read by the backup on its card
    domain/poll/<cluster>       in the domain holder: for a camera that pushes and that NOBODY records, the
                                ingest it polls anyway — so an ask reaches it (Lesson 16, step 8)
    domain/poll                 in the camera's cluster: its agent's copy

The book of primaries is the source book the other way round. A backup on the camera's card with
`when: offline` records while its primary should be written and is not (М10B Lesson 26) — and its primary
is here, in the recording cluster, where the camera's cluster cannot look. So the domain says, per camera,
who records it, whether that recording SHOULD be written (enabled, its `until` not passed) and whether it IS
(a recorder's fresh heartbeat reports it running). No time in it: a book that changed on every pass would
be rewritten on the camera's flash every few seconds. How current it is, the camera learns from its agent's
last contact with the domain, which lives in RAM.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass

from cluster.variables import Conflict
from vms.archive import subtract

from .agent import POLL_PATH, PRIMARIES_PATH, SOURCES_PATH
from .federation import Unreachable, a_heartbeat, published
from w2cplatform.rows import PARSE_ERRORS
from .tokens import kid_of
from .api import ApiError

CROSSINGS = "domain/crossings"
ROADS = "domain/roads"                 # cameras sent to push because a recorder could not pull them: {ref: {on, why, nets}}


class Crossings:
    """The domain's side: which cluster records which camera of another cluster, and the books."""

    def __init__(self, domain_vars, view, wall=time.time, issuer=None, token_lifetime: float = 86400.0,
                 centre: str | None = None, star=frozenset(), poll_home: str | None = None, topology=None):
        """`issuer` is Lesson 16: the domain signer's token issuer. Given it, the book of primaries also tells
        a camera where to PUSH — the recording cluster's ingest — with a stream token for it."""
        self.vars, self.view, self.wall = domain_vars, view, wall
        self.issuer, self.token_lifetime = issuer, token_lifetime
        # Lesson 17: the monitoring centre, and the recording clusters that cannot be pushed to — their cameras
        # push to the centre instead, and the cluster pulls its streams from there.
        # Given explicitly they stand; otherwise the operator's topology says (`domain/topology.py`), read on
        # every use, so an edit there reaches the next pass without a restart.
        self._centre, self._star, self.topology = centre, (frozenset(star) if star else None), topology
        # Lesson 16, step 8: where a pushing camera that nobody records keeps its poll — a cluster every camera
        # already reaches. The centre if there is one, else the cluster that holds the domain: a camera reaches
        # it for its agent's pass anyway.
        self.poll_home = poll_home

    def _topo(self) -> dict | None:
        doc = self.topology.read() if self.topology is not None else None
        return doc if doc and doc["rev"] else None      # written by the operator: it wins over what was configured

    @property
    def centre(self) -> str | None:
        doc = self._topo()
        return doc["centre"] if doc else self._centre

    @property
    def star(self) -> frozenset:
        doc = self._topo()
        return frozenset(doc["star"]) if doc else (self._star or frozenset())

    def via_of(self, member: str | None) -> str | None:
        """The relay this member reaches the domain through: the topology, else how its copy was configured."""
        if member is None:
            return None
        doc = self._topo()
        if doc:
            return doc["via"].get(member)
        c = self.view.fed.clusters.get(member)
        return c.via if c is not None else None

    def _poll_home(self, home: str | None = None) -> str | None:
        """Where a camera of cluster `home` polls when nobody records it. A camera that reaches only its relay
        (Lesson 17, `report@relay`) polls that relay's ingest: the centre and the domain's holder are exactly
        what it cannot reach."""
        via = self.via_of(home)
        if via:
            return via
        if self.poll_home or self.centre:
            return self.poll_home or self.centre
        dc = getattr(self.view.fed, "domain_holder", None)
        return dc.name if dc is not None else None

    # Who holds a poll — one rule (feedback AL): EVERY member camera, its door open or not. A camera of ours
    # says so in its heartbeat (`polls`); one that pushes polls by definition. A camera of a server cluster that
    # does not run the platform holds none, and cannot be asked: a scenario on it is refused when written.
    def members(self) -> dict[str, str]:
        """{ref: its own cluster} for every member camera — every camera that holds a poll to an ingest."""
        out = {}
        for (cluster, _worker), s in self.view.snapshots.items():
            if (s.doors or {}).get("polls") or (s.doors or {}).get("push"):
                for st in s.status:
                    if st.get("ref"):
                        out[str(st["ref"])] = cluster
        return out

    # What a camera says it raises and can be asked to do (`can`, per camera in its heartbeat — a camera of ours
    # from its own description, a server cluster's camera from its holder's, М10B Lesson 25). The newest
    # heartbeat that says it wins; a member that went silent keeps what it last said, because "the yard camera
    # has five presets" is not less true while it reboots. None — nobody has said.
    def can_of(self, ref: str) -> dict | None:
        best = None
        for (_cluster, _worker), s in self.view.snapshots.items():
            for st in s.status:
                if str(st.get("ref", "")) == str(ref) and st.get("can") is not None and (best is None or s.ts > best[0]):
                    best = (s.ts, st["can"])
        return best[1] if best else None

    def unrecorded(self) -> dict[str, str]:
        """{ref: its own cluster} for every member camera that no cluster records: it polls the poll home."""
        rec = self.all()
        return {ref: c for ref, c in self.members().items() if ref not in rec}

    def polled_at(self, ref: str) -> str | None:
        """The cluster whose ingest this camera polls: the one that records it (the centre for a star), or the
        poll home for a pushing camera nobody records; None for a camera that polls nothing."""
        if str(ref) not in self.members():
            return None                                  # not a member camera: it polls nothing, nobody can ask it
        on = self.all().get(str(ref))
        if on is not None:
            return self.centre if on in self.star and self.centre else on
        home = self.unrecorded().get(str(ref))
        return self._poll_home(home) if home is not None else None

    def all(self) -> dict[str, str]:
        items, _ = self.vars.get(CROSSINGS)
        return dict(items or {})

    def record(self, ref: str, on: str, move: bool = False) -> dict:
        """`move`: the camera is recorded elsewhere now — the site was re-wired, a relay took it (feedback AN,
        Lesson 17). The decision is rewritten, and the books follow on the next pass: the old cluster's source
        book loses it and its recorder stops for lack of a source; the new one's gains it; the camera's book of
        primaries names the new cluster and its ingest. The old recording row is that cluster's to remove, and
        its footage stays there for its retention. Without `move`, a second cluster is still refused."""
        ref = str(ref)
        known = self.view.last_known(ref)
        if known is None:
            raise ApiError(404, f"camera {ref} has never been seen by the domain; nothing to record")
        if known[0] == on:
            raise ApiError(400, f"camera {ref} is in {on} already: a cluster records its own cameras as it always did")
        for _ in range(10):
            items, idx = self.vars.get(CROSSINGS)
            items = dict(items or {})
            if items.get(ref) == on:
                return {"camera": ref, "recorded_by": on, "from": known[0]}
            if ref in items and not move:
                raise ApiError(409, f"camera {ref} is recorded by {items[ref]} already: a device serves one live "
                                    f"session and one backfill, and a second recorder would take them from the first")
            was = items.get(ref)
            items[ref] = on
            try:
                self.vars.put(CROSSINGS, items, cas=idx)
                return {"camera": ref, "recorded_by": on, "from": known[0], **({"moved_from": was} if was else {})}
            except Conflict:
                continue
        raise ApiError(409, f"could not record {ref} on {on}: the crossings kept changing")

    # A BACKUP of a camera on another server (М11 lesson 1, two servers as two clusters of one): an ordinary
    # recording on that cluster's `backup` volume, `when: offline` (М10B lesson 26), naming the camera by the
    # domain's name (`cam: ref:<serial>`). The operator makes it there as always; the domain finds it in that
    # cluster's rec snapshot — no record of its own — and from then on the camera has a second road: it pushes
    # there when, and only when, its primary does not take the stream. One stream, never two.
    def backup_of(self, ref: str) -> str | None:
        found = self._backup(ref)
        return found[0] if found else None

    def _backup(self, ref: str) -> tuple[str, str] | None:
        """(the backup's cluster, the backup recording's name)."""
        on, home = self.all().get(str(ref)), (self.view.last_known(ref) or (None,))[0]
        for name in sorted(self.view.fed.clusters):
            if name in (on, home):
                continue
            c = self.view.fed.clusters[name]
            try:
                keys = c.objects.list("rec/snapshot/")
                for key in keys:
                    shard = published(name, key, c.objects.get(key), _recordings) or {}   # one torn shard is that shard's
                    for r in shard.get("recordings", []):
                        if str(r.get("cam")) == f"ref:{ref}" and str(r.get("when") or "") == "offline":
                            return name, str(r.get("name") or r.get("id"))
            except Unreachable:
                continue
        return None

    # What the backup on the other server HOLDS, as its recorder says in its heartbeat — the same summary and
    # door a backup of this cluster gives (М10B lesson 26): coverage, and the URL of its archive. Carried in the
    # PRIMARY's source book, so that the primary, back, knows where to take its hole from.
    def _backup_archive(self, cluster: str, recording: str, now: float, lost_after: float = 45.0) -> dict | None:
        c = self.view.fed.clusters.get(cluster)
        try:
            keys = c.objects.list("rec/heartbeats/") if c is not None else []
            for key in keys:
                hb = published(cluster, key, c.objects.get(key), a_heartbeat) or {}    # …and one recorder's heartbeat, its
                if not hb.get("archive_url") or now - float(hb.get("ts", 0)) > lost_after:
                    continue
                for st in hb.get("status", []):
                    if str(st.get("id")) == recording and st.get("coverage"):
                        return {"cluster": cluster, "recording": recording, "url": hb["archive_url"].rstrip("/"),
                                "coverage": st["coverage"], "as_of": float(hb["ts"])}
        except Unreachable:
            return None
        return None

    # Each recording cluster's book, from the read view's memory: the doors the camera's worker last
    # published, with the time they were published. A camera whose cluster is silent keeps its last entry
    # and says so — the address it had is the best there is, and it is usually still right.
    # A cluster that no longer records anything of another cluster — its last camera moved away — gets an
    # EMPTY book, not the last one it had: its recorder then says "not in this cluster's source book" and
    # stops, instead of recording from an address the domain no longer vouches for.
    def publish(self) -> dict[str, dict]:
        books: dict[str, dict] = {}
        for ref, on in self.all().items():
            books.setdefault(on, {})
            found = self._doors(ref)
            if found is not None:
                kept = self._backup(ref)
                archive = self._backup_archive(*kept, self.wall()) if kept else None
                if archive:
                    found = {**found, "backups": [archive]}  # where the primary takes its hole back from
                books[on][ref] = json.dumps(found, sort_keys=True)
                backup = kept[0] if kept else None          # its backup's cluster resolves `ref:` too — to ITS ingest
                if backup is not None:                      # decided for the backup's cluster by ITS networks
                    there = self._doors(ref, backup) or {}
                    books.setdefault(backup, {})[ref] = json.dumps(there, sort_keys=True)
        self._write_books(SOURCES_PATH, books)
        return books

    def _write_books(self, prefix: str, books: dict[str, dict]) -> None:
        for path in self.vars.list(f"{prefix}/"):
            books.setdefault(path[len(prefix) + 1:], {})     # a book this pass has nothing for: emptied
        for on, book in books.items():
            path = f"{prefix}/{on}"
            have, idx = self.vars.get(path)
            if (have or {}) != book:
                self.vars.put(path, book, cas=idx)

    # Each camera cluster's book of primaries: for every camera of it that another cluster records, what the
    # recording cluster's own objects say — its rec snapshot (desired: enabled, until) and its recorders'
    # heartbeats (actual: running). Read, like the source book, from what the recording cluster publishes and
    # nothing else. A recording cluster that does not answer is a primary nobody can vouch for: `written` is
    # false, and the card covers after its grace — which is right when the room is down, and only costs a
    # card's worth of writing when merely the domain cannot see it.
    def publish_primaries(self, lost_after: float = 45.0) -> dict[str, dict]:
        now, books = self.wall(), {}
        for ref, on in self.all().items():
            known = self.view.last_known(ref)
            if known is None:
                continue
            entry = self._primary(ref, on, now, lost_after)
            have, _ = self.vars.get(f"{PRIMARIES_PATH}/{known[0]}")
            was = _entry((have or {}).get(ref), {})          # an entry nobody can read: as if there were none
            ingest = self._ingest(ref, on, known[0], now, was.get("ingest"))
            if ingest:
                entry["ingest"] = ingest
            backup = self.backup_of(ref)
            if backup is not None:
                # For the backup's cluster: the same facts about the primary, so its recorder's gate knows when
                # to cover (`carried_primary`, by `ref:`) — the book of primaries, for the other side.
                facts = {k: v for k, v in entry.items() if k != "ingest"}     # not the camera's stream token
                books.setdefault(backup, {})[ref] = json.dumps({**facts, "backup": backup}, sort_keys=True)
                there = self._ingest(ref, backup, known[0], now, (was.get("backup") or {}).get("ingest"))
                if there and ingest:                          # the camera's second road: only for one that pushes
                    entry["backup"] = {"cluster": backup, "ingest": there}
            books.setdefault(known[0], {})[ref] = json.dumps(entry, sort_keys=True)
        self._write_books(PRIMARIES_PATH, books)
        return books

    def _primary(self, ref: str, on: str, now: float, lost_after: float) -> dict:
        # `starting` (feedback AB): the recording should be written and no recorder of its cluster has NAMED it
        # yet — a start, which gets the card's grace. Named and not written, or the cluster silent — a stop,
        # covered at once. It changes when a recording starts and when a recorder first reports it: rarely.
        entry = {"cluster": on, "recording": "", "should": True, "written": False, "starting": False}
        c = self.view.fed.clusters.get(on)
        try:
            if c is None:
                raise Unreachable(on)
            rows = []
            for key in c.objects.list("rec/snapshot/"):
                shard = published(on, key, c.objects.get(key), _recordings) or {}
                rows += [r for r in shard.get("recordings", [])
                         if str(r.get("cam")) == f"ref:{ref}" and str(r.get("when") or "") != "offline"]
            names = sorted(str(r.get("name") or r.get("id")) for r in rows)
            running, named = set(), set()
            for key in c.objects.list("rec/heartbeats/"):
                hb = published(on, key, c.objects.get(key), a_heartbeat)
                if not hb:
                    continue
                named |= {str(st.get("id")) for st in hb.get("status", [])}          # fresh or not: it knew of it
                if now - float(hb.get("ts", 0)) <= lost_after:
                    running |= {str(st.get("id")) for st in hb.get("status", []) if st.get("phase") == "running"}
        except Unreachable:
            return entry
        until_ok = lambda r: _until(r) == 0 or _until(r) > now      # an `until` nobody can read: no end known (`_until`)
        should = any(bool(r.get("enabled", True)) and until_ok(r) for r in rows)
        return {**entry, "recording": ",".join(names), "should": should,
                "written": any(n in running for n in names),
                "starting": should and not any(n in named for n in names)}

    # Lesson 16: where the camera pushes, and the token that lets it. The addresses are what the recording
    # cluster's ingest announced (`rec/ingest`). The token is re-issued only when the one the book already
    # holds is past half its life — the book is flash on the camera, and a token minted every pass would
    # rewrite it every pass.
    def _ingest(self, ref: str, on: str, home: str, now: float, old: dict | None) -> dict | None:
        from .ingest import INGEST, audience
        if on in self.star and self.centre:
            on = self.centre                             # a star: the camera pushes to the centre, never to its relay
        c = self.view.fed.clusters.get(on)
        if self.issuer is None or c is None:
            return None
        try:
            raw = c.objects.get(INGEST)
        except Unreachable:
            raw = None
        if raw is None:
            return old                                   # the recording cluster is silent: keep what the camera has
        announced = published(on, INGEST, raw, lambda v: list(v["urls"]))
        if announced is None:
            return old                                   # …and one whose announcement does not parse, the same (the seventh review)
        urls = announced["urls"]
        if old and old.get("urls") == urls and _until(old) - now > self.token_lifetime / 2 \
                and kid_of(old.get("token", "")) == self.issuer.kid:
            return old
        token = self.issuer.issue(home, self.token_lifetime, now=now, aud=audience(on), ref=ref, kind="stream")
        return {"urls": urls, "token": token, "until": now + self.token_lifetime}

    # Lesson 16, step 8: the book of polls. A camera that pushes and that nobody records polls nothing, and an
    # ask for it — "turn to preset 3" is the usual one for a PTZ camera kept for live view only — would have
    # nowhere to wait. So it gets the poll home's ingest and a stream token for it, in a book of its own: the
    # book of primaries says who RECORDS a camera, and a backup on its card reads it (М10B Lesson 26); a poll
    # that records nothing must not look like a primary there. The camera polls, is never told to push, and
    # takes its asks. Kept by the same half-life rule, so the book on its flash does not churn.
    def publish_polls(self) -> dict[str, dict]:
        now, books = self.wall(), {}
        for ref, home in self.unrecorded().items():
            on = self._poll_home(home)
            if on is None:
                continue
            have, _ = self.vars.get(f"{POLL_PATH}/{home}")
            old = _entry((have or {}).get(ref), None)
            ingest = self._ingest(ref, on, home, now, old)
            if ingest:
                books.setdefault(home, {})[ref] = json.dumps({**ingest, "cluster": on}, sort_keys=True)
        for home in {h for h in self.unrecorded().values()} | set(books):
            path = f"{POLL_PATH}/{home}"
            have, idx = self.vars.get(path)
            if (have or {}) != books.get(home, {}):
                self.vars.put(path, books.get(home, {}), cas=idx)
        return books

    # Pull or push — who decides (М12 lessons 1 and 16). Not a person: a fact about the network. The recorder
    # PULLS the camera when its cluster can see the camera's door — a network both say they see (they say it
    # themselves, `federation.REACHES`). The camera PUSHES when they share none, or when the camera says it
    # pushes whatever happens (`push`: a camera on a mobile uplink, seen from nowhere). When either side has said
    # nothing about its networks, there is nothing to decide by, and the camera's word stands, as before.
    #
    # And the witness that beats both: the recorder that was sent to pull and CANNOT reach the camera says so in
    # its heartbeat (`source_unreachable` — a firewall, a route the networks did not show). The domain then has
    # the camera push, and REMEMBERS it (`domain/roads`): once pushing, the recorder no longer pulls and has
    # nothing to complain of, and the next pass would send it back to pull — a swing. The memory is forgotten when
    # what it was decided on changes: the networks either side says, or the cluster that records the camera.
    def _road(self, camera_cluster: str, on: str, flag: bool, ref: str | None = None) -> tuple[bool, str]:
        if flag:
            return True, "the camera says it pushes"
        cam, rec = self.view.fed.clusters.get(camera_cluster), self.view.fed.clusters.get(on)
        cam_nets = cam.networks() if cam is not None else frozenset()
        rec_nets = rec.networks() if rec is not None else frozenset()
        if ref is not None:
            remembered = self._remembered_push(ref, on, cam_nets, rec_nets)
            if remembered:
                return True, remembered
        if not cam_nets or not rec_nets:
            push, why = False, "no networks said on one side: the recorder pulls, as it always did"
        elif cam_nets & rec_nets:
            push, why = False, f"{on} sees {sorted(cam_nets & rec_nets)[0]}, where the camera is: the recorder pulls"
        else:
            return True, f"{on} sees none of the camera's networks ({', '.join(sorted(cam_nets))}): the camera pushes"
        failed = self._pull_failed(ref, on) if ref is not None else None
        if failed:
            why = f"{on}'s recorder could not reach the camera ({failed}): the camera pushes"
            self._remember_push(ref, on, cam_nets, rec_nets, why)
            return True, why
        return push, why

    @staticmethod
    def _nets_mark(cam_nets, rec_nets) -> str:
        return ",".join(sorted(cam_nets)) + "/" + ",".join(sorted(rec_nets))

    def _remembered_push(self, ref: str, on: str, cam_nets, rec_nets) -> str | None:
        items, idx = self.vars.get(ROADS)
        mem = _entry((items or {}).get(ref), None)
        if not mem:
            return None
        if mem.get("on") == on and mem.get("nets") == self._nets_mark(cam_nets, rec_nets):
            return mem["why"]
        items = dict(items); items.pop(ref)                # what it was decided on changed: forget, decide again
        self.vars.put(ROADS, items, cas=idx)
        return None

    def _remember_push(self, ref: str, on: str, cam_nets, rec_nets, why: str) -> None:
        items, idx = self.vars.get(ROADS)
        items = dict(items or {})
        items[ref] = json.dumps({"on": on, "why": why, "since": self.wall(),
                                 "nets": self._nets_mark(cam_nets, rec_nets)}, sort_keys=True)
        self.vars.put(ROADS, items, cas=idx)

    def _pull_failed(self, ref: str, on: str, lost_after: float = 45.0) -> str | None:
        """The recorder of `on` says it cannot reach the camera `ref` — fresh, in its own heartbeat."""
        c = self.view.fed.clusters.get(on)
        try:
            keys = c.objects.list("rec/heartbeats/") if c is not None else []
            for key in keys:
                hb = published(on, key, c.objects.get(key), a_heartbeat) or {}
                if not hb or self.wall() - float(hb.get("ts", 0)) > lost_after:
                    continue
                for st in hb.get("status", []):
                    if str(st.get("cam")) == f"ref:{ref}" and st.get("source_unreachable"):
                        return str(st.get("why") or "source unreachable")
        except Unreachable:
            return None
        return None

    def _doors(self, ref: str, on: str | None = None) -> dict | None:
        on = on or self.all().get(ref, "?")
        for (cluster, worker), s in self.view.snapshots.items():
            if any(str(st.get("ref", "")) == ref for st in s.status) and s.doors:
                doors = dict(s.doors)
                if not (doors.get("polls") or doors.get("push")):   # not a member camera: nothing to push with (AO)
                    push, why = False, "not a member camera: it has nothing to push with, and is always pulled"
                else:
                    push, why = self._road(cluster, on, bool(doors.get("push")), ref)
                doors.update(push=push, road=why)
                if push:                                 # Lesson 16: it pushes to the recording cluster's ingest
                    doors["live_url"] = f"ingest://{on}/{ref}"
                    doors.pop("playback_url", None)      # the card is read by asking the camera to upload a range
                return {"cluster": cluster, "worker": worker, **doors, "as_of": s.ts,
                        "reachable": cluster not in self.view.cluster_down_since}
        return None


class NotResolvable(Exception):
    pass


@dataclass
class Source:
    ref: str
    cluster: str
    live_url: str
    playback_url: str | None          # None: a camera that pushes (Lesson 16) — its card is read by asking for an upload
    coverage: dict | None
    age: float
    reachable: bool
    backups: list = None              # М11 lesson 1: backups of this camera on another server — cluster, recording, url, coverage


# The recorder's side, in the recording cluster: `ref:<serial>` against this cluster's own copy of the book.
# Any other source is this cluster's own and is found as it always was — in its own heartbeats.
def resolve(cluster_vars, source: str, now: float) -> Source | None:
    if not str(source).startswith("ref:"):
        return None
    ref = source[4:]
    items, _ = cluster_vars.get(SOURCES_PATH)
    if not items or ref not in items:
        raise NotResolvable(f"{ref} is not in this cluster's source book: the domain has not asked this cluster "
                            f"to record it, or has never seen it publish a door")
    e = json.loads(items[ref])
    return Source(ref, e["cluster"], e["live_url"], e.get("playback_url"), e.get("coverage"),
                  max(0.0, now - float(e["as_of"])), bool(e.get("reachable", True)), list(e.get("backups", [])))


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
        raw = door_objects.get(f"vms/heartbeats/{serial}")
    except Unreachable:
        return None
    hb = published("camera", f"vms/heartbeats/{serial}", raw, lambda v: list(v.get("taken_by", [])), None)
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


# -- what the books read of others, one entry at a time (М10's seventh review, part 2) ----------------------------------
def _recordings(shard: dict) -> None:
    """A rec snapshot shard: its `recordings` are objects."""
    if not all(isinstance(r, dict) for r in shard.get("recordings", [])):
        raise TypeError("a recording row is not an object")


def _entry(raw, default):
    """One entry of a book this domain wrote itself (a JSON string in a row), or `default` when it does not parse."""
    if raw is None:
        return default
    try:
        return json.loads(raw)
    except PARSE_ERRORS:
        return default


def _until(r: dict) -> float:
    """A row's `until` as a number: 0 — no end — when it is not one."""
    try:
        from w2cplatform.rows import finite
        return finite(r.get("until") or 0)
    except PARSE_ERRORS:
        return 0.0
