"""Generate stagetests for a lesson without its own HTTP seam engine (P/02; ADR-0125 addendum (5), ADR-0126 addendum (7)).

  python3 tools/normgen/gen_cmdtests.py --lesson 02-installer [<out>]
Default: tools/normgen/out/pNN. Read lesson forms, not prose: stages.kit.tsv gates select tests:<chapter>:<scenarios|*>:seams and verdicts:<chapter>:<cases|*> from seams.tsv or verdicts.tsv/classes.tsv/cases/*.subsystem.yaml. puts gates require the P/01 store and runner; inventory marks them excluded with `needs the store of P/01 (runner corpus puts)`, rather than simulating store results.

forms/README.md declares Non-HTTP seams and CALL normalization. RUN takes process/words and optional <<inputs/file or <<$name; expect exit N with optional JSON stdout, JSON-string stdout-text and stderr substring. CALL command|load|load-catalogue|rollout-poll takes JSON and matches a JSON subset: {} is exactly empty, @absent means missing, $name binds a row. @file writes a stand path from an input fixture or JSON string; @read expects JSON, text or absence. @parallel K repeats the next RUN/CALL with each or one/rest expectations. $data/, $run/, $manifest/ roots are fresh per scenario.

Emit closed lessonadapter types Roots/Result/Source/Loaded/Catalogue/Event/Poll/PollResult; one YOURS command.go/load.go/catalogue.go/poll.go file per function, initially failing without panic; stagetests engine and stage tests, verdict subtests, verdicts.jsonl and inventory.tsv. test_gen_cmdtests.py checks a passing fixture adapter and failing adapter/seam mutants."""
import base64
import json
import re
import textwrap
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import gate  # noqa: E402
import lesson  # noqa: E402 -- lesson selection (ADR-0125 addendum (5), item 2)
from gen_checks import go_str, gofmt  # noqa: E402

L = lesson.CURRENT
DEFAULT_OUT = L.out
GO_MODULE = L.go_module
OBSERVATION_CALLS = {
    "installer-role-unit-groups": "InstallerRoleUnitGroups",
    "secrets-walk": "SecretsWalk",
}
CALLS = ("command", "load", "load-catalogue", "rollout-poll", *OBSERVATION_CALLS)
STAND = re.compile(r"\$(data|run|manifest)/[^\s\"]*")
VAR = re.compile(r"\$[A-Za-z_][A-Za-z0-9_]*")
RUN_EXPECT = re.compile(r"exit (0|[1-9][0-9]*)((?:; (?:stdout|stdout-text|stderr) .*)?)")
PUTS_REASON = "needs the store of P/01 (runner corpus puts)"


class GenError(Exception):
    pass


PORT_HEAD = re.compile(r"\| CALL port \| [^|]+\|")
PORT_ROW = re.compile(r"\| `([a-z][a-z0-9-]*)` \| (.+) \|")


def read_ports(root=ROOT):
    """Read {port: declaration} from the forms/README.md CALL port table (P/03, P/04); absent table gives {} (P/02)."""
    path = Path(root) / L.rel / "forms/README.md"
    if not path.is_file():
        return {}
    ports, inside = {}, False
    for line in path.read_text(encoding="utf-8").split("\n"):
        if PORT_HEAD.fullmatch(line.strip()):
            inside = True
            continue
        if inside:
            if line.startswith("|---"):
                continue
            m = PORT_ROW.fullmatch(line.strip())
            if not m:
                break
            if m[1] in ports:
                raise GenError(f"forms/README.md: CALL port {m[1]} repeats")
            ports[m[1]] = m[2]
    if inside and not ports:
        raise GenError("forms/README.md: the table «CALL port» has no rows")
    return ports


def camel(name):
    return "".join(w[:1].upper() + w[1:] for w in re.split(r"[-_]", name) if w)


def acceptance(root, chapter):
    k = chapter.split(".")[1] if "." in chapter else None
    return Path(root) / L.rel / "acceptance" / (k or "")


def json_text(text, where):
    try:
        return json.loads(text)
    except ValueError as exc:
        raise GenError(f"{where}: not JSON: {exc}") from None


def words(text, where):
    """Parse single-space-separated RUN words: an unquoted word or a JSON string."""
    out, i = [], 0
    while i < len(text):
        if text[i] == '"':
            dec = json.JSONDecoder()
            try:
                w, j = dec.raw_decode(text, i)
            except ValueError:
                raise GenError(f"{where}: a bad JSON string word") from None
            if not isinstance(w, str):
                raise GenError(f"{where}: a quoted word is not a JSON string")
            out.append(("lit", w))
            i = j
        else:
            j = text.find(" ", i)
            j = len(text) if j < 0 else j
            w = text[i:j]
            if not w or '"' in w or "\t" in w:
                raise GenError(f"{where}: word {w!r}")
            out.append(("word", w))
            i = j
        if i < len(text):
            if text[i] != " " or i + 1 >= len(text) or text[i + 1] == " ":
                raise GenError(f"{where}: words are separated by one space")
            i += 1
    return out


def parse_expect_run(text, where):
    m = RUN_EXPECT.fullmatch(text)
    if not m:
        raise GenError(f"{where}: RUN expect {text!r} — exit N[; stdout …][; stdout-text …][; stderr ~…]")
    exp = {"exit": int(m[1]), "stdout": None, "stdout_text": None, "stderr": None}
    rest, order = m[2], ["stdout", "stdout-text", "stderr"]
    last = -1
    for part in [p for p in rest.split("; ") if p]:
        key, _, val = part.partition(" ")
        if key not in order or order.index(key) <= last:
            raise GenError(f"{where}: RUN expect part {key!r} out of order or repeated")
        last = order.index(key)
        if key == "stdout":
            json_text(val, where)
            exp["stdout"] = val
        elif key == "stdout-text":
            s = json_text(val, where)
            if not isinstance(s, str):
                raise GenError(f"{where}: stdout-text is a JSON string")
            exp["stdout_text"] = s
        else:
            if not val.startswith("~"):
                raise GenError(f"{where}: stderr ~<JSON string>")
            s = json_text(val[1:], where)
            if not isinstance(s, str):
                raise GenError(f"{where}: stderr ~<JSON string>")
            exp["stderr"] = s
    return exp


def parse_step(root, chapter, scenario, step, request, expect):
    where = f"{scenario} step {step}"
    acc = acceptance(root, chapter)
    if request.startswith("RUN "):
        body = request[4:]
        stdin = None
        if " <<" in body:
            body, _, src = body.rpartition(" <<")
            if src.startswith("inputs/"):
                p = acc / src
                if not p.is_file():
                    raise GenError(f"{where}: no fixture {src}")
                stdin = ("bytes", p.read_text(encoding="utf-8"))
            elif VAR.fullmatch(src):
                stdin = ("var", src)
            else:
                raise GenError(f"{where}: stdin <<{src}")
        ws = words(body, where)
        if not ws or ws[0][0] != "word":
            raise GenError(f"{where}: RUN <process> …")
        return {"kind": "run", "proc": ws[0][1], "argv": ws[1:], "stdin": stdin,
                "expect": [("run", parse_expect_run(expect, where))]}
    if request.startswith("CALL "):
        name, _, rest = request[5:].partition(" ")
        ports = read_ports(root)
        if ports and name not in ports:
            raise GenError(f"{where}: CALL {name!r} — a port of the table «CALL port» of forms/README.md ({', '.join(ports)})")
        if not ports and name not in CALLS:
            raise GenError(f"{where}: CALL {name!r} — one of {CALLS} (forms README «CALL normalization»)")
        json_text(rest, where)
        return {"kind": "call", "name": name, "input": rest, "expect": [("call", parse_expect_call(expect, where))]}
    if request.startswith("@file "):
        path, _, src = request[6:].partition(" ")
        if not STAND.fullmatch(path) or ".." in path.split("/"):
            raise GenError(f"{where}: @file path {path!r}")
        if src.startswith("inputs/"):
            p = acc / src
            if not p.is_file():
                raise GenError(f"{where}: no fixture {src}")
            data = p.read_text(encoding="utf-8")
        else:
            data = json_text(src, where)
            if not isinstance(data, str):
                raise GenError(f"{where}: @file … <JSON string>")
        if expect != "ok":
            raise GenError(f"{where}: @file expects ok")
        return {"kind": "file", "path": path, "data": data, "expect": []}
    if request.startswith("@read "):
        path = request[6:]
        if not STAND.fullmatch(path) or ".." in path.split("/"):
            raise GenError(f"{where}: @read path {path!r}")
        if expect == "@absent":
            mode, val = "absent", ""
        elif expect.startswith("text "):
            v = json_text(expect[5:], where)
            if not isinstance(v, str):
                raise GenError(f"{where}: text <JSON string>")
            mode, val = "text", v
        else:
            json_text(expect, where)
            mode, val = "json", expect
        return {"kind": "read", "path": path, "mode": mode, "value": val, "expect": []}
    if m := re.fullmatch(r"@parallel ([2-9]|[1-9][0-9]+)", request):
        if expect != "ok":
            raise GenError(f"{where}: @parallel expects ok")
        return {"kind": "parallel", "k": int(m[1]), "expect": []}
    raise GenError(f"{where}: request {request[:40]!r} — RUN, CALL, @file, @read, @parallel")


