"""The VMS's housekeeping for a subsystem whose work ENDS — the `vms jobs` process (`python3 -m vms jobs`).

A worker is the only participant that can know a job is finished: the plan and
the progress are files on the server it ran on, and its grant — its epochs, its
slot, its hold (`acl_worker_role`) — forbids it to write the row. The controller
must not either: its grant is placement and the assignments (`acl_controller`),
and a second writer of the row would collide exactly when the operator edits a
job that is finishing.

So `vms jobs` does it, with the console's grant of the families it touches, in a
pass of its own: it reads the workers' heartbeats and moves the row's `state` when
the worker holding the job says the work is over. One writer per row, and the
operator sees `done` in the row they created.

Why the state must be DURABLE and not simply read off the heartbeat, when the
placement predicate lands (Lesson 21): un-placing a finished job makes its worker
drop it, which makes the next heartbeat stop mentioning it, which makes the
evidence of `done` disappear — and the job is placed again, and scans the archive
from the top, for ever. A finished job has to be finished somewhere that does not
depend on its still being assigned.
"""
from __future__ import annotations

import json
import logging
import re
import time

from w2cplatform.requests import count_expired
from w2cplatform.rows import FIELDS, PARSE_ERRORS, Table, finite, number
from w2cplatform.spec import GARBLED_ROW, Refused, SpecController, take_written

TERMINAL = ("done", "failed")
# What a job's row may say, and what the worker's phase is allowed to move it to. The reaper mirrors the
# phase into the row not because the row is a better heartbeat — it is a worse one — but because the row is
# what SURVIVES the job being un-placed, and what the operator opened. `waiting`, `following` and `unsupported` are the
# worker's news and stay in the heartbeat: nothing downstream acts on them.
MIRRORED = ("fetching", "running") + TERMINAL
# How long a finished job's row stays after the reaper saw it end. Its events are in the archive under the
# archive's days and are found by `/events?unit=vms/<cam>`; the ROW is the operator's list of what ran, and a list that
# keeps every scan a scenario ever asked for is a list nobody can read. Three days is the window in which
# somebody asks "did last night's search finish" (the review's second pass).
FINISHED_RETENTION_SECONDS = 3 * 86400.0
log = logging.getLogger("vms.jobs")

# What expired before it was turned into work is counted with the platform's request family (`requests.count_expired`,
# `w2c_requests_expired_total` on this process's `/metrics`): a scenario said `fired` and nothing happened; climbing,
# the loop is late (the review's second pass).


# ONE REQUEST ROW THAT DOES NOT PARSE IS THAT REQUEST'S (the review's seventh pass, M2). `valid_until: "soon"` in one
# `rec/requests/*` row raised out of `record_on_request`, before the rows after it: for seventy-five minutes no
# recording was made on request for anybody and no finished one was ended (`expire_recordings` shared the call). The
# same in `detect_on_request`. A request whose deadline or numbers are not numbers — or are `nan`, `inf` — cannot be
# performed: nobody can say whether it is still meant. It is REFUSED, as a request that asks for nothing is: logged
# once, counted once (`REQUESTS`, `<sub>_console_rows_garbled{table="request"}` on `/metrics`) and cleared — a request
# is a moment's ask, not configuration, and one left standing would be refused again on every turn of the loop.
REQUESTS = Table("request", "refused and cleared: a request nobody can read cannot be performed")


def _deadline(it: dict) -> float:
    """A request's `valid_until`, 0 when it has none; a `ValueError` when it is not a finite number."""
    return finite(it.get("valid_until", 0) or 0)


# A number a heartbeat carries into one of these loops — `closed`, `hits`, a job's `from`/`to` in its status: read
# through `rows.number`, so one word in one recorder's heartbeat is that span's trouble, counted once (the review's
# seventh pass, part 2: one `closed: "7|then|now"` and no scan over arrived footage was made for any recorder).
def _hb_key(ctl, worker: str, field: str) -> str:
    return f"{ctl.sub.heartbeat_key(worker)}#{field}"


# The camera a recording NAME belongs to: its row's `cam` — alive, or a tombstone, which keeps it (`SpecController.
# create`: a name is never another camera's) — and, where no row of that name was ever written, the name itself: the
# tree a camera's footage had before recordings were rows (`vms/console.py`, `recordings_of`).
def recording_cam(vars_, name: str) -> str:
    from .config import REC_SPEC
    items, _ = vars_.get(REC_SPEC.sub.config(REC_SPEC.rows, str(name)))
    return str(items.get("cam") or name) if items else str(name)


