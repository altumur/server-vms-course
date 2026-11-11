"""P01.156: the loop's prep of the attempt-6 task outside the stand — stage_prep (generation_plan, code checks, norm_trace,
profile_probe) and variant_b.prep_violations with stages.m_passport pointed at a local copy of the same passport (same sha256).
Run: python3 -I prep_dryrun.py <minimax-loop clone> <task json> <M tree> <PASSPORT-M.json copy> <loop head>"""
import sys, json, copy, collections
mm, task_p, mtree, mpass = sys.argv[1:5]
sys.path.insert(0, mm)
import loop, variant_b
t = loop.load_task(task_p)
class R: pass
r = R(); r.map = {"specs": mtree}
plan = loop.stage_prep(t, r)
st = plan["stages"]
print("loop_head", sys.argv[5] if len(sys.argv) > 5 else "")
print("stages", len(st), [s["stage"] for s in st])
print("code_at", [s["stage"] for s in st if any(c["gate_kind"] == "code" for c in s["checks"])])
print("mech_only", [s["stage"] for s in st if not any(c["gate_kind"] == "code" for c in s["checks"])])
print("when_unevaluated", plan["when_unevaluated"], "excluded", plan["excluded"])
nt = plan.get("norm_trace")
print("norm_trace", nt["items"] if nt else None, nt["by_stage"] if nt else None)
print("profile_probe_on", loop.profile_probe_cfg(t))
t2 = copy.deepcopy(t); t2["stages"]["m_passport"] = dict(t["stages"]["m_passport"], path=mpass)
bad = variant_b.prep_violations(t2, mtree, None)
print("prep_violations", len(bad), bad[:10])
print("m_passport_violations", variant_b.m_passport_violations(t2["stages"]["m_passport"], mtree, t["specs_sha"]))
for v in ("yes", 1, None, False):
    t3 = copy.deepcopy(t); t3["stages"]["profile_probe"] = v
    if v is None: del t3["stages"]["profile_probe"]
    try: loop.stage_prep(t3, r); print("profile_probe", repr(v), "prep ok")
    except loop.PrepError as e: print("profile_probe", repr(v), "PrepError:", e)
k = t2["stages"]["m_passport"]
print("control wrong_sha", variant_b.m_passport_violations(dict(k, sha256="0" * 64), mtree, t["specs_sha"]) != [])
print("control other_M", variant_b.m_passport_violations(k, mtree, "d5bd29ddb2ddc3fb313b557e965dacefa8bb1d40") != [])
