"""Judge the generated families part against family vectors (ADR-0125 generator 5, addendum (1), item 1).

  python tools/normgen/family_judge.py [--module-dir <families-module-directory>] [--lesson NN-name] [--runs 3] [--json <result>]

Each row of Platform/common/vectors/family-read/<lesson>.tsv (case, family, key, kind, mode, who, text, verdict, paths, outcome, note; see its README) is sent to families/harness. Compare Judge's verdict and path set, and OutcomesFor for every who role, exactly as the runner does. These vectors define the dialect with set-B deltas; check_spec, not this judge, verifies their agreement with the V7 stack. Repeat --runs times because Go map iteration is random (README D18).

--v7 adds independent mutants: extra keys, non-string values, integer/time boundaries, malformed keys and non-JSON text. Expectations come from the course's Python V7 stack (stack.Family, spec.outcomes_for and key templates), not the generator. Requires jsonschema, available in /opt/check-env/lesson-spec. Result: `families: P/<lesson> N/M PASS|FAIL`; exits 0=all match, 1=mismatch, 2=judge startup error."""
import argparse
import hashlib
import math
import re
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import lesson  # noqa: E402 -- lesson selection (ADR-0125 addendum (5), item 2)
L = lesson.CURRENT
VECTORS = ROOT / "Platform/common/vectors/family-read"
HEADER = ["case", "family", "key", "kind", "mode", "who", "text", "verdict", "paths", "outcome", "note"]


class CheckingError(ValueError):
    """Source, preparation, process or report failure; never a semantic mismatch."""


def _positive_runs(value):
    if type(value) is not int or value <= 0:
        raise CheckingError("runs must be a positive integer")
    return value


def _runs_argument(text):
    try:
        return _positive_runs(int(text))
    except (ValueError, TypeError) as exc:
        raise argparse.ArgumentTypeError("runs must be a positive integer") from exc


def _strings(value):
    return type(value) is list and all(type(v) is str for v in value)


def _outcome(value, mode):
    if mode == "writer":
        return _strings(value)
    return type(value) is dict and all(type(k) is str and _strings(v) for k, v in value.items())


