"""Дополнительные числа для части 10: время прохода контроллера (стенд в памяти и настоящая группа configstore из трёх
демонов на петле), чтения на вкладку консоли и цена одного создания при N камерах."""
from __future__ import annotations

import math
import os
import statistics
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import scenario as sc  # noqa: E402  (chdir в clustervms)

sys.path.insert(0, "/Users/murat/w2c/server-vms-course/vmsserver")
import importlib.util as _u
_sp=_u.spec_from_file_location("cse","/Users/murat/w2c/server-vms-course/vmsserver/tests/configstore_election.py")
_m=_u.module_from_spec(_sp); _sp.loader.exec_module(_m); Node=_m.Node
from w2cplatform.variables import open_vars  # noqa: E402

NS = [int(a) for a in sys.argv[1:] if a.isdigit()] or [100, 300, 600]
REAL = "--no-real" not in sys.argv


def build(n):
    cap = max(50, math.ceil(n / 3))
    s = sc.S()
    ws = sc.boot(s, capacity=cap)
    con = s.console("srv-a")
    for i in range(1, n + 1):
        con.create_camera({"name": f"cam-{i}", "source": f"driverpack://acme/10.2.{i // 250}.{i % 250 + 1}",
                           "labels": ["vlan:cctv"]})
    ctl = s.controller("srv-a")
    sc.controller_pass(ctl)
    for w in ws.values():
        w.reconcile_once(); w.heartbeat_once()
    return s, ws, cap


def timed_pass(ctl, k=5):
    ts = []
    for _ in range(k):
        t = time.perf_counter()
        sc.controller_pass(ctl)
        ts.append(time.perf_counter() - t)
    return statistics.median(ts)


def main():
    nodes = []
    if REAL:
        root = tempfile.mkdtemp(prefix="cs-bench-")
        nodes = [Node(k, root, "default") for k in range(3)]
        nodes[0].start()
        for nd in nodes[1:]:
            nd.start(join=nodes[0].adv)
        time.sleep(2)
    try:
        for n in NS:
            s, ws, cap = build(n)
            ctl = s.controller("srv-a")
            m = s.log.mark()
            sc.controller_pass(ctl)
            reads = s.counts(m)
            mem = timed_pass(ctl)
            print(f"N={n} cap={cap}: steady pass {reads}; in-memory {mem*1000:.1f} ms")
            # консоль: чтения на запрос
            c = sc.Console(s, "srv-b")
            for path in ("/cameras", "/metrics", "/servers", "/rec/recordings", "/rec/volumes", "/resources"):
                m = s.log.mark()
                st, _ = c.call("GET", path)
                cs = s.log.calls[m:]
                dom = sum(1 for x in cs if x.kind == "store" and x.target.startswith("/v1/get?key=domain"))
                print(f"   console GET {path}: {st}; store reads {s.counts(m)['store_reads']} (domain/* {dom}), objects {s.counts(m)['object_requests']}")
            c.close()
            # цена одного создания при N камерах
            con = s.console("srv-a")
            m = s.log.mark()
            con.create_camera({"name": "one-more", "source": "driverpack://acme/10.9.9.9", "labels": ["vlan:cctv"]})
            print(f"   create #{n+1}: {s.counts(m)}")
            if REAL:
                admin = open_vars(nodes[0].url("timeout=10"))
                keys = s.vars.list("")
                t = time.perf_counter()
                for k in keys:
                    it, _ = s.vars.get(k)
                    if it is not None:
                        admin.put(k, it)
                print(f"   copied {len(keys)} keys to raft in {time.perf_counter()-t:.1f} s")
                st = [x.status() for x in (open_vars(nd.url()) for nd in nodes)]
                lead = next(i for i, x in enumerate(st) if x.get("state") == "leader")
                for which, nd in (("leader", nodes[lead]), ("follower", nodes[(lead + 1) % 3])):
                    real = open_vars(nd.url("timeout=30"))
                    rctl = sc.stand_controller = None
                    from cluster.controller import ClusterController
                    rctl = ClusterController(real, s.objects_on("srv-a", real, ""), wall=s.wall)
                    tr = real.transport; stat = {"n": 0, "w": 0, "t": 0.0, "max": 0.0}
                    def timed(method, target, raw, headers, timeout, tr=tr, stat=stat):
                        t0 = time.perf_counter()
                        try:
                            return tr(method, target, raw, headers, timeout)
                        finally:
                            d = time.perf_counter() - t0
                            stat["n"] += 1; stat["w"] += raw is not None; stat["t"] += d; stat["max"] = max(stat["max"], d)
                    real.transport = timed
                    sc.controller_pass(rctl)
                    for k in stat: stat[k] = 0
                    sec = timed_pass(rctl, 3)
                    print(f"   raft 3 nodes, through {which}: steady pass {sec*1000:.0f} ms; per pass {stat['n']/3:.0f} req ({stat['w']/3:.0f} writes), "
                          f"in store {stat['t']/3*1000:.0f} ms, slowest {stat['max']*1000:.0f} ms")
                # чистим для следующего N
                for k in admin.list(""):
                    if not k.startswith("vms/epoch/"):
                        try:
                            admin.delete(k)
                        except Exception:
                            pass
    finally:
        for nd in nodes:
            if nd.proc:
                nd.proc.kill()


main()
