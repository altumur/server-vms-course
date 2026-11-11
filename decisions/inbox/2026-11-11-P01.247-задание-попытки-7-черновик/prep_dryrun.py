"""P01.247: the loop's prep of the attempt-7 draft outside the stand. The draft is filled by fill_pair.py with the pair of
attempt 6 (M bf846208, passport ccd61598…) — only to see that the loop takes the keys; the pair of attempt 7 is not out yet.
stage_prep (generation_plan, code checks, norm_trace, the bool keys of P01.179/P01.216, profile_probe), variant_b.prep_violations
with stages.m_passport pointed at a local copy of the same passport (same sha256), the window and the caps the loop reads.
Run: python3 -I prep_dryrun.py <minimax-loop tree> <filled task json> <M tree> <PASSPORT-M.json copy> <loop head> [<main tree>]"""
import sys, copy
mm, task_p, mtree, mpass = sys.argv[1:5]
sys.path.insert(0, mm)
import loop, variant_b, mutation_trace as mt, mode_trace as mdt
t = loop.load_task(task_p)
class R: pass
r = R(); r.map = {"specs": mtree}
print("loop_head", sys.argv[5] if len(sys.argv) > 5 else "")
print("prep_bool_keys", mt.prep_violations(t) + mdt.prep_violations(t))
plan = loop.stage_prep(t, r)
st = plan["stages"]
print("stages", len(st), [s["stage"] for s in st])
print("code_at", [s["stage"] for s in st if any(c["gate_kind"] == "code" for c in s["checks"])])
print("when_unevaluated", plan["when_unevaluated"], "excluded", plan["excluded"])
nt = plan.get("norm_trace")
print("norm_trace", nt["items"] if nt else None, nt["by_stage"] if nt else None)
print("norm_trace_mutation", mt.mutation_cfg(t), "stage_tests", mt.stage_tests_cfg(t), "norm_trace_mode", mdt.mode_cfg(t))
print("mode_stages", mdt.mode_stages(mtree, t["lesson"]))
print("profile_probe_on", loop.profile_probe_cfg(t))
print("context_window", loop.context_window(t), "share", loop.WINDOW_SHARE, "budget", variant_b.budget(t),
      "ceilings", loop.token_ceilings(t))
print("round_caps", {k: t.get(k) for k in ("miniswe_steps", "miniswe_round_max_input_tokens", "miniswe_plan_round",
      "miniswe_plan_steps", "miniswe_plan_round_max_input_tokens", "miniswe_stable_prefix", "miniswe_head")})
t2 = copy.deepcopy(t); t2["stages"]["m_passport"] = dict(t["stages"]["m_passport"], path=mpass)
bad = variant_b.prep_violations(t2, mtree, None)
print("prep_violations", len(bad), bad[:10])
print("m_passport_violations", variant_b.m_passport_violations(t2["stages"]["m_passport"], mtree, t["specs_sha"]))
for k in ("norm_trace_mutation", "norm_trace_mode", "stage_tests"):
    t3 = copy.deepcopy(t); t3["stages"][k] = 1
    print("control", k, "=1:", mt.prep_violations(t3) + mdt.prep_violations(t3))
t4 = copy.deepcopy(t); t4["stages"]["norm_trace"] = False
print("control norm_trace=false:", mt.prep_violations(t4) + mdt.prep_violations(t4))
if len(sys.argv) > 6:   # the mode stages on today's main: the M of attempt 7 is cut from it after the spec tasks
    print("mode_stages_main", mdt.mode_stages(sys.argv[6], t["lesson"]))