# WHAT THE REQUEST LOOP REMEMBERS BETWEEN ITS TURNS (the scaling pass after the eighth review). The loop turns every two
# seconds (`__main__._requests_loop`), and each turn read every row of `rec/requests/` — the backfills a person asked
# for included, which are the recorder's and which it skips — and every recording and every detector, for their
# `until`: some 3 000 reads every two seconds at a thousand of each, 33 000 with ten scenarios firing (each request read
# the detectors and the recordings again). Inside a turn each key is read once now (`contract.one_pass`); across turns
# this keeps only what saves a read, never what a row says:
#
#   seen         the request rows a turn found to be the recorder's: not read again while they stay listed. Every
#                `REREAD` seconds the family is read whole, as every turn read it — a writer never files a scenario's
#                `record` under a backfill's id (`<unit>-<from>-<to>`, `asks-…`; a scenario's is `<firing>-<i>`), and the
#                whole read is what would notice if one did
#   retry_at     a request the store did not answer for (not a refusal: a conflict, a store away, a row over the
#                ceiling): tried again after a pause that doubles from two seconds to `RETRY_MAX`, not every turn — one
#                that has no `valid_until` was tried every two seconds for ever
#   deadlines    per subsystem, the rows that have an `until` and when: the rows are read whole every `REREAD` seconds,
#                and between those reads only a row whose `until` has come or is `NEAR` is read again — and ended
#                only if the row read then still says so.
#
# WHEN AN END TAKES EFFECT, said as it is (the eleventh review: the tenth's wording "an `until` this console writes is
# noted at once" was untrue for the console's DOOR — `until = now + 1` through it ended the recording 23 s later; only
# the loop's own writes were noted). Every row this PROCESS writes, through any controller of it, is read at the loop's
# next turn (`spec.take_written`). The console's door is another process since the boundary's step 6 — the platform's
# console — and what it writes is no note here: an end given there to a row whose end this loop has not seen takes
# effect at the next whole read, within `REREAD`; one that moves a remembered end is seen before anything is ended
# when it moves it LATER (the row is read), within a turn when the end it moves EARLIER is `NEAR`, else within
# `REREAD`.
class Remembered:
    REREAD = 30.0
    NEAR = 10.0                                         # seconds before a remembered end its row is read every turn
    RETRY_MAX = 300.0
    RETRY_FIRST = 2.0                                   # the first pause after a store that failed a request

    def __init__(self):
        self.seen: set[str] = set()
        self.retry_at: dict[str, tuple[float, float]] = {}      # key -> (when to try again, the pause that led there)
        self.deadlines: dict[str, dict[str, float]] = {}        # subsystem -> {unit id: until}
        self.read_at: dict[str, float] = {}                     # what was read whole -> when

    def due(self, what: str, now: float) -> bool:
        """Whether `what` is to be read whole this turn: first, and every `REREAD` seconds after."""
        at = self.read_at.get(what)
        return at is None or now - at >= self.REREAD or now < at

    def read_whole(self, what: str, now: float) -> None:
        self.read_at[what] = now

    def waits(self, key: str, now: float) -> bool:
        return key in self.retry_at and now < self.retry_at[key][0]

    def failed(self, key: str, now: float) -> None:
        pause = min(self.RETRY_MAX, 2 * self.retry_at[key][1]) if key in self.retry_at else self.RETRY_FIRST
        self.retry_at[key] = (now + pause, pause)

    def listed(self, prefix: str, keys) -> None:
        """What a family's listing holds now: what left it is forgotten."""
        keys = set(keys)
        self.seen = {k for k in self.seen if not k.startswith(prefix) or k in keys}
        for k in [k for k in self.retry_at if k.startswith(prefix) and k not in keys]:
            del self.retry_at[k]

    def note(self, sub: str, uid: str, until: float) -> None:
        self.deadlines.setdefault(sub, {})[str(uid)] = until


