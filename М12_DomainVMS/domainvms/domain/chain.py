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
import threading

from .federation import Unreachable
from .tokens import kid_of
from .uplink import REPORTED, UPLINK, base

from .agent import UPSTREAM_PATH       # in a recording cluster: where its streams go up, or come down from (star)


# -- the domain's side: the book of a recording cluster's upstream ----------------------------------------
# For every camera a cluster records, the centre's ingest and a token to push to it — or, for a star relay,
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
    # Every camera a relay records — and every camera that only POLLS a relay (nobody records it, and it
    # reaches only that relay, Lesson 16 step 8): the centre must have a road down to it too, for asks, and for
    # a viewer in the centre, whose want the relay's forwarder carries down like any other.
    polled = {ref: crossings._poll_home(home) for ref, home in crossings.unrecorded().items()}
    for ref, on in [*crossings.all().items(), *((r, o) for r, o in polled.items() if o and o != centre)]:
        if on == centre:
            continue
        mode = "pull" if on in star else "push"
        have, _ = crossings.vars.get(f"{UPSTREAM_PATH}/{on}")
        old = json.loads((have or {}).get(ref, "{}"))
        if old.get("urls") == urls and old.get("mode") == mode and float(old.get("until", 0)) - now > lifetime / 2 \
                and kid_of(old.get("token", "")) == crossings.issuer.kid:
            entry = old
        else:
            entry = {"urls": urls, "mode": mode, "until": now + lifetime,
                     "token": crossings.issuer.issue(on, lifetime, now=now, aud=audience(centre), ref=ref, kind="stream")}
        books.setdefault(on, {})[ref] = json.dumps(entry, sort_keys=True)
    for on, book in books.items():
        path = f"{UPSTREAM_PATH}/{on}"
        have, idx = crossings.vars.get(path)
        if have != book:
            crossings.vars.put(path, book, cas=idx)
    return books


