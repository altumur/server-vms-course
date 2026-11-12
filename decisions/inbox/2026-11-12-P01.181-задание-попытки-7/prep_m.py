"""P01.181: the loop's prep of task-attempt7.json on the M of the pair P01.180 (be48405e) outside the stand.
As prep_dryrun.py of P01.247, but task["specs"] points at a local copy of the M tree (norm_trace_prep reads the items
from task["specs"]; on the stand both paths name the same M) and stages.m_passport at a local copy of PASSPORT-M.json
(same sha256). Prints the method marks the loop read (P01.248) and the items each gate leaves neutral.
Run: python3 -I prep_m.py <minimax-loop tree> <task-attempt7.json> <M tree> <PASSPORT-M.json copy> <loop head>"""
import sys, os, copy
mm, task_p, mtree, mpass, head = sys.argv[1:6]
sys.path.insert(0, mm)
import loop, variant_b, norm_trace as nt, mutation_trace as mt, mode_trace as mdt
t = loop.load_task(task_p)
specs_on_stand = t["specs"]
t["specs"] = os.path.abspath(mtree)
class R: pass
r = R(); r.map = {"specs": t["specs"]}
print("loop_head", head)
print("specs_on_stand", specs_on_stand, "specs_sha", t["specs_sha"], "name", t["name"])
print("prep_bool_keys", mt.prep_violations(t) + mdt.prep_violations(t))
plan = loop.stage_prep(t, r)
st = plan["stages"]
print("stages", len(st), [s["stage"] for s in st])
print("code_at", [s["stage"] for s in st if any(c["gate_kind"] == "code" for c in s["checks"])])
print("when_unevaluated", plan["when_unevaluated"], "excluded", plan["excluded"])
n = plan.get("norm_trace") or {}
print("norm_trace", n.get("items"), n.get("by_stage"))
print("norm_trace_marks", n.get("marks"))
items = nt.read_items(t["specs"], t["lesson"])
got, ms = mdt.mode_items(t["specs"], t["lesson"], items)
print("mode_stages", ms)
print("mode_items", len(got), "not_by_test", sorted(set(got) & set(nt.not_by_test(items))))
print("norm_trace_mutation", mt.mutation_cfg(t), "stage_tests", mt.stage_tests_cfg(t), "norm_trace_mode", mdt.mode_cfg(t))
print("profile_probe_on", loop.profile_probe_cfg(t))
print("context_window", loop.context_window(t), "share", loop.WINDOW_SHARE, "budget", variant_b.budget(t),
      "ceilings", loop.token_ceilings(t))
print("round_caps", {k: t.get(k) for k in ("miniswe_steps", "miniswe_round_max_input_tokens", "miniswe_plan_round",
      "miniswe_plan_steps", "miniswe_plan_round_max_input_tokens", "miniswe_stable_prefix", "miniswe_head")})
t2 = copy.deepcopy(t); t2["stages"]["m_passport"] = dict(t["stages"]["m_passport"], path=mpass)
bad = variant_b.prep_violations(t2, t["specs"], None)
print("prep_violations", len(bad), bad[:10])
print("m_passport_violations", variant_b.m_passport_violations(t2["stages"]["m_passport"], t["specs"], t["specs_sha"]))
t5 = copy.deepcopy(t2); t5["stages"]["m_passport"]["sha256"] = "ccd61598be4d50b3ed4ddc35088b458c10a34a3ba66d0be612b0d43de27a5ec2"
print("control passport of attempt 6:", variant_b.m_passport_violations(t5["stages"]["m_passport"], t["specs"], t["specs_sha"])[:2])
for k in ("norm_trace_mutation", "norm_trace_mode", "stage_tests"):
    t3 = copy.deepcopy(t); t3["stages"][k] = 1
    print("control", k, "=1:", mt.prep_violations(t3) + mdt.prep_violations(t3))
t4 = copy.deepcopy(t); t4["stages"]["norm_trace"] = False
print("control norm_trace=false:", mt.prep_violations(t4) + mdt.prep_violations(t4))
