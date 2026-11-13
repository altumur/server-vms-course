"""Judge refusal catalogs against the form, acceptance and door (ADR-0125 generator 4, addendum 1, item 1).

  python tools/normgen/refusal_judge.py [--module-dir <module-with-refusals-and-door>] [--json <result>]
Default module: out/p01-1/go; stdlib and Go 1.22 suffice. Reread refusals.tsv independently and compare every harness-reported Spec's code, kind, fields, headers and log. Each acceptance chapters1..3 4xx/5xx JSON expectation must match a catalog code/kind: chapter 1.1 requires all mandatory fields plus optional fields, while1.2/1.3 use subsets. Every HTTP Spec must encode through apidoor.Refuse/Encode for at least one OpenAPI operation, with required/all fields and Retry-After where declared. Fixed Headers and bare DynamicHeaders remain separate metadata. Private wire observations preserve explicit header inputs; Retry-After witnesses use integer syntax without choosing the implementation's admission delay.

Runner refusal steps on the door stub are the door judge's task. Result: refusals:P/N PASS|FAIL; exit 0=all pass, 1=failure, 2=judge startup error."""
import argparse
import csv
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import lesson  # noqa: E402 -- lesson selection (ADR-0125 addendum(5), item 2)
L = lesson.CURRENT
TABLE = L.form("refusals.tsv")
ACCEPTANCE = L.path("acceptance")
WHOLE = {"1"}                 # Chapters comparing full bodies (acceptance1.1 README); others use subsets.


class CheckingError(RuntimeError):
    """The source or observation is unavailable, malformed or incomplete; never a semantic kill."""


def read_table(path=None):
    path = TABLE if path is None else Path(path)
    lines = [x for x in path.read_text(encoding="utf-8").splitlines() if x and not x.startswith("#")]
    columns = ["chapter", "row", "name", "surface", "code", "kind", "fields", "headers", "log", "norm"]
    if not lines or lines[0].split("\t") != columns:
        raise CheckingError("missing or malformed HTTP refusal catalogue header")
    rows = []
    names = set()
    for cells in csv.reader(lines[1:], delimiter="\t", quoting=csv.QUOTE_NONE):
        if len(cells) != len(columns):
            raise CheckingError("malformed HTTP refusal catalogue row")
        r = dict(zip(columns, cells))
        if (not re.fullmatch(r"[a-z][a-z0-9_]*", r["name"]) or r["name"] in names or
                not re.fullmatch(r"[0-9]+\.[0-9]+", r["chapter"]) or
                not re.fullmatch(r"[1-9][0-9]*", r["row"])):
            raise CheckingError("missing/duplicate name or malformed source coordinates")
        names.add(r["name"])
        fields = [] if r["fields"] == "-" else r["fields"].split(",")
        if any(not re.fullmatch(r"[a-z][a-z_]*\??", f) or f.rstrip("?") in ("kind", "error") for f in fields):
            raise CheckingError(f"{r['name']}: malformed field token")
        if len({f.rstrip("?") for f in fields}) != len(fields):
            raise CheckingError(f"{r['name']}: duplicate field")
        r["req"] = {f for f in fields if not f.endswith("?")}
        r["opt"] = {f[:-1] for f in fields if f.endswith("?")}
        if r["surface"] == "http":
            if not re.fullmatch(r"[1-5][0-9]{2}", r["code"]) or not re.fullmatch(r"[a-z]+", r["kind"]):
                raise CheckingError(f"{r['name']}: malformed HTTP code/kind")
            r["code_n"] = int(r["code"])
        elif r["surface"] in ("start", "cli"):
            if r["code"] not in ("exit 2", "exit !0") or any(r[k] != "-" for k in ("kind", "fields", "headers")):
                raise CheckingError(f"{r['name']}: malformed process refusal")
            r["code_n"] = 2 if r["code"] == "exit 2" else 1
        else:
            raise CheckingError(f"{r['name']}: unknown source surface")
        r["header_pairs"], r["dynamic_headers"] = [], []
        header_names = {}
        if r["headers"] != "-":
            for header in r["headers"].split(";"):
                fixed = re.fullmatch(r"\s*([A-Za-z][A-Za-z0-9-]*): (\S.*?)\s*", header)
                bare = re.fullmatch(r"\s*([A-Za-z][A-Za-z0-9-]*)\s*", header)
                match = fixed or bare
                if match is None or (match[1].lower() in header_names and
                                     (not fixed or header_names[match[1].lower()])):
                    raise CheckingError(f"{r['name']}: malformed header or repeated dynamic name")
                header_names[match[1].lower()] = not bool(fixed)
                if fixed:
                    r["header_pairs"].append([match[1], match[2]])
                else:
                    r["dynamic_headers"].append(match[1])
        logs = [] if r["log"] == "-" else [x.strip() for x in re.findall(r"«[^«»]*»|[^,«»]+", r["log"]) if x.strip()]
        r["log_names"] = [x for x in logs if not x.startswith("«")]
        r["log_words"] = [x[1:-1] for x in logs if x.startswith("«")]
        rows.append(r)
    if not rows:
        raise CheckingError("the HTTP refusal source has no catalogue rows")
    return rows


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise CheckingError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _constant(value):
    raise CheckingError(f"nonfinite JSON constant: {value}")


