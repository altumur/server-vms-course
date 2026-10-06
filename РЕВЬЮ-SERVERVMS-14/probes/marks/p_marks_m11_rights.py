# Checks (COURSE, М11, ADR-0054 addition "грант консоли"; 13th review major 20): under the committed cluster rights, through
# the console's own socket, the reaper reads a holder's mark, writes `expired` create-only, completes a gone holder's
# mark `unknown` by index (reading its slot row), and may NOT delete a mark. Expected: the author's test passes, and the
# console's delete of a mark is refused.
# Usage: python p_marks_m11_rights.py <course-tree-root>
import os, sys, threading

root = sys.argv[1]
src = os.path.join(root, "Source")
sys.path.insert(0, src)
os.chdir(src)
os.environ.setdefault("STORE_VOLATILE", "1")
os.environ.setdefault("WATERMARK_DEFAULT", "off")
threading.Timer(180, lambda: (print("DEADLINE", flush=True), os._exit(9))).start()

from tests import runroot
runroot.enter()
from tests.cluster import test_lesson2_jobs as t

ok = True
try:
    t.test_the_consoles_reaper_ends_a_command_nobody_performed_under_the_clusters_rights()
    print("author's M11 reaper test under the cluster's rights: ok", flush=True)
except Exception as e:
    ok = False
    print("author's M11 reaper test FAILED:", type(e).__name__, e, flush=True)

from tests.cluster.stand import Cluster
c = Cluster(); c.resources_up()
con, w = c.console(), c.worker("srv-a")
assert w._mark("m1", "1", c.wall())
try:
    con.objects.delete("vms/commands/m1")
    gone = con.objects.get("vms/commands/m1") is None
    print("console deleted a mark:", "YES (DEFECT)" if gone else "call returned, mark still there", flush=True)
    ok = ok and not gone
except Exception as e:
    print("console's delete of a mark refused:", type(e).__name__, str(e)[:120], flush=True)
try:
    took = con.objects.put_at("vms/commands/m1", b'{"outcome":"unknown"}', 0)
    print("console put_at at a stale index (0) took:", took, flush=True)
    ok = ok and not took
except Exception as e:
    print("console put_at stale:", type(e).__name__, str(e)[:120], flush=True)
print("RESULT", "OK" if ok else "DEFECT", flush=True)
os._exit(0 if ok else 1)
