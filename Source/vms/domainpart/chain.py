"""Lesson 17 — a chain: site, relay, centre.

Cameras behind NATs on remote sites, recorded by relays that are behind NATs too, watched from one
monitoring centre. Nothing new is needed beyond Lesson 16 repeated on every hop, and one rule that
generalises Lessons 10 and 16: EACH LEVEL DIALS THE LEVEL ABOVE; a level must be reachable from below and
never from above.

    control  flat where it can be: one customer, one domain, held by the centre, and every member that can
             reach the centre reports to it directly (Lesson 10). A camera that can reach ONLY ITS RELAY
             cannot — and then the relay is its road to the domain both ways. The relay's agent RELAYS down
             everything the domain leaves for that camera (keys, revocations, its grants, kept edits, its books,
             stream tokens, the holder record, shared settings and backups, with their objects) into `relay/` in
             the relay's own stores, with the time the relay last reached the domain; the camera's agent reads
             that instead of the domain (`Relay`). Up, the camera reports into the relay's store and the relay
             carries ONE object for all such cameras (`bundle`, `member_copy(..., via=relay)`). The price: an
             relay down makes its cameras silent too, and nothing can be done about it — there is no other road
    media    Lesson 16 on every hop. The relay's ingest is to the centre what the camera is to the relay:
             its FORWARDER keeps a long poll to the centre's ingest and pushes while the centre wants a stream.
             And the want travels DOWN: a viewer in the centre wants camera X, so the centre's ingest wants X
             from the relay, so the relay's ingest wants X from the camera. A camera recorded continuously is
             already pushing, and the chain answers at once; one recorded on events starts two polls later
    first    one cluster receives a camera's stream FROM THE CAMERA — its recording cluster (Lesson 13): the
             camera serves one session. Everyone else — the centre's viewers, a copy of an important camera on
             the centre's volume (М10B Lesson 26) — receives it from that cluster
    ranges   the relay's archive, asked for by the centre, is uploaded by the relay — the card's rule
             (Lesson 16) one level up
    asks     a scenario between two sites of two relays (Lesson 16, step 8), when the trigger camera sees only
             its relay: it leaves the ask at its OWN relay, on a road marked "up"; the relay's forwarder,
             woken by the ask itself, takes it to the centre with a token the domain gave the relay for exactly
             that pair; the other relay's forwarder, whose poll the centre is holding, carries it down; the
             outcome comes back the same way, each hop woken by the one before. Seconds, not passes. An ask for
             a camera in the same relay never takes this road — its book names the relay directly
    star     a relay that cannot open a port to its sites — a cloud cluster that takes no inbound, sites and
             relays on mobile operators — cannot be pushed to. Then the camera pushes to the CENTRE, and the
             relay takes the streams of its cameras from the centre, calling in (`Ingest.pull`). Every byte
             goes through the centre's link: Lesson 8's arithmetic decides whether a site can afford it

In the tests every "dial" is a function the caller owns; nobody below is ever called.
"""
from __future__ import annotations

import json
import logging
import random
import threading

from w2cplatform.rows import PARSE_ERRORS, finite

from w2cplatform.domain.federation import Unreachable
from w2cplatform.trust.tokens import kid_of
from w2cplatform.domain.uplink import REPORTED, UPLINK, base

from .keys import UPSTREAM_PATH  # in a recording cluster: where its streams go up, or come down from (star)

log = logging.getLogger("chain")


# A CENTRE THAT DID NOT ANSWER IS ASKED AGAIN AT EACH CAMERA'S OWN MOMENT (the product's cross-check, after the twelfth
# review: its camera pusher tried again after exactly 2 s). Every camera of a relay loses the centre at the same moment —
# its held polls break together — and a fixed wait brought them all back at the same millisecond, again and again. The
# wait is `period` give or take half, drawn afresh every time, as the long poll's `BACKOFF` is.
def retry_wait(period: float) -> float:
    return period * random.uniform(0.5, 1.5)


