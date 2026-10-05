import sys
sys.path.insert(0, "/private/tmp/claude-501/-Users-murat-w2c/2bb348d1-4209-4bed-b182-709fa7b18d2e/scratchpad/three_cameras")
import scenario as sc
s = sc.S()
ws, ctl = sc.running(s, capacity=1)
con = s.console("srv-a")
con.set_policy({"servers": "distinct"}); print(ctl.policy())
con.create_camera({"name": "Касса", "source": "driverpack://acme/10.2.0.14", "labels": ["vlan:cctv"]})
mark = s.log.mark()
rep = sc.controller_pass(ctl)
print({k: rep[k] for k in ("units_short","workers_needed","spare_offers","spares_withheld","unplaced")})
print([l for l in s.view(mark, sc.writes_only).render().splitlines() if "POST" in l])