def _shape(value, keys):
    if type(value) is not dict or set(value) != set(keys):
        raise CheckingError("missing/extra/malformed private report members")


def _strings(value):
    if value is not None and (type(value) is not list or any(type(x) is not str for x in value)):
        raise CheckingError("private report requires a string array or null")
    for text in value or []:
        _text(text)


def _text(value):
    if type(value) is not str:
        raise CheckingError("private report requires text")
    try:
        value.encode("utf-8", "strict")
    except UnicodeError as exc:
        raise CheckingError("private report contains a non-scalar Unicode string") from exc


def read_report(raw):
    """Validate the whole service frame before comparing any generated metadata with Source."""
    try:
        if type(raw) is bytes:
            raw = raw.decode("utf-8", "strict")
        if type(raw) is not str:
            raise CheckingError("private report is not UTF-8 text")
        raw.encode("utf-8", "strict")
        report = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_constant)
    except (UnicodeError, ValueError) as exc:
        raise CheckingError(f"invalid private report: {exc}") from exc
    _shape(report, ("version", "declared", "completed", "rows"))
    if (type(report["version"]) is not int or report["version"] != 1 or
            type(report["declared"]) is not int or report["declared"] < 0 or
            type(report["completed"]) is not int or report["completed"] != report["declared"] or
            type(report["rows"]) is not list or len(report["rows"]) != report["declared"]):
        raise CheckingError("incomplete private catalogue observation")
    for row in report["rows"]:
        _shape(row, ("Chapter", "Row", "Name", "Surface", "Code", "Kind", "Fields", "Headers",
                     "RetryAfter", "DynamicHeaders", "Log", "Words", "Norm", "probes"))
        if (any(type(row[k]) is not str for k in ("Chapter", "Name", "Surface", "Kind", "Norm")) or
                any(type(row[k]) is not int for k in ("Row", "Code")) or type(row["RetryAfter"]) is not bool):
            raise CheckingError("mistyped observed catalogue scalar")
        for key in ("Chapter", "Name", "Surface", "Kind", "Norm"):
            _text(row[key])
        for key in ("Log", "Words", "DynamicHeaders"):
            _strings(row[key])
        fields = row["Fields"] or []
        if row["Fields"] is not None and type(row["Fields"]) is not list:
            raise CheckingError("mistyped observed fields")
        for field in fields:
            _shape(field, ("Name", "Optional"))
            if type(field["Name"]) is not str or type(field["Optional"]) is not bool:
                raise CheckingError("mistyped observed field role")
            _text(field["Name"])
        if row["Headers"] is not None and type(row["Headers"]) is not list:
            raise CheckingError("mistyped observed headers")
        for header in row["Headers"] or []:
            if type(header) is not list or len(header) != 2 or any(type(x) is not str for x in header):
                raise CheckingError("mistyped observed header pair")
            for value in header:
                _text(value)
        required = [f["Name"] for f in fields if not f["Optional"]]
        all_fields = [f["Name"] for f in fields]
        sets = [required] + ([all_fields] if len(required) != len(all_fields) else []) if row["Surface"] == "http" else []
        probes = row["probes"] or []
        if row["probes"] is not None and type(row["probes"]) is not list:
            raise CheckingError("mistyped probe cohort")
        if len(probes) != len(sets):
            raise CheckingError("partial/extra observation of declared field cohorts")
        for probe, expected_fields in zip(probes, sets):
            _shape(probe, ("fields", "ints", "ops", "retry", "body", "wire"))
            for key in ("fields", "ints", "ops"):
                _strings(probe[key])
            if ((probe["fields"] or []) != expected_fields or type(probe["retry"]) is not bool or
                    type(probe["body"]) is not str):
                raise CheckingError("wrong field-cohort identity or mistyped probe")
            _text(probe["body"])
            if type(probe["wire"]) is not list or len(probe["wire"]) != len(probe["ops"] or []):
                raise CheckingError("partial/extra wire header observation")
            for op, witness in zip(probe["ops"] or [], probe["wire"]):
                _shape(witness, ("op", "requested", "headers"))
                if witness["op"] != op:
                    raise CheckingError("wrong wire operation identity")
                for key in ("requested", "headers"):
                    if type(witness[key]) is not list:
                        raise CheckingError("wire headers must be an array")
                    for pair in witness[key]:
                        if type(pair) is not list or len(pair) != 2 or any(type(x) is not str for x in pair):
                            raise CheckingError("mistyped wire header pair")
                        for value in pair:
                            _text(value)
                    if len({p[0].lower() for p in witness[key]}) != len(witness[key]):
                        raise CheckingError("duplicate wire header name")
    return report["rows"]


