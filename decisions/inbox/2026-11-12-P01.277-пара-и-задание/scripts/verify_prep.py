"""Verify real offline prep and capture heads, without constructing any agent/model.
Usage: loop-venv-python -I -B verify_prep.py <evidence> <report directory>
"""
from pathlib import Path
import copy
import hashlib
import json
import os
import sys
import tempfile

B, D = map(lambda p: Path(p).resolve(), sys.argv[1:3])
sys.path.insert(0, str(B / "loop"))
import loop
import mode_trace
import mutation_trace
import norm_trace
import variant_b

report = json.loads((B / "PREP-FULL.json").read_text())
run = json.loads((B / "PREP-FULL.run.json").read_text())
identities = json.loads((B / "IDENTITIES.json").read_text())
assert run["exit"] == 0 and report["ok"] and report["turns"] == report["acceptance_rounds"] == 0
assert report["specs"] == identities["M"]
task = loop.load_task(str(B / "task-prep-final.json"))
task["_run"] = report["run"]
for key in ("work", "rules", "acc"):
    task["_" + key] = str(Path(report["run"]) / key)
assert task["miniswe_steps"] == task["miniswe_plan_steps"] == 60
assert task["miniswe_round_max_input_tokens"] == task["miniswe_plan_round_max_input_tokens"] == 6000000
assert task["miniswe_plan_idle_steps"] == 8 and task["miniswe_design_max"] == 32000
assert task["max_input_tokens"] == 150000000 and task["max_active_hours"] == 24
assert task["stall_rounds"] == 3 and task["miniswe_stable_prefix"] is True
assert task["stages"]["mech"]["test"] == "go test -race -count=1 ./..."
assert all(task["stages"][key] is True for key in ("norm_trace", "norm_trace_mutation", "norm_trace_mode", "stage_tests"))
assert not mutation_trace.prep_violations(task) and not mode_trace.prep_violations(task)
assert not variant_b.m_passport_violations(task["stages"]["m_passport"], task["specs"], task["specs_sha"])
plan = report["plan"]
assert len(plan["stages"]) == 11
assert [s["stage"] for s in plan["stages"]] == task["stages"]["list"]
trace = plan["norm_trace"]
items = norm_trace.read_items(task["specs"], task["lesson"])
assert len(items) == 54 and len(norm_trace.active_items(items)) == 53
assert trace["items"] == trace["marks"]["read"] == 53 and not trace["marks"]["unread"]
assert len(trace["marks"]["not_by_test"]) == 12
assert trace["by_stage"]["group"] == 16
warnings = report["warnings"]
assert len(warnings) == 7
assert sum("over miniswe_section_max 20000" in s for s in warnings) == 6
assert [s for s in warnings if "cited path not in M" in s] == ["cited path not in M: group: forms/group.tsv"]
assert report["head_files"] == 14 and report["initial_requests"]["design_chars"] == 0
controls = []
for key in ("norm_trace_mutation", "norm_trace_mode", "stage_tests"):
    bad = copy.deepcopy(task)
    bad["stages"][key] = 1
    reasons = mutation_trace.prep_violations(bad) + mode_trace.prep_violations(bad)
    assert reasons
    controls.append({"name": key + "=1", "reasons": reasons})
bad = copy.deepcopy(task)
bad["stages"]["norm_trace"] = False
reasons = mutation_trace.prep_violations(bad) + mode_trace.prep_violations(bad)
assert reasons
controls.append({"name": "norm_trace=false", "reasons": reasons})
bad = copy.deepcopy(task)
bad["stages"]["m_passport"]["sha256"] = "0" * 64
reasons = variant_b.m_passport_violations(bad["stages"]["m_passport"], bad["specs"], bad["specs_sha"])
assert reasons
controls.append({"name": "wrong-passport-sha256", "reasons": reasons})

# Mini-SWE imports read a global dotenv by default. Import under an empty,
# private configuration directory as the unchanged prep_task.py does.
with tempfile.TemporaryDirectory(prefix="verify-heads-config-", dir=B) as config:
    os.environ.update(MSWEA_GLOBAL_CONFIG_DIR=config, MSWEA_SILENT_STARTUP="1", LITELLM_LOCAL_MODEL_COST_MAP="True")
    import agent_miniswe as agent
    heads = B / "heads-final"
    heads.mkdir()
    root = loop.Roots(task)
    head, taken, missing = loop.build_head(task, root, True)
    assert not missing and len(taken) == 14
    rules = agent.work_rules_text(task)
    assert rules
    metadata = []
    const, text = agent.plan_prompt(task)
    assert rules in const
    for name, body in (("plan-constant", const), ("plan-task", text)):
        (heads / (name + ".txt")).write_text(body)
    metadata.append({"round": "plan", "rules_full": True, "chars": len(const) + len(text)})
    for index, stage in enumerate(plan["stages"]):
        state = dict(plan, plan=plan["stages"], cur=index)
        note = loop.stage_note_text(task, state)
        messages = [{"role": "system", "content": loop.SYSTEM}, {"role": "user", "content": head},
                    {"role": "user", "content": note}]
        const, text = agent.stage_prompt(task, messages, first=index == 0)
        assert rules in const
        for suffix, body in (("constant", const), ("task", text)):
            (heads / (stage["stage"] + "-" + suffix + ".txt")).write_text(body)
        metadata.append({"round": stage["stage"], "rules_full": True, "chars": len(const) + len(text),
                         "cited_missing": list(agent.HEAD_INFO.get("cited_missing") or [])})
        if stage["stage"] == "group":
            assert agent.HEAD_INFO["cited_missing"] == ["forms/group.tsv"]
            assert not (Path(task["specs"]) / "Platform/01-store/forms/group.tsv").exists()
            assert "=== $SPECS/Platform/01-store/forms/group.tsv ===" not in text
            assert "P/01.3-" in text   # checklist items remain available with the public group norms
    manifest = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(heads.iterdir())}
    (heads / "MANIFEST.json").write_text(json.dumps(manifest, indent=1) + "\n")
out = {"M": identities["M"], "loop_head": json.loads((B / "LOOP-MANIFEST.json").read_text())["head"],
       "prep_exit": 0, "turns": 0, "acceptance_rounds": 0, "known_items": 54, "active_items": 53,
       "norm_trace": trace, "head_files": 14, "rules_in_all_12_heads": True,
       "group_head_without_group_form": True, "heads": metadata,
       "negative_controls": controls, "warnings": warnings, "OK": True}
(B / "PREP-VERIFY.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
rows = ["round\tchars_without_templates\tchars_with_templates\ttokens_estimate_with_templates"]
requests = report["initial_requests"]
for name, size in [("plan", requests["plan"])] + [(s["stage"], s) for s in requests["stages"]]:
    rows.append("\t".join(map(str, (name, size["without_templates"]["chars"], size["with_templates"]["chars"],
                                   size["with_templates"]["tokens_estimate"]))))
(D / "INITIAL-REQUESTS.tsv").write_text("\n".join(rows) + "\n")
print(json.dumps({"OK": True, "heads": len(metadata), "rules_full": True, "controls": len(controls), "warnings": len(warnings)}))