def _cases(cases):
    if type(cases) is not list or not cases:
        raise CheckingError("a nonempty Source case roster is required")
    names = set()
    for case in cases:
        if (type(case) is not dict or any(type(case.get(k)) is not str for k in
                ("case", "family", "key", "mode", "text", "verdict", "note")) or
                not case["case"] or case["case"] in names or case["mode"] not in ("reader", "writer") or
                case.get("kind") not in ("row", "object", "file") or case["verdict"] not in ("ok", "refused") or
                not _strings(case.get("who")) or not _strings(case.get("paths")) or
                not _outcome(case.get("outcome"), case["mode"])):
            raise CheckingError("missing, duplicate or mistyped Source case")
        names.add(case["case"])
    try:
        json.dumps(cases, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise CheckingError("Source cases are not finite UTF-8 JSON") from exc
    return cases


def checked_answers(cases, answers):
    _cases(cases)
    if type(answers) is not list or len(answers) != len(cases):
        raise CheckingError("a complete nonempty family report is required")
    for identity, (case, answer) in enumerate(zip(cases, answers), 1):
        if (type(answer) is not dict or type(answer.get("id")) is not int or answer["id"] != identity or
                type(answer.get("case")) is not str or answer["case"] != case["case"]):
            raise CheckingError("missing, duplicate, extra or out-of-order family identity")
        if set(answer) == {"id", "case", "error"}:
            if type(answer["error"]) is not str or not answer["error"]:
                raise CheckingError("mistyped family error observation")
        elif (set(answer) != {"id", "case", "verdict", "paths", "outcome"} or
              type(answer["verdict"]) is not str or answer["verdict"] not in ("ok", "refused") or not _strings(answer["paths"]) or
              not _outcome(answer["outcome"], case["mode"])):
            raise CheckingError("missing, extra or mistyped family result fields")
    try:
        json.dumps(answers, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise CheckingError("family report is not finite UTF-8 JSON") from exc
    return answers


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CheckingError("duplicate family JSON key")
        result[key] = value
    return result


def _constant(value):
    raise CheckingError("non-JSON family report constant: " + value)


def read_report(cases, done):
    if type(getattr(done, "returncode", None)) is not int or done.returncode != 0:
        raise CheckingError("family service did not complete normally")
    try:
        raw, err = done.stdout, done.stderr
        if type(raw) is bytes:
            raw = raw.decode("utf-8", "strict")
        if type(err) is bytes:
            err = err.decode("utf-8", "strict")
        if type(raw) is not str or type(err) is not str or err:
            raise CheckingError("invalid family stdout/stderr capture")
        raw.encode("utf-8", "strict")
        if not raw.endswith("\n"):
            raise CheckingError("truncated family report: final LF required")
        lines = raw.split("\n")
        if lines and lines[-1] == "":
            lines.pop()
        if not lines or any(not line for line in lines):
            raise CheckingError("empty or partial family report")
        answers = [json.loads(line, object_pairs_hook=_unique, parse_constant=_constant) for line in lines]
    except (UnicodeError, ValueError, TypeError, AttributeError, RecursionError) as exc:
        raise CheckingError("invalid UTF-8/JSON family report") from exc
    return checked_answers(cases, answers)


def _service_source():
    """Instrument only the owned temporary service's identity and I/O accounting."""
    source = (HERE / "families/harness/main.go").read_text(encoding="utf-8")
    changes = [
        ("type caseIn struct {", 'type caseIn struct {\n\tID int `json:"id"`\n\tCase string `json:"case"`'),
        ('\t\t\t_ = out.Encode(map[string]any{"error": "no family " + c.Family})',
         '\t\t\tif err := out.Encode(map[string]any{"id": c.ID, "case": c.Case, "error": "no family " + c.Family}); err != nil { fmt.Fprintln(os.Stderr, "encode:", err); os.Exit(2) }'),
        ('\t\t_ = out.Encode(map[string]any{"verdict": r.Verdict, "paths": r.Paths, "outcome": outcome})',
         '\t\tif err := out.Encode(map[string]any{"id": c.ID, "case": c.Case, "verdict": r.Verdict, "paths": append([]string{}, r.Paths...), "outcome": outcome}); err != nil { fmt.Fprintln(os.Stderr, "encode:", err); os.Exit(2) }'),
        ('\t\t\t\tm[role] = f.OutcomesFor(r.Paths, role)',
         '\t\t\t\tm[role] = append([]string{}, f.OutcomesFor(r.Paths, role)...)'),
        ('\t}\n}\n', '\t}\n\tif err := in.Err(); err != nil { fmt.Fprintln(os.Stderr, "scanner:", err); os.Exit(2) }\n}\n'),
    ]
    for old, new in changes:
        if source.count(old) != 1:
            raise CheckingError("owned family service instrumentation anchor changed")
        source = source.replace(old, new, 1)
    return source.replace('"normgen/p01-1/', f'"{L.go_module}/')


def rows(lesson):
    path = VECTORS / f"{lesson}.tsv"
    lines = [x for x in path.read_text(encoding="utf-8").split("\n") if x]
    if lines[0].split("\t") != HEADER:
        raise SystemExit(f"family_judge: {path}: header is not {HEADER}")
    out = []
    for x in lines[1:]:
        r = dict(zip(HEADER, x.split("\t")))
        r["who"] = json.loads(r["who"])
        r["paths"] = json.loads(r["paths"])
        r["outcome"] = json.loads(r["outcome"])
        out.append(r)
    return out


def harness(module_dir, cases):
    _cases(cases)
    work = Path(tempfile.mkdtemp(prefix="family-judge-"))
    env = dict(os.environ, GOFLAGS="-mod=mod", GOPROXY="off", GOWORK="off", GOTOOLCHAIN="local")
    try:
        (work / "main.go").write_text(_service_source(), encoding="utf-8")
        (work / "go.mod").write_text(f"module normgen/familyharness\n\ngo 1.22\n\nrequire {L.go_module} v0.0.0\n\n"
                                     f"replace {L.go_module} => {Path(module_dir).resolve()}\n", encoding="utf-8")
        build = subprocess.run(["go", "build", "-o", "harness", "."], cwd=work, capture_output=True,
                               timeout=300, env=env)
        if type(build.returncode) is not int or build.returncode != 0:
            raise CheckingError(f"family harness build failed: {build.stderr!r}")
        stdin = "".join(json.dumps(dict(id=i, case=c["case"], family=c["family"], key=c["key"],
                                    mode=c["mode"], who=c["who"], text=c["text"]),
                                   ensure_ascii=False, allow_nan=False) + "\n" for i, c in enumerate(cases, 1))
        done = subprocess.run([str(work / "harness")], input=stdin.encode("utf-8"), capture_output=True,
                              timeout=300, env=env)
        return read_report(cases, done)
    except (OSError, UnicodeError, subprocess.SubprocessError) as exc:
        raise CheckingError(f"family preparation/process failed: {exc}") from exc
    finally:
        shutil.rmtree(work, ignore_errors=True)


def compare(case, got):
    if "error" in got:
        return got["error"]
    if got["verdict"] != case["verdict"] or sorted(got["paths"]) != sorted(case["paths"]) \
            or got["outcome"] != case["outcome"]:
        return (f"expected {case['verdict']} {case['paths']} {json.dumps(case['outcome'], ensure_ascii=False)}, "
                f"got {got['verdict']} {got['paths']} {json.dumps(got['outcome'], ensure_ascii=False)}")
    return None


V7_SCRIPTS = ROOT / "skills/lesson-spec/scripts"


DEEP_PER_FIELD = 80                                  # Per-field mutation limit; traversal order is deterministic.


def deep_texts(items, stack):
    """Mutate field JSON documents: remove or add object keys; duplicate the first array element, empty it, or drop its last element; change leaf types and boundary values. Serialize both JCS and indented JSON; V7 supplies both expectations."""
    out = []
    for k, t in items.items():
        if not isinstance(t, str) or t[:1] not in ("{", "["):
            continue
        try:
            doc = json.loads(t)
        except ValueError:
            continue
        muts = []

        def walk(x, path):
            if isinstance(x, dict):
                for key in list(x)[:6]:
                    muts.append((path, ("del", key)))
                muts.append((path, ("add", "zz_extra")))
                muts.append((path, ("badname", "!! not a name")))   # Invalid key-template name combined with a value outside the schema.
                for key in list(x)[:12]:
                    walk(x[key], path + [key])
            elif isinstance(x, list):
                if x:
                    muts.append((path, ("dup", 0)))
                    muts.append((path, ("pop", None)))
                    walk(x[0], path + [0])
                muts.append((path, ("empty", None)))
            else:
                for leaf in (1, "", "x" * 300, -1, 1.5, 9007199254740993, True, None, "1e400"):
                    muts.append((path, ("set", leaf)))
        walk(doc, [])
        per_op, picked = {}, []
        for m in muts:                                    # Limit each operation kind separately so deep paths remain covered.
            if per_op.get(m[1][0], 0) < DEEP_PER_FIELD // 2:
                per_op[m[1][0]] = per_op.get(m[1][0], 0) + 1
                picked.append(m)
        for path, (op, arg) in picked:
            d = json.loads(t)
            parent = d
            for seg in path:
                parent = parent[seg]
            if op == "del":
                del parent[arg]
            elif op == "add":
                parent[arg] = "x"
            elif op == "badname":
                parent[arg] = {"zz": [1, 1]}
            elif op == "dup":
                parent.insert(0, parent[0])
            elif op == "pop":
                parent.pop()
            elif op == "empty":
                if path:
                    holder = d
                    for seg in path[:-1]:
                        holder = holder[seg]
                    holder[path[-1]] = []
                else:
                    d = []
            elif op == "set":
                if path:
                    holder = d
                    for seg in path[:-1]:
                        holder = holder[seg]
                    holder[path[-1]] = arg
                else:
                    d = arg
            for enc in (stack.jcs(d) if not _has_huge(d) else None, json.dumps(d, indent=1, ensure_ascii=False)):
                if enc is None:
                    continue
                if isinstance(enc, str) and enc.count('"1e400"'):
                    enc = enc.replace('"1e400"', "1e400")
                out.append(json.dumps(dict(items, **{k: enc}), ensure_ascii=False))
    seen, uniq = set(), []
    for x in out:
        if x not in seen:
            seen.add(x)
            uniq.append(x)
    return uniq


def _has_huge(d):
    return False


def v7_cases(lesson, base_rows):
    """Create independent cases over each family's base row; the Python V7 stack supplies expectations."""
    sys.path.insert(0, str(V7_SCRIPTS))
    from v7 import spec, stack                       # noqa: E402 -- course V7 stack
    catalog = spec.read_catalog(ROOT)
    templates, _ = spec.key_templates(ROOT, catalog)
    out = []
    for row in catalog:
        if not (spec.is_v7_family(row) and row["owner"][2:4] == lesson):
            continue
        _, _, doc, _, outcomes = spec.load_family(ROOT, row)
        fam, tmpl = stack.Family(doc, row["kind"], family_template=row["key"]), templates[(row["key"], row["kind"])]
        bases = {r["mode"]: r for r in base_rows if r["family"] == row["key"] and r["note"] == "base"}
        if set(bases) != {"writer", "reader"}:
            raise SystemExit(f"family_judge: {row['key']}: no base rows of both modes in the vectors")
        items = json.loads(bases["writer"]["text"])
        key = bases["writer"]["key"]
        texts = ['"x"', "[]", "{}", "x", json.dumps(dict(items, zz_extra="1")), json.dumps(dict(items, zz_extra=1))]
        for k in items:
            for raw in ("1", "0", "true", "null", '"0"', '"9007199254740991"', '"0.5"', '"1.000"', '"1.123456"',
                        '"-0"', '"01"', '"1e3"', '"1E400"', '"' + "9" * 400 + '"'):
                texts.append("{" + ",".join(json.dumps(x) + ":" + (raw if x == k else json.dumps(v))
                                            for x, v in items.items()) + "}")
        deep = []                                     # Mutations inside x-encoding field documents (P/02):
        for seed in [r for r in base_rows if r["family"] == row["key"] and r["verdict"] == "ok"
                     and r["mode"] == "writer"]:          # Seed from readable writer rows containing documents.
            try:
                its = json.loads(seed["text"])
            except ValueError:
                continue
            if isinstance(its, dict):
                deep += [t for t in deep_texts(its, stack) if t not in deep]
        keys = [key, key + "/x", key.rsplit("/", 1)[0] + "/." if "/" in key else key + ".", key.upper()]
        for text in texts + deep:
            for k in (keys if text not in deep else [key]):
                for mode in ("writer", "reader"):
                    who = bases[mode]["who"]
                    v = spec.judge_family(fam, tmpl, k, row["kind"], text, mode)
                    outcome = ({r: [o.path for o in spec.outcomes_for(outcomes, v["paths"], r)] for r in who}
                               if mode == "reader" else [])
                    out.append({"case": f"v7-{len(out) + 1:04d}", "family": row["key"], "key": k, "kind": row["kind"],
                                "mode": mode, "who": who, "text": text, "verdict": v["verdict"], "paths": v["paths"],
                                "outcome": outcome, "note": f"v7 {k} {text}"})
    return out


# Explicit independent R008 controls; these do not repin rows() or v7_cases().
R008_SOURCE = "244355d161139bd6fe65fd68c7e5134598c21ba3"
R008_INPUTS = {
    "Platform/common/data/catalog.tsv": "d5d8f0e11ccaa9081a42b0fecfb1523e4cea42e9c9e4ad91496b62e3a7d7261a",
    "Platform/common/data/key-placeholders.tsv": "432ecdafbd78569eb820e24ba2d21862497e310ba5d81467ae19a993c9638ee4",
    "Platform/common/vectors/family-read/01.tsv": "0226d33edec0dd646ce8790db80084076742a90e744916c286fd48bc3935d310",
    "Platform/common/vectors/family-read/03.tsv": "7258b223fc3487ccdfda4c6d69a90fe009d595b49b2e819e100511d077426c94",
    "Platform/common/data/codec.tsv": "fc8f59027628a14ed0b18495989ea5c45a45a558f6fc6d8fe8f61fc9fd2808dd",
    "Platform/01-store/spec/01.1-store.norms.md": "184fd477ff7e920fdd865e21b9d773c86401418bfe6eb09b037edc9e5693a505",
    "Platform/01-store/spec/01.3-store.norms.md": "99d80b8108c952d599bd2fda15944c9f7f2c19e2acd1580a2ea4715b066c9bab",
    "Platform/03-worker/spec/03.4-worker.norms.md": "ae0aa963b5e1fd5bd3f3a0bc99e4a6b6d2c029784b54534088432dbd00f44ce7",
    "Platform/01-store/data/epoch_floor.schema.json": "537add27ae2016c0efa0dcf8959dbeac7827eab535c59ecaacccb3e14b1df839",
    "Platform/01-store/data/epoch_floor.layers.tsv": "59dc184bb582a9ab1ac2629d84eb50cca25fb8a98c8d3bfccc0d3f95138b9dcf",
    "Platform/01-store/data/epoch_floor.outcomes.tsv": "ba25c35ad1e5b3f580640d64ce7922d1e7752735101d90eb4738b66e45ae2283",
    "Platform/01-store/data/configstore-doors.schema.json": "5e01688a43dfb4c8a03053f4bdb7f77cefa7ff625571e6644e7f0f3c3cb7c331",
    "Platform/01-store/data/configstore-doors.layers.tsv": "f9fc249e4ff9938120810c2109cc3c6225bb4281538641e895779be236fbc88c",
    "Platform/01-store/data/configstore-doors.outcomes.tsv": "b24083716a70f709048e99659901ece2bc22ed9d904fe7883558d60c1d0f1c7b",
    "Platform/03-worker/data/heartbeats.schema.json": "19f863324a1f0a02db34b53f6c7ea4fc06bcd729eef2b972ee79fbb567988477",
    "Platform/03-worker/data/heartbeats.layers.tsv": "0912cbdf0d7e15c86d9ce2584734ab0e08cd1058e29af664870a3dd1ab002b10",
    "Platform/03-worker/data/heartbeats.outcomes.tsv": "947b7b0aabb1d3fd686829e1982635801df98d4c58f84f211fc95e81e61b6bc1"
}


def _r008_time_lexeme(text):
    """R006–R010: inspect the original decimal spelling before binary64 decoding."""
    return (type(text) is str and
            re.fullmatch(r"(0|[1-9][0-9]*)(\.[0-9]{1,3})?", text) is not None and
            math.isfinite(float(text)))


def _r008_inputs(source_root, source_pin):
    """Only an explicit Source244 public context can supply this independent roster."""
    if source_pin != R008_SOURCE:
        raise CheckingError("R008 controls require explicit Source244; existing Source pins are unchanged")
    context = {}
    try:
        for name, digest in R008_INPUTS.items():
            raw = (Path(source_root) / name).read_bytes()
            if hashlib.sha256(raw).hexdigest() != digest:
                raise CheckingError("R008 Source244 input identity differs: " + name)
            context[name] = raw.decode("utf-8", "strict")
    except (OSError, UnicodeError, TypeError) as exc:
        raise CheckingError("R008 Source244 context unavailable") from exc
    return context


def _r008_mutations(base, field, failure_path):
    """Source positive first; expectations use R008, never the producer or old V7 Time."""
    # All spellings derive from R006/R008/R010. Finite binary64 is the only upper
    # bound: the integer 2**53 is legal Time, unlike the separate uint53 type.
    spellings = [
        ("normal", "1.123"), ("zero", "0"), ("millisecond", "0.001"),
        ("one-digit", "1.1"), ("two-digits", "1.12"),
        ("trailing-zero", "1.120"), ("three-zeros", "1.000"),
        ("beyond-uint53", "9007199254740992"),
        ("finite-large", "1" + "0" * 308),
        ("excess", "1.1234"), ("excess-zero", "1.1230"),
        ("four-zeros", "1.0000"), ("no-truncate", "0.0001"),
        ("no-round", "0.9999"), ("float-collapse", "1.00000000000000001"),
        ("negative", "-1"), ("negative-zero", "-0"), ("sign", "+1"),
        ("leading-zero", "01"), ("exponent", "1e0"),
        ("space", " 1"), ("final-lf", "1\n"), ("dot", "1."),
        ("no-integer", ".1"), ("empty", ""),
        ("timezone", "1970-01-01T00:00:01Z"),
        ("overflow", "1" + "0" * 309),
    ]
    items = json.loads(base["text"])
    out = []
    for label, spelling in spellings:
        # Numeric transport is used only by an existing object Time field. Rows
        # remain dictionaries of strings even when their logical type is Time.
        transports = ["string"]
        if base["kind"] == "object":
            try:
                json.loads(spelling)
            except ValueError:
                pass
            else:
                # JSON whitespace is outside the number token, not part of its
                # Time notation. Keep those neighbours on the string path.
                if spelling == spelling.strip():
                    transports.append("number")
        for transport in transports:
            fields = [json.dumps(k) + ":" +
                      (spelling if transport == "number" else json.dumps(spelling))
                      if k == field else json.dumps(k) + ":" + json.dumps(v)
                      for k, v in items.items()]
            ok = _r008_time_lexeme(spelling)
            paths = [] if ok else ["/" + field]
            outcome = ([] if base["mode"] == "writer" else
                       {role: ([] if ok else [failure_path]) for role in base["who"]})
            out.append(dict(base, case=f"r008-{field}-{base['mode']}-{label}-{transport}",
                            text="{" + ",".join(fields) + "}", verdict="ok" if ok else "refused",
                            paths=paths, outcome=outcome,
                            note=f"Source {R008_SOURCE} P/01.1 R006–R010; /{field}; {label}; {transport}"))
    if base["kind"] == "row":
        # A JSON number in items violates the row string codec independently of
        # precision. It must not be confused with the object's numeric bypass.
        for label, value in (("numeric-normal", 1.123), ("numeric-excess", 1.1234)):
            out.append(dict(base, case=f"r008-{field}-{base['mode']}-{label}",
                            text=json.dumps(dict(items, **{field: value})), verdict="refused",
                            paths=["/" + field], outcome=[] if base["mode"] == "writer" else
                            {role: [failure_path] for role in base["who"]},
                            note=f"Source {R008_SOURCE} R009; row items require strings"))
    return _cases(out)


def r008_time_cases(source_root, *, source_pin, lesson):
    """Prepare public Time cases only; caller binds a future actual runtime separately.

    P/01 exercises the row codec; P/03 exercises object numeric/string Time.
    No Go, generation, old stack oracle, or change to the default vector roster.
    The full public context is hash-bound before any expectation is constructed.
    """
    if lesson not in ("01", "03"):
        raise CheckingError("R008 has only the public P/01 row and P/03 heartbeat bindings")
    context = _r008_inputs(source_root, source_pin)
    lines = context[f"Platform/common/vectors/family-read/{lesson}.tsv"].splitlines()
    if lines[0].split("\t") != HEADER:
        raise CheckingError("R008 Source vector header differs")
    bases = []
    for line in lines[1:]:
        row = dict(zip(HEADER, line.split("\t")))
        if row.get("note") != "base":
            continue
        for field in ("who", "paths", "outcome"):
            row[field] = json.loads(row[field])
        bases.append(row)
    bindings = ([("platform/epoch_floor", "generation_at", "/generation_at"),
                 ("platform/configstore-doors/<id>", "seen_at", "")]
                if lesson == "01" else [("<sub>/heartbeats/<name>", "ts", "")])
    out = []
    for family, field, failure_path in bindings:
        selected = [r for r in bases if r["family"] == family]
        if len(selected) != 2 or {r["mode"] for r in selected} != {"reader", "writer"}:
            raise CheckingError("R008 requires both positive Source bases: " + family)
        _cases(selected)
        for base in selected:
            if base["verdict"] != "ok" or base["paths"]:
                raise CheckingError("R008 Source base is not positive")
            # Source P/03.4 R006 requires worker to equal the concrete key name;
            # the historical generic form seed uses 'a'. Keep the public key and
            # make the value obey the owner before deriving Time-only mutations.
            if lesson == "03":
                value = json.loads(base["text"])
                value["worker"] = base["key"].rsplit("/", 1)[-1]
                base = dict(base, text=json.dumps(value))
            out.extend(_r008_mutations(base, field, failure_path))
    # Establish every field/mode normal control before malformed neighbours.
    out.sort(key=lambda case: "-normal-" not in case["case"])
    return _cases(out)


def judge(module_dir, lesson=L.nn, runs=3, v7=False):
    _positive_runs(runs)
    try:
        cases = rows(lesson)
        if v7:
            cases += v7_cases(lesson, cases)
    except (OSError, UnicodeError, ValueError, IndexError, KeyError, TypeError) as exc:
        raise CheckingError(f"family Source input failed: {exc}") from exc
    _cases(cases)
    bad = {}
    for _ in range(runs):
        answers = checked_answers(cases, harness(module_dir, cases))
        for c, a in zip(cases, answers):
            why = compare(c, a)
            if why and c["case"] not in bad:
                bad[c["case"]] = f"{c['note']}: {why}"
    return {"lesson": lesson, "cases": len(cases), "pass": len(cases) - len(bad), "runs": runs,
            "failures": [{"case": k, "why": v} for k, v in sorted(bad.items())]}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--module-dir", help="module to judge; default: the validated prepared lesson module")
    ap.add_argument("--runs", type=_runs_argument, default=3)
    ap.add_argument("--v7", action="store_true", help="also own instances judged by the V7 stack of the course")
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    if a.module_dir is None:
        try:
            a.module_dir = str(lesson.ready_outputs(profiles=lesson.PROFILES)[L.slug] / "go")
        except (lesson.LessonError, OSError) as exc:
            print(f"family_judge: {exc}", file=sys.stderr)
            return 2
    try:
        res = judge(a.module_dir, L.nn, a.runs, a.v7)
    except (SystemExit, CheckingError, OSError, UnicodeError) as exc:
        print(exc, file=sys.stderr)
        return 2
    if a.json:
        try:
            Path(a.json).write_text(json.dumps(res, ensure_ascii=False, indent=1, allow_nan=False) + "\n", encoding="utf-8")
        except (OSError, UnicodeError, ValueError, TypeError) as exc:
            print(f"family_judge: cannot publish report: {exc}", file=sys.stderr)
            return 2
    for f in res["failures"]:
        print(f"FAIL {f['case']}: {f['why']}")
    ok = not res["failures"]
    print(f"families: P/{L.nn} {res['pass']}/{res['cases']} {'PASS' if ok else 'FAIL'} (runs {res['runs']})")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
