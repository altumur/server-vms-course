"""Lesson 17 — a chain: site, office, centre.

Cameras behind NATs on remote sites, recorded by offices that are behind NATs too, watched from one
monitoring centre. Nothing new is needed beyond Lesson 16 repeated on every hop, and one rule that
generalises Lessons 10 and 16: EACH LEVEL DIALS THE LEVEL ABOVE; a level must be reachable from below and
never from above.

    control  flat, as it always was: one customer, one domain, hosted by the centre. Cameras and offices are
             its members and report to it directly (Lesson 10) — all of them can reach the centre. The
             summary report is the variant: cameras report to their office, and the office carries ONE object
             for all of them — fewer writes in the centre's raft, at the price that an office down makes its
             cameras invisible too (`bundle`, `member_copy(..., via=office)`)
    media    Lesson 16 on every hop. The office's ingest is to the centre what the camera is to the office:
             its FORWARDER keeps a long poll to the centre's ingest and pushes while the centre wants a stream.
             And the want travels DOWN: a viewer in the centre wants camera X, so the centre's ingest wants X
             from the office, so the office's ingest wants X from the camera. A camera recorded continuously is
             already pushing, and the chain answers at once; one recorded on events starts two polls later
    first    one cluster receives a camera's stream FROM THE CAMERA — its recording cluster (Lesson 13): the
             camera serves one session. Everyone else — the centre's viewers, a copy of an important camera on
             the centre's volume (М10B Lesson 26) — receives it from that cluster
    ranges   the office's archive, asked for by the centre, is uploaded by the office — the card's rule
             (Lesson 16) one level up
    star     an office that cannot open a port to its sites — a cloud cluster that takes no inbound, sites and
             offices on mobile operators — cannot be pushed to. Then the camera pushes to the CENTRE, and the
             office takes the streams of its cameras from the centre, calling in (`Ingest.pull`). Every byte
             goes through the centre's link: Lesson 8's arithmetic decides whether a site can afford it

In the tests every "dial" is a function the caller owns; nobody below is ever called.
"""
from __future__ import annotations

import json

from .federation import Unreachable
from .uplink import REPORTED, UPLINK, base

from .agent import UPSTREAM_PATH       # in a recording cluster: where its streams go up, or come down from (star)


# -- the domain's side: the book of a recording cluster's upstream ----------------------------------------
# For every camera a cluster records, the centre's ingest and a token to push to it — or, for a star office,
# a token to PULL from it. Tokens are the domain signer's, re-issued past their half-life (Lesson 16).
def publish_upstream(crossings, centre: str, star=frozenset(), lifetime: float = 86400.0) -> dict[str, dict]:
    from .ingest import INGEST, audience
    now, books = crossings.wall(), {}
    c = crossings.view.fed.clusters.get(centre)
    raw = None
    if c is not None:
        try:
            raw = c.objects.get(INGEST)
        except Unreachable:
            raw = None
    if raw is None or crossings.issuer is None:
        return {}
    urls = json.loads(raw)["urls"]
    for ref, on in crossings.all().items():
        if on == centre:
            continue
        mode = "pull" if on in star else "push"
        have, _ = crossings.vars.get(f"{UPSTREAM_PATH}/{on}")
        old = json.loads((have or {}).get(ref, "{}"))
        if old.get("urls") == urls and old.get("mode") == mode and float(old.get("until", 0)) - now > lifetime / 2:
            entry = old
        else:
            entry = {"urls": urls, "mode": mode, "until": now + lifetime,
                     "token": crossings.issuer.issue(on, lifetime, now=now, aud=audience(centre), ref=ref)}
        books.setdefault(on, {})[ref] = json.dumps(entry, sort_keys=True)
    for on, book in books.items():
        path = f"{UPSTREAM_PATH}/{on}"
        have, idx = crossings.vars.get(path)
        if have != book:
            crossings.vars.put(path, book, cas=idx)
    return books