# "Record this camera for ten minutes" — a request turned into a row, by the one token that may write
# rows: the console's grant, which `vms jobs` holds. Run in its request loop, beside the reaper.
#
# The division is the same as everywhere and it is the reason this function is here rather than in the
# recorder or in the controller. A worker writes no configuration, and a recording IS configuration — it
# has an id, a retention, a home and a placement. The controller writes placement and not rows. What is
# left is the console's grant — the operator's agent — and a scenario asking for ten minutes of a camera is
# the operator asking through something they wrote.
#
# The row is named `<cam>-auto`, which is the naming rule the page already uses one field over: a camera
# recorded by hand and by a scenario has two recordings, two trees and two retentions, and neither
# surprises the other. A second request while it runs EXTENDS it — ten more minutes from now — instead of
# making `<cam>-auto-2`: the scenario meant "keep recording", not "record twice".
def record_on_request(rec_ctl, now: float, mem: Remembered | None = None) -> int:
    started = 0
    prefix = rec_ctl.sub.requests_prefix()
    keys = sorted(rec_ctl.vars.list(prefix))
    whole = mem is None or mem.due(prefix, now)
    if mem is not None:
        mem.listed(prefix, keys)
        if whole:
            mem.read_whole(prefix, now)
            mem.seen = {k for k in mem.seen if not k.startswith(prefix)}
    for key in keys:
        if mem is not None and ((not whole and key in mem.seen) or mem.waits(key, now)):
            continue                                        # the recorder's, seen already; or a pause after the store failed it
        it, _ = rec_ctl.vars.get(key)
        if not it or str(it.get("action", "")) != "record":
            if it and mem is not None:
                mem.seen.add(key)
            continue                                        # a backfill: the recorder's, not ours
        rid = key.rsplit("/", 1)[1]
        try:
            until, minutes = _deadline(it), finite(it.get("minutes", 0) or 0)
        except PARSE_ERRORS as e:
            REQUESTS.garbled(key, e)                        # refused, cleared: counted and said once
            rec_ctl.vars.delete(key)
            continue
        if until and now > until:
            rec_ctl.vars.delete(key)                        # asked for too late to mean what it meant
            count_expired(rec_ctl.spec.name)
            log.warning("%s: %s expired before it was turned into a recording", rec_ctl.spec.name, rid)
            continue
        cam = str(it.get("cam") or it.get("unit") or "")
        if not cam or minutes <= 0:
            rec_ctl.vars.delete(key)
            log.warning("%s: %s asks to record nothing: %s", rec_ctl.spec.name, rid, it)
            continue
        name, ends = f"{cam}-auto", now + minutes * 60
        try:
            row = rec_ctl.unit(name)                        # in the try: that recording's row garbled is this request's trouble
            if row is None:
                fields = {"name": name, "cam": cam, "until": ends}
                if it.get("archive"):
                    fields["home"] = str(it["archive"])
                rec_ctl.create(fields)
                started += 1
            elif number(f"{rec_ctl.sub.config(rec_ctl.spec.rows, name)}#until", row.get("until") or 0) < ends:
                rec_ctl.update(name, {"until": ends})       # keep recording, not record twice
                started += 1
            else:
                ends = None                                 # nothing written: the row's own `until` stands
            if mem is not None and ends is not None:
                mem.note(rec_ctl.spec.name, name, ends)     # its end, known without reading the row back
        except Refused as e:                                # a refusal is an answer, and it is ours to log
            log.warning("%s: %s refused for %s: %s", rec_ctl.spec.name, rid, name, e)
        except Exception as e:                              # noqa: BLE001
            # NOT an answer: the store conflicted, or did not answer at all. The request stays and the next
            # pass tries again — it carries `valid_until`, so it cannot wait for ever. It used to be deleted
            # here with the rest: the scenario fired, the recording was never made, and nothing said so
            # (the product's `RecordOnRequest`, feedback BC). Tried again after a pause that doubles (`Remembered`).
            log.warning("%s: %s could not start %s this pass: %s", rec_ctl.spec.name, rid, name, e)
            if mem is not None:
                mem.failed(key, now)
            continue
        rec_ctl.vars.delete(key)                            # performed or refused, it has nothing left to say
    return started


# …and the other end of it. A recording with an `until` in the past is over: the row goes, the controller
# unplaces it, the recorder stops the pipeline. The ordinary path for a recording somebody removed,
# reached by a clock instead of by a click.
#
# `until: 0` is every recording an operator made by hand, and this function never touches one.
#
# Any subsystem whose row has an `until` ends the same way — a detector asked for ten minutes too
# (`detect_on_request`) — so the function is the field's, not the recorder's.
#
# A row's `until` that is not a finite number is that row's (the seventh pass): skipped, counted (`rows.number`), and
# the rows after it still end — it raised out of here, and with it every recording due to end stayed recording.
#
# With `mem` (the request loop's, every two seconds) the rows are read whole every `Remembered.REREAD` seconds, and
# between those reads only a row whose remembered `until` has come or is near, and a row this process wrote since the
# last turn — read again, and ended on what it says then (`Remembered`, "when an end takes effect").
def expire(ctl, now: float, mem: Remembered | None = None) -> int:
    gone = 0
    sub = ctl.spec.name
    written = take_written(sub) if mem is not None else set()    # what this process wrote since the last turn
    if mem is None or mem.due(f"{sub}#until", now):
        rows = ctl.units()
        if mem is not None:
            mem.read_whole(f"{sub}#until", now)
            mem.deadlines[sub] = {}
    else:
        # Read again: a row whose remembered end has come; a row this process wrote since the last turn — an `until` given
        # through another controller of this process, the loop's memory never heard of it (the eleventh review: it ended
        # up to `REREAD` late); and a row whose remembered end is NEAR (`Remembered.NEAR`) — the console's door, another
        # process, that shortened it is seen in a turn, not in `REREAD`.
        mine = mem.deadlines.get(sub, {})
        due = sorted(set(u for u, until in mine.items() if until - now <= mem.NEAR) | written)
        rows = []
        for u in due:
            try:
                r = ctl.parsed_unit(ctl.spec.parse_id(u))
            except PARSE_ERRORS:
                continue                                    # a name that is no id of this subsystem: nothing to end
            if r is not None and r is not GARBLED_ROW:
                rows.append(r)
            mine.pop(u, None)                               # read again just now: what it says goes back in below
    for row in rows:
        until = number(f"{ctl.sub.config(ctl.spec.rows, str(row['id']))}#until", row.get("until") or 0)
        if until and now > until:
            ctl.delete(row["id"])
            gone += 1
            log.info("%s: %s reached its end", ctl.spec.name, row["id"])
        elif until and mem is not None:
            mem.note(sub, str(row["id"]), until)
    return gone