# -- the domain's side: the book of a recording cluster's upstream ----------------------------------------
# For every camera a cluster records, the centre's ingest and a token to push to it — or, for a star relay,
# a token to PULL from it. Tokens are the domain signer's, re-issued past their half-life (Lesson 16).
#
# Where the centre takes streams is what its recorders say in their heartbeats (`ingest_urls`: ADR-0065, its addition of
# 2026-10-08 — the ingest lives in the recorder, and no object of the centre's announces it). The books' own entries are
# read past what does not parse (the eighth review's sibling, left here by the М12 pass): a torn entry is issued anew. A
# centre none of whose recorders heard lately says an ingest keeps the road each entry already names — tokens are still
# re-issued on it; one torn heartbeat raised out of the whole pass once, and a day later every relay's token to push up
# had run out. A centre that does not answer: nothing is written.
def publish_upstream(crossings, centre: str, star=frozenset(), lifetime: float = 86400.0) -> dict[str, dict]:
    from .ingest import BOOKS, _an_object, audience, ingest_urls
    now, books = crossings.wall(), {}
    c = crossings.view.fed.clusters.get(centre)
    if c is None or crossings.issuer is None:
        return {}
    try:
        urls = ingest_urls(centre, c.objects, now) or None       # none said: each entry keeps the road it names
    except Unreachable:
        return {}
    # Every camera a relay records — and every camera that only POLLS a relay (nobody records it, and it
    # reaches only that relay, Lesson 16 step 8): the centre must have a road down to it too, for asks, and for
    # a viewer in the centre, whose want the relay's forwarder carries down like any other.
    polled = {ref: crossings._poll_home(home) for ref, home in crossings.unrecorded().items()}
    for ref, on in [*crossings.all().items(), *((r, o) for r, o in polled.items() if o and o != centre)]:
        if on == centre:
            continue
        mode = "pull" if on in star else "push"
        have, _ = crossings.vars.get(f"{UPSTREAM_PATH}/{on}")
        raw_old = (have or {}).get(ref)
        old = BOOKS.read(f"{UPSTREAM_PATH}/{on}/{ref}", lambda: _an_object(json.loads(raw_old)), {}) if raw_old else {}
        road = urls if urls is not None else old.get("urls")
        if not isinstance(road, list):
            continue                                                  # no road known to the centre: none to give
        try:
            fresh = float(old.get("until", 0)) - now > lifetime / 2
        except PARSE_ERRORS:
            fresh = False
        if old.get("urls") == road and old.get("mode") == mode and fresh \
                and kid_of(str(old.get("token_secret", ""))) == crossings.issuer.kid:
            entry = old
        else:
            entry = {"urls": road, "mode": mode, "until": now + lifetime,
                     "token_secret": crossings.issuer.issue("stream", on, now=now, aud=audience(centre), ref=ref)}
        books.setdefault(on, {})[ref] = json.dumps(entry, sort_keys=True)
    for on, book in books.items():
        path = f"{UPSTREAM_PATH}/{on}"
        have, idx = crossings.vars.get(path)
        if have != book:
            crossings.vars.put(path, book, cas=idx)
    return books


# -- the relay's side: the forwarder ------------------------------------------------------------------------
# WHAT THE FORWARDER HOLDS FOR THE CENTRE, STATED (the eighth review, a minor: "does not lose frames when a push fails"
# held for about a second and a half — thirty frames in its subscription, fifty kept — and what it dropped was counted
# where nobody looked). A push the centre did not take is pushed again: up to `FORWARD_HOLD` seconds of the stream, never
# more than `FORWARD_BYTES`, cut clean to a key frame; and what waits between two pushes is up to `FORWARD_FRAMES` — the
# same seconds at thirty frames a second. Past them it is dropped, counted per camera (`dropped`, `queue_dropped`) and
# said in the camera's state and in `stats`. Longer than that the centre's copy is backfill's, out of this relay's
# archive (Lesson 17, "ranges").
FORWARD_HOLD = 10.0
FORWARD_BYTES = 16 << 20
FORWARD_FRAMES = 300


# THE CENTRE'S WORD, KEPT ACROSS A RESTART OF THE RELAY (ADR-0019: the product first, `recproc/upkept.go`; its r22). What the
# centre confirmed of a camera (`Ingest.up_have`) was in this process's memory alone: a relay restarted while the centre
# was unreachable said nothing of it, and the camera took what the relay records as delivered — its card let go of what
# the centre does not have. So the forwarder writes the centre's word down per camera in a ROW of this cluster's store
# (`rec/ingest/up/<ref>.json`, rec.subsystem.yaml `objects.rows`: every recorder of the cluster reads the store, the next
# writer may be on another box), `{"v": 1, "have": <archive ms, this relay's clock>, "every": <s>, "heard": <unix ms>}` —
# `have` and `every` left out when there is none (the course's centre says no step: `every` is never written) — and the
# restarted relay seeds `up_have` from it before its first pass. Not on every answer (one a second): when the centre
# starts wanting the stream, when its `have` goes back, at most once per `UP_KEPT_EVERY` while it moves on, once per
# `UP_KEPT_REFRESH` while it stands (so `heard` ages right after a restart). A centre that does not want the stream drops
# the row. Not for ever: a word older than `UP_KEPT_FOR` (a day: about what a camera's card holds) is dropped at the
# restart, counted (`up_expired`) and logged — and while the relay runs and the centre stays silent that long, the word is
# said no more, counted the same way: the card goes by the relay's own `have` again.
UP_KEPT = "rec/ingest/up"
UP_KEPT_FOR = 86400.0
UP_KEPT_EVERY = 60.0
UP_KEPT_REFRESH = 3600.0


def up_key(ref: str) -> str:
    return f"{UP_KEPT}/{ref}.json"


