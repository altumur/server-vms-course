"""Run the exact OBSH.56 reference checker; retain every diagnostic and select OBSH.57 lessons."""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--root", type=Path, default=Path.cwd())
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
root = args.root.resolve()
checker_commit = "8e7457483660d3339beab46ccdbf38a7a204f03b"
checker_path = "skills/lesson-spec/scripts/form_refs.py"
lessons = ("04-controller", "05-resource", "06-console", "08-domain")
sys.dont_write_bytecode = True
sys.path.insert(0, str(root / "skills/lesson-spec/scripts"))
from check_spec import Check

source = subprocess.check_output(["git", "show", f"{checker_commit}:{checker_path}"], cwd=root)
with tempfile.TemporaryDirectory(prefix="OBSH.57-form-refs-") as tmp:
    module_path = Path(tmp) / "form_refs.py"
    module_path.write_bytes(source)
    spec = importlib.util.spec_from_file_location("obsh57_form_refs", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    check = Check(root, scope="platform")
    forms = module.forms(root)
    module.run(check)

selected = [e for e in check.errors if any(e.startswith(f"Platform/{lesson}/") for lesson in lessons)]
result = {
    "task": "OBSH.57",
    "root": str(root),
    "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
    "checker_commit": checker_commit,
    "checker_path": checker_path,
    "checker_sha256": hashlib.sha256(source).hexdigest(),
    "checked_forms": [p.relative_to(root).as_posix() for p in forms],
    "selected_forms": [p.relative_to(root).as_posix() for p in forms if p.parts[len(root.parts) + 1] in lessons],
    "stats": dict(sorted(check.stats.items())),
    "all_errors": check.errors,
    "selected_errors": selected,
    "selected_error_count": len(selected),
    "other_error_count": len(check.errors) - len(selected),
    "selected_exit_code": 1 if selected else 0,
}
args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({k: result[k] for k in ("stats", "selected_error_count", "other_error_count", "selected_exit_code")}, ensure_ascii=False))
sys.exit(result["selected_exit_code"])
