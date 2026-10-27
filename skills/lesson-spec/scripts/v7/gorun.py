"""Стек В7 на Go через раннер `go/main.go` (santhosh-tekuri/jsonschema/v6, cel-go): библиотека Go, слои — общие (stack).

Бинарь строится один раз: `go build -o <стенд>/v7check ./go` (GOTOOLCHAIN=local); путь — V7CHECK или по умолчанию.
"""
import json
import os
import subprocess
from pathlib import Path

from . import stack

BIN = os.environ.get("V7CHECK", "/Users/murat/w2c/v7-stand/v7check")


class GoError(Exception):
    pass


def typed(path, instance):
    """Путь Go (строки) → путь диалекта: индекс списка — число."""
    out, v = [], instance
    for s in path:
        if isinstance(v, list):
            s = int(s)
            v = v[s] if 0 <= s < len(v) else None
        elif isinstance(v, dict):
            v = v.get(s)
        out.append(s)
    return out


SCALARS = str(Path(__file__).resolve().parents[4] / "Platform/02-installer/spec/02.1-installer.scalars.tsv")


class TextRefused(Exception):
    def __init__(self, d):
        super().__init__("%s line %s: %s" % (d["rule"], d["line"], d["msg"]))
        self.rule, self.line, self.msg, self.path = d["rule"], d["line"], d["msg"], d.get("path")


class GoText:
    """Слой 1 на Go (go/text.go) с тем же видом, что v7.textv7: load_text_map(байты) → (дерево, numbers, empties, {})."""
    TextRefused = TextRefused

    def __init__(self, go):
        self.go = go

    def load_text_map(self, data):
        import base64
        r = self.go.call({"op": "text", "data": base64.b64encode(data).decode("ascii"), "scalars": SCALARS})
        if "refused" in r:
            raise TextRefused(r["refused"])
        return r["tree"], [(p, s) for p, s in r["numbers"] or []], [p for p in r["empties"] or []], {}


class Go:
    def __init__(self):
        self.p = subprocess.Popen([BIN], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8")
        self.loaded = None
        self.text = GoText(self)

    def call(self, req):
        self.p.stdin.write(json.dumps(req, ensure_ascii=False) + "\n")
        self.p.stdin.flush()
        resp = json.loads(self.p.stdout.readline())
        if "error" in resp:
            raise GoError(resp["error"])
        return resp

    def records(self, file, instance, ptr=""):
        resp = self.call({"op": "schema", "file": str(file), "ptr": ptr, "instance": instance})
        out = []
        for r in resp["records"]:
            path = typed(r["path"], instance)
            kw, extra = r["kw"], r["extra"]
            if kw == "uniqueItems":
                extra = stack.repeats(stack.at(instance, path))
            out.append((path, kw, extra))
        return out

    def cel(self, file=None):
        go = self

        class Runner:
            def run(self, tree):
                return [(no, p) for no, p in go.call({"op": "cel", "doc": tree})["fired"]]
        file = file or str(Path(__file__).resolve().parent / "out" / "02.1-installer.relations.json")
        self.call({"op": "cel_load", "file": file})
        return Runner()

    def manifest(self, m, data, file=None):
        """Загрузчик манифеста: текст — слой эталона; форма — Go; связи — Go (m создан с go.cel())."""
        textlayer = m.text
        file = file or str(Path(__file__).resolve().parent / "out" / "02.1-installer.schema.json")
        try:
            tree, numbers, empties, lines = textlayer.load_text_map(data)
        except textlayer.TextRefused as exc:
            return {"verdict": "refused", "layer": "text", "paths": [list(exc.path)] if exc.path is not None else [],
                    "rows": []}
        if numbers or empties:
            clean = stack.Manifest.nonfinite(tree)
            paths = [p for p, _ in numbers] + list(empties) + stack.norm(self.records(file, clean), clean)
            return {"verdict": "refused", "layer": "form", "paths": stack.canonical(paths), "rows": []}
        return m.judge_tree(tree, self.records(file, tree))

    def close(self):
        self.p.stdin.close()
        self.p.wait()
