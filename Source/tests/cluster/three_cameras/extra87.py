import sys
sys.path.insert(0, "/private/tmp/claude-501/-Users-murat-w2c/2bb348d1-4209-4bed-b182-709fa7b18d2e/scratchpad/three_cameras")
import scenario as sc
s = sc.S()
ws, ctl = sc.running(s)
a = ws["srv-a"]
b = s.worker("srv-a", tag="(вторая копия, srv-a:4104:001008)")
b.reconcile_once(); b.heartbeat_once()
mark = s.log.mark()
lost = a.lease_pass()
print("==== first lease_pass", lost, a.name, a.seeking, a.nameless)
print(s.view(mark).render())
mark = s.log.mark()
a.clock_offset = 0
lost = a.lease_pass(); a.reconcile_once(); a.heartbeat_once()
print("==== second lease_pass", lost, repr(a.name), a.seeking, a.nameless)
print(s.view(mark).render())
mark = s.log.mark()
print("==== controller pass")
print(sc.controller_pass(ctl))
v = s.view(mark).render()
print("\n".join(l for l in v.splitlines() if "contenders" in l or "conflict" in l))
print(getattr(ctl, "_names_said", None))