def parse_expect_call(text, where):
    if text in ("@absent", "@exit 2"):
        return text
    json_text(text, where)
    return text


def apply_parallel(steps, where):
    """Parse @parallel K: repeat the next RUN/CALL K times with each <expect> or one <expect>; rest <expect>."""
    out, k = [], None
    for st in steps:
        if st["kind"] == "parallel":
            k = st
            out.append(st)
            continue
        if k is not None:
            if st["kind"] not in ("run", "call"):
                raise GenError(f"{where}: @parallel is followed by {st['kind']}, want RUN or CALL")
            raw = st["raw_expect"]
            kind = "run" if st["kind"] == "run" else "call"
            parse = (lambda x: parse_expect_run(x, where)) if kind == "run" else (lambda x: parse_expect_call(x, where))
            if raw.startswith("each "):
                st["each"] = True
                st["expect"] = [(kind, parse(raw[5:]))]
            elif m := re.fullmatch(r"one (.+?); rest (.+)", raw):
                st["each"] = False
                st["expect"] = [(kind, parse(m[1])), (kind, parse(m[2]))]
            else:
                raise GenError(f"{where}: after @parallel — each <expect> | one <expect>; rest <expect>")
            st["k"] = k["k"]
            k = None
        out.append(st)
    if k is not None:
        raise GenError(f"{where}: @parallel is the last step")
    return out


def read_seams(root, chapter):
    import tsv_input

    path = acceptance(root, chapter) / "seams.tsv"
    if not path.is_file():
        raise GenError(f"no {path.relative_to(root)}")
    try:
        table = tsv_input.read(path, names=("scenario", "step", "request", "expect"),
                               positional=True, root=root)
    except tsv_input.TSVError as exc:
        raise GenError(str(exc)) from None
    scen = {}
    for no, row in table.rows:
        name, step, request, expect = (row[c] for c in ("scenario", "step", "request", "expect"))
        scen.setdefault(name, [])
        if str(len(scen[name]) + 1) != step:
            raise GenError(f"{path.name}:{no}: {name} step {step} — the steps are consecutive from 1")
        scen[name].append((no, step, request, expect))
    return path, scen


def stage_steps(root, chapter, name, rows):
    steps = []
    after_parallel = False
    for no, step, request, expect in rows:
        if after_parallel:
            st = parse_step_raw(root, chapter, name, step, request, expect)
        else:
            st = parse_step(root, chapter, name, step, request, expect)
        st["n"], st["line"], st["raw_expect"] = int(step), no, expect
        after_parallel = st["kind"] == "parallel"
        steps.append(st)
    return apply_parallel(steps, name)


def parse_step_raw(root, chapter, scenario, step, request, expect):
    """After @parallel, apply_parallel parses each or one/rest expectations."""
    if request.startswith("RUN ") or request.startswith("CALL "):
        probe = "exit 0" if request.startswith("RUN ") else "{}"
        st = parse_step(root, chapter, scenario, step, request, probe)
        st["expect"] = []
        return st
    raise GenError(f"{scenario} step {step}: @parallel is followed by {request[:20]!r}")


def read_verdicts(root, chapter):
    acc = acceptance(root, chapter)
    vpath, cpath = acc / "verdicts.tsv", acc / "classes.tsv"
    if not vpath.is_file():
        raise GenError(f"no {vpath.relative_to(root)}")
    classes = {}
    if cpath.is_file():
        for line in cpath.read_text(encoding="utf-8").split("\n"):
            if line and not line.startswith("#"):
                c, k = line.split("\t")
                classes[c] = k
    rows = []
    for no, line in enumerate(vpath.read_text(encoding="utf-8").split("\n"), 1):
        if not line or line.startswith("#"):
            continue
        case, verdict = line.split("\t")
        if verdict not in ("ok", "refused"):
            raise GenError(f"{vpath.name}:{no}: verdict {verdict!r}")
        f = acc / "cases" / f"{case}.subsystem.yaml"
        if not f.is_file():
            raise GenError(f"{vpath.name}:{no}: no cases/{case}.subsystem.yaml")
        rows.append({"case": case, "verdict": verdict, "class": classes.get(case, ""),
                     "b64": base64.b64encode(f.read_bytes()).decode("ascii")})
    files = {p.name[:-len(".subsystem.yaml")] for p in (acc / "cases").glob("*.subsystem.yaml")}
    if files != {r["case"] for r in rows}:
        raise GenError(f"{vpath.name}: the files of cases/ and the rows differ: {sorted(files ^ {r['case'] for r in rows})[:5]}")
    for c in classes:
        if c not in {r["case"] for r in rows if r["verdict"] == "refused"}:
            raise GenError(f"classes.tsv: {c} is not a refused case of verdicts.tsv")
    return vpath, rows


# ---------------------------------------------------------------- Go

def go_word(w):
    kind, val = w
    return f"{{lit: {'true' if kind == 'lit' else 'false'}, text: {go_str(val)}}}"


def go_run_expect(e):
    opt = lambda v: "nil" if v is None else f"strp({go_str(v)})"   # noqa: E731
    return (f"&runExpect{{exit: {e['exit']}, stdout: {go_str(e['stdout'] or '')}, hasStdout: "
            f"{'true' if e['stdout'] is not None else 'false'}, stdoutText: {opt(e['stdout_text'])}, stderr: {opt(e['stderr'])}}}")


def go_expect(e):
    kind, val = e
    return f"expect{{run: {go_run_expect(val)}}}" if kind == "run" else f"expect{{call: {go_str(val)}}}"


def go_step(st):
    parts = [f"n: {st['n']}", f"line: {st['line']}", f"kind: {go_str(st['kind'])}"]
    if st["kind"] == "run":
        parts += [f"proc: {go_str(st['proc'])}", "argv: []word{" + ", ".join(go_word(w) for w in st["argv"]) + "}"]
        if st["stdin"]:
            parts += [f"stdinKind: {go_str(st['stdin'][0])}", f"stdin: {go_str(st['stdin'][1])}"]
    elif st["kind"] == "call":
        parts += [f"name: {go_str(st['name'])}", f"input: {go_str(st['input'])}"]
    elif st["kind"] == "file":
        parts += [f"path: {go_str(st['path'])}", f"data: {go_str(st['data'])}"]
    elif st["kind"] == "read":
        parts += [f"path: {go_str(st['path'])}", f"mode: {go_str(st['mode'])}", f"value: {go_str(st['value'])}"]
    elif st["kind"] == "parallel":
        parts += [f"k: {st['k']}"]
    if st.get("k") and st["kind"] != "parallel":
        parts += [f"k: {st['k']}", f"each: {'true' if st['each'] else 'false'}"]
    if st["expect"]:
        parts.append("expects: []expect{" + ", ".join(go_expect(e) for e in st["expect"]) + "}")
    return "{" + ", ".join(parts) + "}"


