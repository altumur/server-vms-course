"""Exact P01.332 vs P01.299 rosters and per-file added/deleted line counts.

Own delta.git imports the six parentless exports. Git --no-renames --numstat
counts lines; a binary result stays '-'. No implementation is executed.
Usage: python3 -B delta_pair.py <evidence> <report directory>
"""
from pathlib import Path
import collections
import csv
import hashlib
import json
import subprocess
import sys

B, D = map(lambda x: Path(x).resolve(), sys.argv[1:3])
I = json.loads((B / "IDENTITIES.json").read_text())
O = Path("/home/pilot/P01.299-evidence/r2")
R = B / "delta.git"
assert not R.exists()
subprocess.run(["git", "init", "--quiet", "--bare", str(R)], check=True)


def g(*args):
    return subprocess.check_output(["git", "--git-dir", str(R), *args])


def tree(commit):
    result = {}
    for row in g("ls-tree", "-r", "-l", "-z", commit).split(b"\0"):
        if row:
            meta, name = row.split(b"\t", 1)
            mode, kind, blob, size = meta.decode().split()
            result[name.decode()] = {"mode": mode, "type": kind,
                "blob": blob, "bytes": int(size)}
    return result


views = {
    "M": (O / "narrow/M.git", "bfa66fa76ecfb2c1d9b59c7ac7e2641722493942",
          Path(I["M_git"]), I["M"]),
    "J": (O / "pair-30310352523e/J.git", "ff76875d0e5e44a0f6ed36bf9d66500ad1af3124",
          Path(I["pair_directory"]) / "J.git", I["J"]),
    "J-input": (O / "ji-30310352523e/JI.git", "b4241b80947513de0afb1832dcacacc8569c5dcb",
                Path(I["JI_directory"]) / "JI.git", I["JI"]),
}
result = {"from_C": "30310352523e30aa7e7879d901e44d80e01b118d", "to_C": I["C"],
          "line_method": "git diff --no-renames --numstat -z; '-' means binary", "views": {}}
table = []
for name, (od, oc, nd, nc) in views.items():
    for gd, commit, label in ((od, oc, "before"), (nd, nc, "after")):
        subprocess.run(["git", "--git-dir", str(R), "fetch", "--quiet", "--no-tags", str(gd),
                        commit + ":refs/heads/" + name + "-" + label], check=True)
    a, b = tree(oc), tree(nc)
    changes = []
    counts = collections.Counter()
    groups = collections.defaultdict(collections.Counter)
    nums = {}
    for row in g("diff", "--no-renames", "--numstat", "-z", oc, nc).split(b"\0"):
        if row:
            plus, minus, path = row.decode().split("\t", 2)
            nums[path] = (plus, minus)
    expected = {p for p in set(a) | set(b) if a.get(p) != b.get(p)}
    assert set(nums) == expected, (name, set(nums) ^ expected)
    for path in sorted(expected):
        action = "add" if path not in a else "delete" if path not in b else "modify"
        plus, minus = nums[path]
        item = {"path": path, "action": action, "lines_added": plus, "lines_deleted": minus,
                "before": a.get(path), "after": b.get(path)}
        changes.append(item)
        counts[action] += 1
        groups[path.split("/")[1]][action] += 1
        table.append([name, path, action, plus, minus,
                      a.get(path, {}).get("blob", "-"), b.get(path, {}).get("blob", "-")])
    result["views"][name] = {
        "before": {"commit": oc, "files": len(a), "bytes": sum(x["bytes"] for x in a.values())},
        "after": {"commit": nc, "files": len(b), "bytes": sum(x["bytes"] for x in b.values())},
        "counts": {key: counts[key] for key in ("add", "modify", "delete")},
        "lines_added": sum(int(v[0]) for v in nums.values() if v[0] != "-"),
        "lines_deleted": sum(int(v[1]) for v in nums.values() if v[1] != "-"),
        "binary_changes": sum(v[0] == "-" for v in nums.values()),
        "groups": dict(groups), "paths": changes}
(B / "DELTA-PAIR.json").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n")
header = ["view", "path", "action", "lines_added", "lines_deleted", "blob_before", "blob_after"]
for target in (B / "DELTA-FILES.tsv", D / "DELTA-FILES.tsv"):
    with target.open("w", newline="") as f:
        writer = csv.writer(f, delimiter="\t", lineterminator="\n")
        writer.writerow(header)
        writer.writerows(table)

lines = ["# P01.332 — дельта M8′/J8′ к M8″/J8″", "", f"C8′: `{result['from_C']}`; C8″: `{I['C']}`.", "", "Сравнены все пути, режимы и blob. Числа строк — `git diff --no-renames --numstat`; бинарные изменения обозначены `-`. Служебный COURSE_COMMIT учтён.", "", "| Выгрузка | Файлов до → после | Добавлено | Изменено | Удалено | +строк | −строк |", "|---|---:|---:|---:|---:|---:|---:|"]
for name, row in result["views"].items():
    count = row["counts"]
    lines.append(f"| {name} | {row['before']['files']} → {row['after']['files']} | {count['add']} | {count['modify']} | {count['delete']} | {row['lines_added']} | {row['lines_deleted']} |")
lines += ["", "[DELTA-FILES.tsv](DELTA-FILES.tsv) перечисляет каждый изменённый файл, число строк и оба blob. Машинная опись с режимами и размерами до/после — DELTA-PAIR.json в каталоге доказательств.", "", "Новая M отобрана текущим pair_m точного C с обязательным COURSE_COMMIT. J содержит всю Platform из C с маркером; J-вход — точный include собранного фильтра. Журнал изменений норм для доработки — CHANGED-NORMS.md; полная дельта файлов не содержит выводов о поведении кандидата.", ""]
(D / "DELTA-PAIR.md").write_text("\n".join(lines))
print(json.dumps({name:{k:row[k] for k in ("counts","lines_added","lines_deleted")} for name,row in result["views"].items()},indent=1))
