#!/usr/bin/env python3
"""OBSH.75: execute common/log-mask cases.tsv from its existing wire.tsv row.
The native frame is a JSON string. Compare its decoded UTF-8 bytes against masked
without normalizing, trimming or newline conversion. Validate the closed outer
response shape and canonical base64. This is a minimal vector executor, not a
candidate or judge runner. The mask_in row is outside this extracted package.
Usage: vecrun.py <course-root> common/log-mask '<command> {input}' <out.json>
"""
import base64
import json
import os
import shlex
import subprocess
import sys
import tempfile


def strict(text):
    def pairs(ps):
        d = {}
        for k, v in ps:
            if k in d:
                raise ValueError("duplicate key " + k)
            d[k] = v
        return d

    def bad(c):
        raise ValueError("non-JSON number " + c)
    return json.loads(text, object_pairs_hook=pairs, parse_constant=bad)


def wire_row(specs, package):
    rows = []
    with open(os.path.join(specs, "Platform/common/vectors/wire.tsv"), encoding="utf-8") as f:
        header = None
        for line in f:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            cells = line.split("\t")
            if header is None:
                header = cells
                continue
            r = dict(zip(header, cells))
            if r["package"] == package and r["surface"] == "vectors" and r["table"] == "cases.tsv":
                rows.append(r)
    if len(rows) != 1:
        raise SystemExit("expected one vectors wire row of %s, got %d" % (package, len(rows)))
    return rows[0]


def decode(spec, row):
    cell = row[spec["column"]]
    if spec.get("decode") == "text":
        return cell
    if spec.get("decode") == "json":
        return strict(cell)
    raise SystemExit("unsupported decode %r" % spec.get("decode"))


def expected(value, row):
    if "column" in value:
        return decode(value, row)
    if "object" in value:
        return {k: decode(v, row) for k, v in value["object"].items()}
    raise SystemExit("unsupported value constructor %r" % sorted(value))


def main():
    specs, package, command, out = sys.argv[1:5]
    w = wire_row(specs, package)
    pkgdir = os.path.join(specs, "Platform", package.replace("common/", "common/vectors/", 1))
    table = w["table"]
    header = w["header"].split(",")
    inputs, files_decl, expect = strict(w["inputs"]), strict(w["files"]), strict(w["expect"])
    assert len(inputs) == 1 and inputs[0]["variant"] == "" and "cells" in inputs[0], inputs
    assert len(expect) == 1 and expect[0]["variant"] == "" and expect[0].get("when", "true") == "true", expect
    assert w["compare"] == "raw" and strict(w["markers"]) == [], (w["compare"], w["markers"])
    files = {}
    for name, d in files_decl.items():
        assert d["base"] == "package", d
        with open(os.path.join(pkgdir, d["path"]), "rb") as f:
            files[name] = base64.b64encode(f.read()).decode("ascii")
    results, n_rows = [], 0
    with open(os.path.join(pkgdir, table), encoding="utf-8") as f:
        lines = f.read().split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    names = header[1:] if header[0] == "-" else None
    for no, line in enumerate(lines, 1):
        if not line.strip() or line.startswith("#"):
            continue
        cells = line.split("\t")
        if names is None:
            assert cells == header, ("header differs", cells, header)
            names = header
            continue
        assert len(cells) == len(names), ("field count", no, cells)
        row = dict(zip(names, cells))
        n_rows += 1
        case = row["case"] if "case" in row and not inputs[0].get("case") else "line-%d" % no
        env = {"format": 1, "package": package, "table": table, "case": case, "variant": "",
               "cells": {k: row[v["column"]] for k, v in inputs[0]["cells"].items()}, "files": files}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as t:
            t.write(json.dumps(env, ensure_ascii=False) + "\n")
        try:
            p = subprocess.run(command.replace("{input}", shlex.quote(t.name)), shell=True, capture_output=True,
                               timeout=60)
        finally:
            os.unlink(t.name)
        res = {"line": no, "case": case}
        try:
            if p.returncode != 0:
                raise ValueError("outer exit %d" % p.returncode)
            o = strict(p.stdout.decode("utf-8"))
            if set(o) != {"exit_code", "stdout_b64", "stderr_b64"} or type(o["exit_code"]) is not int:
                raise ValueError("outer answer form")
            raw = base64.b64decode(o["stdout_b64"], validate=True)
            err = base64.b64decode(o["stderr_b64"], validate=True)
            if base64.b64encode(err).decode("ascii") != o["stderr_b64"]:
                raise ValueError("non-canonical stderr base64")
            if base64.b64encode(raw).decode("ascii") != o["stdout_b64"]:
                raise ValueError("non-canonical base64")
            if o["exit_code"] != expect[0]["code"]:
                raise ValueError("native exit %d, expected %d" % (o["exit_code"], expect[0]["code"]))
            got, want = strict(raw.decode("utf-8")), expected(expect[0]["value"], row)
            res["ok"] = type(got) is str and type(want) is str and got.encode("utf-8") == want.encode("utf-8")
            if not res["ok"]:
                res["why"] = "native value differs"
        except (ValueError, UnicodeError) as e:
            res["ok"], res["why"] = False, str(e)
        results.append(res)
    green = sum(r["ok"] for r in results)
    rep = {"package": package, "table": table, "rows": n_rows, "green": green, "red": [r for r in results if not r["ok"]],
           "wire_norm": w["norm"]}
    with open(out, "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    print("%s %s: %d/%d green" % (package, table, green, n_rows))
    sys.exit(0 if green == n_rows and n_rows else 1)


if __name__ == "__main__":
    main()
