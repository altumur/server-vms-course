"""The console's side of a subsystem whose work ENDS.

A worker is the only participant that can know a job is finished: the plan and
the progress are files on the server it ran on, and its ACL —
`[<name>/epoch/*, <name>/slots/*]` — forbids it to write the row. A controller
could write it (its grant is `<name>/*`), but then one row has two writers and
they collide exactly when the operator edits a job the controller is finishing.

So the console does it, in a pass of its own beside the blob sweep: it reads the
heartbeats it already reads, and moves the row's `state` when the worker holding
the job says the work is over. One writer per row, and the operator sees `done`
in the row they created.

Why the state must be DURABLE and not simply read off the heartbeat, when the
placement predicate lands (Lesson 21): un-placing a finished job makes its worker
drop it, which makes the next heartbeat stop mentioning it, which makes the
evidence of `done` disappear — and the job is placed again, and scans the archive
from the top, for ever. A finished job has to be finished somewhere that does not
depend on its still being assigned.
"""
from __future__ import annotations

import logging

from w2cplatform.spec import Refused

TERMINAL = ("done", "failed")
# What a job's row may say, and what the worker's phase is allowed to move it to. The console mirrors the
# phase into the row not because the row is a better heartbeat — it is a worse one — but because the row is
# what SURVIVES the job being un-placed, and what the operator opened. `waiting`, `following` and `unsupported` are the
# worker's news and stay in the heartbeat: nothing downstream acts on them.
MIRRORED = ("fetching", "running") + TERMINAL
# How long a finished job's row stays after the reaper saw it end. Its events are in the archive under the
# archive's days and are found by `/events?cam=`; the ROW is the operator's list of what ran, and a list that
# keeps every scan a scenario ever asked for is a list nobody can read. Three days is the window in which
# somebody asks "did last night's search finish" (the review's second pass).
FINISHED_RETENTION_SECONDS = 3 * 86400.0
log = logging.getLogger("vms.jobs")

# Requests that reached the console after their `valid_until` — dropped, and COUNTED, per family. A line in
# a log is read by nobody; this number climbing says the requests' loop is running late, which is how it was
# found (the review's second pass: a thirty-second request read every thirty seconds). One tally per process:
# the console's loops and its `/metrics` are the same process (`vms.console.vms_metrics`).
expired: dict[str, int] = {"rec": 0, "det": 0}


def _expired(sub: str) -> None:
    expired[sub] = expired.get(sub, 0) + 1


# "Record this camera for ten minutes" — a request turned into a row, by the one token that may write
# rows: the CONSOLE's. Run in the console process's loop, beside the reaper that clears requests.
#
# The division is the same as everywhere and it is the reason this function is here rather than in the
# recorder or in the controller. A worker writes no configuration, and a recording IS configuration — it
# has an id, a retention, a home and a placement. The controller writes placement and not rows. What is
# left is the console, which is the operator's agent, and a scenario asking for ten minutes of a camera is
# the operator asking through something they wrote.
#
# The row is named `<cam>-auto`, which is the naming rule the page already uses one field over: a camera
# recorded by hand and by a scenario has two recordings, two trees and two retentions, and neither
# surprises the other. A second request while it runs EXTENDS it — ten more minutes from now — instead of
# making `<cam>-auto-2`: the scenario meant "keep recording", not "record twice".
def record_on_request(rec_ctl, now: float) -> int:
    started = 0
    for key in sorted(rec_ctl.vars.list(rec_ctl.sub.requests_prefix())):
        it, _ = rec_ctl.vars.get(key)
        if not it or str(it.get("action", "")) != "record":
            continue                                        # a backfill: the recorder's, not ours
        rid = key.rsplit("/", 1)[1]
        until = float(it.get("valid_until", 0) or 0)
        if until and now > until:
            rec_ctl.vars.delete(key)                        # asked for too late to mean what it meant
            _expired(rec_ctl.spec.name)
            log.warning("%s: %s expired before it was turned into a recording", rec_ctl.spec.name, rid)
            continue
        cam = str(it.get("cam") or it.get("unit") or "")
        minutes = float(it.get("minutes", 0) or 0)
        if not cam or minutes <= 0:
            rec_ctl.vars.delete(key)
            log.warning("%s: %s asks to record nothing: %s", rec_ctl.spec.name, rid, it)
            continue
        name, ends = f"{cam}-auto", now + minutes * 60
        row = rec_ctl.unit(name)
        try:
            if row is None:
                fields = {"name": name, "cam": cam, "until": ends}
                if it.get("archive"):
                    fields["home"] = str(it["archive"])
                rec_ctl.create(fields)
                started += 1
            elif float(row.get("until") or 0) < ends:
                rec_ctl.update(name, {"until": ends})       # keep recording, not record twice
                started += 1
        except Refused as e:                                # a refusal is an answer, and it is ours to log
            log.warning("%s: %s refused for %s: %s", rec_ctl.spec.name, rid, name, e)
        except Exception as e:                              # noqa: BLE001
            # NOT an answer: the store conflicted, or did not answer at all. The request stays and the next
            # pass tries again — it carries `valid_until`, so it cannot wait for ever. It used to be deleted
            # here with the rest: the scenario fired, the recording was never made, and nothing said so
            # (the product's `RecordOnRequest`, feedback BC).
            log.warning("%s: %s could not start %s this pass: %s", rec_ctl.spec.name, rid, name, e)
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
def expire(ctl, now: float) -> int:
    gone = 0
    for row in ctl.units():
        until = float(row.get("until") or 0)
        if until and now > until:
            ctl.delete(row["id"])
            gone += 1
            log.info("%s: %s reached its end", ctl.spec.name, row["id"])
    return gone


