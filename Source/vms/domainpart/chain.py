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
# The centre's announcement and the books' own entries are read past what does not parse (the eighth review's sibling,
# left here by the М12 pass): a torn announcement keeps the road each entry already names — tokens are still re-issued
# on it — and a torn entry is issued anew. Either raised out of the whole pass, and a day later every relay's token to
# push up had run out.
def publish_upstream(crossings, centre: str, star=frozenset(), lifetime: float = 86400.0) -> dict[str, dict]:
    from w2cplatform.domain.federation import published
    from .ingest import BOOKS, INGEST, _an_object, _urls, audience
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
    said = published(centre, INGEST, raw, _urls)
    urls = said["urls"] if said is not None else None             # torn: each entry keeps the road it names
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


# One pass. For every camera in this cluster's upstream book: PUSH mode — poll the centre's ingest; if it wants
# the stream, want it here too (that is the want travelling down to the camera) and push up what arrived;
# upload any range the centre asked for, out of this cluster's archive; carry down any ask left there for the camera
# and carry its outcome back up. PULL mode (the star) — this cluster
# wants the stream for its own recorder: pull it from the centre and inject it here.
class Forwarder:
    sealer = None                  # the ring its books' tokens are opened with: this process's (`keys.ring`) when None

    def __init__(self, name: str, local, cluster_vars, dial, archive=None, needs=None):
        """`local`: this cluster's `Ingest`. `dial(url)`: calling OUT to the centre. `archive(ref, t0, t1)`:
        frames of a range from this cluster's archive — called with `recording=` when the centre named one, and
        raising `OSError` for a range it could not read. `needs(ref)`: whether this cluster wants the stream
        itself — its recorder — which in star mode it must fetch."""
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
        for ref, e in self.book().items():
            ing = self._centre(e)
            if ing is None:
                self.state[ref] = "no ingest of the centre answered"
                continue
            try:                                                # one camera's centre that stopped answering is that
                if e["mode"] == "pull":                         # camera's, not the end of the pass (the seventh review)
                    self.state[ref] = self._pull(ing, ref, e)
                else:
                    self.state[ref] = self._push(ing, ref, e)
            except Unreachable as err:
                self.state[ref] = f"the centre stopped answering: {err}"
        return dict(self.state)

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
          back) and runs `lift` at once; `period` is only its fallback.
        · one per camera in the upstream book — a HELD poll at the centre: the centre answers it the moment a
          want, a range or an ask for that camera arrives there. While the centre wants the stream, it forwards.
        · outcomes — while asks it took up are open, a held wait at the centre for their outcome.
        On a real relay the per-camera polls are one held request for all its cameras; here, a thread each."""
        threads: dict[str, threading.Thread] = {}

        def down(ref):
            while not stop.is_set():
                e = self.book().get(ref)
                ing = self._centre(e) if e else None
                if ing is None or e["mode"] != "push":
                    stop.wait(retry_wait(period))                 # no centre answered (or nothing to push): not in step
                    continue
                try:
                    streaming = self.forwarding.get(ref, False)
                    self.state[ref] = self._push(ing, ref, e, wait=0.0 if streaming else period)
                    if streaming:
                        stop.wait(stream_every)
                except Unreachable:
                    stop.wait(retry_wait(period))

        def asks():
            while not stop.is_set():
                self.woken.wait(period)
                self.woken.clear()
                for ref in self.book():
                    if ref not in threads:
                        threads[ref] = threading.Thread(target=down, args=(ref,), daemon=True, name=f"fwd-{ref}")
                        threads[ref].start()
                try:
                    self.lift()
                except Exception:                                        # noqa: BLE001 — a bad round is retried on the next event
                    pass

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
                except Unreachable:
                    stop.wait(retry_wait(period))                 # every relay's held wait broke at once: not in step
                self.woken.set()                                         # settle it: `lift` does

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

    # …left where a monitor reads it (the eleventh review, a minor: `dropped` and `holes` were said nowhere): an object in
    # this relay's own store, beside its ingest's (`rec/forwarded/<name>`), which the domain's console says on its
    # `/metrics` (`ingest.stream_metrics`). The process that runs the forwarder leaves it as its ingest leaves its own.
    def publish(self, objects) -> dict:
        from .ingest import FORWARDED
        st = self.stats()
        key = f"{FORWARDED}/" + "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in self.name)
        objects.put(key, json.dumps({"cluster": self.local.cluster, "forwarder": self.name, "ts": self.local.wall(),
                                     "cameras": st}).encode())
        return st

    def stats(self) -> dict[str, dict]:
        """Per camera: its state, and what was dropped past what the forwarder holds — kept to push again
        (`dropped`), and waiting between two pushes (`queue_dropped`); and how many times a pull found its centre restarted
        since the last — a batch may have gone with it (`holes`)."""
        return {ref: {"state": self.state.get(ref, ""), "dropped": self.dropped.get(ref, 0),
                      "queue_dropped": getattr(self.queues.get(ref), "dropped", 0), "holes": self.holes.get(ref, 0)}
                for ref in sorted(set(self.state) | set(self.queues) | set(self.pulled) | set(self.dropped) | set(self.holes))}

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
