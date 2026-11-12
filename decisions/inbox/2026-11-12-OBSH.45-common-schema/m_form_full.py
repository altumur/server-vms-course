"""Run all seven existing m_form checks per Platform lesson, without changing the skill."""
import json
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root / "skills/lesson-spec/scripts"))
import m_form
from check_spec import Check

results = {}
m_form.M_FORM_STAGE_A = set()
m_form.M_FORM_COMMON = ()
for number in range(1, 11):
    key = f"P/{number:02d}"
    m_form.M_FORM_LESSONS = {key}
    check = Check(root, scope="platform")
    m_form.run(check, {f"{number:02d}"})
    results[key] = {
        "status": "PASS" if not check.errors else "FAIL",
        "stats": dict(check.stats),
        "errors": check.errors,
    }
print(json.dumps(results, ensure_ascii=False, indent=2))