expire_recordings = expire                              # the name the recorder's callers know it by


# What automation asks the DETECTORS for: `det/requests/<id>`, turned into rows by the console, beside
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


def detect_on_request(det_ctl, job_ctl, rec_ctl, now: float) -> int:
    made = 0
    for key in sorted(det_ctl.vars.list(det_ctl.sub.requests_prefix())):
        it, _ = det_ctl.vars.get(key)
        rid = key.rsplit("/", 1)[1]
        if not it:
            continue
        action = str(it.get("action", ""))
        until = float(it.get("valid_until", 0) or 0)
        if until and now > until:
            det_ctl.vars.delete(key)                        # asked for too late to mean what it meant
            _expired(det_ctl.spec.name)
            log.warning("%s: %s expired before it was turned into work", det_ctl.spec.name, rid)
            continue
        cam, kind = str(it.get("cam") or ""), str(it.get("kind") or "")
        try:
            if not cam or not kind or action not in ("detect", "scan"):
                raise Refused(f"a request names a camera, a model and detect|scan: {dict(it)}")
            same = _settings(det_ctl, cam, kind, it)
            made += _detect(det_ctl, cam, kind, it, same, now) if action == "detect" else \
                _scan(job_ctl, rec_ctl, cam, kind, it, same, now)
        except Refused as e:                                # a refusal is an answer, and it is ours to log
            log.warning("%s: %s refused: %s", det_ctl.spec.name, rid, e)
        except Exception as e:                              # noqa: BLE001 — not an answer: stays, and is tried again
            log.warning("%s: %s could not be turned into work this pass: %s", det_ctl.spec.name, rid, e)
            continue
        det_ctl.vars.delete(key)                            # performed or refused, it has nothing left to say
    return made


def _settings(det_ctl, cam: str, kind: str, it: dict) -> dict:
    out = {f: it[f] for f in ("params",) if it.get(f)}
    if not out:
        for d in sorted(det_ctl.units(), key=lambda d: str(d["id"])):
            if str(d.get("cam")) == cam and str(d.get("kind")) == kind and not str(d["id"]).endswith(DETECT_KEY):
                out = {f: d[f] for f in ("params", "mask", "labels") if d.get(f)}
                break
    return out


def _detect(det_ctl, cam: str, kind: str, it: dict, same: dict, now: float) -> int:
    minutes = float(it.get("minutes", 0) or 0)
    if minutes <= 0:
        raise Refused(f"detect asks for no minutes: {dict(it)}")
    for d in det_ctl.units():
        if str(d.get("cam")) == cam and str(d.get("kind")) == kind and d.get("enabled", True) \
                and not float(d.get("until") or 0):
            log.info("%s: camera %s is watched for %s already (%s) — nothing to start", det_ctl.spec.name, cam, kind, d["id"])
            return 0
    name, ends = f"{cam}-{kind}{DETECT_KEY}", now + minutes * 60
    row = det_ctl.unit(name)
    if row is None:
        det_ctl.create({"name": name, "cam": cam, "kind": kind, "until": ends, **same})
        return 1
    if float(row.get("until") or 0) < ends:
        det_ctl.update(name, {"until": ends})               # keep watching, not watch twice
        return 1
    return 0


def _scan(job_ctl, rec_ctl, cam: str, kind: str, it: dict, same: dict, now: float) -> int:
    at = float(it.get("at", 0) or now)
    before = float(it.get("before", SCAN_BEFORE) or 0)
    after = float(it.get("after", SCAN_AFTER) or 0)
    t0, t1 = at - before, at + after
    if t1 <= t0:
        raise Refused(f"scan asks for an empty interval: before {before}, after {after}")
    rec = str(it.get("rec") or "")
    if not rec:
        recs = sorted(str(r["id"]) for r in rec_ctl.units() if str(r.get("cam", r["id"])) == cam)
        rec = cam if cam in recs else (recs[0] if recs else "")
    if not rec or rec_ctl.unit(rec) is None:
        raise Refused(f"nothing records camera {cam}: a scan reads the archive, and there is none to read")
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


