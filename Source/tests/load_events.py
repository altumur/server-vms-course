#!/usr/bin/env python3
"""The event log under load — measured, not multiplied (the notes on the event log's load and concurrency,
28 September, whose numbers were products of constants).

Not part of the suite: it builds a tree of days of buckets and takes a minute or two. Run it as

    python3 tests/load_events.py                 # 20 cameras + 20 detectors, 2 days, 3 resources
    python3 tests/load_events.py --days 7        # the same, a week: the old costs grow, the index's do not

What it measures, on one machine, over real HTTP where a real deployment has it:

  1. the index: one query for automation's window (5 min, one kind) and a timeline's (1 h, one camera),
     first read and cached — against the SQLite database it replaced (from git), whose rebuild and whose
     tail pass (every 3 s) read the whole tree;
  2. a resource's `/events` over HTTP: latency, and what `EVENTS_INFLIGHT` does to a burst of readers;
  3. automation's pass over 50 scenarios on three resources: as it is now (one query per kind a pass, the
     resources asked at once) and as it was (a query per scenario and kind, the resources one after another).

Every number printed is a wall-clock measurement on this machine. The old database's module is taken from
the commit before the index replaced it and imported beside the new one, so both read the same tree.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from w2cplatform.eventdatabase import EventIndex, MergedIndex  # noqa: E402
from w2cplatform.events import bucket_path  # noqa: E402

B = 600


def build_tree(root: str, cams: list[int], days: float, per_bucket: int, now: float) -> int:
    """`vms/<cam>` and `det/<cam>-motion` for each camera, a bucket every 10 minutes for `days`, `per_bucket`
    lines in each; one line in fifty an alarm. Written as files, the way a worker leaves them."""
    files = 0
    first = int((now - days * 86400) // B) * B
    last = int(now // B) * B
    for cam in cams:
        for sub, unit, kind in (("vms", str(cam), "motion"), ("det", f"{cam}-motion", "motion")):
            start = first
            while start <= last:
                p = bucket_path(root, sub, unit, 1, start)
                os.makedirs(os.path.dirname(p), exist_ok=True)
                step = B / per_bucket
                with open(p, "w") as f:
                    for i in range(per_bucket):
                        t = start + i * step
                        if t > now:
                            break
                        line = {"t": t, "kind": "io.input" if (sub == "vms" and i % 7 == 0) else kind, "n": i}
                        if sub == "det":
                            line["cam"] = cam
                        if i % 50 == 0:
                            line["class"] = "alarm"
                        f.write(json.dumps(line) + "\n")
                files += 1
                start += B
    return files


def timed(fn, repeat: int = 1):
    out = []
    for _ in range(repeat):
        t0 = time.perf_counter()
        r = fn()
        out.append(time.perf_counter() - t0)
    return (statistics.median(out) if len(out) > 1 else out[0]), r


def ms(s: float) -> str:
    return f"{s * 1000:.1f} ms" if s < 1 else f"{s:.2f} s"


def old_database_module():
    """The SQLite database as it was, from git, importable beside the index."""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = subprocess.run(["git", "show", "13ceaa8^:vmsserver/w2cplatform/eventdatabase.py"], cwd=here,
                         capture_output=True, text=True, check=True).stdout
    path = os.path.join(tempfile.mkdtemp(prefix="olddb-"), "old_eventdatabase.py")
    open(path, "w").write(src.replace("from .events", "from w2cplatform.events").replace("from .resource", "from w2cplatform.resource"))
    spec = importlib.util.spec_from_file_location("old_eventdatabase", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def part1(root: str, now: float, files: int) -> dict:
    print(f"\n1. One resource's tree: {files} bucket files")
    res = {}
    idx = EventIndex(root, "srv-1")
    res["auto_first"], r = timed(lambda: idx.query(now - 300, now, kind="io.input", subsystem="vms", limit=500))
    res["auto_cached"], _ = timed(lambda: idx.query(now - 300, now, kind="io.input", subsystem="vms", limit=500), 20)
    res["timeline_first"], _ = timed(lambda: EventIndex(root, "srv-1").query(now - 3600, now, unit="vms/7", limit=1000))
    res["timeline_cached"], _ = timed(lambda: idx.query(now - 3600, now, unit="vms/7", limit=1000), 5)
    idx.query(now - 3600, now, unit="vms/7", limit=1000)
    res["timeline_cached"], _ = timed(lambda: idx.query(now - 3600, now, unit="vms/7", limit=1000), 10)
    print(f"   index, automation's window (5 min, one kind, all units): first {ms(res['auto_first'])}, "
          f"cached {ms(res['auto_cached'])}  ({len(r['events'])} events)")
    print(f"   index, a timeline (1 h, camera 7):                        first {ms(res['timeline_first'])}, "
          f"cached {ms(res['timeline_cached'])}")
    old = old_database_module()
    db = old.EventDatabase(root, "srv-1")
    res["old_rebuild"], rep = timed(db.rebuild)
    res["old_tail"], _ = timed(db.tail)
    res["old_query_auto"], _ = timed(lambda: db.query(now - 300, now, kind="io.input", subsystem="vms", limit=500), 20)
    print(f"   old SQLite: rebuild {ms(res['old_rebuild'])} ({rep['added']} rows), one tail pass {ms(res['old_tail'])} "
          f"— every 3 s, whatever was asked; a query then {ms(res['old_query_auto'])}")
    return res


def serve_resources(roots: dict, now: float):
    """Three resource processes over HTTP, each over its own tree, heartbeating into one object store."""
    from tests.conftest import Box
    from vms.archive import ArchiveResource
    from w2cplatform.resource import platform_resource
    from w2cplatform.resource import serve
    box = Box()
    rs, srvs = {}, []
    for name, root in roots.items():
        arch = ArchiveResource(os.path.join(box.root, f"spool-{name}"), root)
        r = platform_resource(arch, name, "", box.vars, box.objects, wall=time.time)
        srv = serve(r, "127.0.0.1", 0)
        r.url = f"http://127.0.0.1:{srv.server_address[1]}"
        r.heartbeat()
        rs[name] = r
        srvs.append(srv)
    return box, rs, srvs


def part2(rs: dict, now: float) -> dict:
    print("\n2. A resource's /events over HTTP")
    res = {}
    r = next(iter(rs.values()))
    url = f"{r.url}/events?from={now - 300}&to={now}&subsystem=vms&kind=io.input&limit=500"
    urllib.request.urlopen(url).read()
    res["http_auto"], _ = timed(lambda: urllib.request.urlopen(url).read(), 30)
    print(f"   one query, automation's window: {ms(res['http_auto'])} (median of 30)")
    for readers in (8, 32):
        codes, lat = [], []

        def one():
            t0 = time.perf_counter()
            try:
                urllib.request.urlopen(url).read(); codes.append(200)
            except urllib.error.HTTPError as e:
                codes.append(e.code)
            lat.append(time.perf_counter() - t0)
        ts = [threading.Thread(target=one) for _ in range(readers)]
        t0 = time.perf_counter()
        for t in ts: t.start()
        for t in ts: t.join()
        wall = time.perf_counter() - t0
        busy = codes.count(503)
        res[f"burst_{readers}"] = {"wall": wall, "busy": busy, "p50": statistics.median(lat), "max": max(lat)}
        print(f"   {readers} readers at once: all answered in {ms(wall)}, {busy} told busy (503), "
              f"median {ms(statistics.median(lat))}, slowest {ms(max(lat))}")
    return res


def part3(box, rs: dict, now: float, scenarios: int) -> dict:
    print(f"\n3. Automation's pass: {scenarios} scenarios, {len(rs)} resources")
    from w2cplatform.contract import requests_acl
    from vms.auto import AutoController, Catalog
    from vms.autoworker import AutoWorker
    from vms.config import AUTO_SPEC
    for cam in range(1, 21):
        box.vars.put(f"vms/cameras/{cam}", {"id": str(cam), "name": f"cam{cam}", "source": f"driverpack://file/{cam}"})
        box.vars.put(f"det/units/{cam}-motion", {"name": f"{cam}-motion", "cam": str(cam), "kind": "motion"})
    con = AutoController(box.vars.as_writer("console", AUTO_SPEC.acl_console()), box.objects, wall=time.time,
                         catalog=Catalog(box.vars))
    names = []
    for i in range(scenarios):
        cam = i % 20 + 1
        when = [{"sub": "vms", "kind": "io.input", "unit": str(cam)}]
        if i % 3 == 0:
            when.append({"sub": "det", "kind": "motion", "unit": f"{cam}-motion"})
        if i % 5 == 0:
            when.append({"sub": "vms", "kind": "motion", "unit": str(cam)})
        con.create({"name": f"s{i}", "when": when, "within": 30 if len(when) > 1 else 0,
                    "then": [{"sub": "vms", "action": "output", "unit": str(cam), "port": 1}], "rate_per_minute": 600})
        names.append(f"s{i}")
    AutoController(box.vars.as_writer("autocontroller", AUTO_SPEC.acl_controller()), box.objects,
                   wall=time.time).assign("a-1", names)
    res = {}
    w = AutoWorker("a-1", box.vars.as_writer("autoworker", AUTO_SPEC.sub.acl_worker() + requests_acl("vms", "rec")),
                   box.objects, index=MergedIndex(box.objects), wall=time.time, server="srv-a",
                   archive_root=os.path.join(box.root, "auto"), env={})
    res["pass_first"], _ = timed(w.reconcile_once)
    res["pass_queries"] = w.pass_stats["queries"]
    res["pass_cut"] = sum(1 for st in w.status() if st.get("cut"))
    res["pass_next"], _ = timed(w.reconcile_once)
    print(f"   a whole pass now (reads, evaluation, filing): first {ms(res['pass_first'])}, next {ms(res['pass_next'])}; "
          f"{res['pass_queries']} queries, {res['pass_cut']} scenarios with a cut window")
    rows = [con.unit(n) for n in names]
    keys = sorted({(t["sub"], t["kind"], str(t.get("unit") or "")) for row in rows for t in row["when"]})
    new = MergedIndex(box.objects)

    def new_reads():
        cut = 0
        for sub, kind, unit in keys:
            rep = new.query(now - 330, time.time(), subsystem=sub, kind=kind, unit=unit or None, limit=500)
            cut += bool(rep["truncated"])
        return cut
    res["new_reads"], res["new_truncated"] = timed(new_reads, 3)
    res["new_queries"] = len(keys)
    old = MergedIndex(box.objects, lanes=1)

    def old_reads():
        cut = 0
        for row in rows:
            for sub, kind in sorted({(t["sub"], t["kind"]) for t in row["when"]}):
                rep = old.query(now - 300 - float(row.get("within") or 0), time.time(), subsystem=sub, kind=kind, limit=500)
                cut += bool(rep["truncated"])
        return cut
    res["old_reads"], res["old_truncated"] = timed(old_reads, 3)
    res["old_queries"] = sum(len({(t["sub"], t["kind"]) for t in row["when"]}) for row in rows)
    print(f"   reads now: one query per (subsystem, kind, unit), resources at once — {res['new_queries']} queries, "
          f"{ms(res['new_reads'])}, {res['new_truncated']} answers cut")
    print(f"   reads as they were: per scenario and kind, all units, resources one by one — {res['old_queries']} queries, "
          f"{ms(res['old_reads'])}, {res['old_truncated']} answers cut")
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cameras", type=int, default=20)
    ap.add_argument("--days", type=float, default=2.0)
    ap.add_argument("--per-bucket", type=int, default=60, help="lines per 10-minute bucket: 60 is one every 10 s")
    ap.add_argument("--scenarios", type=int, default=50)
    ap.add_argument("--json", help="write the numbers here as well")
    a = ap.parse_args()
    now = time.time()
    base = tempfile.mkdtemp(prefix="load-events-")
    cams = list(range(1, a.cameras + 1))
    print(f"# {a.cameras} cameras + {a.cameras} detectors, {a.days:g} days, {a.per_bucket} lines per bucket")
    t0 = time.perf_counter()
    files = build_tree(os.path.join(base, "one"), cams, a.days, a.per_bucket, now)
    print(f"# tree built in {ms(time.perf_counter() - t0)}")
    out = {"cameras": a.cameras, "days": a.days, "per_bucket": a.per_bucket, "files": files}
    out["index_vs_sqlite"] = part1(os.path.join(base, "one"), now, files)
    roots = {}
    for k, name in enumerate(("srv-a", "srv-b", "srv-c")):
        roots[name] = os.path.join(base, name)
        build_tree(roots[name], [c for c in cams if c % 3 == k], min(a.days, 1.0), a.per_bucket, now)
    box, rs, srvs = serve_resources(roots, now)
    try:
        out["http"] = part2(rs, now)
        out["automation"] = part3(box, rs, now, a.scenarios)
    finally:
        for s in srvs:
            s.shutdown(); s.server_close()
    if a.json:
        with open(a.json, "w") as f:
            json.dump(out, f, indent=1, default=float)
    print("\ndone")


if __name__ == "__main__":
    main()