expire_recordings = expire                              # the name the recorder's callers know it by


# What automation asks the DETECTORS for: `det/requests/<id>`, turned into rows by `vms jobs`, beside
# `record_on_request` and for its reasons — a worker writes no configuration, and both answers are
# configuration. The recorder's family has two kinds of asking, and so does this one:
#
#   detect   {cam, kind, minutes}        the STREAM, from now: a detector row `<cam>-<kind>-auto` with an
#                                         `until`. A second request while it runs extends it. A camera whose
#                                         `kind` already runs by the operator's hand, with no end, is
#                                         watched already: a second model would count every car twice
#   scan     {cam, kind, before, after}  an INTERVAL around the moment the scenario fired — `at − before`
#                                         to `at + after`: a job of `detjob`. With `after` the interval
#                                         reaches into the future, and the job FOLLOWS the recording until
#                                         its end (`DetJobWorker`) — the archive as it is being written
#
# Two answers, two subsystems, ONE door — which is the whole of what the two have in common. The budgets stay
# apart (Lesson 21): a scan placed on a GPU is still placed against the scans that GPU will carry, never
# against its streams.
#
# The settings travel with the request, or — when it names none — are copied from a detector the operator
# made for the same camera and model: "the plates on camera 7" means the plates as camera 7 is set up for.
# A refusal is an answer and the request goes; a store that did not answer is not, and it stays.
DETECT_KEY = "-auto"
SCAN_BEFORE, SCAN_AFTER = 60.0, 60.0


def detect_on_request(det_ctl, job_ctl, rec_ctl, now: float, mem: Remembered | None = None) -> int:
    made = 0
    prefix = det_ctl.sub.requests_prefix()
    keys = sorted(det_ctl.vars.list(prefix))
    if mem is not None:
        mem.listed(prefix, keys)
    for key in keys:
        if mem is not None and mem.waits(key, now):
            continue                                        # a pause after the store failed it (`Remembered`)
        it, _ = det_ctl.vars.get(key)
        rid = key.rsplit("/", 1)[1]
        if not it:
            continue
        action = str(it.get("action", ""))
        try:
            until = _deadline(it)
            for f in ("minutes", "at", "before", "after"):  # the request's own numbers, checked here: a row of a detector
                if it.get(f) not in (None, ""):              # or a recording that does not parse is not THIS request's word
                    finite(it[f])
        except PARSE_ERRORS as e:
            REQUESTS.garbled(key, e)                        # refused, cleared: counted and said once
            det_ctl.vars.delete(key)
            continue
        if until and now > until:
            det_ctl.vars.delete(key)                        # asked for too late to mean what it meant
            count_expired(det_ctl.spec.name)
            log.warning("%s: %s expired before it was turned into work", det_ctl.spec.name, rid)
            continue
        cam, kind = str(it.get("cam") or ""), str(it.get("kind") or "")
        try:
            if not cam or not kind or action not in ("detect", "scan"):
                raise Refused(f"a request names a camera, a model and detect|scan: {dict(it)}")
            same = _settings(det_ctl, cam, kind, it)
            made += _detect(det_ctl, cam, kind, it, same, now, mem) if action == "detect" else \
                _scan(job_ctl, rec_ctl, cam, kind, it, same, now)
        except Refused as e:                                # a refusal is an answer, and it is ours to log
            log.warning("%s: %s refused: %s", det_ctl.spec.name, rid, e)
        except Exception as e:                              # noqa: BLE001 — not an answer: stays, and is tried again
            log.warning("%s: %s could not be turned into work this pass: %s", det_ctl.spec.name, rid, e)
            if mem is not None:
                mem.failed(key, now)                        # …after a pause that doubles, not on every turn
            continue
        det_ctl.vars.delete(key)                            # performed or refused, it has nothing left to say
    return made


# What the standing detector of this camera and model is set up with — its params, its mask, its labels — and the
# request's own `params` over them. A request that brought params used to bring ONLY them (the review's third
# pass, Н-m7): the mask and the labels stayed behind, and the scenario's detector watched the whole frame on
# whatever worker came first, gpu or not.
def _settings(det_ctl, cam: str, kind: str, it: dict) -> dict:
    out = {}
    for d in sorted(det_ctl.units(), key=lambda d: str(d["id"])):
        if str(d.get("cam")) == cam and str(d.get("kind")) == kind and not str(d["id"]).endswith(DETECT_KEY):
            out = {f: d[f] for f in ("params", "mask", "labels") if d.get(f)}
            break
    if it.get("params"):
        out["params"] = it["params"]
    return out