def dynamic_header_error(names, witnesses):
    """Compare explicit test inputs with Encode wire values, never choose an admission delay."""
    for witness in witnesses:
        supplied = {k.lower(): v for k, v in witness["requested"]}
        observed = {k.lower(): v for k, v in witness["headers"]}
        if all(name.lower() in supplied and observed.get(name.lower()) == supplied[name.lower()]
               and (name.lower() != "retry-after" or re.fullmatch(r"-?(0|[1-9][0-9]*)", supplied[name.lower()]))
               for name in names):
            return None
    return "no operation preserves typed dynamic-header inputs on the wire"


def harness(module_dir, work):
    hdir = Path(work) / "harness"
    hdir.mkdir()
    shutil.copy(HERE / "refusals/harness/main.go", hdir / "main.go")
    (hdir / "go.mod").write_text(f"module normgen/refusalharness\n\ngo 1.22\n\nrequire {L.go_module} v0.0.0\n\n"
                                 f"replace {L.go_module} => {Path(module_dir).resolve()}\n", encoding="utf-8")
    try:
        done = subprocess.run(["go", "run", "."], cwd=hdir, capture_output=True, timeout=300)
    except (OSError, subprocess.SubprocessError) as exc:
        raise CheckingError(f"cannot execute the harness: {exc}") from exc
    if type(done.returncode) is not int or done.returncode != 0 or done.stderr:
        raise CheckingError(f"the harness did not complete normally: exit={done.returncode}, stderr={done.stderr!r}")
    return read_report(done.stdout)


def expectations():
    """Return acceptance refusal expectations as [(chapter, scenario, step, status, kind, fields)]."""
    out = []
    for ch in sorted(p.name for p in ACCEPTANCE.iterdir() if p.is_dir()):
        for line in (ACCEPTANCE / ch / "scenarios.tsv").read_text(encoding="utf-8").splitlines():
            cells = line.split("\t")
            if len(cells) != 4 or not (m := re.fullmatch(r"([45][0-9]{2}) (\{.*\})", cells[3])):
                continue
            try:
                body = json.loads(m[2])
            except ValueError:
                continue
            if isinstance(body, dict) and "kind" in body:
                out.append((ch, cells[0], cells[1], int(m[1]), body["kind"], set(body) - {"kind", "error"}))
    return out