def _build(root=ROOT):
    """Return ({go/-relative path: text}, [(step id, stage, test, status, reason)] inventory)."""
    stages_path = Path(root) / L.rel / "forms/stages.kit.tsv"
    rows = [ln.split("\t") for ln in stages_path.read_text(encoding="utf-8").split("\n") if ln and not ln.startswith("#")]
    head = rows[0]
    files, inventory, tests = {}, [], {}
    verdicts_data = []
    for r in rows[1:]:
        st = dict(zip(head, r))
        stage = st["stage"]
        checks = gate.parse(st["gate"], f"stages.kit.tsv: {stage}")
        for c in checks:
            if c.kind == "puts":
                inventory.append((f"{c.chapter}/puts.tsv/{'*' if c.names is None else ','.join(c.names)}", stage, "-",
                                  "excluded", PUTS_REASON))
            elif c.kind == "verdicts":
                vpath, vrows = read_verdicts(root, c.chapter)
                sel = [v for v in vrows if c.names is None or v["case"] in c.names]
                if c.names is not None and len(sel) != len(c.names):
                    raise GenError(f"{stage}: verdicts names {set(c.names) - {v['case'] for v in sel}} are not cases")
                test = f"Test{camel(stage)}_Verdicts"
                tests.setdefault(stage, []).append(("verdicts", c.chapter, test, len(sel)))
                verdicts_data += sel
                for v in sel:
                    inventory.append((f"{c.chapter}/verdicts.tsv/{v['case']}", stage, f"{test}/{v['case']}",
                                      "translated", "-"))
            elif c.kind == "tests" and c.seams:
                spath, scen = read_seams(root, c.chapter)
                names = c.names if c.names is not None else tuple(scen)
                for name in names:
                    if name not in scen:
                        raise GenError(f"{stage}: {name} is not a scenario of {spath.relative_to(root)}")
                    steps = stage_steps(root, c.chapter, name, scen[name])
                    test = f"Test{camel(stage)}_{camel(name)}"
                    tests.setdefault(stage, []).append(("seams", c.chapter, test, steps))
                    for s in steps:
                        inventory.append((f"{c.chapter}/seams.tsv/{name}/{s['n']}", stage, test, "translated", "-"))
            elif c.kind == "tests":
                raise GenError(f"{stage}: {c.text} — scenarios.tsv of a lesson without HTTP: not yet")
    if not tests:
        raise GenError("no stage of the lesson has seams or verdicts — an empty projection")
    for stage, items in tests.items():
        body = [f"// Code generated by tools/normgen/gen_cmdtests.py (stage {stage} of forms/stages.kit.tsv); DO NOT EDIT.",
                "", "package stagetests", "", 'import "testing"', ""]
        for kind, chapter, test, data in items:
            if kind == "verdicts":
                body += [f"// {test} — chapter {chapter}, verdicts.tsv: {data} cases (testdata/verdicts.jsonl).",
                         f"func {test}(t *testing.T) {{", f"\trunVerdicts(t, {go_str(chapter)})", "}", ""]
            else:
                body += [f"// {test} — chapter {chapter}, seams.tsv.", f"func {test}(t *testing.T) {{",
                         "\trunSeam(t, []step{"] + [f"\t\t{go_step(s)}," for s in data] + ["\t})", "}", ""]
        files[f"go/stagetests/{stage.replace('-', '_')}_test.go"] = gofmt("\n".join(body))
    ports = read_ports(root)
    if ports:
        return build_ports(files, inventory, tests, ports)
    files["go/stagetests/engine_test.go"] = gofmt(ENGINE.replace("normgen/p02/", GO_MODULE + "/"))
    files["go/stagetests/doc.go"] = gofmt(DOC)
    files["go/stagetests/testdata/verdicts.jsonl"] = "".join(
        json.dumps({"case": v["case"], "verdict": v["verdict"], "class": v["class"], "b64": v["b64"]},
                   ensure_ascii=False) + "\n" for v in verdicts_data)
    files["go/lessonadapter/lessonadapter.go"] = gofmt(ADAPTER_TYPES)
    for name, text in STUBS.items():
        files[f"go/lessonadapter/{name}"] = gofmt(STUB_HEAD + text)
    for port, fn in OBSERVATION_CALLS.items():
        files[f"go/lessonadapter/{port.replace('-', '_')}.go"] = gofmt(STUB_HEAD + f'''import (
    "encoding/json"
    "fmt"
)

// {fn} calls the implementation's {port} seam with the scenario roots and input.
// Return observations of the actual call described in acceptance/4/README.md,
// without calculating an expected answer. Errors and panics fail the seam.
func {fn}(roots Roots, input json.RawMessage) (json.RawMessage, error) {{
    return nil, fmt.Errorf("lessonadapter.{fn}: not implemented")
}}
''')
    inv = ["# Inventory of the stage tests of the lesson (gen_cmdtests.py): every selected step or case — translated or excluded.",
           "step\tstage\ttest\tstatus\treason"] + ["\t".join(map(str, r)) for r in inventory]
    files["go/stagetests/inventory.tsv"] = "\n".join(inv) + "\n"
    return files, inventory


def build(root=ROOT):
    files, inventory = _build(root)
    if L.key == "03-worker":
        import gen_policy_machines
        try:
            files.update(gen_policy_machines.build(root))
        except gen_policy_machines.GenError as exc:
            raise GenError(str(exc)) from None
    return files, inventory


def go_ident(port):
    return "".join(w[:1].upper() + w[1:] for w in port.split("-"))


def build_ports(files, inventory, tests, ports):
    """Generate CALL-port seams (P/03, P/04): CALL-only engine and one YOURS adapter file per port."""
    used, names = set(), set()
    for stage, items in tests.items():
        for _, _, test, _ in items:
            if test in names:
                raise GenError(f"{stage}: two seams give one test name {test} (scenario names repeat across chapters)")
            names.add(test)
        for kind, chapter, test, data in items:
            if kind != "seams":
                raise GenError(f"{stage}: {kind} in a lesson of CALL ports — not yet")
            for st in data:
                if st["kind"] != "call" or st.get("k"):
                    raise GenError(f"{stage}: {test} step {st['n']}: {st['kind']} — a lesson of CALL ports has CALL "
                                   "steps only (not yet RUN, @file, @read, @parallel)")
                if st["expect"][0][1] in ("@absent", "@exit 2"):
                    raise GenError(f"{stage}: {test} step {st['n']}: {st['expect'][0][1]} is not a CALL port answer")
                used.add(st["name"])
    table = "".join(f"\t{go_str(p)}: lessonadapter.{go_ident(p)},\n" for p in ports)
    files["go/stagetests/engine_test.go"] = gofmt(PORT_ENGINE.replace("normgen/p02/", GO_MODULE + "/")
                                                  .replace("//PORTS\n", table) + "\n" + PORT_HELPERS)
    files["go/stagetests/doc.go"] = gofmt(PORT_DOC.replace("{lesson}", L.code))
    files["go/lessonadapter/lessonadapter.go"] = gofmt(PORT_ADAPTER.replace("{lesson}", L.code))
    for port, text in ports.items():
        doc = "\n".join("// " + line for line in textwrap.wrap(text.replace("`", ""), 112))
        files[f"go/lessonadapter/{port.replace('-', '_')}.go"] = gofmt(
            PORT_STUB_HEAD + 'import "encoding/json"\n\n'
            f"// {go_ident(port)} — the CALL port {port} (forms/README.md «Seams»): input is its one JSON value; it returns\n"
            "// the JSON value the seams compare (an object by subset). Invoke your real code and record its effects;\n"
            "// never answer a case from its expected output. An error is «cannot answer», never a normal refusal.\n"
            f"//\n{doc}\n"
            f"func {go_ident(port)}(input json.RawMessage) (json.RawMessage, error) {{\n"
            f'\treturn nil, ErrNotImplemented("{port}")\n}}\n')
    for port in ports:
        if port not in used:
            inventory.append((f"forms/README.md/CALL {port}", "-", "-", "excluded",
                              "no seam of the stage plan calls this port"))
    inv = ["# Inventory of the stage tests of the lesson (gen_cmdtests.py): every selected step — translated or excluded.",
           "step\tstage\ttest\tstatus\treason"] + ["\t".join(map(str, r)) for r in inventory]
    files["go/stagetests/inventory.tsv"] = "\n".join(inv) + "\n"
    return files, inventory


