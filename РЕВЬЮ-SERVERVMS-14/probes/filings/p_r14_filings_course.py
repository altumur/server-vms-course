# r14 probe (COURSE; argv[1] = course tree root, the dir holding Source/, or Source/ itself): Worker.file_request on
# FileVariables (a box), MemVariables and MemVariables under the worker's grant. Expected on e7443379: the claims hold
# on every store (stamps by/at/filed refused, nothing written; repeat -> False + again; conflict -> RequestRefused +
# refused; `filings` in platform_fields); EDGES printed: a refile after the row was cleared is a fresh filing (True,
# filed=2); rid `asks-<16 hex>` (a person's ledger name) is accepted from a worker; a NaN `at` raises ValueError (not
# RequestRefused, uncounted); no `filings` line on any /metrics producer (console.py, metrics.py).
import math
import os
import re
import sys

root = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
src = root if os.path.isdir(os.path.join(root, "w2cplatform")) else os.path.join(root, "Source")
sys.path.insert(0, src)
os.chdir(src)

from tests.conftest import Box, testsub2  # noqa: E402
from w2cplatform.memvariables import MemVariables  # noqa: E402
from w2cplatform.worker import RequestRefused, Worker  # noqa: E402


class Bare(Worker):
    def reconcile_once(self, now=None):
        return []


def run(label, box, vars_):
    spec = testsub2()
    w = Bare(spec.sub, None, vars_, box.objects, clock=box.clock, wall=box.wall, spec=spec, resource_root=box.resource_root)
    w.claim_slot("t-1")
    out = {}
    for k in ("by", "at", "filed"):
        try:
            w.file_request("testsub", f"s-{k}", {"unit": "testsub/c1", k: "x"})
            out[f"stamp {k}"] = "FILED (defect)"
        except RequestRefused:
            out[f"stamp {k}"] = "refused"
    out["written after stamps"] = vars_.list("testsub/requests/")
    t0 = box.wall()
    row = {"unit": "testsub/c1", "add": 2, "valid_until": t0 + 600}
    out["file"] = w.file_request("testsub", "fire-1-0", row, unit="t1", at=t0)
    box.wall.advance(5)
    out["repeat"] = w.file_request("testsub", "fire-1-0", dict(row), unit="t1", at=t0)
    try:
        w.file_request("testsub", "fire-1-0", {**row, "add": 3}, unit="t1", at=t0)
        out["conflict"] = "FILED (defect)"
    except RequestRefused:
        out["conflict"] = "refused"
    # the console clears the answered row (requests.clear_requests) and a sweep removes its mark (Worker.sweep_marks);
    # an evaluator that lost `fired` (failover: its cursor is in the old server's RESOURCE_ROOT) refiles inside valid_until
    vars_.delete("testsub/requests/fire-1-0")
    box.wall.advance(120)
    out["refile after clear"] = w.file_request("testsub", "fire-1-0", dict(row), unit="t1", at=t0)
    try:
        out["rid asks-<16hex>"] = w.file_request("testsub", "asks-0123456789abcdef", {"unit": "testsub/c1", "add": 1})
    except RequestRefused as e:
        out["rid asks-<16hex>"] = f"refused: {e}"
    try:
        w.file_request("testsub", "nan-at", {"unit": "testsub/c1", "add": 1}, at=math.nan)
        out["NaN at"] = "filed"
    except RequestRefused:
        out["NaN at"] = "RequestRefused"
    except Exception as e:  # noqa: BLE001
        out["NaN at"] = f"{type(e).__name__} (not RequestRefused): {e}"
    out["filings"] = dict(w.filings)
    out["heartbeat filings"] = w.platform_fields().get("filings")
    print(f"--- {label}")
    for k, v in out.items():
        print(f"  {k}: {v}")


box = Box()
run("FileVariables (a box)", box, box.vars)
box2 = Box()
run("MemVariables", box2, MemVariables())
box3 = Box()
run("MemVariables under the worker's grant", box3, MemVariables().as_writer("testsub2worker", testsub2().acl_worker_role()))

hits = []
for rel in ("w2cplatform/console.py", "w2cplatform/metrics.py", "vms/console.py"):
    with open(os.path.join(src, rel), encoding="utf-8") as f:
        hits += [f"{rel}:{i}" for i, line in enumerate(f, 1) if re.search(r"filings", line)]
yamls = [p for p in os.listdir(os.path.join(src, "vms")) if p.endswith(".subsystem.yaml")]
for y in yamls:
    with open(os.path.join(src, "vms", y), encoding="utf-8") as f:
        hits += [f"vms/{y}:{i}" for i, line in enumerate(f, 1) if "filings" in line]
print("--- /metrics producers mentioning `filings`:", hits or "NONE")
