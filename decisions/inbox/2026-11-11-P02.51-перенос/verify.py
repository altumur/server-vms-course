"""P02.51: the assembled registry and filters of a tree are byte-equal to the former whole files of a base commit.

Usage: python3 -I verify.py <repo> <base-commit>   (the tree checked is the working tree of <repo>)

Registry: target_registry.assemble (check_spec, P02.50) over the tree; its rows, in assembly order, are compared with the
data rows of the former Platform/common/acceptance/forms/targets.tsv and targets.routing.tsv of <base>, byte for byte.
Filters: by the rule of Platform/common/acceptance/README.md («Target registry and export lists assembled from the
lessons»): the records of the common filter and of the lists forms/export.json of the lessons, sorted by path, written as
JSON with indent 2, non-ASCII as is, final LF. The result minus the records of the files new in the tree (the lesson
forms of this transfer) must be byte-equal to the former whole filter of <base>; the new records are printed.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

repo, base = Path(sys.argv[1]).resolve(), sys.argv[2]
sys.path.insert(0, str(repo / "skills/lesson-spec/scripts"))
import target_registry  # noqa: E402

LESSON_DIR = re.compile(r"^\d\d-[a-z0-9-]+$")
COMMON = {"model": "Platform/common/export-model-filter.json", "judge": "Platform/common/acceptance/judge-input-filter.json"}
failed = False


def old(path):
    return subprocess.run(["git", "-C", str(repo), "show", f"{base}:{path}"], check=True, capture_output=True).stdout.decode()


def data_rows(text):
    rows = [line for line in text.split("\n") if line and not line.startswith("#")]
    return rows[0], rows[1:]


def dump(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


targets, routing, errors, stats = target_registry.assemble(repo)
print("registry errors:", errors, "stats:", stats)
failed |= bool(errors)
for name, got in (("targets.tsv", targets), ("targets.routing.tsv", routing)):
    header, want = data_rows(old(f"Platform/common/acceptance/forms/{name}"))
    have = ["\t".join(row[c] for c in header.split("\t")) for _, _, row in got]
    same = have == want
    failed |= not same
    places = sorted({str(p.relative_to(repo)) for p, _, _ in got})
    print(f"registry {name}: {len(have)} rows from {places}; byte-equal to {base[:12]}: {same}")

lessons = sorted(p.name for p in (repo / "Platform").iterdir() if p.is_dir() and LESSON_DIR.match(p.name))
for side, common_path in COMMON.items():
    common = json.loads((repo / common_path).read_text(encoding="utf-8"))
    records = list(common["files"])
    for lesson in lessons:
        form = repo / "Platform" / lesson / "forms" / "export.json"
        if form.is_file():
            records += json.loads(form.read_text(encoding="utf-8"))[side]
    records.sort(key=lambda r: r["path"].encode())
    paths = [r["path"] for r in records]
    dup = len(paths) != len(set(paths))
    assembled = dict(common, files=records)
    former_text = old(common_path)
    former = json.loads(former_text)
    former_paths = {r["path"] for r in former["files"]}
    new = [r for r in records if r["path"] not in former_paths]
    rest = dict(assembled, files=[r for r in records if r["path"] in former_paths])
    same = dump(rest) == former_text
    failed |= dup or not same
    print(f"filter {side}: {len(records)} records assembled, duplicates {dup}; without the {len(new)} new records "
          f"byte-equal to {common_path} of {base[:12]}: {same}")
    for r in new:
        print(f"  new {r['path']}: {r['disposition']}")
sys.exit(1 if failed else 0)