PLAIN_HARNESS = '''// Harness of refusal_judge.py for a catalogue without an HTTP door: refusals.All as one JSON.
package main

import (
	"encoding/json"
	"os"

	"%s/refusals"
)

func main() { _ = json.NewEncoder(os.Stdout).Encode(refusals.All) }
'''
RUN_EXIT = re.compile(r"^exit (0|[1-9][0-9]*)(;|$)")


def plain(a):
    """For non-HTTP P/02, compare independently reread closed catalog columns with the package; each nonzero RUN exit expectation must match that code or exit !0."""
    lines = [x for x in TABLE.read_text(encoding="utf-8").splitlines() if x and not x.startswith("#")]
    if len(lines) < 2:
        raise ValueError("the refusal source has no catalogue rows")
    cols = lines[0].split("\t")
    if len(cols) != len(set(cols)) or any(len(x.split("\t")) != len(cols) for x in lines[1:]):
        raise ValueError("duplicate columns or malformed refusal source row")
    rows = [dict(zip(cols, x.split("\t"))) for x in lines[1:]]
    with tempfile.TemporaryDirectory(prefix="refusal-judge-") as work:
        hdir = Path(work) / "harness"
        hdir.mkdir()
        (hdir / "main.go").write_text(PLAIN_HARNESS % L.go_module, encoding="utf-8")
        (hdir / "go.mod").write_text(f"module normgen/refusalharness\n\ngo 1.22\n\nrequire {L.go_module} v0.0.0\n\n"
                                     f"replace {L.go_module} => {Path(a.module_dir).resolve()}\n", encoding="utf-8")
        done = subprocess.run(["go", "run", "."], cwd=hdir, capture_output=True, text=True, timeout=300)
        if done.returncode:
            raise ValueError(f"the harness failed: {done.stderr.strip()}")
        got = json.loads(done.stdout)
        if type(got) is not list:
            raise ValueError("the harness did not return a catalogue array")
    results = []

    def check(name, why):
        results.append({"name": name, "ok": why is None, "why": why})
        if why:
            print(f"FAIL {name}: {why}", flush=True)

    check("catalogue: the same names in order", None if [g["Name"] for g in got] == [r["name"] for r in rows]
          else "the names differ from the table")
    by = {g["Name"]: g for g in got}
    for r in rows:
        g = by.get(r["name"])
        if not g:
            continue
        code = r["code"]
        exit_, anyc, status = -1, code == "exit !0", 0
        if code.startswith("exit ") and code[5:].isdigit():
            exit_ = int(code[5:])
        elif code.isdigit():
            status = int(code)
        logs = [] if r["log"] == "-" else [x.strip() for x in re.findall(r"«[^«»]*»|[^,«»]+", r["log"]) if x.strip()]
        names = [x for x in logs if not x.startswith("«")]
        words = [x[1:-1] for x in logs if x.startswith("«")]
        want_word, want_any = ("" if r["word"] == "-" else r["word"]), []
        if L.key != "02-installer":                     # P/03+: word retains the source cell; quoted tokens are a projection.
            toks = re.findall(r"`([^`]+)`", r["word"])
            plain_cell = re.sub(r"`[^`]+`|,|\s", "", r["word"]) == ""
            want_word, want_any = "", []
            if toks and plain_cell:
                want_word, want_any = (toks[0], []) if len(toks) == 1 else ("", toks)
        want_fields, want_optional = [], []
        for token in [] if r["fields"] == "-" else r["fields"].split(","):
            field = re.fullmatch(r"([a-z][a-z0-9_]*)(\??)", token.strip())
            if field is None or field[1] in want_fields:
                raise ValueError(f"{r['name']}: malformed or duplicate field token")
            if field[2] and not (L.key == "06-console" and r["surface"] == "http"
                                 and r.get("response_schema", "-") != "-"):
                raise ValueError(f"{r['name']}: optional field outside the P/06 response context")
            want_fields.append(field[1])
            if field[2]:
                want_optional.append(field[1])
        want_headers = [] if r["headers"] == "-" else [[x.strip() for x in h.split(": ", 1)] for h in r["headers"].split(";")]
        diffs = [k for k, ok in (("chapter", g["Chapter"] == r["chapter"]), ("row", g["Row"] == int(r["row"])),
                                 ("surface", g["Surface"] == r["surface"]), ("exit", g["Exit"] == exit_),
                                 ("any", g["AnyNonZero"] == anyc), ("status", g["Status"] == status),
                                 ("word", g["Word"] == want_word), ("named", (g.get("Named") or []) == want_any),
                                 ("word_cell", L.key == "02-installer" or g.get("WordCell") == r["word"]),
                                 ("fields", (g.get("Fields") or []) == want_fields),
                                 ("optional_fields", (g.get("OptionalFields") or []) == want_optional),
                                 ("headers", (g.get("Headers") or []) == want_headers),
                                 ("response", "response_schema" not in r or
                                  g.get("Response") == ("" if r["response_schema"] == "-" else r["response_schema"])),
                                 ("log", (g["Log"] or []) == names), ("words", (g["Words"] or []) == words),
                                 ("norm", g["Norm"] == r["norm"])) if not ok]
        check(f"catalogue {r['name']}", f"differs from the table in {diffs}" if diffs else None)
    codes = {g["Exit"] for g in got if g["Exit"] > 0}
    anyc = any(g["AnyNonZero"] for g in got)
    for seams in sorted(ACCEPTANCE.glob("*/seams.tsv")):
        for line in seams.read_text(encoding="utf-8").splitlines():
            cells = line.split("\t")
            if line.startswith("#") or len(cells) != 4 or not cells[2].startswith("RUN "):
                continue
            m = RUN_EXIT.match(cells[3])
            if not m or m[1] == "0":
                continue
            n = int(m[1])
            check(f"acceptance {seams.parent.name} {cells[0]} step {cells[1]}",
                  None if n in codes or anyc else f"exit {n}: no row of the catalogue with this code or «exit !0»")
    passed = sum(r["ok"] for r in results)
    verdict = "PASS" if passed == len(results) else "FAIL"
    print(f"refusals: {L.code} {passed}/{len(results)} {verdict}")
    if a.json:
        Path(a.json).write_text(json.dumps({"passed": passed, "total": len(results), "verdict": verdict,
                                            "results": results}, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if verdict == "PASS" else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--module-dir", help="module to judge; default: the validated prepared lesson module")
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    if a.module_dir is None:
        try:
            a.module_dir = str(lesson.ready_outputs(profiles=lesson.PROFILES)[L.slug] / "go")
        except (lesson.LessonError, OSError) as exc:
            print(f"refusal_judge: {exc}", file=sys.stderr)
            return 2
    if not shutil.which("go"):
        print("refusal_judge: go is not in PATH", file=sys.stderr)
        return 2
    try:
        head = next((x for x in TABLE.read_text(encoding="utf-8").splitlines() if x and not x.startswith("#")), None)
        if head is None:
            raise ValueError("the refusal source has no header")
    except (OSError, ValueError) as exc:
        print(f"refusal_judge: checking error: {exc}", file=sys.stderr)
        return 2
    if "word" in head.split("\t"):                         # Non-HTTP lesson catalog (P/02).
        try:
            return plain(a)
        except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
            print(f"refusal_judge: checking error: {exc}", file=sys.stderr)
            return 2
    try:
        rows = read_table()
        with tempfile.TemporaryDirectory(prefix="refusal-judge-") as work:
            got = harness(a.module_dir, work)
    except (CheckingError, OSError, ValueError, TypeError, KeyError, RecursionError) as exc:
        print(f"refusal_judge: checking error: {exc}", file=sys.stderr)
        return 2
    results = []

    def check(name, why):
        results.append({"name": name, "ok": why is None, "why": why})
        if why:
            print(f"FAIL {name}: {why}", flush=True)

    by = {g["Name"]: g for g in got}
    check("catalogue: the same names in order", None if [g["Name"] for g in got] == [r["name"] for r in rows]
          else f"{[g['Name'] for g in got]} vs the table")
    for r in rows:
        g = by.get(r["name"])
        if not g:
            check(f"catalogue {r['name']}", "the complete compiled catalogue has no such row")
            if r["surface"] == "http":
                sets = [r["req"]] + ([r["req"] | r["opt"]] if r["opt"] else [])
                for fields in sets:
                    check(f"door {r['name']} {sorted(fields)}", "the compiled catalogue has no such row")
            continue
        fields = {f["Name"]: f["Optional"] for f in g["Fields"] or []}
        want = {**{f: False for f in r["req"]}, **{f: True for f in r["opt"]}}
        headers = r["header_pairs"]
        diffs = [k for k, ok in (("chapter", g["Chapter"] == r["chapter"]), ("row", g["Row"] == int(r["row"])),
                                 ("surface", g["Surface"] == r["surface"]), ("code", g["Code"] == r["code_n"]),
                                 ("kind", g["Kind"] == ("" if r["kind"] == "-" else r["kind"])),
                                 ("fields", fields == want and len(g["Fields"] or []) == len(want)),
                                 ("headers", (g["Headers"] or []) == headers),
                                 ("dynamic headers", (g["DynamicHeaders"] or []) == r["dynamic_headers"]),
                                 ("retry", g["RetryAfter"] == any(n.lower() == "retry-after" for n in
                                     [h[0] for h in headers] + r["dynamic_headers"])),
                                 ("log", (g["Log"] or []) == r["log_names"]),
                                 ("words", (g["Words"] or []) == r["log_words"]),
                                 ("norm", g["Norm"] == r["norm"]))
                 if not ok]
        check(f"catalogue {r['name']}", f"differs from the table in {diffs}" if diffs else None)
        if r["surface"] == "http":
            sets = [r["req"]] + ([r["req"] | r["opt"]] if r["opt"] else [])
            for fields in sets:
                why = None
                candidates = [p for p in g["probes"] or [] if sorted(p["fields"] or []) == sorted(fields)]
                p = candidates[0] if len(candidates) == 1 else None
                if p is None:
                    why = "no unambiguous observation for the source field cohort"
                elif not p["ops"]:
                    why = f"apidoor.Refuse/Encode take the fields {p['fields'] or []} at no operation"
                elif g["RetryAfter"] and not p["retry"]:
                    why = "no operation declares Retry-After for it"
                elif any({n.lower(): value for n, value in w["headers"]}.get(k.lower()) != v
                         for w in p["wire"] for k, v in w["requested"]):
                    why = "an operation changes an explicit header input on the wire"
                elif r["dynamic_headers"]:
                    why = dynamic_header_error(r["dynamic_headers"], p["wire"])
                check(f"door {r['name']} {sorted(fields)}", why)
    http = [r for r in rows if r["surface"] == "http"]
    for ch, sc, step, code, kind, fields in expectations():
        cands = [r for r in http if r["code_n"] == code and r["kind"] == kind]
        if ch in WHOLE:
            ok = any(r["req"] <= fields <= r["req"] | r["opt"] for r in cands)
        else:
            ok = any(fields <= r["req"] | r["opt"] for r in cands)
        check(f"acceptance {ch} {sc} step {step}", None if ok else
              f"{code} {kind} {sorted(fields)}: no row of the catalogue " +
              (f"(rows {[(r['name'], sorted(r['req']), sorted(r['opt'])) for r in cands]})" if cands else
               "with this code and kind"))
    passed = sum(r["ok"] for r in results)
    verdict = "PASS" if passed == len(results) else "FAIL"
    print(f"refusals: {passed}/{len(results)} {verdict}")
    if a.json:
        Path(a.json).write_text(json.dumps({"passed": passed, "total": len(results), "verdict": verdict,
                                            "results": results}, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
