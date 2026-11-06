"""Judge the generated families part against family vectors (ADR-0125 generator 5, addendum (1), item 1).

  python tools/normgen/family_judge.py [--module-dir <families-module-directory>] [--lesson NN-name] [--runs 3] [--json <result>]

Each row of Platform/common/vectors/family-read/<lesson>.tsv (case, family, key, kind, mode, who, text, verdict, paths, outcome, note; see its README) is sent to families/harness. Compare Judge's verdict and path set, and OutcomesFor for every who role, exactly as the runner does. These vectors define the dialect with set-B deltas; check_spec, not this judge, verifies their agreement with the V7 stack. Repeat --runs times because Go map iteration is random (README D18).

--v7 adds independent mutants: extra keys, non-string values, integer/time boundaries, malformed keys and non-JSON text. Expectations come from the course's Python V7 stack (stack.Family, spec.outcomes_for and key templates), not the generator. Requires jsonschema, available in /opt/check-env/lesson-spec. Result: `families: P/<lesson> N/M PASS|FAIL`; exits 0=all match, 1=mismatch, 2=judge startup error."""
import argparse
import json
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
    work = Path(tempfile.mkdtemp(prefix="family-judge-"))
    try:
        (work / "main.go").write_text((HERE / "families/harness/main.go").read_text(encoding="utf-8")
                                      .replace('"normgen/p01-1/', f'"{L.go_module}/'), encoding="utf-8")
        (work / "go.mod").write_text(f"module normgen/familyharness\n\ngo 1.22\n\nrequire {L.go_module} v0.0.0\n\n"
                                     f"replace {L.go_module} => {Path(module_dir).resolve()}\n", encoding="utf-8")
        build = subprocess.run(["go", "build", "-o", "harness", "."], cwd=work, capture_output=True, text=True,
                               timeout=300)
        if build.returncode:
            raise SystemExit(f"family_judge: the harness does not build: {build.stderr.strip()}")
        stdin = "".join(json.dumps({"family": c["family"], "key": c["key"], "mode": c["mode"], "who": c["who"],
                                    "text": c["text"]}, ensure_ascii=False) + "\n" for c in cases)
        done = subprocess.run([str(work / "harness")], input=stdin, capture_output=True, text=True, timeout=300)
        if done.returncode:
            raise SystemExit(f"family_judge: the harness: {done.stderr.strip()}")
        return [json.loads(x) for x in done.stdout.splitlines()]
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
        fam, tmpl = stack.Family(doc, row["kind"]), templates[(row["key"], row["kind"])]
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


def judge(module_dir, lesson=L.nn, runs=3, v7=False):
    cases = rows(lesson)
    if v7:
        cases += v7_cases(lesson, cases)
    bad = {}
    for _ in range(runs):
        answers = harness(module_dir, cases)
        if len(answers) != len(cases):
            raise SystemExit(f"family_judge: {len(answers)} answers to {len(cases)} cases")
        for c, a in zip(cases, answers):
            why = compare(c, a)
            if why and c["case"] not in bad:
                bad[c["case"]] = f"{c['note']}: {why}"
    return {"lesson": lesson, "cases": len(cases), "pass": len(cases) - len(bad), "runs": runs,
            "failures": [{"case": k, "why": v} for k, v in sorted(bad.items())]}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--module-dir", default=str(L.out / "go"))
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--v7", action="store_true", help="also own instances judged by the V7 stack of the course")
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    try:
        res = judge(a.module_dir, L.nn, a.runs, a.v7)
    except SystemExit as exc:
        print(exc, file=sys.stderr)
        return 2
    for f in res["failures"]:
        print(f"FAIL {f['case']}: {f['why']}")
    ok = not res["failures"]
    print(f"families: P/{L.nn} {res['pass']}/{res['cases']} {'PASS' if ok else 'FAIL'} (runs {res['runs']})")
    if a.json:
        Path(a.json).write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