# -- the relay's side: the forwarder ------------------------------------------------------------------------
# One pass. For every camera in this cluster's upstream book: PUSH mode — poll the centre's ingest; if it wants
# the stream, want it here too (that is the want travelling down to the camera) and push up what arrived;
# upload any range the centre asked for, out of this cluster's archive; carry down any ask left there for the camera
# and carry its outcome back up. PULL mode (the star) — this cluster
# wants the stream for its own recorder: pull it from the centre and inject it here.
class Forwarder:
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
        # with the failure (`unsent`, a stream: past `PEER_BUFFER` frames it is cut clean to a keyframe, counted in
        # `dropped`); and a pull remembers the last batch it got (`pulled`), so the centre hands a batch whose answer
        # was lost on its way down over again (`Ingest.pull`).
        self.unsent: dict[str, list] = {}
        self.dropped: dict[str, int] = {}
        self.pulled: dict[str, int] = {}
        self._lock = threading.RLock()
        self.woken = threading.Event()                           # set by the local ingest: something changed here
        self.pending = threading.Event()                         # set when an ask went up: an outcome to wait for
        local.listen(self.woken.set)

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
            try:                                                # one camera's centre that stopped answering is that
                if e["mode"] == "pull":                         # camera's, not the end of the pass (the seventh review)
                    self.state[ref] = self._pull(ing, ref, e)
                else:
                    self.state[ref] = self._push(ing, ref, e)
            except Unreachable as err:
                self.state[ref] = f"the centre stopped answering: {err}"
        return dict(self.state)

    def _push(self, ing, ref: str, e: dict, wait: float = 0.0) -> str:
        work = ing.poll(e["token"], ref, version=self.versions.get(ref) if wait else None, wait=wait)
        self.versions[ref], self.forwarding[ref] = work["version"], work["push"]
        if work["push"]:
            self.local.want(ref, self.up)                       # the centre wants it: so do we, from the camera
            q = self.queues.setdefault(ref, self.local.subscribe(ref, self.up))
            frames = self.unsent.pop(ref, []) + q.drain()       # what the centre did not take last time, first
            if frames:
                try:
                    ing.push(e["token"], ref, frames)
                except Unreachable:
                    self.unsent[ref] = self._kept(ref, frames)
                    raise
            said = f"forwarding {len(frames)} frame(s) up"
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
                ing.upload(e["token"], ref, rid, [], failed=str(err))
                continue
            ing.upload(e["token"], ref, rid, frames)                     # the answer to that request (AD)
        for aid, a in work.get("asks", {}).items():                     # an ask left above: down it goes…
            with self._lock:
                self.carried.setdefault((ref, aid), (ing, e["token"], float(a["deadline"])))
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
        from .ingest import ASKS_PATH
        items, _ = self.vars.get(ASKS_PATH)
        return {k: json.loads(v) for k, v in (items or {}).items() if "|" in k}

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
                                sent = (c, c.ask(road["token"], a["target"], a["action"], a["deadline"]))
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
                    stop.wait(period)
                    continue
                try:
                    streaming = self.forwarding.get(ref, False)
                    self.state[ref] = self._push(ing, ref, e, wait=0.0 if streaming else period)
                    if streaming:
                        stop.wait(stream_every)
                except Unreachable:
                    stop.wait(period)

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
                    stop.wait(period)
                self.woken.set()                                         # settle it: `lift` does

        started = [threading.Thread(target=asks, daemon=True, name=f"fwd-asks-{self.name}"),
                   threading.Thread(target=outcomes, daemon=True, name=f"fwd-outcomes-{self.name}")]
        for t in started:
            t.start()
        self.woken.set()
        return started

    def _kept(self, ref: str, frames: list) -> list:
        """What is kept to push again: a stream, so at most `PEER_BUFFER` frames, from a keyframe — the rest dropped,
        counted, as a peer that falls behind is cut (`PeerLink`)."""
        from .ingest import PEER_BUFFER, _is_key
        if len(frames) <= PEER_BUFFER:
            return frames
        kept = frames[-PEER_BUFFER:]
        while kept and not _is_key(kept[0]):
            kept.pop(0)
        self.dropped[ref] = self.dropped.get(ref, 0) + len(frames) - len(kept)
        return kept

    def _pull(self, ing, ref: str, e: dict) -> str:
        if not self.needs(ref) and not self.local.wanted(ref):
            return "nobody here wants it"
        # calling in; the centre wants it from the camera — and says which batch it last GOT: a pull whose answer was
        # lost on the way down is answered with that batch again, first
        frames = ing.pull(e["token"], ref, self.up, have=self.pulled.get(ref, 0))
        self.pulled[ref] = getattr(frames, "seq", 0)
        self.local.inject(ref, frames)
        return f"pulled {len(frames)} frame(s) down"


# -- the summary report ------------------------------------------------------------------------------------
# The relay carries its cameras' reports as ONE object in the domain holder. Cameras report to the RELAY's
# object store (the relay is reachable from its sites — that is the whole premise of this layout); the
# relay's agent folds what is there into `domain/members/<relay>/bundle`, only when it changed.
BUNDLE = "bundle"


def bundle(relay: str, members: list[str], relay_objects, domain_objects) -> bool:
    out: dict[str, dict[str, str]] = {}
    for m in members:
        b = base(m)
        keys = relay_objects.list(b)
        if keys:
            out[m] = {k[len(b):]: relay_objects.get(k).decode("utf-8", "surrogateescape") for k in keys}
    raw = json.dumps(out, sort_keys=True).encode()
    key = base(relay) + BUNDLE
    if domain_objects.get(key) == raw:
        return False
    domain_objects.put(key, raw)
    return True


class BundleView:
    """The domain holder's store as a member reporting through `relay` sees it: its report, out of the
    relay's bundle. Read only; what `member_copy(..., via=relay)` reads through."""

    def __init__(self, relay: str, domain_objects):
        self.relay, self.store = relay, domain_objects

    def _entries(self, member: str) -> dict[str, str]:
        raw = self.store.get(base(self.relay) + BUNDLE)
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


# -- the relay: a cluster as its cameras' road to the domain ---------------------------------------------
# What the domain leaves for a member, as its agent reads it (`DomainAgent.sync`): named once here, so the
# relay carries exactly that and a camera's agent needs no other code.
RELAY = "relay/"
RELAY_SEEN = "relay/domain/seen"


