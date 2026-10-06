# b4 (course): a STRICT place (row names no server) held by A, whose store went silent; B's wall clock is 8 s ahead.
# B may take it only after watching the row unchanged for slot_ttl + HOLD_SKEW by its own clock (`_hold_stale`), so
# never while A's `may_write_place` is true. Tree: course. Expected: TWO_WRITERS False at every step.
# Usage: python b4_claim_hold_by_foreign_clock.py <course Source>
import sys; sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else ".")
from tests.conftest import Box, testsub2
from w2cplatform.worker import Worker
spec, box = testsub2(), Box()
box.vars.put(spec.sub.config("shelves", "net"), {"name": "net", "enabled": True})
real = [1000.0]
ca, wa = (lambda: real[0]), (lambda: real[0])
cb, wb = (lambda: real[0] + 3.0), (lambda: real[0] + 8.0)
a = Worker(spec.sub, None, box.vars, box.objects, clock=ca, wall=wa, instance="hostA:1:a", spec=spec); a.server = "srv-a"
b = Worker(spec.sub, None, box.vars, box.objects, clock=cb, wall=wb, instance="hostB:1:b", spec=spec); b.server = "srv-b"
assert a.claim_slot(prefer="t-1") == "t-1" and b.claim_slot(prefer="t-2") == "t-2"
assert a.claim_hold(["net"]) == "net"
bad = False
for at in (1, 30, 37.5, 39, 41, 52):
    real[0] = 1000 + at
    got = b.claim_hold(["net"])
    two = a.may_write_place("net") and b.hold == "net"; bad |= two
    print(f"t=+{at}s A.may_write={a.may_write_place('net')} B.claim={got!r} TWO_WRITERS={two}")
print("ANY_TWO_WRITERS", bad)
