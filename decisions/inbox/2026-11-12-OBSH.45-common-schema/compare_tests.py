"""Compare unittest failures including subtest identities, not just aggregate counts."""
import json
import re
from collections import Counter
from pathlib import Path

home = Path(__file__).resolve().parent
def load(name):
    text = (home / name).read_text()
    ran = re.search(r"^Ran ([0-9]+) tests in ([0-9.]+)s$", text, re.M)
    final = re.search(r"^(?:FAILED \([^\n]+\)|OK(?: \([^\n]+\))?)$", text, re.M)
    assert ran and final, (name, "incomplete suite")
    failures = Counter(re.findall(r"^(FAIL|ERROR): (.+)$", text, re.M))
    return {"tests": int(ran[1]), "seconds": float(ran[2]), "result": final[0]}, failures

before, old = load("skill-tests-before.log")
after, new = load("skill-tests-after.log")
added, removed = new - old, old - new
def rows(counter):
    return [{"kind": key[0], "test_and_subtest": key[1], "count": count}
            for key, count in sorted(counter.items())]

result = {"before": before, "after": after, "new_failures": rows(added),
          "resolved_failures": rows(removed), "unchanged_failures": rows(old & new),
          "no_new_failures": not added and before["tests"] == after["tests"]}
print(json.dumps(result, ensure_ascii=False, indent=2))
raise SystemExit(0 if result["no_new_failures"] else 1)
