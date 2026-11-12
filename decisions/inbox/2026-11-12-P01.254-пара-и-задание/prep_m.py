"""P01.254: the loop's prep of task-attempt7.json on the recut M outside the stand.
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
known_items = nt.read_items(t["specs"], t["lesson"])
items = nt.active_items(known_items)
print("known_items", len(known_items), "active_items", len(items))
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

# Fail if preparation or a negative control no longer behaves as printed above.
assert not bad, bad
assert not variant_b.m_passport_violations(t2["stages"]["m_passport"], t["specs"], t["specs_sha"])
assert len(st) == 11 and [s["stage"] for s in st] == t["stages"]["list"]
assert len([s for s in st if any(c["gate_kind"] == "code" for c in s["checks"])]) == 9
assert n.get("items") == 53 and n.get("marks", {}).get("read") == 53
assert not n.get("marks", {}).get("unread")
assert len(n["marks"]["not_by_test"]) == 12
assert len(known_items) == 54 and len(items) == 53
assert "P/01.1-21" not in {it["id"] for it in items}
assert len(got) == 16 and len(set(got) & set(nt.not_by_test(items))) == 5
assert variant_b.m_passport_violations(t5["stages"]["m_passport"], t["specs"], t["specs_sha"])
for key in ("norm_trace_mutation", "norm_trace_mode", "stage_tests"):
    control = copy.deepcopy(t); control["stages"][key] = 1
    assert mt.prep_violations(control) + mdt.prep_violations(control), key
assert mt.prep_violations(t4) + mdt.prep_violations(t4)
assert loop.profile_probe_cfg(t) and loop.context_window(t) == 200000 and loop.WINDOW_SHARE == 0.9
assert t["max_input_tokens"] == 150000000 and t["max_active_hours"] == 24 and t["stall_rounds"] == 3
assert t["miniswe_steps"] == 60 and t["miniswe_round_max_input_tokens"] == 6000000
assert t["miniswe_plan_round"] is True and t["miniswe_plan_steps"] == 30
assert t["miniswe_plan_round_max_input_tokens"] == 6000000 and t["miniswe_stable_prefix"] is True
assert t["miniswe_design_max"] == 32000 and t["miniswe_plan_idle_steps"] == 3
print("plan_limits", {k: t[k] for k in ("miniswe_design_max", "miniswe_plan_idle_steps")})
assert all(os.path.isfile(os.path.join(t["specs"], p)) for p in t["head_files"])
# Read only M data; no candidate, product command or start is executed.
import profile_probe as pp
form = os.path.join(t["specs"], "Platform", pp.STAND_ENV_REL)
assert os.path.isfile(form)
rows = pp._tsv(form)
env, reason = pp.stand_env(t["specs"], "Platform")
print("stand_environment_form", len(rows), "rows; names_read", sorted(env), "reason", reason)
assert len(rows) == 45 and env and reason is None
print("stand_environment_limit", "P01.253: reader takes the form; processes not started by preparation")
examples = pp.json_examples(t["specs"], "Platform")
print("json_example_names", sorted(examples))
print("stand_directories", [(x["name"], x["rel"], x["mode"]) for x in pp.stand_dirs(t["specs"], "Platform")])
if not examples:
    print("start_input_limit", "no inline JSON example read; new M names an input file; start not validated by this preparation")
print("PREP PASS")
