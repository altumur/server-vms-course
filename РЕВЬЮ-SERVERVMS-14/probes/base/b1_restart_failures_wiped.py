# b1: course reconcile.py — a key up longer than Backoff.max whose in-place Restart keeps failing: its failures must
# accumulate (lagging, then stalled; the delay doubles). Tree: course. Expected (ADR-0033): failures 1,2,3.. and
# stalled at 3. Defect: `_settle` wipes the count of a STALE running key each pass -> failures stay 1, never stalled.
# Also b2 part: a wanted key at rev 0 whose start always fails reports `converged`. Usage: python b1.py <course Source>
import sys; sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else ".")
from w2cplatform.reconcile import Reconciler, Backoff, Want
t = [0.0]
r = Reconciler(lambda k, w: True, lambda k: None, Backoff(1, 60, 0.5), restart=lambda k, w: False)
r.now = lambda: t[0]; r.rand = lambda: 0.5
r.once({"a": Want(1)})                    # up at rev 1
t[0] = 100.0                              # held 100 s > max
seen = []
for i in range(6):
    p = r.once({"a": Want(2)})
    st = r.status()["a"]
    seen.append((t[0], p.failed, p.waiting, st.state, st.failures, round(st.retry_at - t[0], 2)))
    t[0] += 3.0
for s in seen: print("t=%5.1f failed=%s waiting=%s state=%s failures=%d wait=%.2f" % s)
print("RESTART_FAILURES_ACCUMULATE", max(s[4] for s in seen) >= 3, "EVER_STALLED", any(s[3] == "stalled" for s in seen))
# rev 0
r2 = Reconciler(lambda k, w: False, lambda k: None, Backoff(1, 60, 0.5)); t2 = [0.0]; r2.now = lambda: t2[0]
for i in range(5):
    r2.once({"z": Want(0)}); t2[0] += 100
print("REV0_FAILING_STATUS", r2.status()["z"])
