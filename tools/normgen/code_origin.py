#!/usr/bin/env python3
"""Count final source lines by kit provenance, from pinned Git objects only (ADR-0127 (2)).

No source comments, working-tree files, manifest line totals or Git authors are used.
The JSON report contains hashes and decisions for each counted file, never its text.
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

ORIGINS = ("generated", "handwritten", "model")
KINDS = ("code", "tests")


class CountError(ValueError):
    pass


def object_pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise CountError(f"duplicate JSON key: {key}")
        out[key] = value
    return out


def read_json(raw):
    try:
        return json.loads(raw, object_pairs_hook=object_pairs)
    except (ValueError, UnicodeError) as exc:
        raise CountError(f"invalid JSON: {exc}") from exc


def fields(value, required, optional=()):
    if not isinstance(value, dict) or set(value) - set(required) - set(optional) or set(required) - set(value):
        raise CountError(f"expected fields {', '.join(required)}; optional {', '.join(optional)}")


def path(value):
    if (not isinstance(value, str) or not value or "\\" in value
            or any(ord(c) < 32 for c in value) or PurePosixPath(value).is_absolute()
            or ".." in value.split("/") or str(PurePosixPath(value)) != value):
        raise CountError(f"not a canonical relative path: {value!r}")
    return value


def strings(values, label):
    if not isinstance(values, list) or not values or any(not isinstance(v, str) or not v for v in values):
        raise CountError(f"{label}: expected a nonempty string array")
    if len(set(values)) != len(values):
        raise CountError(f"{label}: duplicate entry")
    return values


def within(file, directory):
    return directory == "." or file == directory or file.startswith(directory + "/")


def physical_lines(data):
    """LF-terminated physical lines; count a nonempty unterminated last line too."""
    return data.count(b"\n") + int(bool(data) and not data.endswith(b"\n"))


def sha256(data):
    return hashlib.sha256(data).hexdigest()


class Snapshot:
    def __init__(self, repo, commit):
        if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", commit):
            raise CountError("a full lowercase Git commit SHA is required")
        self.repo = repo
        self.commit = commit
        if self.git("rev-parse", "--verify", commit + "^{commit}").decode().strip() != commit:
            raise CountError("pin is not a commit object")
        self.tree = self.git("rev-parse", commit + "^{tree}").decode().strip()
        self.entries = {}
        self.blobs = {}
        for record in self.git("ls-tree", "-r", "-z", commit).split(b"\0"):
            if not record:
                continue
            meta, name = record.split(b"\t", 1)
            mode, kind, oid = meta.decode("ascii").split()
            self.entries[path(name.decode("utf-8"))] = (mode, kind, oid)

    def git(self, *args):
        result = subprocess.run(["git", "--no-replace-objects", *args], cwd=self.repo,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode:
            # Do not echo object contents or paths from arbitrary Git error messages.
            raise CountError(f"Git {args[0]} failed for pin {self.commit}")
        return result.stdout

    def blob(self, name):
        if name not in self.entries:
            raise CountError(f"file missing at {self.commit}: {name}")
        mode, kind, oid = self.entries[name]
        if mode not in ("100644", "100755") or kind != "blob":
            raise CountError(f"not a regular Git file: {name}")
        if oid not in self.blobs:
            self.blobs[oid] = self.git("cat-file", "blob", oid)
        return self.blobs[oid]


def empty_totals():
    return {kind: {origin: {"files": 0, "lines": 0} for origin in ORIGINS} for kind in KINDS}


def add(totals, row):
    cell = totals[row["kind"]][row["origin"]]
    cell["files"] += 1
    cell["lines"] += row["lines"]


def count(config, repos):
    fields(config, ("version", "implementation", "include_dirs", "exclude_dir_names", "exclude_paths",
                    "suffixes", "test_suffixes", "packages"))
    if type(config["version"]) is not int or config["version"] != 1:
        raise CountError("unsupported config version")
    includes = [path(p) for p in strings(config["include_dirs"], "include_dirs")]
    for i, left in enumerate(includes):
        if any(within(left, right) or within(right, left) for right in includes[i + 1:]):
            raise CountError("include_dirs overlap")
    excluded_names = strings(config["exclude_dir_names"], "exclude_dir_names")
    if "vendor" not in excluded_names or any(path(p) != p or "/" in p or p == "." for p in excluded_names):
        raise CountError("exclude_dir_names must contain vendor and only directory basenames")
    if not isinstance(config["exclude_paths"], list):
        raise CountError("exclude_paths must be an array")
    excluded_paths = [path(p) for p in config["exclude_paths"]]
    if len(set(excluded_paths)) != len(excluded_paths):
        raise CountError("duplicate exclude_paths")
    suffixes = strings(config["suffixes"], "suffixes")
    test_suffixes = strings(config["test_suffixes"], "test_suffixes")
    if any("/" in s or not s.startswith(".") for s in suffixes):
        raise CountError("suffixes must be file extensions")
    if any(not any(s.endswith(ext) for ext in suffixes) or "/" in s for s in test_suffixes):
        raise CountError("test_suffixes must end in a counted extension")

    def selected(p):
        return (any(within(p, d) for d in includes) and p.endswith(tuple(suffixes))
                and not set(PurePosixPath(p).parts[:-1]) & set(excluded_names)
                and not any(within(p, d) for d in excluded_paths))

    cache = {}

    def snapshot(spec):
        alias = spec["repo"]
        if not isinstance(alias, str) or alias not in repos:
            raise CountError(f"no repository mapping for {alias!r}")
        if not isinstance(spec["commit"], str) or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", spec["commit"]):
            raise CountError("a full lowercase Git commit SHA is required")
        key = (alias, spec["commit"])
        if key not in cache:
            cache[key] = Snapshot(repos[alias], spec["commit"])
        return cache[key]

    fields(config["implementation"], ("repo", "commit"))
    impl = snapshot(config["implementation"])
    for d in includes:
        if not any(within(p, d) and p != d for p in impl.entries):
            raise CountError(f"include directory missing or empty at implementation pin: {d}")
    # Submodules cannot be silently treated as directories with no code.
    for p, (_, kind, _) in impl.entries.items():
        if (kind == "commit" and any(within(p, d) for d in includes)
                and not set(PurePosixPath(p).parts) & set(excluded_names)
                and not any(within(p, d) for d in excluded_paths)):
            raise CountError(f"included submodule requires a separate pinned input: {p}")
    packages, owners = [], {}
    if not isinstance(config["packages"], list):
        raise CountError("packages must be an array (possibly empty)")
    ids = set()
    for package in config["packages"]:
        fields(package, ("id", "repo", "commit", "manifest", "source_root", "target_root"))
        name = package["id"]
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", name) or name in ids:
            raise CountError("invalid or duplicate package id")
        ids.add(name)
        source_root, target_root = path(package["source_root"]), path(package["target_root"])
        src = snapshot(package)
        manifest_bytes = src.blob(path(package["manifest"]))
        manifest = read_json(manifest_bytes)
        if not isinstance(manifest, dict) or not isinstance(manifest.get("files"), list):
            raise CountError(f"{name}: manifest.files must be an array")
        packages.append(dict(package, tree=src.tree, manifest_sha256=sha256(manifest_bytes),
                             course_commit=manifest.get("commit"), export=manifest.get("export")))
        seen = set()
        for entry in manifest["files"]:
            if not isinstance(entry, dict):
                raise CountError(f"{name}: manifest file is not an object")
            rel = path(entry.get("path"))
            if rel == "." or rel in seen:
                raise CountError(f"{name}: duplicate or invalid manifest path: {rel}")
            seen.add(rel)
            if not isinstance(entry.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]):
                raise CountError(f"{name}: invalid sha256: {rel}")
            if entry.get("origin") not in (*ORIGINS[:2], "vendored") or type(entry.get("editable", False)) is not bool:
                raise CountError(f"{name}: invalid origin/editable: {rel}")
            target = str(PurePosixPath(target_root) / rel)
            if not selected(target):
                continue
            if entry["origin"] == "vendored":
                raise CountError(f"vendored file outside exclusions: {target}")
            if target in owners:
                raise CountError(f"overlapping package ownership: {target}")
            source = str(PurePosixPath(source_root) / rel)
            if sha256(src.blob(source)) != entry["sha256"]:
                raise CountError(f"{name}: package bytes do not match manifest: {source}")
            owners[target] = dict(entry, package=name, package_path=source)

    rows, missing = [], []
    totals = empty_totals()
    by_directory = {d: empty_totals() for d in sorted(includes)}
    for p in sorted(impl.entries):
        if not selected(p):
            continue
        data = impl.blob(p)
        digest = sha256(data)
        kit = owners.get(p)
        row = {"path": p, "blob": impl.entries[p][2], "sha256": digest, "lines": physical_lines(data),
               "kind": "tests" if p.endswith(tuple(test_suffixes)) else "code", "origin": "model",
               "reason": "outside_package"}
        if kit:
            same = digest == kit["sha256"]
            editable = kit.get("editable", False)
            row.update(package=kit["package"], package_path=kit["package_path"],
                       package_sha256=kit["sha256"], package_origin=kit["origin"], editable=editable)
            if same:
                row.update(origin=kit["origin"], reason="unchanged_editable" if editable else "unchanged_closed")
            elif editable:
                row["reason"] = "changed_editable"
            else:
                raise CountError(f"closed package file changed: {p}")
        rows.append(row)
        add(totals, row)
        add(by_directory[next(d for d in includes if within(p, d))], row)
    if not rows:
        raise CountError("no source files selected by the explicit scope")
    # Deleted files contribute zero final lines; report them rather than hiding them.
    for p in sorted(set(owners) - set(impl.entries)):
        kit = owners[p]
        missing.append({"path": p, "package": kit["package"], "origin": kit["origin"],
                        "editable": kit.get("editable", False), "package_sha256": kit["sha256"]})
    return {"version": 1, "implementation": dict(config["implementation"], tree=impl.tree),
            "scope": {k: config[k] for k in ("include_dirs", "exclude_dir_names", "exclude_paths",
                                            "suffixes", "test_suffixes")},
            "method": {"lines": "LF plus nonempty unterminated final line; comments and blanks included",
                       "editable": "same sha256: manifest origin; changed: whole final file is model",
                       "closed": "sha256 must match; changed closed file is an error",
                       "missing": "zero final lines; listed separately", "headers": "not inspected"},
            "packages": sorted(packages, key=lambda p: p["id"]), "totals": totals,
            "by_directory": by_directory, "files": rows, "missing_package_files": missing}


def markdown(report):
    out = ["# Происхождение кода: проба ADR-0127", "",
           f"Реализация: `{report['implementation']['repo']}` / `{report['implementation']['commit']}`.", "",
           "Снимки читаются из Git; рабочее дерево и шапки файлов не участвуют. Строка — LF, плюс последняя",
           "непустая строка без LF; комментарии и пустые строки включены. Совпавший SHA editable сохраняет origin",
           "манифеста; изменённый editable целиком относится к модели по конечным байтам. Изменённый закрытый файл — ошибка.", "",
           "| Состав | generated | handwritten пакета | модель | всего |", "|---|---:|---:|---:|---:|"]
    for kind, title in (("code", "Код"), ("tests", "Тесты")):
        values = [report["totals"][kind][o]["lines"] for o in ORIGINS]
        out.append(f"| {title} | " + " | ".join(map(str, [*values, sum(values)])) + " |")
    out.extend(["", "Включённые каталоги: " + ", ".join(f"`{p}`" for p in report["scope"]["include_dirs"]) + ".",
                "Исключены каталоги с именами на любой глубине: " + ", ".join(f"`{p}`" for p in report["scope"]["exclude_dir_names"]) + ".",
                "Дополнительные исключённые пути: " + (", ".join(f"`{p}`" for p in report["scope"]["exclude_paths"]) or "нет") + ".",
                "Суффиксы: " + ", ".join(f"`{p}`" for p in report["scope"]["suffixes"]) + "; тесты: " + ", ".join(f"`{p}`" for p in report["scope"]["test_suffixes"]) + ".", "",
                "| Каталог, код без тестов | generated | handwritten пакета | модель |", "|---|---:|---:|---:|"])
    for d, totals in report["by_directory"].items():
        out.append(f"| `{d}` | " + " | ".join(str(totals["code"][o]["lines"]) for o in ORIGINS) + " |")
    out.extend(["", "Пины пакетов — коммиты импорта: содержат манифест и проверенные по его SHA-256 байты пакета.", ""])
    for p in report["packages"]:
        out.extend([f"- `{p['id']}`: `{p['repo']}` / `{p['commit']}`; манифест `{p['manifest']}`;",
                    f"  SHA-256 `{p['manifest_sha256']}`; курс `{p['course_commit']}`, выгрузка `{p['export']}`."])
    reasons = {}
    for row in report["files"]:
        if row["reason"] == "unchanged_editable":
            reasons[row["path"]] = row
    if reasons:
        out.extend(["", "Editable, оставшиеся байт в байт пакетными:", ""])
        for p, row in reasons.items():
            out.append(f"- `{p}`: {row['lines']} строк, `{row['origin']}` (SHA совпал).")
    out.extend(["", f"Отсутствующих файлов пакета в выбранном составе: {len(report['missing_package_files'])}.",
                "JSON-вывод содержит по каждому файлу итоговый SHA-256, Git blob, число строк и основание классификации.", ""])
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--repo", action="append", default=[], metavar="ALIAS=PATH",
                    help="repository location, independent of the pinned report")
    ap.add_argument("--format", choices=("json", "markdown"), default="json")
    args = ap.parse_args(argv)
    try:
        repos = {}
        for item in args.repo:
            alias, sep, location = item.partition("=")
            if not sep or not alias or not location or alias in repos:
                raise CountError("--repo expects a unique ALIAS=PATH")
            repos[alias] = location
        report = count(read_json(args.config.read_bytes()), repos)
        print(markdown(report) if args.format == "markdown" else
              json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", end="")
    except (CountError, OSError, UnicodeError) as exc:
        print(f"code_origin: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