PORT_STUB_HEAD = """// Generated by tools/normgen/gen_cmdtests.py. YOURS from here: the kit puts this file once and never overwrites it.
// One port per file: replace the body with a call of your own code; keep the signature (the stage tests call it).

package lessonadapter

"""

PORT_ADAPTER = """// Code generated by tools/normgen/gen_cmdtests.py; DO NOT EDIT.

// Package lessonadapter — the CALL ports of the seams of {lesson} (forms/README.md «Seams»): one function per port, in
// its own file (yours). The port names and JSON are test normalization, not the API of your implementation.
package lessonadapter

import "errors"

// ErrNotImplemented — the stub's answer: the port is not connected yet (the test is red, never a refusal).
func ErrNotImplemented(port string) error { return errors.New("lessonadapter: the CALL port " + port + " is not implemented") }
"""

PORT_DOC = """// Code generated by tools/normgen/gen_cmdtests.py; DO NOT EDIT.

// Package stagetests — the stage tests of {lesson} from forms/stages.kit.tsv and the seams acceptance/…/seams.tsv: each
// scenario is a list of CALL <port> <JSON> steps through lessonadapter; the answer is compared by the common acceptance
// rules (an object by subset, {} exactly empty, "@absent" — no field, "$name" — a binding, numbers by value). Run:
// go test ./internal/stagetests/.
package stagetests
"""

PORT_ENGINE = r"""// Code generated by tools/normgen/gen_cmdtests.py: the engine of the CALL ports; DO NOT EDIT.

package stagetests

import (
	"bytes"
	"encoding/json"
	"fmt"
	"math/big"
	"regexp"
	"sort"
	"testing"

	"normgen/p02/lessonadapter"
)

type expect struct {
	call string
}

type step struct {
	n       int
	line    int
	kind    string
	name    string
	input   string
	expects []expect
}

var varRx = regexp.MustCompile(`^\$[A-Za-z_][A-Za-z0-9_]*$`)

var ports = map[string]func(json.RawMessage) (json.RawMessage, error){
//PORTS
}

// runSeam — one scenario: a fresh start per scenario is the adapter's (forms README); the steps in order, a failed
// step stops the scenario.
func runSeam(t *testing.T, steps []step) {
	t.Helper()
	env := map[string]string{}
	for _, st := range steps {
		if errs := callStep(st, env); len(errs) > 0 {
			t.Fatalf("seams.tsv line %d (step %d, CALL %s):\n  %s", st.line, st.n, st.name, joinErrs(errs))
		}
	}
}

func joinErrs(errs []string) string {
	out := ""
	for i, e := range errs {
		if i > 0 {
			out += "\n  "
		}
		out += e
	}
	return out
}

func callStep(st step, env map[string]string) (errs []string) {
	port, ok := ports[st.name]
	if !ok {
		return []string{"no port " + st.name}
	}
	var out json.RawMessage
	var err error
	func() {
		defer func() {
			if r := recover(); r != nil {
				err = fmt.Errorf("the port panicked: %v (a panic is not a refusal)", r)
			}
		}()
		out, err = port(json.RawMessage(st.input))
	}()
	if err != nil {
		return []string{err.Error()}
	}
	act, err := decode(out)
	if err != nil {
		return []string{fmt.Sprintf("the answer %q: %v", clip(out), err)}
	}
	for _, e := range st.expects {
		exp, err := decode([]byte(e.call))
		if err != nil {
			return []string{"the expectation: " + err.Error()}
		}
		trial := copyEnv(env)
		match(exp, act, trial, "$", &errs)
		if len(errs) == 0 {
			for k, v := range trial {
				env[k] = v
			}
		}
	}
	return errs
}

func copyEnv(env map[string]string) map[string]string {
	out := make(map[string]string, len(env))
	for k, v := range env {
		out[k] = v
	}
	return out
}

var _ = sort.Strings
var _ = big.NewRat
var _ = bytes.NewReader
"""

PORT_HELPERS = r'''// decode — JSON with numbers as json.Number (compared by value).
func decode(data []byte) (any, error) {
	dec := json.NewDecoder(bytes.NewReader(data))
	dec.UseNumber()
	var v any
	if err := dec.Decode(&v); err != nil {
		return nil, err
	}
	if dec.More() {
		return nil, fmt.Errorf("more than one JSON value")
	}
	return v, nil
}

// match — the common acceptance rules: an object by subset ({} — exactly empty; "@absent" — the field is absent),
// a list element by element, "$name" — a string binding, numbers by value, the rest equal.
func match(exp, act any, env map[string]string, path string, out *[]string) {
	if s, ok := exp.(string); ok && varRx.MatchString(s) {
		as, ok := act.(string)
		switch {
		case !ok:
			*out = append(*out, fmt.Sprintf("%s: %s must be a string, got %s", path, s, show(act)))
		case env[s] != "":
			if env[s] != as {
				*out = append(*out, fmt.Sprintf("%s: %s is %q, got %q", path, s, env[s], as))
			}
		default:
			env[s] = as
		}
		return
	}
	switch e := exp.(type) {
	case map[string]any:
		a, ok := act.(map[string]any)
		if !ok {
			*out = append(*out, fmt.Sprintf("%s: want an object, got %s", path, show(act)))
			return
		}
		if len(e) == 0 && len(a) != 0 {
			*out = append(*out, fmt.Sprintf("%s: want {} exactly, got %s", path, show(act)))
			return
		}
		keys := make([]string, 0, len(e))
		for k := range e {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		for _, k := range keys {
			v := e[k]
			av, has := a[k]
			if v == "@absent" {
				if has {
					*out = append(*out, fmt.Sprintf("%s.%s: want absent, got %s", path, k, show(av)))
				}
				continue
			}
			if !has {
				*out = append(*out, fmt.Sprintf("%s.%s: missing", path, k))
				continue
			}
			match(v, av, env, path+"."+k, out)
		}
	case []any:
		a, ok := act.([]any)
		if !ok || len(a) != len(e) {
			*out = append(*out, fmt.Sprintf("%s: want %s, got %s", path, show(exp), show(act)))
			return
		}
		for i := range e {
			match(e[i], a[i], env, fmt.Sprintf("%s[%d]", path, i), out)
		}
	case json.Number:
		an, ok := act.(json.Number)
		x, okx := new(big.Rat).SetString(string(e))
		var y *big.Rat
		oky := false
		if ok {
			y, oky = new(big.Rat).SetString(string(an))
		}
		if !ok || !okx || !oky || x.Cmp(y) != 0 {
			*out = append(*out, fmt.Sprintf("%s: want %s, got %s", path, e, show(act)))
		}
	default:
		if fmt.Sprintf("%T %v", exp, exp) != fmt.Sprintf("%T %v", act, act) {
			*out = append(*out, fmt.Sprintf("%s: want %s, got %s", path, show(exp), show(act)))
		}
	}
}

func show(v any) string {
	b, err := json.Marshal(v)
	if err != nil {
		return fmt.Sprint(v)
	}
	if len(b) > 300 {
		return string(b[:300]) + "…"
	}
	return string(b)
}

func clip(b []byte) string {
	if len(b) > 300 {
		return string(b[:300]) + "…"
	}
	return string(b)
}

'''