def _detect(det_ctl, cam: str, kind: str, it: dict, same: dict, now: float, mem: Remembered | None = None) -> int:
    minutes = finite(it.get("minutes", 0) or 0)
    if minutes <= 0:
        raise Refused(f"detect asks for no minutes: {dict(it)}")
    for d in det_ctl.units():
        if str(d.get("cam")) == cam and str(d.get("kind")) == kind and d.get("enabled", True) \
                and not number(f"{det_ctl.sub.config(det_ctl.spec.rows, str(d['id']))}#until", d.get("until") or 0):
            log.info("%s: camera %s is watched for %s already (%s) — nothing to start", det_ctl.spec.name, cam, kind, d["id"])
            return 0
    name, ends = f"{cam}-{kind}{DETECT_KEY}", now + minutes * 60
    row = det_ctl.unit(name)
    if row is None:
        det_ctl.create({"name": name, "cam": cam, "kind": kind, "until": ends, **same})
    elif number(f"{det_ctl.sub.config(det_ctl.spec.rows, name)}#until", row.get("until") or 0) < ends:
        det_ctl.update(name, {"until": ends})               # keep watching, not watch twice
    else:
        return 0
    if mem is not None:
        mem.note(det_ctl.spec.name, name, ends)             # its end, known without reading the row back
    return 1


def _scan(job_ctl, rec_ctl, cam: str, kind: str, it: dict, same: dict, now: float) -> int:
    at = finite(it.get("at", 0) or now)
    before = finite(it.get("before", SCAN_BEFORE) or 0)
    after = finite(it.get("after", SCAN_AFTER) or 0)
    t0, t1 = at - before, at + after
    if t1 <= t0:
        raise Refused(f"scan asks for an empty interval: before {before}, after {after}")
    rec = str(it.get("rec") or "")
    if not rec:
        recs = sorted(str(r["id"]) for r in rec_ctl.units() if str(r.get("cam", r["id"])) == cam)
        rec = cam if cam in recs else (recs[0] if recs else "")
    if not rec or rec_ctl.unit(rec) is None:
        raise Refused(f"nothing records camera {cam}: a scan reads the archive, and there is none to read")
    # A request's `rec` is another camera's: not this camera's scan — refused before a job of this camera is widened by
    # it (the platform refuses the row the same way, `must_match` in detjob.subsystem.yaml, the review's fifth pass).
    if str((rec_ctl.unit(rec) or {}).get("cam") or "") != cam:
        raise Refused(f"recording {rec} is camera {(rec_ctl.unit(rec) or {}).get('cam')}'s, not camera {cam}'s: a scan "
                      f"reads the footage of the camera it names")
    # One job per (recording, model) at a time, not one per firing (the review's second pass). A swaying camera
    # fires every second, and every firing used to be a two-minute job of its own: each second scanned a dozen
    # times, thousands of rows a day, both of a worker's places taken by the same minute. A request whose
    # interval overlaps or touches a job of the same recording and model that has not ended WIDENS that job to
    # the union of the two; the worker re-plans from the row every pass, so the new minutes are simply more
    # stretches, and a `done` it said about the old shape is not believed (`reap`).
    for j in job_ctl.units():
        if str(j.get("rec")) != rec or str(j.get("kind")) != kind or str(j.get("state", "")) in TERMINAL:
            continue
        if j["from"] <= t1 and t0 <= j["to"]:
            wider = {f: v for f, v in (("from", min(j["from"], t0)), ("to", max(j["to"], t1))) if v != j[f]}
            if not wider:
                return 0                                    # inside a job that is already asked for
            job_ctl.update(j["id"], wider)
            log.info("%s: %s widened to [%.0f, %.0f) — a scenario asked again", job_ctl.spec.name, j["id"],
                     wider.get("from", j["from"]), wider.get("to", j["to"]))
            return 1
    jid = f"{rec}-{kind}-{int(t0)}-{int(t1)}"
    if job_ctl.vars.get(job_ctl.sub.config(job_ctl.spec.rows, jid))[0]:
        return 0                                            # made already, or deleted on purpose
    job_ctl.create({"name": jid, "cam": cam, "rec": rec, "kind": kind, "from": t0, "to": t1,
                    **{k: v for k, v in same.items() if k in ("params", "mask", "labels")}})
    log.info("%s: scanning %s [%.0f, %.0f) with %s — a scenario asked", job_ctl.spec.name, rec, t0, t1, kind)
    return 1


