"""Exact P01.277 vs P01.254 rosters and per-file added/deleted line counts.

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
O = Path("/home/pilot/run-p01254-pair-20261112-r3")
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
    "M": (O / "pair-298e28fda4b9/M.git", "847ac9d1fb36bd1153450f99ddc4805c2609877e",
          Path(I["M_git"]), I["M"]),
    "J": (O / "pair-298e28fda4b9/J.git", "0b34ab1bee38b72451cbcb4466feea6ab96d8da0",
          Path(I["pair_directory"]) / "J.git", I["J"]),
    "J-input": (O / "ji-298e28fda4b9/JI.git", "2fc272022ff073aaa75ce6dac1b953286c0d8b3d",
                Path(I["JI_directory"]) / "JI.git", I["JI"]),
}
result = {"from_C": "298e28fda4b91df25357e3a83d5e70045bea7bb2", "to_C": I["C"],
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

lines = ["# P01.277 — дельта против P01.254", "", f"C P01.254: `{result['from_C']}`; C P01.277: `{I['C']}`.", "", "Сравнены все пути, режимы и blob. Числа строк — `git diff --no-renames --numstat`; бинарные изменения обозначены `-`. Служебный COURSE_COMMIT учтён.", "", "| Выгрузка | Файлов до → после | Добавлено | Изменено | Удалено | +строк | −строк |", "|---|---:|---:|---:|---:|---:|---:|"]
for name, row in result["views"].items():
    count = row["counts"]
    lines.append(f"| {name} | {row['before']['files']} → {row['after']['files']} | {count['add']} | {count['modify']} | {count['delete']} | {row['lines_added']} | {row['lines_deleted']} |")
lines += ["", "[DELTA-FILES.tsv](DELTA-FILES.tsv) перечисляет каждый изменённый файл, число строк и оба blob. [REMOVED-M.tsv](REMOVED-M.tsv) содержит полный список снятых файлов M. Машинная опись с размерами до/после — DELTA-PAIR.json в каталоге доказательств.", "", "Состав M изменён только целыми файлами: сначала действующий фильтр курса, затем pair_m для P/01 и два разрешённых исключения common по answered 20:17:43Z. J остаётся всей Platform из C с COURSE_COMMIT. J-вход получает role-certificate.md; остальная разница его данных и текста пришла из принятого main.", "", "Семантическая дельта фильтров против P01.254 — четыре записи: rights.json, group.tsv и stand-manifests.tsv перешли в judge_only; role-certificate.md — в include J-входа. Классификации проверены принятыми обзорами P01.283 и P01.271. Сужение до P/01 не меняет глобальные фильтры или операторы.", ""]
(D / "DELTA-PAIR.md").write_text("\n".join(lines))
with (D / "REMOVED-M.tsv").open("w", newline="") as f:
    writer=csv.writer(f, delimiter="\t", lineterminator="\n")
    writer.writerow(["path","blob_before","bytes_before","basis"])
    for row in result["views"]["M"]["paths"]:
        if row["action"] != "delete": continue
        path=row["path"]
        reason = "authorized P03 common exclusion" if path in {"Platform/common/acceptance/testsub-stand.md","Platform/common/vectors/slot/README.md"} else "global filter now judge_only" if path in {"Platform/01-store/acceptance/1/inputs/rights.json","Platform/01-store/forms/group.tsv","Platform/common/acceptance/forms/stand-manifests.tsv"} else "other lesson outside explicit P01 dependency table"
        writer.writerow([path,row["before"]["blob"],row["before"]["bytes"],reason])
print(json.dumps({name:{k:row[k] for k in ("counts","lines_added","lines_deleted")} for name,row in result["views"].items()},indent=1))