ADAPTER_TYPES = '''// Code generated by tools/normgen/gen_cmdtests.py; DO NOT EDIT.

// Package lessonadapter — the adapter of the lesson to its generated stage tests (stagetests): the types here are the
// kit's (closed); each function is YOURS in its own file (command.go, load.go, catalogue.go, poll.go) — the kit puts
// each once and never overwrites it. The stage tests call only these functions, in process (no OS process, no shell).
package lessonadapter

// Roots — the roots of one scenario: $data/, $run/, $manifest/ of the seams (fresh temporary directories).
type Roots struct {
	Data     string
	Run      string
	Manifest string
}

// Result — the outcome of a command: its exit code and the bytes of its streams.
type Result struct {
	Exit   int
	Stdout []byte
	Stderr []byte
}

// Source — a manifest text with its source name (the file name the refusal names).
type Source struct {
	Source string
	Text   []byte
}

// Loaded — the outcome of the regular loader for one manifest: OK and the loaded name, or the refusal — its class
// (text | form | relations, the layer of the refusal) and the message (it names the file).
type Loaded struct {
	OK      bool
	Name    string
	Class   string
	Message string
}

// Catalogue — the outcome of loading a set of manifests and checking the complete set (load_catalogue): OK and the
// names, or the refusal class (text | form | relations | catalogue) and the message. No partial catalogue.
type Catalogue struct {
	OK      bool
	Names   []string
	Class   string
	Message string
}

// Event — one external event of the rollout poll at the virtual time T (seconds; forms/rollout-poll.machine.yaml).
type Event struct {
	T     float64
	Event string
}

// Poll — the final observation of the rollout poll: State polling | passed | refused and the refusal result.
type Poll struct {
	State  string
	Result *PollResult
}

// PollResult — the refusal of the poll: its exit code and word.
type PollResult struct {
	Code int
	Word string
}
'''

STUB_HEAD = '''// Generated by tools/normgen/gen_cmdtests.py. YOURS from here: the kit puts this file once and never overwrites it.
// One function per file: replace the body with a call of your own code; keep the signature (the stage tests call it).

package lessonadapter

'''

STUBS = {
    "command.go": '''// Command runs the operator command process with argv (the words after the process name, stand paths already
// resolved to the roots) and stdin, in process: your command function, not an OS process. A refusal is a normal
// return with its exit code; a panic is not a refusal (the test fails). The stub answers exit -1 «not implemented».
func Command(r Roots, process string, argv []string, stdin []byte) Result {
	return Result{Exit: -1, Stderr: []byte("lessonadapter.Command: not implemented\\n")}
}
''',
    "load.go": '''// Load runs your regular loader (the path by which a manifest is read from the store or a file) on exactly the bytes
// text of the file source, alone, without a catalogue of other manifests. The stub refuses nothing and loads nothing.
func Load(source string, text []byte) Loaded {
	return Loaded{Message: "lessonadapter.Load: not implemented"}
}
''',
    "catalogue.go": '''// LoadCatalogue loads each manifest by the same loader and checks their complete set (load_catalogue); no implicit
// stand manifest is added. The stub answers nothing.
func LoadCatalogue(manifests []Source) Catalogue {
	return Catalogue{Message: "lessonadapter.LoadCatalogue: not implemented"}
}
''',
    "poll.go": '''import "encoding/json"

// RolloutPoll runs your rollout poll (forms/rollout-poll.machine.yaml) from t=0 on the machine input (input.const may
// override constants) through events: advance the virtual clock to each event (timers first at equality), then
// deliver it; "advance" only advances the timers. It returns the final state and the refusal. The stub answers
// state "".
func RolloutPoll(input json.RawMessage, events []Event) Poll {
	return Poll{}
}
''',
}

DOC = '''// Code generated by tools/normgen/gen_cmdtests.py; DO NOT EDIT.

// Package stagetests — the stage tests of a lesson without its own HTTP, generated from forms/stages.kit.tsv: the seams
// (acceptance/K/seams.tsv: RUN, CALL, @file, @read, @parallel) and the loader corpus (verdicts.tsv). They call only
// package lessonadapter (yours). Run one stage: go test -run '^Test<Stage>_' ./internal/stagetests/.
package stagetests
'''