# One pass: `{done: n, failed: n}` — how many rows this pass moved.
#
# Only the worker the CONTROLLER placed the job on is believed. A heartbeat object outlives its worker,
# so a slot that finished this job yesterday, before it was moved to another server, still says `done`
# in the store; taking that at face value would end a scan that is running right now, somewhere else,
# from the beginning.
def reap(ctl) -> dict:
    moved = {"done": 0, "failed": 0}
    placed: dict[str, str] = {}
    state: dict[str, str] = {}
    ends: dict[str, float] = {}
    # Every number here is read through `rows.number` (the review's seventh pass, part 2): a row's `to`, and what a
    # worker's heartbeat says of a job — one word in one of them raised out of the reaper, and no job of the family was
    # moved to `done`, every thirty seconds.
    for row in ctl.units():
        if str(row.get("state", "")) in TERMINAL:
            continue                                        # already moved; the predicate un-places it, not us
        state[str(row["id"])] = str(row.get("state", ""))
        ends[str(row["id"])] = number(f"{ctl.sub.config(ctl.spec.rows, str(row['id']))}#to", row.get("to") or 0)
        p = ctl.placement(row["id"])
        if p is not None:
            placed[str(row["id"])] = p.worker
    for st in ctl.read_model():
        uid, phase = str(st.get("id")), str(st.get("phase", ""))
        if phase not in MIRRORED or placed.get(uid) != st.get("worker"):
            continue
        if str(state.get(uid, "")) == phase:
            continue                                        # already says it: a row that moves every pass is a
                                                            # revision that moves every pass, for every reader downstream
        said = lambda field, kind=float: number(_hb_key(ctl, str(st.get("worker")), f"{uid}.{field}"), st.get(field), kind)
        if phase in TERMINAL and "to" in st and number(_hb_key(ctl, str(st.get("worker")), f"{uid}.to"), st["to"], float, None) != ends.get(uid):
            continue                                        # finished an OLDER shape of the row: a scenario widened it
                                                            # since (`_scan`), and the worker has not seen the new end
        fields = {"state": phase}
        if phase in TERMINAL:
            fields["ended"] = ctl.wall()                    # when it was SEEN to end — `to` is media time, and a
                                                            # search over last month ends today (`forget_finished`)
        ctl.update(uid, fields)
        if phase in TERMINAL:
            moved[phase] += 1
            log.info("%s %s: %s (%.0f s of footage, %d event(s))", ctl.spec.name, uid, phase,
                     said("covered"), said("events", int))
    return moved


# The other end of a job's row: finished for longer than `FINISHED_RETENTION_SECONDS`, it goes. Until this the
# rows of finished scans were never removed by anything (the review's second pass), and a scenario firing
# all night left the operator a list of hundreds of `done`. The events stay — they are the archive's, under
# its days — and the row is marked rather than removed, as every deleted row is: `_scan` and
# `scan_what_arrived` read the mark as "made already, or deleted on purpose", and a request that names the
# same interval again is not turned into the same job a second time.
#
# A row finished before `ended` was written has none; its `to` stands in — the shape the review named,
# three days past the interval's end.
def forget_finished(ctl, now: float) -> int:
    gone = 0
    for row in ctl.units():
        if str(row.get("state", "")) not in TERMINAL:
            continue
        at = ctl.sub.config(ctl.spec.rows, str(row["id"]))
        ended = number(f"{at}#ended", row.get("ended") or 0) or number(f"{at}#to", row.get("to") or 0)
        if not ended:
            continue                                        # when it ended is not known (`rows.number`): not "long ago"
        if now - ended > FINISHED_RETENTION_SECONDS:
            ctl.delete(row["id"])
            gone += 1
            log.info("%s: %s finished %.0f days ago — forgotten", ctl.spec.name, row["id"], (now - ended) / 86400)
    return gone


# A job that cannot run because the footage is still on the device: ask the recorder for it.
#
# The scan does NOT read the device itself, and that is the design and not a shortcut. The playback door
# admits two sessions per device (М10B Lesson 15), and those two belong to the operator watching the gap
# and to the recorder saving it; a scan is exactly the greedy third. Worse, a card keeps three days: a
# search that races the device's own retention can find a car whose evidence is gone by the time anyone
# clicks. So the range is fetched ONCE, into our archive, with our epoch and our retention — and the scan
# then runs over footage we own, with `vms/scan.py` unchanged.
#
# The request id is the range, so a job asking every thirty seconds writes one row, not a queue.
#
# FILED AS THE PLATFORM'S REQUEST FAMILY FILES ONE (М10A 14): the unit as `rec/<recording>`, and a deadline —
# `valid_until`, `FETCH_WAIT` away (never past the spec's `most_valid` where it says one; `rec`'s family is `free` and
# says none, so the deadline is the job's: how long it waits for a recorder to begin). A recorder that has not
# begun it by then answers it expired and the reaper ends the row; a job still fetching asks again on its next turn,
# and the recorder goes on from the first moment its volume does not show (`RecWorker.requests`).
#
# NOT A WORKER'S FILING (ADR-0013): the scan's worker only says `fetching` in its heartbeat — its spec names no
# `worker.requests` and its grant reaches no `rec/requests/*`. This is the VMS's housekeeping, filing with the
# console's grant through rec's controller, as an operator's console does; a worker files only by `Worker.file_request`.
FETCH_WAIT = 600.0


