"""Проверка формы RUN-SOAK и идентичности дерева Q без запуска стенда."""
import hashlib
import json
from pathlib import Path
import subprocess

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[3]
BASE = "89eceb87596288e1a1e879e3af06d7236580a124"
FILTER = "Platform/common/qualification-input-filter.json"
FORM = "Platform/01-store/forms/production/soak.json"
SCHEMA = "Platform/01-store/forms/production/soak.schema.json"


def git(*args, data=None):
    return subprocess.check_output(["git", "-C", str(ROOT), *args], input=data)


def tree_id(files):
    directories = {}
    for row in files:
        node = directories
        parts = row["path"].split("/")
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = row

    def build(node):
        entries = []
        for name, value in node.items():
            if "blob" in value:
                mode, kind, oid = value["mode"], "blob", value["blob"]
            else:
                mode, kind, oid = "040000", "tree", build(value)
            entries.append(f"{mode} {kind} {oid}\t{name}\0".encode())
        return git("mktree", "-z", data=b"".join(entries)).decode().strip()

    return build(directories)


def inventory(revision=None):
    raw = git("show", revision + ":" + FILTER) if revision else (ROOT / FILTER).read_bytes()
    records = json.loads(raw)["files"]
    paths = [r["path"] for r in records]
    assert paths == sorted(set(paths), key=lambda p: p.encode())
    modes = {}
    for line in git("ls-files", "--stage", "-z").split(b"\0"):
        if line:
            meta, path = line.split(b"\t")
            modes[path.decode()] = meta.split()[0].decode()
    files = []
    for row in records:
        path = row["path"]
        assert row["disposition"] == "include" and "/ru/" not in path
        if revision:
            mode, kind, oid = git("ls-tree", revision, "--", path).split(b"\t")[0].split()
            assert kind == b"blob"
            raw_file = git("cat-file", "blob", oid.decode())
            mode, oid = mode.decode(), oid.decode()
        else:
            raw_file = (ROOT / path).read_bytes()
            mode = modes[path]
            oid = git("hash-object", "-w", "--stdin", data=raw_file).decode().strip()
        files.append({"path": path, "mode": mode, "blob": oid,
                      "sha256": hashlib.sha256(raw_file).hexdigest(), "bytes": len(raw_file)})
    return {"filter_sha256": hashlib.sha256(raw).hexdigest(),
            "q_input_tree": tree_id(files), "files": files}


def main():
    schema = json.loads((ROOT / SCHEMA).read_bytes())
    record = json.loads((ROOT / FORM).read_bytes())
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(record)
    exports = json.loads((ROOT / "Platform/01-store/forms/export.json").read_bytes())
    for path in (FORM, SCHEMA):
        assert next(r for r in exports["model"] if r["path"] == path)["disposition"] == "judge_only"
        assert next(r for r in exports["judge"] if r["path"] == path)["disposition"] == "include"
    current, before = inventory(), inventory(BASE)
    assert {FORM, SCHEMA} <= {r["path"] for r in current["files"]}
    assert current["q_input_tree"] != before["q_input_tree"]
    result = {"result": "PASS", "base": BASE,
              "base_q_input_tree": before["q_input_tree"], **current,
              "checks": ["RUN-SOAK schema and record", "outside M; classified in J",
                         "Q paths unique and sorted; whole files with Git modes",
                         "Q inventory includes record and schema; input tree changed"],
              "execution": "Documents and Git objects only; no candidate, probe or qualifier run."}
    print(json.dumps(result, ensure_ascii=False, indent=2) + "\n", end="")


if __name__ == "__main__":
    main()