ENGINE = r'''// Code generated by tools/normgen/gen_cmdtests.py: the engine of the seams without HTTP (forms/README.md «Non-HTTP
// seams», «CALL normalization») and of the loader corpus; DO NOT EDIT.

package stagetests

import (
	"bufio"
	"bytes"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"math/big"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"sync"
	"testing"

	"normgen/p02/lessonadapter"
)

type word struct {
	lit  bool // a JSON-string word: taken as is
	text string
}

type runExpect struct {
	exit       int
	stdout     string
	hasStdout  bool
	stdoutText *string
	stderr     *string
}

type expect struct {
	run  *runExpect
	call string
}

type step struct {
	n, line              int
	kind                 string
	proc                 string
	argv                 []word
	stdinKind, stdin     string
	name, input          string
	path, data           string
	mode, value          string
	k                    int
	each                 bool
	expects              []expect
}

func strp(s string) *string { return &s }

var varRx = regexp.MustCompile(`^\$[A-Za-z_][A-Za-z0-9_]*$`)

type scenario struct {
	roots lessonadapter.Roots
	env   map[string]string
	mu    sync.Mutex
}

// runSeam — one scenario: fresh roots, the steps in order; a failed step stops the scenario (later steps depend on it).
func runSeam(t *testing.T, steps []step) {
	t.Helper()
	base := t.TempDir()
	sc := &scenario{env: map[string]string{}, roots: lessonadapter.Roots{
		Data: filepath.Join(base, "data"), Run: filepath.Join(base, "run"), Manifest: filepath.Join(base, "manifest")}}
	for _, d := range []string{sc.roots.Data, sc.roots.Run, sc.roots.Manifest} {
		if err := os.MkdirAll(d, 0o755); err != nil {
			t.Fatal(err)
		}
	}
	failed := false
	for _, st := range steps {
		st := st
		t.Run(fmt.Sprint(st.n), func(t *testing.T) {
			if failed {
				t.Fatalf("a previous step failed")
			}
			if errs := sc.step(st); len(errs) > 0 {
				failed = true
				for _, e := range errs {
					t.Errorf("seams.tsv:%d step %d: %s", st.line, st.n, e)
				}
			}
		})
	}
}

func (sc *scenario) path(p string) (string, error) {
	for prefix, root := range map[string]string{"$data/": sc.roots.Data, "$run/": sc.roots.Run, "$manifest/": sc.roots.Manifest} {
		if strings.HasPrefix(p, prefix) {
			return filepath.Join(root, filepath.FromSlash(p[len(prefix):])), nil
		}
	}
	return "", fmt.Errorf("%q is not a stand path", p)
}

// resolve — a stand path to its root, a bound $name to its value; other words as they are.
func (sc *scenario) resolve(w string) (string, error) {
	if strings.HasPrefix(w, "$data/") || strings.HasPrefix(w, "$run/") || strings.HasPrefix(w, "$manifest/") {
		return sc.path(w)
	}
	if varRx.MatchString(w) {
		sc.mu.Lock()
		v, ok := sc.env[w]
		sc.mu.Unlock()
		if !ok {
			return "", fmt.Errorf("unbound %s", w)
		}
		return v, nil
	}
	return w, nil
}

// resolveJSON — every string of the input: stand paths and bound names resolved.
func (sc *scenario) resolveJSON(v any) (any, error) {
	switch x := v.(type) {
	case string:
		return sc.resolve(x)
	case []any:
		out := make([]any, len(x))
		for i, e := range x {
			r, err := sc.resolveJSON(e)
			if err != nil {
				return nil, err
			}
			out[i] = r
		}
		return out, nil
	case map[string]any:
		out := map[string]any{}
		for k, e := range x {
			r, err := sc.resolveJSON(e)
			if err != nil {
				return nil, err
			}
			out[k] = r
		}
		return out, nil
	}
	return v, nil
}

func (sc *scenario) step(st step) []string {
	switch st.kind {
	case "parallel":
		return nil
	case "file":
		p, err := sc.path(st.path)
		if err != nil {
			return []string{err.Error()}
		}
		if err := os.MkdirAll(filepath.Dir(p), 0o755); err != nil {
			return []string{err.Error()}
		}
		if err := os.WriteFile(p, []byte(st.data), 0o644); err != nil {
			return []string{err.Error()}
		}
		return nil
	case "read":
		return sc.read(st)
	case "run", "call":
		if st.k > 0 {
			return sc.parallel(st)
		}
		got, errs := sc.invoke(st)
		if len(errs) > 0 {
			return errs
		}
		env := sc.snapshot()
		out := check(st.expects[0], got, env)
		if len(out) == 0 {
			sc.commit(env)
		}
		return out
	}
	return []string{"unknown step kind " + st.kind}
}

func (sc *scenario) snapshot() map[string]string {
	sc.mu.Lock()
	defer sc.mu.Unlock()
	env := map[string]string{}
	for k, v := range sc.env {
		env[k] = v
	}
	return env
}

func (sc *scenario) commit(env map[string]string) {
	sc.mu.Lock()
	defer sc.mu.Unlock()
	for k, v := range env {
		sc.env[k] = v
	}
}

func (sc *scenario) read(st step) []string {
	p, err := sc.path(st.path)
	if err != nil {
		return []string{err.Error()}
	}
	data, err := os.ReadFile(p)
	if st.mode == "absent" {
		if err == nil {
			return []string{fmt.Sprintf("@read %s: want absent, the file exists", st.path)}
		}
		if !os.IsNotExist(err) {
			return []string{fmt.Sprintf("@read %s: %v (not an absence)", st.path, err)}
		}
		return nil
	}
	if err != nil {
		return []string{fmt.Sprintf("@read %s: %v", st.path, err)}
	}
	env := sc.snapshot()
	var out []string
	if st.mode == "text" {
		if varRx.MatchString(st.value) {
			if v, ok := env[st.value]; ok {
				if v != string(data) {
					out = append(out, fmt.Sprintf("@read %s: %q, want %s = %q", st.path, data, st.value, v))
				}
			} else {
				env[st.value] = string(data)
			}
		} else if st.value != string(data) {
			out = append(out, fmt.Sprintf("@read %s: %q, want %q", st.path, data, st.value))
		}
	} else {
		act, err := decode(data)
		if err != nil {
			return []string{fmt.Sprintf("@read %s: not JSON: %v", st.path, err)}
		}
		exp, _ := decode([]byte(st.value))
		match(exp, act, env, "file", &out)
	}
	if len(out) == 0 {
		sc.commit(env)
	}
	return out
}

// outcome — what one RUN or CALL returned: a run result or a normalized JSON value of the call.
type outcome struct {
	run  *lessonadapter.Result
	call any
}

func (sc *scenario) invoke(st step) (got outcome, errs []string) {
	defer func() {
		if r := recover(); r != nil {
			errs = []string{fmt.Sprintf("panic: %v (a crash is not a valid refusal)", r)}
		}
	}()
	if st.kind == "run" {
		args := make([]string, 0, len(st.argv))
		for _, w := range st.argv {
			if w.lit {
				args = append(args, w.text)
				continue
			}
			v, err := sc.resolve(w.text)
			if err != nil {
				return got, []string{err.Error()}
			}
			args = append(args, v)
		}
		var stdin []byte
		switch st.stdinKind {
		case "bytes":
			stdin = []byte(st.stdin)
		case "var":
			v, err := sc.resolve(st.stdin)
			if err != nil {
				return got, []string{err.Error()}
			}
			stdin = []byte(v)
		}
		r := lessonadapter.Command(sc.roots, st.proc, args, stdin)
		if r.Exit < 0 {
			return got, []string{fmt.Sprintf("exit %d is not an exit code (the command is not implemented?): %q", r.Exit, clip(r.Stderr))}
		}
		return outcome{run: &r}, nil
	}
	in, err := decode([]byte(st.input)) // numbers as json.Number: the times of the events keep their value
	if err != nil {
		return got, []string{"the CALL input: " + err.Error()}
	}
	v, err := sc.call(st.name, in)
	if err != nil {
		return got, []string{err.Error()}
	}
	return outcome{call: v}, nil
}

// call — the CALL normalization of forms/README.md: the adapter's answer as the JSON value the seams compare.
func (sc *scenario) call(name string, in any) (any, error) {
	obj, _ := in.(map[string]any)
	switch name {
	case "installer-role-unit-groups", "secrets-walk":
		raw, err := json.Marshal(in)
		if err != nil { return nil, err }
		var out json.RawMessage
		if name == "installer-role-unit-groups" {
			out, err = lessonadapter.InstallerRoleUnitGroups(sc.roots, raw)
		} else {
			out, err = lessonadapter.SecretsWalk(sc.roots, raw)
		}
		if err != nil { return nil, err }
		return decode(out)
	case "command":
		r, err := sc.resolveJSON(obj["argv"])
		if err != nil {
			return nil, err
		}
		argv, _ := r.([]any)
		if len(argv) == 0 {
			return nil, fmt.Errorf("command: argv is empty")
		}
		words := make([]string, len(argv))
		for i, a := range argv {
			s, ok := a.(string)
			if !ok {
				return nil, fmt.Errorf("command: argv[%d] is not a string", i)
			}
			words[i] = s
		}
		res := lessonadapter.Command(sc.roots, words[0], words[1:], nil)
		if res.Exit < 0 {
			return nil, fmt.Errorf("exit %d is not an exit code (the command is not implemented?): %q", res.Exit, clip(res.Stderr))
		}
		return map[string]any{"success": res.Exit == 0, "exit_code": json.Number(fmt.Sprint(res.Exit))}, nil
	case "load":
		src, _ := obj["source"].(string)
		text, _ := obj["text"].(string)
		l := lessonadapter.Load(src, []byte(text))
		if l.OK {
			return map[string]any{"verdict": "ok", "name": l.Name}, nil
		}
		return map[string]any{"verdict": "refused", "class": l.Class}, nil
	case "load-catalogue":
		list, _ := obj["manifests"].([]any)
		var ms []lessonadapter.Source
		for _, m := range list {
			mo, _ := m.(map[string]any)
			src, _ := mo["source"].(string)
			text, _ := mo["text"].(string)
			ms = append(ms, lessonadapter.Source{Source: src, Text: []byte(text)})
		}
		c := lessonadapter.LoadCatalogue(ms)
		if c.OK {
			names := make([]any, 0, len(c.Names))
			sorted := append([]string{}, c.Names...)
			sort.Strings(sorted) // the names sorted only by the test adapter (forms README)
			for _, n := range sorted {
				names = append(names, n)
			}
			return map[string]any{"verdict": "ok", "names": names}, nil
		}
		return map[string]any{"verdict": "refused", "class": c.Class}, nil
	case "rollout-poll":
		raw, err := json.Marshal(obj["input"])
		if err != nil {
			return nil, err
		}
		var events []lessonadapter.Event
		evs, _ := obj["events"].([]any)
		for i, e := range evs {
			eo, _ := e.(map[string]any)
			tn, ok1 := eo["t"].(json.Number)
			ev, ok2 := eo["event"].(string)
			if !ok1 || !ok2 {
				return nil, fmt.Errorf("rollout-poll: events[%d] is not {t, event}", i)
			}
			tf, err := tn.Float64()
			if err != nil {
				return nil, err
			}
			events = append(events, lessonadapter.Event{T: tf, Event: ev})
		}
		p := lessonadapter.RolloutPoll(raw, events)
		var res any
		if p.Result != nil {
			res = map[string]any{"code": json.Number(fmt.Sprint(p.Result.Code)), "word": p.Result.Word}
		}
		return map[string]any{"state": p.State, "result": res}, nil
	}
	return nil, fmt.Errorf("CALL %s: not a call of the forms README", name)
}

// parallel — K calls of one step at once; each <expect> or one <expect>; rest <expect>.
func (sc *scenario) parallel(st step) []string {
	outs := make([]outcome, st.k)
	errs := make([][]string, st.k)
	var wg sync.WaitGroup
	for i := 0; i < st.k; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			outs[i], errs[i] = sc.invoke(st)
		}(i)
	}
	wg.Wait()
	for i := range errs {
		if len(errs[i]) > 0 {
			return append([]string{fmt.Sprintf("call %d of %d:", i+1, st.k)}, errs[i]...)
		}
	}
	env := sc.snapshot()
	if st.each {
		for i, o := range outs {
			if e := check(st.expects[0], o, copyEnv(env)); len(e) > 0 {
				return append([]string{fmt.Sprintf("each: call %d of %d:", i+1, st.k)}, e...)
			}
		}
		return nil
	}
	ones := []int{}
	for i, o := range outs {
		if len(check(st.expects[0], o, copyEnv(env))) == 0 {
			ones = append(ones, i)
		}
	}
	for _, one := range ones {
		trial := copyEnv(env)
		check(st.expects[0], outs[one], trial)
		ok := true
		for i, o := range outs {
			if i != one && len(check(st.expects[1], o, copyEnv(trial))) > 0 {
				ok = false
				break
			}
		}
		if ok {
			sc.commit(trial)
			return nil
		}
	}
	return []string{fmt.Sprintf("one …; rest …: %d of %d calls match «one», no split with all the rest matching «rest»", len(ones), st.k)}
}

func copyEnv(env map[string]string) map[string]string {
	out := map[string]string{}
	for k, v := range env {
		out[k] = v
	}
	return out
}

// check — one outcome against one expectation; env takes new bindings.
func check(e expect, o outcome, env map[string]string) []string {
	var out []string
	if e.run != nil {
		r := o.run
		if r == nil {
			return []string{"a RUN expectation for a CALL"}
		}
		if r.Exit != e.run.exit {
			out = append(out, fmt.Sprintf("exit %d, want %d (stderr %q)", r.Exit, e.run.exit, clip(r.Stderr)))
		}
		if e.run.hasStdout {
			act, err := decode(r.Stdout)
			if err != nil {
				out = append(out, fmt.Sprintf("stdout is not JSON: %v (%q)", err, clip(r.Stdout)))
			} else {
				exp, _ := decode([]byte(e.run.stdout))
				match(exp, act, env, "stdout", &out)
			}
		}
		if e.run.stdoutText != nil && string(r.Stdout) != *e.run.stdoutText {
			out = append(out, fmt.Sprintf("stdout %q, want %q", clip(r.Stdout), *e.run.stdoutText))
		}
		if e.run.stderr != nil && !bytes.Contains(r.Stderr, []byte(*e.run.stderr)) {
			out = append(out, fmt.Sprintf("stderr %q has no %q", clip(r.Stderr), *e.run.stderr))
		}
		return out
	}
	switch e.call {
	case "@absent":
		if o.call != nil {
			out = append(out, fmt.Sprintf("want @absent, got %s", show(o.call)))
		}
		return out
	case "@exit 2":
		m, _ := o.call.(map[string]any)
		if m == nil || fmt.Sprint(m["exit_code"]) != "2" {
			out = append(out, fmt.Sprintf("want @exit 2, got %s", show(o.call)))
		}
		return out
	}
	exp, err := decode([]byte(e.call))
	if err != nil {
		return []string{"the expectation is not JSON: " + err.Error()}
	}
	b, _ := json.Marshal(o.call)
	act, _ := decode(b)
	match(exp, act, env, "result", &out)
	return out
}

// decode — JSON with numbers as json.Number (compared by value).
func decode(data []byte) (any, error) {
	dec := json.NewDecoder(bytes.NewReader(data))
	dec.UseNumber()
	var v any
	if err := dec.Decode(&v); err != nil {
		return nil, err
	}
	if dec.More() {
		return nil, fmt.Errorf("more than one JSON value")
	}
	return v, nil
}

// match — the common acceptance rules: an object by subset ({} — exactly empty; "@absent" — the field is absent),
// a list element by element, "$name" — a string binding, numbers by value, the rest equal.
func match(exp, act any, env map[string]string, path string, out *[]string) {
	if s, ok := exp.(string); ok && varRx.MatchString(s) {
		as, ok := act.(string)
		switch {
		case !ok:
			*out = append(*out, fmt.Sprintf("%s: %s must be a string, got %s", path, s, show(act)))
		case env[s] != "":
			if env[s] != as {
				*out = append(*out, fmt.Sprintf("%s: %s is %q, got %q", path, s, env[s], as))
			}
		default:
			env[s] = as
		}
		return
	}
	switch e := exp.(type) {
	case map[string]any:
		a, ok := act.(map[string]any)
		if !ok {
			*out = append(*out, fmt.Sprintf("%s: want an object, got %s", path, show(act)))
			return
		}
		if len(e) == 0 && len(a) != 0 {
			*out = append(*out, fmt.Sprintf("%s: want {} exactly, got %s", path, show(act)))
			return
		}
		keys := make([]string, 0, len(e))
		for k := range e {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		for _, k := range keys {
			v := e[k]
			av, has := a[k]
			if v == "@absent" {
				if has {
					*out = append(*out, fmt.Sprintf("%s.%s: want absent, got %s", path, k, show(av)))
				}
				continue
			}
			if !has {
				*out = append(*out, fmt.Sprintf("%s.%s: missing", path, k))
				continue
			}
			match(v, av, env, path+"."+k, out)
		}
	case []any:
		a, ok := act.([]any)
		if !ok || len(a) != len(e) {
			*out = append(*out, fmt.Sprintf("%s: want %s, got %s", path, show(exp), show(act)))
			return
		}
		for i := range e {
			match(e[i], a[i], env, fmt.Sprintf("%s[%d]", path, i), out)
		}
	case json.Number:
		an, ok := act.(json.Number)
		x, okx := new(big.Rat).SetString(string(e))
		var y *big.Rat
		oky := false
		if ok {
			y, oky = new(big.Rat).SetString(string(an))
		}
		if !ok || !okx || !oky || x.Cmp(y) != 0 {
			*out = append(*out, fmt.Sprintf("%s: want %s, got %s", path, e, show(act)))
		}
	default:
		if fmt.Sprintf("%T %v", exp, exp) != fmt.Sprintf("%T %v", act, act) {
			*out = append(*out, fmt.Sprintf("%s: want %s, got %s", path, show(exp), show(act)))
		}
	}
}

func show(v any) string {
	b, err := json.Marshal(v)
	if err != nil {
		return fmt.Sprint(v)
	}
	if len(b) > 300 {
		return string(b[:300]) + "…"
	}
	return string(b)
}

func clip(b []byte) string {
	if len(b) > 300 {
		return string(b[:300]) + "…"
	}
	return string(b)
}

// runVerdicts — the loader corpus of the chapter (testdata/verdicts.jsonl from verdicts.tsv, cases/ as base64, classes.tsv):
// each case loaded alone by Load; ok — a manifest; refused — a refusal whose message names the file, of the class of
// classes.tsv when the case is there. A panic is a mismatch.
func runVerdicts(t *testing.T, chapter string) {
	t.Helper()
	f, err := os.Open(filepath.Join("testdata", "verdicts.jsonl"))
	if err != nil {
		t.Fatal(err)
	}
	defer f.Close()
	in := bufio.NewScanner(f)
	in.Buffer(make([]byte, 1<<20), 1<<26)
	n := 0
	for in.Scan() {
		var c struct{ Case, Verdict, Class, B64 string }
		if err := json.Unmarshal(in.Bytes(), &c); err != nil {
			t.Fatal(err)
		}
		n++
		text, err := base64.StdEncoding.DecodeString(c.B64)
		if err != nil {
			t.Fatalf("testdata/verdicts.jsonl %s: %v", c.Case, err)
		}
		t.Run(c.Case, func(t *testing.T) {
			source := c.Case + ".subsystem.yaml"
			var l lessonadapter.Loaded
			func() {
				defer func() {
					if r := recover(); r != nil {
						t.Fatalf("Load(%s): panic: %v (a crash is a mismatch)", source, r)
					}
				}()
				l = lessonadapter.Load(source, text) // the file's bytes as they are (a text-layer case may not be UTF-8)
			}()
			switch {
			case c.Verdict == "ok" && !l.OK:
				t.Fatalf("Load(%s): refused %s %q, want ok", source, l.Class, l.Message)
			case c.Verdict == "refused" && l.OK:
				t.Fatalf("Load(%s): loaded %q, want refused", source, l.Name)
			case c.Verdict == "refused" && !strings.Contains(l.Message, source):
				t.Fatalf("Load(%s): the refusal %q does not name the file", source, l.Message)
			case c.Verdict == "refused" && c.Class != "" && l.Class != c.Class:
				t.Fatalf("Load(%s): class %q, want %q", source, l.Class, c.Class)
			}
		})
	}
	if err := in.Err(); err != nil {
		t.Fatal(err)
	}
	if n == 0 {
		t.Fatalf("no cases in testdata/verdicts.jsonl")
	}
}
'''


