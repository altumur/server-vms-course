"""Exact P01.254 vs P01.251 rosters and per-file added/deleted line counts.

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
O = Path("/home/pilot/run-p01251-pair-20261112-r2")
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
    "M": (O / "pair-2d101991ac6e/M.git", "da04d237b656aafc8b30fb382c44406a80642cac",
          Path(I["pair_directory"]) / "M.git", I["M"]),
    "J": (O / "pair-2d101991ac6e/J.git", "f0855df6131ee0eda2bf1e4c93ef4ca8ca5f961c",
          Path(I["pair_directory"]) / "J.git", I["J"]),
    "J-input": (O / "ji-2d101991ac6e/JI.git", "c0f91c726a635db26f4d22449b93731813042251",
                Path(I["JI_directory"]) / "JI.git", I["JI"]),
}
result = {"from_C": "2d101991ac6eb656421f6e86a1ce742af994363d", "to_C": I["C"],
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
lines = ["# P01.254 — дельта выгрузок против P01.251", "",
         f"C P01.251: `{result['from_C']}`. Новый C: `{I['C']}`.", "",
         "Сравнены все пути, режимы, типы объектов и blob. Числа строк получены Git с `--no-renames --numstat`; бинарные файлы отмечены `-`. Смена маркера `Platform/COURSE_COMMIT` включена в каждую выгрузку.", "",
         "| Выгрузка | Файлов до → после | Добавлено | Изменено | Удалено | +строк | −строк |",
         "|---|---:|---:|---:|---:|---:|---:|"]
for name, r in result["views"].items():
    c = r["counts"]
    lines.append(f"| {name} | {r['before']['files']} → {r['after']['files']} | {c['add']} | {c['modify']} | {c['delete']} | {r['lines_added']} | {r['lines_deleted']} |")
lines += ["", "Полная таблица **каждого** изменённого файла с +/− строк и обоими blob — [DELTA-FILES.tsv](DELTA-FILES.tsv). В ней нет выборочного сокращения; её строки покрывают всю дельту M, J и J-входа. Полная JSON-опись со старыми и новыми режимами, размерами и группировкой — `" + str(B / "DELTA-PAIR.json") + "`.", "",
          "Новые файлы: `01-store/acceptance/1/inputs/rights.json`, `common/acceptance/forms/stand-manifests.tsv` и схема, `common/vectors/compare-scope.tsv`, `probe-tables.tsv` и схема. В M входят rights, stand-manifests и probe-tables; compare-scope и схемы закрыты. J-вход получает rights, stand-manifests, compare-scope, probe-tables и ранее исключённый OpenAPI P/01. Схемы остаются закрытыми. Семантическая дельта фильтров: шесть добавленных записей и одна смена `exclude` → `include` для OpenAPI; удалений нет.", "",
          "Остальные изменения пришли из принятого main: этап Б формы M всех уроков, снятие See also, общие определения OBSH.45, P/10-якорь и принятые P01.256–P01.259. Путь/режим/blob каждой выгрузки вычислен штатными операторами; ручного вырезания или подмены файлов не было. ASCII-кавычки двух basis исправил Архитектор в C `298e28fda`, классификации сохранены.", ""]
(D / "DELTA-PAIR.md").write_text("\n".join(lines))
print(json.dumps({name: {k: r[k] for k in ("counts", "lines_added", "lines_deleted", "binary_changes")}
                  for name, r in result["views"].items()}, ensure_ascii=False, indent=1))