# -- the office's side: the forwarder ------------------------------------------------------------------------
# One pass. For every camera in this cluster's upstream book: PUSH mode — poll the centre's ingest; if it wants
# the stream, want it here too (that is the want travelling down to the camera) and push up what arrived;
# upload any range the centre asked for, out of this cluster's archive. PULL mode (the star) — this cluster
# wants the stream for its own recorder: pull it from the centre and inject it here.
class Forwarder:
    def __init__(self, name: str, local, cluster_vars, dial, archive=None, needs=None):
        """`local`: this cluster's `Ingest`. `dial(url)`: calling OUT to the centre. `archive(ref, t0, t1)`:
        frames of a range from this cluster's archive. `needs(ref)`: whether this cluster wants the stream
        itself — its recorder — which in star mode it must fetch."""
        self.name, self.local, self.vars, self.dial = name, local, cluster_vars, dial
        self.archive = archive or (lambda ref, t0, t1: [])
        self.needs = needs or (lambda ref: False)
        self.up = f"up:{name}"
        self.queues: dict[str, object] = {}
        self.state: dict[str, str] = {}

    def book(self) -> dict[str, dict]:
        items, _ = self.vars.get(UPSTREAM_PATH)
        return {ref: json.loads(raw) for ref, raw in (items or {}).items()}

    def _centre(self, e: dict):
        for url in e["urls"]:
            try:
                return self.dial(url)
            except Unreachable:
                continue
        return None

    def pass_once(self) -> dict[str, str]:
        for ref, e in self.book().items():
            ing = self._centre(e)
            if ing is None:
                self.state[ref] = "no ingest of the centre answered"
                continue
            if e["mode"] == "pull":
                self.state[ref] = self._pull(ing, ref, e)
            else:
                self.state[ref] = self._push(ing, ref, e)
        return dict(self.state)

    def _push(self, ing, ref: str, e: dict) -> str:
        work = ing.poll(e["token"], ref)
        if work["push"]:
            self.local.want(ref, self.up)                       # the centre wants it: so do we, from the camera
            q = self.queues.setdefault(ref, self.local.subscribe(ref, self.up))
            frames = q.drain()
            if frames:
                ing.push(e["token"], ref, frames)
            said = f"forwarding {len(frames)} frame(s) up"
        else:
            self.local.release(ref, self.up)
            said = "the centre does not want it"
        for rid, (t0, t1) in work["ranges"].items():
            ing.upload(e["token"], ref, rid, (t0, t1), self.archive(ref, t0, t1))
        return said

    def _pull(self, ing, ref: str, e: dict) -> str:
        if not self.needs(ref) and not self.local.wanted(ref):
            return "nobody here wants it"
        frames = ing.pull(e["token"], ref, self.up)             # calling in; the centre wants it from the camera
        self.local.inject(ref, frames)
        return f"pulled {len(frames)} frame(s) down"


# -- the summary report ------------------------------------------------------------------------------------
# The office carries its cameras' reports as ONE object in the domain cluster. Cameras report to the OFFICE's
# object store (the office is reachable from its sites — that is the whole premise of this layout); the
# office's agent folds what is there into `domain/members/<office>/bundle`, only when it changed.
BUNDLE = "bundle"


def bundle(office: str, members: list[str], office_objects, domain_objects) -> bool:
    out: dict[str, dict[str, str]] = {}
    for m in members:
        b = base(m)
        keys = office_objects.list(b)
        if keys:
            out[m] = {k[len(b):]: office_objects.get(k).decode("utf-8", "surrogateescape") for k in keys}
    raw = json.dumps(out, sort_keys=True).encode()
    key = base(office) + BUNDLE
    if domain_objects.get(key) == raw:
        return False
    domain_objects.put(key, raw)
    return True


class BundleView:
    """The domain cluster's store as a member reporting through `office` sees it: its report, out of the
    office's bundle. Read only; what `member_copy(..., via=office)` reads through."""

    def __init__(self, office: str, domain_objects):
        self.office, self.store = office, domain_objects

    def _entries(self, member: str) -> dict[str, str]:
        raw = self.store.get(base(self.office) + BUNDLE)
        return (json.loads(raw) if raw else {}).get(member, {})

    @staticmethod
    def _split(key: str) -> tuple[str, str]:
        rest = key[len(UPLINK) + 1:]
        member, _, sub = rest.partition("/")
        return member, sub

    def get(self, key: str) -> bytes | None:
        member, sub = self._split(key)
        v = self._entries(member).get(sub)
        return v.encode("utf-8", "surrogateescape") if v is not None else None

    def list(self, prefix: str) -> list[str]:
        member, sub = self._split(prefix)
        return [base(member) + k for k in self._entries(member) if k.startswith(sub)]