def generate(root=ROOT, out=DEFAULT_OUT):
    files, inventory = build(root)
    out = Path(out)
    for rel, text in files.items():
        (out / rel).parent.mkdir(parents=True, exist_ok=True)
        (out / rel).write_text(text, encoding="utf-8")
    mod = out / "go/go.mod"
    if not mod.exists():
        mod.write_text(f"module {GO_MODULE}\n\ngo 1.22\n", encoding="utf-8")
    if L.key == "03-worker":
        import gen_policy_machines
        for name, data in gen_policy_machines.module_files(GO_MODULE, root).items():
            (out / "go" / name).write_bytes(data)
    return out, inventory


KIT_DIRS = ("stagetests",) + (("workerpolicy",) if L.key == "03-worker" else ())
JUDGE = HERE / "test_gen_cmdtests.py"


def kit_files(module, out=DEFAULT_OUT):
    """Return [(internal directory, name, bytes, origin, source, editable)]; stale output raises GenError."""
    files, _ = build(ROOT)
    res = []
    for rel, text in sorted(files.items()):
        kept = Path(out) / rel
        if not kept.is_file() or kept.read_text(encoding="utf-8") != text:
            raise GenError(f"{kept} is stale: run tools/normgen/gen_cmdtests.py --lesson {L.key}")
        data = kept.read_bytes().replace(f'"{GO_MODULE}/'.encode(), f'"{module}/internal/'.encode())
        sub, name = rel[3:].rsplit("/", 1)
        own = sub == "lessonadapter" and name != "lessonadapter.go"
        res.append((sub, name, data, "generated", L.output_source(kept, out), own))
    return res