def _relayed_rows(member: str) -> list[str]:
    from .agent import GRANTS_PATH, KEYS_PATH, PER_CLUSTER, REVOKED_PATH
    from .pending import PENDING_PATH
    from .shared import POINTER
    from .term import BACKUP, HOLDER
    return [KEYS_PATH, REVOKED_PATH, HOLDER, POINTER, f"{GRANTS_PATH}/{member}", f"{PENDING_PATH}/{member}",
            f"{BACKUP}/{member}", *[f"{p}/{member}" for p in PER_CLUSTER]]


def relay_down(members: list[str], domain_vars, domain_objects, relay_vars, relay_objects, now: float) -> int:
    """One pass of relaying down, after the relay's agent has reached the domain. Copies each row a member's agent
    would read, and the object a pointer names (shared settings, backup), into `relay/`; only what changed.
    How current it all is, the relay says on every pass of its own, reached or not (`say_seen`)."""
    written, seen = 0, set()
    for m in members:
        for path in _relayed_rows(m):
            if path in seen:
                continue
            seen.add(path)
            items, _ = domain_vars.get(path)
            have, idx = relay_vars.get(RELAY + path)
            if items is None and have is None:
                continue
            items = dict(items or {})
            if have != items:
                relay_vars.put(RELAY + path, items, cas=idx)
                written += 1
            obj = items.get("object") if isinstance(items, dict) else None
            if obj and domain_objects is not None:
                raw = domain_objects.get(obj)
                if raw is not None and relay_objects.get(RELAY + obj) != raw:
                    relay_objects.put(RELAY + obj, raw)
                    written += 1
    return written


# How current the relayed books are — an AGE, measured on the relay's clock: how long ago the relay last
# reached the domain, said on every relay pass, the failed ones above all, with a counter. The camera takes a
# new counter as "said just now" and sets its own mark to ITS clock minus the age: two clocks never compared,
# and the error is at most one camera pass (feedback AM — the product sends the same age in its exchange).
def say_seen(relay_objects, last_contact: float | None, now: float) -> dict:
    raw = relay_objects.get(RELAY_SEEN)
    n = int(json.loads(raw).get("n", 0)) + 1 if raw else 1
    mark = {"n": n, "age": None if last_contact is None else max(0.0, now - last_contact)}
    relay_objects.put(RELAY_SEEN, json.dumps(mark).encode())
    return mark


class Relay:
    """What a camera that can reach only its relay uses in place of the domain: `vars` and `objects` over the
    relay's `relay/` copy — its reports go into the relay's store as they are — and `seen()`, how long ago the
    RELAY last reached the domain (`say_seen`), which is how current the camera's books are."""

    def __init__(self, relay_vars, relay_objects):
        self.vars = _RelayVars(relay_vars, relay_objects)
        self.objects = _RelayObjects(relay_objects)


class _RelayVars:
    def __init__(self, relay_vars, relay_objects):
        self.relay_vars, self.relay_objects = relay_vars, relay_objects

    def get(self, path):
        return self.relay_vars.get(RELAY + path)

    def list(self, prefix):
        return [k[len(RELAY):] for k in self.relay_vars.list(RELAY + prefix)]

    def seen(self) -> dict | None:
        raw = self.relay_objects.get(RELAY_SEEN)
        return json.loads(raw) if raw else None


class _RelayObjects:
    """Documents from the relay; the member's own report straight into the relay's store."""

    def __init__(self, relay_objects):
        self.relay = relay_objects

    def _key(self, key: str) -> str:
        return key if key.startswith(UPLINK + "/") else RELAY + key

    def get(self, key):
        return self.relay.get(self._key(key))

    def list(self, prefix):
        return self.relay.list(prefix) if prefix.startswith(UPLINK + "/") else \
            [k[len(RELAY):] for k in self.relay.list(RELAY + prefix)]

    def put(self, key, data):
        return self.relay.put(key, data)

    def delete(self, key):
        return self.relay.delete(key)