def _ask_recorder(rec_ctl, unit: str, cam: str, t0: float, t1: float, now: float, by: str) -> bool:
    from w2cplatform.canonical import number_text
    from w2cplatform.doors import unit_ref
    key = rec_ctl.sub.request_key(f"{unit}-{int(t0)}-{int(t1)}")
    if rec_ctl.vars.get(key)[0]:
        return False                                    # already asked; the recorder says when it is fetched
    most = min(FETCH_WAIT, float(rec_ctl.spec.requests.get("most_valid", FETCH_WAIT)))
    rec_ctl.vars.put(key, {"unit": unit_ref(rec_ctl.spec.name, unit), "cam": cam, "from": number_text(t0),
                           "to": number_text(t1), "at": number_text(now), "by": by,
                           "valid_until": number_text(now + most)})            # numbers by the platform's one rule
    return True


def ask_for_footage(job_ctl, rec_ctl) -> int:
    asked = 0
    for st in job_ctl.read_model():
        if str(st.get("phase", "")) != "fetching":
            continue
        hk = _hb_key(job_ctl, str(st.get("worker")), str(st.get("id")))
        unit, t0, t1 = str(st.get("rec", "")), number(f"{hk}.from", st.get("from", 0), float, None), number(f"{hk}.to", st.get("to", 0), float, None)
        if not unit or t0 is None or t1 is None or t1 <= t0:          # an end that is a word: not a range to ask for
            continue
        if not _ask_recorder(rec_ctl, unit, str(st.get("cam", unit)), t0, t1, job_ctl.wall(),
                             f"{job_ctl.spec.name}/{st.get('id')}"):
            continue
        asked += 1
        log.info("%s %s: asking the recorder for %s [%.0f, %.0f)", job_ctl.spec.name, st.get("id"), unit, t0, t1)
    return asked


# THE SPANS A HEARTBEAT LISTS — `<name>|<from>|<to>,…` — AND THE ONE COUNT FOR THEM (the eighth review's minor, not fixed
# until the ninth): each end was read through `rows.number` under a key that held the span's TEXT, so a recorder whose
# `closed` kept a word in it counted a new garbled "row" every time the list moved — 8640 a day from one heartbeat
# field. The field is the row: one key per heartbeat and field (`<heartbeat>#closed`), garbled once while any of its
# spans does not read, parsed again when none is left. A span that does not read is passed by; the others are work.
def _spans(key: str, said) -> list[tuple[str, float, float]]:
    out, bad = [], None
    for span in str(said or "").split(","):
        parts = span.split("|")
        if len(parts) != 3:
            continue
        try:
            out.append((parts[0], finite(parts[1]), finite(parts[2])))
        except PARSE_ERRORS as e:
            bad = bad or e
    if bad is not None:
        FIELDS.garbled(key, bad)
    else:
        FIELDS.parsed(key)
    return out


# What the recorder just fetched from a device is a hole in the DETECTIONS too: nothing was watching the
# camera while nothing was recording it. This closes the second hole with the first.
#
# One scan per (range × detector), because "no hole" means every model that runs live on that camera also
# ran over those minutes — and with the SAME settings, so `params` and `mask` are copied from the detector's
# own row rather than re-entered.
#
# The id is the range and the detector, so the pass is idempotent by construction: the recorder keeps
# reporting a range for as long as it stays in its window, and the second pass finds the row already there.
# A row an operator DELETED stays deleted — the marker outlives the row, which is what `vars.get` sees and
# `unit()` does not.
def scan_what_arrived(rec_ctl, det_ctl, job_ctl) -> int:
    from w2cplatform.console import heartbeats
    made = 0
    for w, hb in heartbeats(rec_ctl.objects, rec_ctl.spec.name + "/").items():
        for unit, t0, t1 in _spans(_hb_key(rec_ctl, w, "closed"), hb.extra.get("closed", "")):
            try:
                rec = rec_ctl.unit(unit)
            except PARSE_ERRORS:
                continue                                    # that recording's row does not parse: its span waits for it
            if rec is None or t1 <= t0:
                continue
            cam = str(rec.get("cam", unit))
            for d in det_ctl.units():
                if str(d.get("cam", "")) != cam or not d.get("enabled", True):
                    continue
                jid = f"{unit}-{d['kind']}-{int(t0)}-{int(t1)}"
                if job_ctl.vars.get(job_ctl.sub.config(job_ctl.spec.rows, jid))[0]:
                    continue                                # made already, or deleted on purpose
                body = {"name": jid, "cam": cam, "rec": unit, "kind": str(d["kind"]),
                        "from": t0, "to": t1}
                for f in ("params", "mask", "labels"):      # the same settings — and the same place — the live detector runs with
                    if d.get(f):
                        body[f] = d[f]
                job_ctl.create(body)
                made += 1
                log.info("%s: scanning %s [%.0f, %.0f) with %s — the footage arrived from a device",
                         job_ctl.spec.name, unit, t0, t1, d["kind"])
    return made