# The other half of `<name>/requests/<id>`: the worker fetched it and said so in its heartbeat; the row goes.
#
# Same division as `reap` below, and for the same reason — a worker writes no configuration. Here it is
# cheaper still, because a request has no state to move: once the work named in it is done the row has
# nothing left to say, and a store that keeps every range anyone ever asked for is a store that grows
# without anybody deciding it should.
def clear_requests(ctl) -> int:
    from w2cplatform.console import heartbeats
    fetched: set[str] = set()
    for _, hb in heartbeats(ctl.objects, ctl.spec.name + "/").items():
        fetched |= {r for r in str(hb.extra.get("fetched", "")).split(",") if r}
    gone = 0
    for key in ctl.vars.list(ctl.sub.requests_prefix()):
        if key.rsplit("/", 1)[1] in fetched:
            ctl.vars.delete(key)
            gone += 1
    return gone


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
    for row in ctl.units():
        if str(row.get("state", "")) in TERMINAL:
            continue                                        # already moved; the predicate un-places it, not us
        state[str(row["id"])] = str(row.get("state", ""))
        ends[str(row["id"])] = float(row.get("to") or 0)
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
        if phase in TERMINAL and "to" in st and float(st["to"]) != ends.get(uid):
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
                     float(st.get("covered", 0)), int(st.get("events", 0)))
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
        ended = float(row.get("ended") or 0) or float(row.get("to") or 0)
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
def ask_for_footage(job_ctl, rec_ctl) -> int:
    asked = 0
    for st in job_ctl.read_model():
        if str(st.get("phase", "")) != "fetching":
            continue
        unit, t0, t1 = str(st.get("rec", "")), float(st.get("from", 0)), float(st.get("to", 0))
        if not unit or t1 <= t0:
            continue
        rid = f"{unit}-{int(t0)}-{int(t1)}"
        key = rec_ctl.sub.request_key(rid)
        it, _ = rec_ctl.vars.get(key)
        if it:
            continue                                        # already asked; the recorder clears it when it is fetched
        rec_ctl.vars.put(key, {"unit": unit, "cam": str(st.get("cam", unit)), "from": str(t0), "to": str(t1),
                               "at": str(job_ctl.wall()), "by": f"{job_ctl.spec.name}/{st.get('id')}"})
        asked += 1
        log.info("%s %s: asking the recorder for %s [%.0f, %.0f)", job_ctl.spec.name, st.get("id"), unit, t0, t1)
    return asked


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
    for _, hb in heartbeats(rec_ctl.objects, rec_ctl.spec.name + "/").items():
        for span in str(hb.extra.get("closed", "")).split(","):
            parts = span.split("|")
            if len(parts) != 3:
                continue
            unit, t0, t1 = parts[0], float(parts[1]), float(parts[2])
            rec = rec_ctl.unit(unit)
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
# same division as everywhere here — the worker knows and may not write, the console writes — and the same
# reason the request's id is the range: a pass every thirty seconds must write one row, not a queue.
#
# What lands in `rec/<cam>/` this way is ordinary footage with the ordinary retention, and that is the
# point rather than an omission: when only the interesting minutes are copied, everything on the server is
# interesting, and "evidence" needs no second archive and no second lifetime.
def keep_what_fired(survey_ctl, rec_ctl) -> int:
    from w2cplatform.console import heartbeats
    asked = 0
    for _, hb in heartbeats(survey_ctl.objects, survey_ctl.spec.name + "/").items():
        for span in str(hb.extra.get("hits", "")).split(","):
            parts = span.split("|")
            if len(parts) != 3:
                continue
            cam, t0, t1 = parts[0], float(parts[1]), float(parts[2])
            if t1 <= t0:
                continue
            unit = next((str(r["id"]) for r in rec_ctl.units() if str(r.get("cam", r["id"])) == cam), None)
            if unit is None:
                continue                                # nothing on this server records that camera: nowhere to put it
            rid = f"{unit}-{int(t0)}-{int(t1)}"
            key = rec_ctl.sub.request_key(rid)
            if rec_ctl.vars.get(key)[0]:
                continue                                # already asked; the recorder clears it when it is fetched
            rec_ctl.vars.put(key, {"unit": unit, "cam": cam, "from": str(t0), "to": str(t1),
                                   "at": str(survey_ctl.wall()), "by": f"{survey_ctl.spec.name}/{cam}"})
            asked += 1
            log.info("%s: keeping %s [%.0f, %.0f) — a model liked it", survey_ctl.spec.name, unit, t0, t1)
    return asked