def keep_ups(objects) -> tuple:
    """`(load_up, save_up, drop_up)` over a cluster's object store — the recorder's — or three `None` without one: a relay
    with nowhere to keep the centre's word forgets it at a restart, as before."""
    if objects is None:
        return None, None, None

    def load_up(ref):
        return objects.get(up_key(ref))                     # a store that did not answer: `restore_up` counts it, reads again

    def save_up(ref, data):
        try:
            objects.put(up_key(ref), data)
        except OSError as err:
            log.warning("forwarder: the centre's word on %s could not be kept; a restart of this relay forgets it: %s", ref, err)

    def drop_up(ref):
        try:
            objects.delete(up_key(ref))
        except OSError as err:
            log.warning("forwarder: the centre's word on %s kept for a restart could not be dropped: %s", ref, err)
    return load_up, save_up, drop_up


# One pass. For every camera in this cluster's upstream book: PUSH mode — poll the centre's ingest; if it wants
# the stream, want it here too (that is the want travelling down to the camera) and push up what arrived;
# upload any range the centre asked for, out of this cluster's archive; carry down any ask left there for the camera
# and carry its outcome back up. PULL mode (the star) — this cluster
# wants the stream for its own recorder: pull it from the centre and inject it here.
class Forwarder:
    sealer = None                  # the ring its books' tokens are opened with: this process's (`keys.ring`) when None

    def __init__(self, name: str, local, cluster_vars, dial, archive=None, needs=None, objects=None,
                 load_up=None, save_up=None, drop_up=None):
        """`local`: this cluster's `Ingest`. `dial(url)`: calling OUT to the centre. `archive(ref, t0, t1)`:
        frames of a range from this cluster's archive — called with `recording=` when the centre named one, and
        raising `OSError` for a range it could not read. `needs(ref)`: whether this cluster wants the stream
        itself — its recorder — which in star mode it must fetch. `load_up(ref) -> bytes | None`, `save_up(ref, data)`,
        `drop_up(ref)`: where the centre's word on a camera is kept across a restart — by default over `objects`, this
        cluster's object store (`keep_ups`), and nowhere without it."""
        self.name, self.local, self.vars, self.dial = name, local, cluster_vars, dial
        self.archive = archive or (lambda ref, t0, t1, recording=None: [])
        self.needs = needs or (lambda ref: False)
        self.up = f"up:{name}"
        self.queues: dict[str, object] = {}
        self.state: dict[str, str] = {}
        self.versions: dict[str, int] = {}                       # per camera: what the centre last answered
        self.forwarding: dict[str, bool] = {}
        self.lifted: dict[str, dict] = {}                        # asks carried UP, waiting for their outcome
        self.carried: dict[tuple, tuple] = {}                    # asks carried DOWN: (ref, id) -> (centre, token, deadline)
        # THE CAMERA'S RULE, ONE LEVEL UP (the seventh review: state moved before the push was taken). Frames drained
        # from this cluster's ingest and not taken by the centre — its push failed — are pushed again first, not lost
        # with the failure (`unsent`, a stream: past `FORWARD_HOLD` it is cut clean to a keyframe, counted in
        # `dropped`); and a pull remembers the mark of the last batch it got (`pulled`), so the centre hands a batch whose
        # answer was lost on its way down over again (`Ingest.pull`).
        self.unsent: dict[str, list] = {}
        self.dropped: dict[str, int] = {}
        self.pulled: dict[str, tuple] = {}
        self.holes: dict[str, int] = {}                          # pulls whose centre had restarted since the last (`_pull`)
        self._read_last: dict[tuple[str, str], dict] = {}        # (book, entry) -> the entry as read last (`_entries`)
        self._lock = threading.RLock()
        self.woken = threading.Event()                           # set by the local ingest: something changed here
        self.pending = threading.Event()                         # set when an ask went up: an outcome to wait for
        local.listen(self.woken.set)
        # The centre's word kept across a restart (`UP_KEPT`): the three callables, what was last written per camera
        # (`_up_kept`: on, have ms, at, seen), when the centre last answered (`heard`, this relay's wall), the words that
        # outlived `UP_KEPT_FOR` (`up_expired`), how many times written (`up_writes`), and the cameras whose kept word was
        # read already (`_up_read`).
        defaults = keep_ups(objects)
        self.load_up = load_up if load_up is not None else defaults[0]
        self.save_up = save_up if save_up is not None else defaults[1]
        self.drop_up = drop_up if drop_up is not None else defaults[2]
        self._up_kept: dict[str, dict] = {}
        self.heard: dict[str, float] = {}
        self.up_expired: dict[str, int] = {}
        self.up_writes: dict[str, int] = {}
        self._up_read: set[str] = set()
        # WHAT FAILED, COUNTED AND SAID (the fifteenth review's blocker; ADR-0065, its addition): `errors` per loop — a
        # camera's own (its ref), `asks`, `outcomes` — and `_failing`, what each loop last failed with, so a failure is
        # logged once per change and its end once (`_failed`, `_works`).
        self.errors: dict[str, int] = {}
        self._failing: dict[str, str] = {}
        self._said = threading.Lock()
        try:
            self.restore_up()                                    # before the first pass: a camera polling now hears it
        except Exception as err:                                 # noqa: BLE001 — the book unread: the asks' round reads it again
            self._failed("asks", "reading the upstream book before the first pass", err)

    # A LOOP OF THE FORWARDER THAT FAILED GOES ON (the fifteenth review's blocker; ADR-0065, its addition). The store not
    # answering once (`OSError`; the file store's `StoreBusy` is one) killed the loop it hit: a camera's thread, the asks'
    # thread — in silence, for good, while the heartbeat repeated the last word. Now each round of each loop is one try: a
    # failure is counted (`errors`, said per camera in `upstream.<ref>.errors`, and all of them in the recorder's
    # `forwarder_errors`), logged when it is new or changed, and the loop waits about a period and goes on — as the
    # product's loops do (`recproc/forwarder.go`: a failed poll is a note and the next round). Its end is logged once.
    def _failed(self, where: str, what: str, err: BaseException) -> None:
        said = f"{type(err).__name__}: {err}"
        with self._said:
            self.errors[where] = self.errors.get(where, 0) + 1
            new, self._failing[where] = self._failing.get(where) != said, said
            n = self.errors[where]
        if new:
            log.warning("%s: %s failed (%s); counted (%d so far), tried again in about a period", self.name, what, said, n,
                        exc_info=None if isinstance(err, OSError) else err)

    def _works(self, where: str, what: str) -> None:
        with self._said:
            was = self._failing.pop(where, None)
        if was is not None:
            log.info("%s: %s works again (last failure: %s)", self.name, what, was)

    def errors_total(self) -> int:
        with self._said:
            return sum(self.errors.values())

    # The books the relay's agent carried, read entry by entry (the eighth review's sibling): an entry that does not
    # parse is the one read last — or none, when there never was one — counted (`ingest.BOOKS`); it raised out of the
    # whole pass, every camera of the relay with it.
    def _entries(self, path: str, keep, check) -> dict[str, dict]:
        from .ingest import BOOKS
        from .keys import opened
        items = opened(self.vars.get(path)[0], path, self.sealer)
        out = {}
        for k, raw in (items or {}).items():
            if not keep(k):
                continue
            e = BOOKS.read(f"{path}/{k}", lambda: check(json.loads(raw)))
            if e is not None:
                self._read_last[(path, k)] = e
            e = self._read_last.get((path, k)) if e is None else e
            if e is not None:
                out[k] = e
        return out

    def book(self) -> dict[str, dict]:
        from .ingest import _a_road, _an_object

        def entry(e):
            _a_road(_an_object(e))
            if e.get("mode") not in ("push", "pull"):
                raise ValueError(f"its mode is {e.get('mode')!r}")
            return e
        return self._entries(UPSTREAM_PATH, lambda k: True, entry)

    def _centre(self, e: dict):
        for url in e["urls"]:
            try:
                return self.dial(url)
            except Unreachable:
                continue
        return None

    def pass_once(self) -> dict[str, str]:
        book = self.book()
        self.restore_up(book)
        for ref, e in book.items():
            ing = self._centre(e)
            if ing is None:
                self.state[ref] = "no ingest of the centre answered"
                self._silent(ref)
                continue
            try:                                                # one camera's centre that stopped answering is that
                if e["mode"] == "pull":                         # camera's, not the end of the pass (the seventh review)
                    self.state[ref] = self._pull(ing, ref, e)
                else:
                    self.state[ref] = self._push(ing, ref, e)
            except Unreachable as err:
                self.state[ref] = f"the centre stopped answering: {err}"
                self._silent(ref)
        return dict(self.state)

    # -- the centre's word, kept (`UP_KEPT`) ------------------------------------------------------------------
    def restore_up(self, book: dict | None = None) -> None:
        """Seeds `Ingest.up_have` from the word an earlier process of this relay kept, for every push camera of the book
        not read yet — at construction, before the first pass, and for a camera new to the book. A word that does not
        read is dropped and said; one older than `UP_KEPT_FOR` is dropped, counted (`up_expired`) and said. A store that
        did not answer is that camera's failure — counted and said (`_failed`), and read again on the next round: it was
        taken for "no word kept", and a store that blinked at a restart lost the centre's word for good."""
        if self.load_up is None:
            return
        for ref, e in (self.book() if book is None else book).items():
            if ref in self._up_read or e.get("mode") != "push":
                continue
            try:
                raw = self.load_up(ref)
            except OSError as err:
                self._failed(ref, f"reading the centre's word on {ref} kept for a restart", err)
                continue
            self._up_read.add(ref)
            if raw is None:
                continue
            try:
                k = json.loads(raw)
                heard = finite(k["heard"]) / 1000.0
                have = None if k.get("have") is None else finite(k["have"]) / 1000.0
                if k.get("v") != 1 or heard <= 0:
                    raise ValueError(f"v {k.get('v')!r}, heard {k.get('heard')!r}")
            except PARSE_ERRORS as err:
                log.warning("%s: the centre's word on %s kept for a restart does not read; dropped: %s", self.name, ref, err)
                if self.drop_up is not None:
                    self.drop_up(ref)
                continue
            silent = self.local.wall() - heard
            if silent > UP_KEPT_FOR:
                self.up_expired[ref] = self.up_expired.get(ref, 0) + 1
                log.warning("%s: the centre wanted %s and has said nothing for %.0f s, longer than it is kept (%.0f s); the "
                            "camera's card goes by this relay's word again", self.name, ref, silent, UP_KEPT_FOR)
                if self.drop_up is not None:
                    self.drop_up(ref)
                continue
            if have is not None:
                self.local.up_have[ref] = have
            self.heard[ref] = heard
            self._up_kept[ref] = {"on": True, "have": None if have is None else round(have * 1000), "at": heard,
                                  "seen": False}
            log.info("%s: the centre's word on %s, kept from before: up_have %s until the centre answers", self.name, ref, have)

    def _keep_up(self, ref: str, push: bool, up: float | None) -> None:
        """Writes the centre's word down as it answered, when it changed enough to: the first answer that wants the
        stream, a `have` gone back at once, one moved on at most once per `UP_KEPT_EVERY`, one standing still once per
        `UP_KEPT_REFRESH`; an answer that does not want it drops the row (once — and the first answer of this process
        drops what a process before may have left)."""
        now = self.local.wall()
        self.heard[ref] = now
        if self.save_up is None:
            return
        k = self._up_kept.setdefault(ref, {"on": False, "have": None, "at": 0.0, "seen": False})
        if not push:
            if (k["on"] or not k["seen"]) and self.drop_up is not None:
                self.drop_up(ref)
            k.update(on=False, seen=True)
            return
        k["seen"] = True
        have = None if up is None else int(up * 1000)               # down to the ms: the card keeps more, never less
        since = now - k["at"]
        if k["on"] and (have or 0) >= (k["have"] or 0) and (have == k["have"] or since < UP_KEPT_EVERY) \
                and since < UP_KEPT_REFRESH:
            return
        row = {"v": 1, **({"have": have} if have else {}), "heard": int(now * 1000)}
        self.save_up(ref, json.dumps(row, separators=(",", ":")).encode())
        k.update(on=True, have=have, at=now)
        self.up_writes[ref] = self.up_writes.get(ref, 0) + 1

    def _silent(self, ref: str) -> None:
        """The centre did not answer: its word stands — but not past `UP_KEPT_FOR` since it last did. Then it is said no
        more (`up_have` dropped), counted and logged, once; the centre answering again says it again."""
        heard = self.heard.get(ref)
        if heard is None or ref not in self.local.up_have or self.local.wall() - heard <= UP_KEPT_FOR:
            return
        self.local.up_have.pop(ref, None)
        self.up_expired[ref] = self.up_expired.get(ref, 0) + 1
        log.warning("%s: the centre wanted %s and has said nothing for longer than it is kept (%.0f s); the camera's card "
                    "goes by this relay's word again", self.name, ref, UP_KEPT_FOR)

    def _left(self, ref: str, stop: threading.Event) -> None:
        """A camera's loop ended — its camera left the upstream book (the fifteenth review, minor 9; the product's `Pass`
        closes `c.stop`, `recproc/forwarder.go`), or the recorder stops: what it held goes with it — its subscription at
        this relay's ingest and its want there, what it kept to push again, the centre's word told to the camera. Its
        thread and its subscription grew with every camera the relay ever forwarded."""
        q = self.queues.pop(ref, None)
        if q is not None:
            self.dropped[ref] = self.dropped.get(ref, 0) + getattr(q, "dropped", 0)   # its losses stay counted
            self.local.unsubscribe(ref, self.up)
        self.local.release(ref, self.up)
        for kept in (self.unsent, self.versions, self.forwarding, self.state):
            kept.pop(ref, None)
        self.local.up_have.pop(ref, None)
        with self._said:
            self._failing.pop(ref, None)
        if not stop.is_set():
            log.info("%s: %s is no longer in the upstream book; its stream up ended", self.name, ref)

    def _push(self, ing, ref: str, e: dict, wait: float = 0.0) -> str:
        work = ing.poll(e["token_secret"], ref, version=self.versions.get(ref) if wait else None, wait=wait)
        self.versions[ref], self.forwarding[ref] = work["version"], work["push"]
        # WHAT THE CENTRE WROTE GOES DOWN TO THE CAMERA (the product's DY, checked in the course): what this relay's ingest
        # took, the camera counted delivered and its card let go of — whether or not it ever reached the centre. The
        # centre's `have` (how far its recorder wrote the camera) is left at this relay's ingest while it forwards the
        # camera up (`Ingest.up_have`), and the camera's `have` is the lesser of the two (`Ingest._have`).
        try:
            up = None if not work["push"] or work.get("have") is None else finite(work["have"])
        except PARSE_ERRORS:
            up = None
        if up is None:
            self.local.up_have.pop(ref, None)
        else:
            self.local.up_have[ref] = up
        self._keep_up(ref, bool(work["push"]), up)                # …and kept across a restart of this relay (`UP_KEPT`)
        if work["push"]:
            self.local.want(ref, self.up)                       # the centre wants it: so do we, from the camera
            q = self.queues.setdefault(ref, self.local.subscribe(ref, self.up, maxsize=FORWARD_FRAMES))
            frames = self.unsent.pop(ref, []) + q.drain()       # what the centre did not take last time, first
            if frames:
                try:
                    ing.push(e["token_secret"], ref, frames)
                except Unreachable:
                    self.unsent[ref] = self._kept(ref, frames)
                    raise
            lost = self.dropped.get(ref, 0) + getattr(q, "dropped", 0)
            said = f"forwarding {len(frames)} frame(s) up" + (f"; {lost} dropped so far, past what it holds" if lost else "")
        else:
            self.local.release(ref, self.up)
            self.unsent.pop(ref, None)                          # nobody up there wants it: nothing to send again
            said = "the centre does not want it"
        # The card's rule, one level up — all of it (the sixth review): the recording the centre named goes to the
        # archive's reader, and an archive that could not read the range says so (`failed`) instead of leaving the
        # centre to its timeout. One upload, not pieces: the relay is a server, and the centre asks a minute at a time.
        for rid, r in work["ranges"].items():
            named = {"recording": r["recording"]} if r.get("recording") else {}
            try:
                frames = self.archive(ref, r["from"], r["to"], **named)
            except OSError as err:
                ing.upload(e["token_secret"], ref, rid, [], failed=str(err))
                continue
            ing.upload(e["token_secret"], ref, rid, frames)                     # the answer to that request (AD)
        for aid, a in work.get("asks", {}).items():                     # an ask left above: down it goes…
            with self._lock:
                self.carried.setdefault((ref, aid), (ing, e["token_secret"], float(a["deadline"])))
            self.local.carry_ask(ref, aid, a)
        self._answer_carried()                                           # …and what became of it, up
        return said

    # -- asks: down and up ----------------------------------------------------------------------------------
    def _answer_carried(self) -> None:
        from .ingest import ANSWER_GRACE
        now = self.local.wall()
        with self._lock:
            for (ref, aid), (ing, token, deadline) in list(self.carried.items()):
                out = self.local.ask_outcome(ref, aid)
                if out is not None:
                    try:
                        ing.answer_ask(token, ref, aid, out)
                    except Unreachable:
                        continue                                          # the centre is away: next time
                    del self.carried[(ref, aid)]
                elif now > deadline + ANSWER_GRACE:
                    del self.carried[(ref, aid)]                          # the centre has called it expired itself

    def asks_book(self) -> dict[str, dict]:
        """What the domain let this relay carry up: {"<target>|<asker>": {"roads": [...]}}, one token per pair."""
        from .ingest import ASKS_PATH, _a_road, _an_object

        def entry(e):
            roads = _an_object(e).get("roads")
            if not isinstance(roads, list):
                raise TypeError("its roads are not a list")
            for road in roads:
                _a_road(road)
            return e
        return self._entries(ASKS_PATH, lambda k: "|" in k, entry)

    def lift(self) -> dict[str, str]:
        """One round of the asks' work, run whenever the local ingest says something changed: new asks up to
        the centre, the outcomes of those that went up back down to the asker, and the outcomes of asks carried
        down back up. Nothing here waits; the waiting is `serve`'s."""
        from .ingest import ANSWER_GRACE, Refused
        said: dict[str, str] = {}
        with self._lock:
            book = self.asks_book()
            for ing in self.local._cluster():
                for aid, a in ing.take_up():
                    e = book.get(f"{a['target']}|{a['by']}")
                    if e is None:
                        ing.settle_up(aid, f"refused: {self.name} may not carry asks from {a['by']} to {a['target']}")
                        continue
                    sent = None
                    for road in e["roads"]:
                        for url in road["urls"]:
                            try:
                                c = self.dial(url)
                                sent = (c, c.ask(road["token_secret"], a["target"], a["action"], a["deadline"]))
                                break
                            except Unreachable:
                                continue
                            except Refused as err:
                                ing.settle_up(aid, f"refused: {err}")
                                sent = False
                                break
                        if sent is not None:
                            break
                    if sent is None:
                        ing.untake_up(aid)                                # the centre did not answer: again, till the deadline
                        said[aid] = "the centre did not answer"
                    elif sent:
                        self.lifted[aid] = {"at": ing, "target": a["target"], "centre": sent[0], "aid": sent[1],
                                            "deadline": a["deadline"]}
                        self.pending.set()
                        said[aid] = "up"
            now = self.local.wall()
            for aid, x in list(self.lifted.items()):
                try:
                    out = x["centre"].ask_outcome(x["target"], x["aid"])
                except Unreachable:
                    out = None
                if out is None and now > x["deadline"] + ANSWER_GRACE:
                    out = "unknown: the centre does not know this ask any more"
                if out is not None:
                    x["at"].settle_up(aid, out)
                    del self.lifted[aid]
                    said[aid] = out
        self._answer_carried()
        return said

    # -- by event ---------------------------------------------------------------------------------------------
    def serve(self, stop: threading.Event, period: float = 5.0, stream_every: float = 0.05) -> list[threading.Thread]:
        """The forwarder as a process: three kinds of thread, none of them on a timer that matters.
        · asks — waits for the local ingest to say something changed (an ask to take up, an outcome to take
          back) and runs `lift` at once; `period` is only its fallback. Each round it reads the upstream book again
          and starts a thread for a camera new to it.
        · one per camera in the upstream book — a HELD poll at the centre: the centre answers it the moment a
          want, a range or an ask for that camera arrives there. While the centre wants the stream, it forwards. It
          reads the book every round, and ends when its camera is no longer there (`_left`).
        · outcomes — while asks it took up are open, a held wait at the centre for their outcome.
        A round of any of them that fails is counted, said and tried again (`_failed`); no failure ends a thread.
        On a real relay the per-camera polls are one held request for all its cameras; here, a thread each."""
        threads: dict[str, threading.Thread] = {}

        def down(ref):
            try:
                while not stop.is_set():
                    try:
                        e = self.book().get(ref)
                        if e is None:
                            return                                # the camera left the book: so does its loop
                        ing = self._centre(e)
                        if ing is None or e["mode"] != "push":
                            self._silent(ref)
                            self._works(ref, f"the stream of {ref} up")
                            stop.wait(retry_wait(period))         # no centre answered (or nothing to push): not in step
                            continue
                        streaming = self.forwarding.get(ref, False)
                        self.state[ref] = self._push(ing, ref, e, wait=0.0 if streaming else period)
                        self._works(ref, f"the stream of {ref} up")
                        if streaming:
                            stop.wait(stream_every)
                    except Unreachable:
                        self._silent(ref)
                        stop.wait(retry_wait(period))
                    except Exception as err:                      # noqa: BLE001 — counted, said, and the next round
                        self._failed(ref, f"the stream of {ref} up", err)
                        self.state[ref] = f"failed, tried again: {err}"
                        stop.wait(retry_wait(period))
            finally:
                self._left(ref, stop)

        def asks():
            while not stop.is_set():
                self.woken.wait(period)
                self.woken.clear()
                try:
                    book = self.book()
                    self.restore_up(book)                         # a camera new to the book: its kept word first
                    for ref in book:
                        if ref not in threads or not threads[ref].is_alive():
                            threads[ref] = threading.Thread(target=down, args=(ref,), daemon=True, name=f"fwd-{ref}")
                            threads[ref].start()
                    self.lift()
                    self._works("asks", "carrying asks up and down (lift)")
                except Exception as err:                          # noqa: BLE001 — counted, said, and the next event
                    self._failed("asks", "carrying asks up and down (lift)", err)
                    stop.wait(retry_wait(period))

        def outcomes():
            while not stop.is_set():
                open_ = list(self.lifted.values())
                if not open_:
                    self.pending.wait(period)
                    self.pending.clear()
                    continue
                x = open_[0]
                try:
                    x["centre"].outcome_wait(x["target"], x["aid"], wait=period)
                    self._works("outcomes", "waiting for an ask's outcome at the centre")
                except Unreachable:
                    stop.wait(retry_wait(period))                 # every relay's held wait broke at once: not in step
                except Exception as err:                          # noqa: BLE001 — counted, said, and the next round
                    self._failed("outcomes", "waiting for an ask's outcome at the centre", err)
                    stop.wait(retry_wait(period))
                self.woken.set()                                  # settle it: `lift` does

        started = [threading.Thread(target=asks, daemon=True, name=f"fwd-asks-{self.name}"),
                   threading.Thread(target=outcomes, daemon=True, name=f"fwd-outcomes-{self.name}")]
        for t in started:
            t.start()
        self.woken.set()
        return started

    def _kept(self, ref: str, frames: list) -> list:
        """What is kept to push again: a stream, so the last `FORWARD_HOLD` seconds of it, at most `FORWARD_BYTES` and
        `FORWARD_FRAMES`, from a keyframe — the rest dropped, counted, as a peer that falls behind is cut (`PeerLink`)."""
        from .ingest import _is_key, _t, _weight
        newest = next((_t(f) for f in reversed(frames) if _t(f) is not None), None)
        i, size = len(frames), 0
        while i > 0 and len(frames) - i < FORWARD_FRAMES and size + _weight(frames[i - 1]) <= FORWARD_BYTES and (
                newest is None or _t(frames[i - 1]) is None or newest - _t(frames[i - 1]) <= FORWARD_HOLD):
            i -= 1
            size += _weight(frames[i])
        kept = frames[i:]
        if i:
            while kept and not _is_key(kept[0]):
                kept.pop(0)
        self.dropped[ref] = self.dropped.get(ref, 0) + len(frames) - len(kept)
        return kept

    # …SAID IN THE RECORDER'S HEARTBEAT, IN THE PRODUCT'S WORDS — THE ONES IT COUNTS (ADR-0065 and its additions of
    # 2026-10-08 and 2026-10-10; ADR-0019, ADR-0003). The forwarder lives in the relay's recorder (`RecWorker.host_ingest`,
    # as `recproc/run.go`), and what it carried and lost is `upstream: {<ref>: …}` there — words of the product's
    # `Forwarder.Stats` (`recproc/forwarder.go`). Not an object of its own (`rec/forwarded/<name>` is gone). Per camera of
    # the upstream book that names a road:
    #
    #     every camera  mode            `push` or `pull`, as the book says
    #                   state           what the last pass did (`state`, the course's own sentence)
    #                   errors          rounds of the camera's loop that failed — the store, anything but the centre not
    #                                   answering (`_failed`; the fifteenth review's blocker) — the course's own word
    #     pull          down_breaks     pulls whose centre had restarted since the last (`holes`): a batch may be gone
    #     push          up_dropped      frames dropped past what it holds to push again (`dropped`), and past the queue
    #                                   between two pushes (its subscription's `dropped`)
    #                   up_have         what the centre confirmed of it (unix s, `Ingest.up_have`) — only once it said one
    #                   up_kept         the camera is told the word an earlier process of this relay kept, and the centre
    #                                   has not answered since (`restore_up`)
    #                   up_expired      times the centre's word outlived `UP_KEPT_FOR` (`up_expired`)
    #                   up_kept_writes  times it was written down (`up_writes`)
    #
    # The product's other nine words — `up_sent`, `up_gaps`, `up_resumed`, `up_have_every`, `up_unconfirmed_s`, `up_polls`,
    # `up_cuts`, `down_taken`, `down_dropped` — the course does not count, and does not say: a word that is not there is
    # "not counted", one that is there is a count (the fifteenth review, major 3: nine noughts read as health). On
    # `/metrics` the spec's lines over `up_dropped`, `down_breaks`, `up_expired` (`rec.subsystem.yaml`, `upstream_*_total`).
    def stats(self) -> dict[str, dict]:
        out = {}
        for ref, e in self.book().items():
            if not e.get("urls"):
                continue                                         # no road: no loop for it, as the product's `Pass`
            st = {"mode": e["mode"], "state": self.state.get(ref, ""), "errors": self.errors.get(ref, 0)}
            if e["mode"] == "pull":
                st.update(down_breaks=self.holes.get(ref, 0))
            else:
                st.update(up_dropped=self.dropped.get(ref, 0) + getattr(self.queues.get(ref), "dropped", 0))
                if (have := self.local.up_have.get(ref)) is not None:
                    st["up_have"] = have
                kept = self._up_kept.get(ref) or {}
                st.update(up_kept=bool(kept.get("on") and not kept.get("seen") and ref in self.local.up_have),
                          up_expired=self.up_expired.get(ref, 0), up_kept_writes=self.up_writes.get(ref, 0))
            out[ref] = st
        return out

    def _pull(self, ing, ref: str, e: dict) -> str:
        if not self.needs(ref) and not self.local.wanted(ref):
            return "nobody here wants it"
        # calling in; the centre wants it from the camera — and says which batch it last GOT, by the batch's mark
        # `(boot, n)`: a pull whose answer was lost on the way down is answered with that batch again, first, and a
        # mark from before the centre restarted is never taken for one of after (the eighth review, blocker 2)
        had = self.pulled.get(ref, ())
        frames = ing.pull(e["token_secret"], ref, self.up, have=had)
        self.pulled[ref] = mark = getattr(frames, "have", ())
        # A BATCH LOST WITH THE SIDE THAT SENT IT IS COUNTED (the ninth review, a minor; the product's sibling E). The
        # centre keeps the batch it handed over until the relay says it has it — in memory: an answer lost on the way
        # down just before the centre restarted took its batch with it (frame [3] at the centre, [6] at a relay in the
        # middle), and nothing counted it. The relay cannot know whether there was such a batch; it knows the centre
        # restarted — the mark's `boot` changed — and says that much: a POSSIBLE hole, counted (`holes`) and logged, for
        # the recorder's backfill to look at.
        if had and mark and tuple(had)[0] != tuple(mark)[0]:
            self.holes[ref] = self.holes.get(ref, 0) + 1
            log.warning("%s: the centre's ingest restarted since the last batch of %s this relay got: a batch it had "
                        "handed over and whose answer was lost may be gone with it", self.name, ref)
        self.local.inject(ref, frames)
        return f"pulled {len(frames)} frame(s) down"
