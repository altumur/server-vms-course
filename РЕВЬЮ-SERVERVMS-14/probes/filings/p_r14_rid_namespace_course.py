# r14 probe (COURSE; argv[1] = course tree root or Source/): ONE rid namespace for a person's and a worker's requests.
# A worker (testsub2) files `testsub/requests/fire-1-0`; a person then POSTs /testsub/requests with Idempotency-Key
# `fire-1-0` and ANOTHER body. Expected on e7443379 (defect): 202 "queued" whose row is the WORKER's (the person's
# body discarded, unit/add of somebody else's request said back), nothing counted; the worker side would have refused
# the same collision (filings.refused). Reverse order: the person first, then the worker -> RequestRefused, counted.
import os
import sys

root = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
src = root if os.path.isdir(os.path.join(root, "w2cplatform")) else os.path.join(root, "Source")
sys.path.insert(0, src)
os.chdir(src)

from tests.conftest import Box, Served, controller, testsub, testsub2  # noqa: E402
from w2cplatform.console import SpecConsole  # noqa: E402
from w2cplatform.worker import RequestRefused, Worker  # noqa: E402


class Bare(Worker):
    def reconcile_once(self, now=None):
        return []


box = Box()
ctl = controller(box, spec=testsub())
ctl.create({"name": "c1"})
ctl.create({"name": "c2"})
w = Bare(testsub2().sub, None, box.vars, box.objects, clock=box.clock, wall=box.wall, spec=testsub2(),
         resource_root=box.resource_root)
w.claim_slot("t-1")
t0 = box.wall()
print("worker files fire-1-0:", w.file_request("testsub", "fire-1-0", {"unit": "testsub/c1", "add": 2, "valid_until": t0 + 30},
                                               unit="t1", at=t0))
con = SpecConsole(ctl, marks_root=box.resource_root, wall=box.wall)
with Served(con) as call:
    code, body = call("POST", "/requests", {"unit": "testsub/c2", "add": 7}, headers={"X-User": "boris"}, key="fire-1-0")
    print("person POST same rid, other body ->", code, body.get("queued") if isinstance(body, dict) else body)
    row = box.vars.get("testsub/requests/fire-1-0")[0]
    print("row standing:", row)
    print("person's request written anywhere:", [k for k in box.vars.list("testsub/requests/") if box.vars.get(k)[0].get("add") == "7"])
    code, body = call("POST", "/requests", {"unit": "testsub/c2", "add": 7}, headers={"X-User": "boris"}, key="op-1")
    print("person POST op-1 ->", code)
try:
    w.file_request("testsub", "op-1", {"unit": "testsub/c1", "add": 2, "valid_until": t0 + 30}, unit="t1", at=t0)
    print("worker files op-1 after the person: FILED")
except RequestRefused as e:
    print("worker files op-1 after the person: refused:", e)
print("worker filings:", w.filings)