def provenance():
    import hashlib
    import tsv_input

    def entry(path):
        return {"path": str(Path(path).relative_to(ROOT)), "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest()}
    forms = [L.form("stages.kit.tsv"), L.form("README.md")]
    forms += sorted((L.path("acceptance")).glob("*/seams.tsv")) + sorted((L.path("acceptance")).glob("*/verdicts.tsv"))
    forms += [L.path("acceptance/seams.tsv")]           # A single-chapter lesson (P/04) has seams directly under acceptance/.
    for table in sorted(L.path("acceptance").glob("*/verdicts.tsv")):
        forms += [table.parent / "classes.tsv"] + sorted((table.parent / "cases").glob("*.subsystem.yaml"))
    handwritten = []
    if L.key == "03-worker":
        import gen_policy_machines as policies
        forms += policies.sources() + [ROOT / "Platform/common/versions/go.mod", ROOT / "Platform/common/versions/go.sum"]
        handwritten = [policies.HERE / "gen_policy_machines.py", policies.HERE / "test_gen_policy_machines.py",
                       policies.HERE / "policyrt/traces_test.go.txt", *sorted(policies.RUNTIME.glob("*.go"))]
    forms = list(dict.fromkeys(p for src in forms if Path(src).is_file() for p in
                              (tsv_input.source_files(src, root=ROOT) if src.suffix == ".tsv" else [src])))
    return {"form": [entry(f) for f in forms], "generator": entry(Path(__file__).resolve()),
            "generators": [entry(Path(__file__).resolve()), entry(Path(tsv_input.__file__))],
            "handwritten": [entry(p) for p in handwritten], "judge": entry(JUDGE)}


KIT_MD = """
## Part `stagetests`: the stage tests of the lesson (generated; the adapter is **yours**)

| Package | Import path | Origin |
|---|---|---|
| `stagetests` | `{module}/internal/stagetests` | generated from `forms/stages.kit.tsv`, `acceptance/K/seams.tsv`, `verdicts.tsv`; closed |
| `lessonadapter` | `{module}/internal/lessonadapter` | `lessonadapter.go` — the kit's types (closed); `command.go`, `load.go`, `catalogue.go`, `poll.go`, `installer_role_unit_groups.go`, `secrets_walk.go` — **yours** |

```go
func Command(r Roots, process string, argv []string, stdin []byte) Result // your command, in process (no OS process)
func Load(source string, text []byte) Loaded                            // your regular loader, one manifest alone
func LoadCatalogue(manifests []Source) Catalogue                       // load_catalogue of a complete set
func RolloutPoll(input json.RawMessage, events []Event) Poll           // your poll on virtual time (poll.go)
func InstallerRoleUnitGroups(roots Roots, input json.RawMessage) (json.RawMessage, error)
func SecretsWalk(roots Roots, input json.RawMessage) (json.RawMessage, error)
type Roots struct { Data, Run, Manifest string }  // the $data/ $run/ $manifest/ of a scenario
type Result struct { Exit int; Stdout, Stderr []byte }
type Loaded struct { OK bool; Name, Class, Message string }       // Class text|form|relations; Message names the file
type Catalogue struct { OK bool; Names []string; Class, Message string }
type Poll struct { State string; Result *PollResult }; type PollResult struct { Code int; Word string }
```

InstallerRoleUnitGroups and SecretsWalk return observations of the actual implementation seam described in
acceptance/4/README.md; errors, panics and invalid JSON fail the step.
Each function is in its own file — edit one, never delete one. The stubs answer «not implemented» (a negative exit
code is not an exit code), so every test is red until you connect your code. `Test<Stage>_<Scenario>` — a seam,
`Test<Stage>_Verdicts` — the loader corpus (a subtest per case, `testdata/verdicts.jsonl`). The installations of
`puts.tsv` are not here: they need the store of P/01 — the runner judges them (`inventory.tsv` names them).
"""



KIT_MD_PORTS = """
## Part `stagetests`: the stage tests of the lesson over CALL ports (generated; the adapter is **yours**)

| Package | Import path | Origin |
|---|---|---|
| `stagetests` | `{module}/internal/stagetests` | generated from `forms/stages.kit.tsv` and the seams `acceptance/…/seams.tsv`; closed |
| `lessonadapter` | `{module}/internal/lessonadapter` | `lessonadapter.go` — closed; one file per CALL port of `forms/README.md` «Seams» — **yours** |

```go
func WorkerCapture(input json.RawMessage) (json.RawMessage, error) // one function per port: <port> in CamelCase
```

Each port takes the one JSON value of `CALL <port> <JSON>` and returns the JSON value the seam compares (an object
by subset, `{}` exactly empty, `"@absent"` — no field, `"$name"` — a binding within the scenario, numbers by value).
Start a fresh real implementation per scenario, invoke it and record its effects; never answer from the expected
output. An error or a panic is a failed step, never a refusal. The stubs answer «not implemented»: every test is red
until you connect a port. `Test<Stage>_<Scenario>` — one per seam scenario of the stage plan (`inventory.tsv`).
"""
if read_ports():
    KIT_MD = KIT_MD_PORTS

def main(argv):
    out = Path(argv[1]) if len(argv) > 1 else DEFAULT_OUT
    try:
        _, inventory = generate(ROOT, out)
    except (GenError, gate.GateError) as exc:
        print(f"gen_cmdtests: {exc}", file=sys.stderr)
        return 1
    tr = sum(1 for r in inventory if r[3] == "translated")
    print(f"gen_cmdtests: {L.code} translated {tr}, excluded {len(inventory) - tr}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