# The fourth way to use a device archive: watch everything, keep what a model liked.
#
# The survey reports the stretches; this turns them into the request the recorder already understands. The
# same division as everywhere here — the worker knows and may not write, `vms jobs` writes — and the same
# reason the request's id is the range: a pass every thirty seconds must write one row, not a queue.
#
# What lands in `rec/<cam>/` this way is ordinary footage with the ordinary retention, and that is the
# point rather than an omission: when only the interesting minutes are copied, everything on the server is
# interesting, and "evidence" needs no second archive and no second lifetime.
def keep_what_fired(survey_ctl, rec_ctl) -> int:
    from w2cplatform.console import heartbeats
    asked = 0
    for w, hb in heartbeats(survey_ctl.objects, survey_ctl.spec.name + "/").items():
        for cam, t0, t1 in _spans(_hb_key(survey_ctl, w, "hits"), hb.extra.get("hits", "")):
            if t1 <= t0:
                continue
            unit = next((str(r["id"]) for r in rec_ctl.units() if str(r.get("cam", r["id"])) == cam), None)
            if unit is None:
                continue                                # nothing on this server records that camera: nowhere to put it
            if not _ask_recorder(rec_ctl, unit, cam, t0, t1, survey_ctl.wall(), f"{survey_ctl.spec.name}/{cam}"):
                continue
            asked += 1
            log.info("%s: keeping %s [%.0f, %.0f) — a model liked it", survey_ctl.spec.name, unit, t0, t1)
    return asked


# THE SEAL OF A KEEP, SET ONCE (ADR-0057, addendum p. 3; the product's `SealKeeps` in vms/keeps.go). A keep is evidence,
# and the question asked of evidence is whether it is what it was. The recorder holding the incidents volume says, per
# keep, the digest of each recording's copy (`sha256`) and which copies are WHOLE (`whole`: held, and short of nothing
# a source has) in its heartbeat (`RecWorker.keep_pass`). The first time a recording's copy is whole, this pass writes
# that digest into the keep's row — `sealed: [<recording>=<sha256>, …]`, `sealed_at` — and never again for that
# recording: a seal that moved with every pass, or aged out with an event, would vouch for whatever the volume holds
# now. The row is written with the console's grant, which no recorder has, so the archive that holds the footage is not
# the one that vouches for it; the copy is compared with the seal at that recorder's door (`RecWorker.verify_keep`).
# Each seal is a line `archive.keep.sealed` in this process's journal. Written by CAS on the row as read: somebody who
# wrote it meanwhile wins, and the next turn seals. A keep whose interval does not read is sealed never — nothing of it
# is copied (`keeps.as_far_as_read`). Returns how many recordings were sealed.
#
# What it does not cover, as in the product: the footage before the copy was whole, and somebody who can write both the
# incidents volume and the store.
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def seal_keeps(rec_ctl, now: float, journal=None, lost_after: float = 45.0) -> int:
    from w2cplatform.console import heard_live, heartbeats
    from w2cplatform.variables import Conflict
    from . import keeps
    said: dict[str, dict[str, str]] = {}
    for w, hb in heartbeats(rec_ctl.objects, rec_ctl.spec.name + "/").items():
        if not heard_live(rec_ctl.spec.name, w, hb, now, lost_after, getattr(rec_ctl, "eyes", None)):
            continue                                 # a silent recorder's last word is not what its volume holds now
        by = hb.extra.get("keeps")
        for kid, st in (by.items() if isinstance(by, dict) else ()):
            sums, whole = (st.get("sha256"), st.get("whole")) if isinstance(st, dict) else (None, None)
            if not isinstance(sums, dict) or not isinstance(whole, list):
                continue
            for rec in whole:
                digest = sums.get(rec)
                if isinstance(digest, str) and _SHA256.match(digest):
                    said.setdefault(str(kid), {})[str(rec)] = digest
    sealed = 0
    for kid, sums in sorted(said.items()):
        path = keeps.key(kid)
        try:
            items, idx = rec_ctl.vars.get(path)
            k = keeps.Keep.from_items(kid, items) if isinstance(items, dict) and items else None
        except (OSError, *PARSE_ERRORS):
            continue                                 # not read, or its interval does not read: nothing to vouch for
        if k is None or not k.since < k.until:
            continue                                 # lifted meanwhile, or an interval that ends before it starts
        have = k.seals()
        fresh = {rec: d for rec, d in sums.items() if rec not in have}
        if not fresh:
            continue
        # the spec's list form (`Field.to_item`, the product's `p.JoinNames`): a unit's name holds no `,` (`unnamable`)
        row = {**items, "sealed": ",".join(f"{r}={d}" for r, d in sorted({**have, **fresh}.items())),
               "sealed_at": f"{now:.3f}"}
        try:
            rec_ctl.vars.put(path, row, cas=idx)
        except (Conflict, OSError) as e:
            log.info("keep %s: not sealed this turn (%s): the next turn seals", kid, e)
            continue
        for rec, digest in sorted(fresh.items()):
            if journal is not None:
                journal.say("archive.keep.sealed", keep=kid, cam=k.cam, recording=rec, sha256=digest,
                            **{"from": k.since, "to": k.until})
            sealed += 1
    return sealed
