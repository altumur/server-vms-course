"""Генератор № 6 ADR-0125, доп. (3): тесты этапов из сценариев приёмки — часть `tests` пакета Б.

Источники: `Platform/01-store/acceptance/<глава>/scenarios.tsv`, `forms/stages.tsv`; выбор сценариев этапа — явный,
декларацией STAGE_SCENARIOS ниже (параметр генератора, пока у формы этапов нет колонки; ревью доп. (3), п. (б)).

Правила (ревью доп. (3), пп. (а), (в), (г)):
- сценарий переводится префиксом (доп. (4) п. 2): шаги до первого, который процесс не исполняет (директива стенда,
  сокет роли без личности, сырой HTTP, форма ожидания вне движка); остаток исключён целиком с причиной; движок главы
  перенесён (глава 1.1 — `runner/run.py` раннера);
- опись `stagetests/inventory.tsv` — по id шага `<глава>/<сценарий>/<шаг>`: переведён или исключён (причина); у объявленного
  этапа без переведённых сценариев — отказ генератора (пустая проекция);
- сценарий — тест `Test<Этап>_<Сценарий>`, шаги — последовательные подтесты; свежее ядро на сценарий —
  `coreadapter.Open(Config)`, `Core.Handle(Call, method, target, header, body)`, `Core.Close()` (доп. (4) п. 3);
  `Call` — личность вызова отдельно от заголовков; `coreadapter.Wrap` — рамка и маршруты пакета (`apidoor.Dispatch`)
  поверх `apidoor.Handler` модели (п. 4), модель пишет `Handler` и `Open` (`open.go` — её файл);
- связывание `$имя`, ASSERT, сравнение тела — как у движка раннера главы (код `engine_test.go`).

Выход (`out/p01-1/go/`): `coreadapter/coreadapter.go` (пакет: Config, Call, Core, Wrap), `coreadapter/open.go`
(заглушка `Open` — своё у реализации), `stagetests/engine_test.go`,
`stagetests/scenarios_<глава>_test.go`, `stagetests/<этап>_test.go`, `stagetests/doc.go`; `stagetests/inventory.tsv` — опись.
"""
import hashlib
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent

ENGINES = {"1.1": "runner/run.py"}          # главы с перенесённым движком
# Явный выбор сценариев этапа (ревью доп. (3) (б)): этап → (глава, [сценарии]). Этап с gate accept:1.1:01-absent
# берёт свой сценарий; `http` (accept:1.1:*) — названные сценарии главы 1.1 (все 40, перечислены явно).
STAGE_SCENARIOS = {
    "launch": ("1.1", ["01-absent"]),
    "http": ("1.1", ["01-absent", "02-create-once", "03-read-back", "04-stale-cas", "05-unconditional", "06-delete",
                     "07-no-reuse", "08-list", "09-guard", "10-guard-absent", "11-guard-before-cas", "12-id",
                     "13-bad-key", "14-bad-forms", "15-too-large", "16-items", "17-routes", "18-no-echo",
                     "19-key-too-long", "20-guard-forms", "21-rights", "22-body-edge", "23-extra-cmd", "24-key-forms",
                     "25-query-form", "26-json-strict", "27-method-route", "28-admission", "29-key-1025",
                     "30-id-fingerprint", "31-delete-cas-id-order", "32-validation-order", "33-batch-all-or-nothing",
                     "34-batch-create-edit-delete", "35-batch-guards", "36-batch-repeat", "37-batch-times",
                     "38-batch-form", "39-batch-weight", "40-batch-rights"]),
}
METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD")
VAR = re.compile(r"\$[A-Za-z0-9_]+")
BIG = re.compile(r"@big\((\d+)\)")


class GenError(Exception):
    pass


def camel_name(name):
    """02-create-once → 02CreateOnce; rights_eval → RightsEval."""
    return "".join(p[:1].upper() + p[1:] for p in re.split(r"[-_]", name) if p)


def read_scenarios(root, chapter):
    rel = f"Platform/01-store/acceptance/{chapter.split('.')[1]}/scenarios.tsv"
    data = (Path(root) / rel).read_bytes()
    out = {}
    for no, line in enumerate(data.decode("utf-8").split("\n"), 1):
        line = line.rstrip("\r")
        if not line.strip() or line.startswith("#"):
            continue
        cells = line.split("\t")
        if cells[:3] == ["scenario", "step", "request"]:
            continue
        if len(cells) < 3:
            raise GenError(f"{rel}:{no}: want scenario, step, request, expect")
        out.setdefault(cells[0], []).append((cells[1], cells[2], cells[3] if len(cells) > 3 else "", no))
    return out, rel, hashlib.sha256(data).hexdigest()


def step_blocker(chapter, step):
    """Почему шаг не исполняется в процессе (None — исполняется движком главы)."""
    st, req, exp, _ = step
    if chapter not in ENGINES:
        return f"the engine of chapter {chapter} is not ported yet"
    if req.startswith("ASSERT "):
        return None
    method = req.split(" ", 1)[0]
    if method not in METHODS:
        return f"step {st}: the stand directive or door {method!r}"
    rest = BIG.sub("", req)
    if "@" in rest:
        return f"step {st}: a request directive outside @big ({rest[rest.index('@'):][:20]!r})"
    if "@" in exp or exp[4:5] == "~":
        return f"step {st}: an expectation form the engine does not port ({exp[:30]!r})"
    return None


def prefix(chapter, steps):
    """→ (переведённые шаги, причина остатка | None): перевод до первого неисполнимого шага (доп. (4) п. 2)."""
    for k, step in enumerate(steps):
        why = step_blocker(chapter, step)
        if why:
            return steps[:k], why
    return steps, None


def go_raw(s):
    """Строковый литерал Go: печатное — как есть, прочее (управляющие, BOM, U+2028…) — \\uXXXX."""
    out = ['"']
    for ch in s:
        o = ord(ch)
        if ch in '"\\':
            out.append("\\" + ch)
        elif o < 0x20 or o == 0x7F or o == 0xFEFF or not ch.isprintable() and ch != " ":
            out.append(f"\\u{o:04x}" if o <= 0xFFFF else f"\\U{o:08x}")
        else:
            out.append(ch)
    return "".join(out) + '"'


def build(root=ROOT, stages_text=None, declaration=STAGE_SCENARIOS):
    """→ ({путь в out: текст}, строки описи)."""
    root = Path(root)
    stages_rel = "Platform/01-store/forms/stages.tsv"
    text = stages_text if stages_text is not None else (root / stages_rel).read_text(encoding="utf-8")
    rows = [line.split("\t") for line in text.split("\n") if line and not line.startswith("#")]
    head = rows[0]
    stages = {dict(zip(head, r))["stage"]: dict(zip(head, r)) for r in rows[1:]}
    chapters, files, inventory, tests = {}, {}, [], {}
    for stage, (chapter, names) in declaration.items():
        if stage not in stages:
            raise GenError(f"{stages_rel}: no stage {stage!r} of the declaration")
        gate = stages[stage]["gate"]
        t = re.fullmatch(r"tests:([a-z_]+):([0-9.]+):(\*|[a-z0-9,-]+)", gate)     # доп. (4) п. 1: форма wins
        if t:
            if t[1] != stage:
                raise GenError(f"stage {stage}: gate {gate!r} names another stage")
            chapter = t[2]
            names = names if t[3] == "*" else t[3].split(",")
        m = re.fullmatch(r"accept:([0-9.]+):(\*|[a-z0-9,-]+)", gate)
        if not t and not (m and m[1] == chapter) and gate != f"tests:{stage}":
            raise GenError(f"stage {stage}: gate {gate!r} is neither tests:{stage}:{chapter}:…, accept:{chapter}:… "
                           f"nor tests:{stage}")
        if m and m[2] != "*" and set(names) - set(m[2].split(",")):
            raise GenError(f"stage {stage}: {sorted(set(names) - set(m[2].split(',')))} are not of its gate {gate}")
        if chapter not in chapters:
            chapters[chapter] = read_scenarios(root, chapter)
        scenarios, rel, _ = chapters[chapter]
        if len(set(names)) != len(names):
            raise GenError(f"stage {stage}: a scenario repeats in the declaration")
        translated = []
        for name in names:
            if name not in scenarios:
                raise GenError(f"stage {stage}: no scenario {name!r} in {rel}")
            done, reason = prefix(chapter, scenarios[name])
            test = f"Test{camel_name(stage)}_{camel_name(name)}"
            for k, (step, _, _, _) in enumerate(scenarios[name]):
                inventory.append((f"{chapter}/{name}/{step}", stage, test if k < len(done) else "-",
                                  "translated" if k < len(done) else "excluded",
                                  "-" if k < len(done) else f"the rest of the scenario from {reason}"))
            if done:
                translated.append((name, len(done)))
        if not translated:
            raise GenError(f"stage {stage}: the projection is empty (no scenario of {names} runs in process)")
        tests[stage] = (chapter, translated)
    for chapter, (scenarios, rel, sha) in chapters.items():
        used = {}
        for ch, ns in tests.values():
            for n, cnt in ns:
                if ch == chapter:
                    used[n] = max(used.get(n, 0), cnt)
        body = [f"// Code generated by tools/normgen/gen_stagetests.py from {rel} (sha256 {sha}); DO NOT EDIT.", "",
                "package stagetests", "",
                f"// Scenarios of chapter {chapter}: the steps as the table writes them (request, expect, line).",
                f"var chapter{chapter.replace('.', '_')} = map[string][]step{{"]
        for name in sorted(used):
            body.append(f"\t{go_raw(name)}: {{")
            for st, req, exp, no in scenarios[name][:used[name]]:
                body.append(f"\t\t{{{go_raw(st)}, {go_raw(req)}, {go_raw(exp)}, {no}}},")
            body.append("\t},")
        body.append("}")
        files[f"go/stagetests/scenarios_{chapter.replace('.', '_')}_test.go"] = "\n".join(body) + "\n"
    for stage, (chapter, names) in tests.items():
        body = [f"// Code generated by tools/normgen/gen_stagetests.py (stage {stage} of forms/stages.tsv); DO NOT EDIT.",
                "", "package stagetests", "", 'import "testing"', ""]
        for name, cnt in names:
            body += [f"// Test{camel_name(stage)}_{camel_name(name)} — chapter {chapter}, scenario {name}: steps 1…{cnt} of the projection.",
                     f"func Test{camel_name(stage)}_{camel_name(name)}(t *testing.T) {{",
                     f"\trunScenario(t, {go_raw(chapter)}, {go_raw(name)}, chapter{chapter.replace('.', '_')}[{go_raw(name)}][:{cnt}])",
                     "}", ""]
        files[f"go/stagetests/{stage}_test.go"] = "\n".join(body)
    files["go/stagetests/engine_test.go"] = ENGINE_GO
    files["go/stagetests/doc.go"] = DOC_GO
    files["go/coreadapter/coreadapter.go"] = ADAPTER_GO
    files["go/coreadapter/open.go"] = OPEN_GO
    inv = ["# Inventory of the stage tests (ADR-0125 addendum (3)): every step of a declared scenario — translated or "
           "excluded (the reason). Generated by tools/normgen/gen_stagetests.py; the kit's test set is this list.",
           "step\tstage\ttest\tstatus\treason"]
    inv += ["\t".join(r) for r in inventory]
    files["go/stagetests/inventory.tsv"] = "\n".join(inv) + "\n"
    return files, inventory


ADAPTER_GO = '''// Code generated by tools/normgen/gen_stagetests.py (ADR-0125 addenda (3), (4)); DO NOT EDIT.

// Package coreadapter — the adapter of the stage tests (stagetests) to the store core of an implementation: the kit's
// frame and routes (apidoor.Route, apidoor.Dispatch, apidoor.Encode) over your apidoor.Handler. You write Open (open.go,
// your file) and the Handler; this file is the kit's.
package coreadapter

import (
	"encoding/json"

	"normgen/p01-1/apidoor"
)

// Config — the stand of one scenario (the runner's stand of P/01.1): the limits and the rights file.
type Config struct {
	BodyLimit  int64  // the read limit of the HTTP body (1048576 on the stand)
	RowCeiling int64  // the row ceiling (524288 on the stand)
	Rights     []byte // the rights file (P/01.2 Н1.2): the role acc with read, write, delete on acc/*
}

// Call — the identity of a call, apart from the HTTP headers: Sock is the socket ("acc" — the role socket of the
// stand, "admin" — admin.sock); a role header of the request stays a header (a forged one is the scenario's check).
type Call struct {
	Sock string
}

// Request — the context your Handler gets: the identity and the headers of the request.
type Request struct {
	Call   Call
	Header map[string]string
}

// Core — one fresh store instance for one scenario.
type Core interface {
	Handle(call Call, method, target string, header map[string]string, body []byte) (code int, respHeader map[string]string, respBody []byte)
	Close() error
}

// Wrap — the Core of the kit over your Handler: the body limit (413 before the route, Н2.1 order «frame → route →
// identity → body»), apidoor.Route, apidoor.Dispatch to h, apidoor.Encode of the answer. closeFn may be nil.
func Wrap(cfg Config, h apidoor.Handler[*Request], closeFn func() error) Core {
	return &core{cfg: cfg, h: h, closeFn: closeFn}
}

type core struct {
	cfg     Config
	h       apidoor.Handler[*Request]
	closeFn func() error
}

func (c *core) Handle(call Call, method, target string, header map[string]string, body []byte) (int, map[string]string, []byte) {
	if body != nil && int64(len(body)) > c.cfg.BodyLimit {
		b, _ := json.Marshal(map[string]any{"kind": "toolarge", "error": "the body is larger than the limit",
			"limit": c.cfg.BodyLimit, "size": len(body)})
		return 413, map[string]string{"Content-Type": "application/json", "Connection": "close"}, b
	}
	op, query, refusal := apidoor.Route(method, target)
	if refusal != nil {
		return refusal.Code, headers(refusal.Header), refusal.Body
	}
	resp, err := apidoor.Encode(op, apidoor.Dispatch[*Request](c.h, &Request{Call: call, Header: header}, op, query, body))
	if err != nil {
		b, _ := json.Marshal(map[string]any{"kind": "unavailable", "error": "coreadapter: " + err.Error()})
		return 500, map[string]string{"Content-Type": "application/json"}, b
	}
	return resp.Code, headers(resp.Header), resp.Body
}

func (c *core) Close() error {
	if c.closeFn == nil {
		return nil
	}
	return c.closeFn()
}

func headers(h [][2]string) map[string]string {
	out := map[string]string{}
	for _, kv := range h {
		out[kv[0]] = kv[1]
	}
	return out
}
'''

OPEN_GO = '''// Package coreadapter: Open — yours (ADR-0125 addendum (4)). The kit puts this stub once and never overwrites it.
package coreadapter

import "errors"

// Open — a fresh core for one scenario: build your store by cfg and return Wrap(cfg, yourHandler, yourClose).
// yourHandler implements apidoor.Handler[*Request] (Get, List, Write, Rights, Status, Join, Leave, Metrics,
// QueryRefused) over your core of Н3; the kit's frame and routes are in Wrap.
func Open(cfg Config) (Core, error) {
	return nil, errors.New("coreadapter: not implemented")
}
'''

DOC_GO = '''// Package stagetests — Go tests of the stages of forms/stages.tsv from the acceptance scenarios (ADR-0125 addendum (3)),
// generated by tools/normgen/gen_stagetests.py: a scenario is a test Test<Stage>_<Scenario>, its steps are subtests in
// order, each request goes to coreadapter.New() of a fresh core. Only the scenarios that run whole in process are here;
// the inventory inventory.tsv names every step, translated or excluded (the runner judges the excluded ones).
package stagetests
'''

ENGINE_GO = r'''// Code generated by tools/normgen/gen_stagetests.py: the engine of chapter 1.1 of the runner (runner/run.py,
// http_expect.check_json) in Go; DO NOT EDIT.

package stagetests

import (
	"bytes"
	"encoding/json"
	"fmt"
	"math/big"
	"regexp"
	"strconv"
	"strings"
	"testing"
	"unicode/utf8"

	"normgen/p01-1/coreadapter"
)

// standRights — the rights file of the runner's stand of P/01.1 (harness.Instance): the role acc on acc/*.
const standRights = `{"roles": {"acc": {"group": "acc", "read": ["acc/*"], "write": ["acc/*"], "delete": ["acc/*"]}}}`

type step struct {
	step, request, expect string
	line                  int
}

var (
	varRx    = regexp.MustCompile(`\$[A-Za-z0-9_]+`)
	bigRx    = regexp.MustCompile(`@big\((\d+)\)`)
	statusRx = regexp.MustCompile(`^[1-5](?:[0-9]{2}|xx)$`)
	termRx   = `(\$[A-Za-z0-9_]+(?:\s*-\s*\$[A-Za-z0-9_]+)?|-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)`
	assertRx = regexp.MustCompile(`^ASSERT\s+` + termRx + `\s*(==|!=|<=|>=|<|>)\s*` + termRx + `\s*$`)
)

// runScenario — one scenario on a fresh core: the steps in order as subtests; a failed step does not bind and the
// next steps go on (as the runner does).
func runScenario(t *testing.T, chapter, name string, steps []step) {
	core, err := coreadapter.Open(coreadapter.Config{BodyLimit: 1048576, RowCeiling: 524288, Rights: []byte(standRights)})
	if err != nil || core == nil {
		t.Fatalf("coreadapter.Open: %v", err)
	}
	defer core.Close()
	env := map[string]any{}
	if strings.HasPrefix(name, "21-") { // runner/run.py: the preparation of sc. 21 through admin.sock
		code, _, body := core.Handle(coreadapter.Call{Sock: "admin"}, "POST", "/v1/write", map[string]string{"Content-Type": "application/json"},
			[]byte(`{"op":"put","key":"other/21-rights/c9","items":{"n":"1"}}`))
		if code != 200 {
			t.Errorf("preparation via admin.sock: %d %q", code, clip(body))
		}
	}
	for _, st := range steps {
		st := st
		t.Run(st.step, func(t *testing.T) {
			for _, why := range runStep(core, name, st, env) {
				t.Errorf("%s step %s (scenarios.tsv:%d): %s", name, st.step, st.line, why)
			}
		})
	}
}

func runStep(core coreadapter.Core, name string, st step, env map[string]any) []string {
	if strings.HasPrefix(st.request, "ASSERT ") {
		return checkAssert(st.request, env)
	}
	req, err := substitute(st.request, env)
	if err != "" {
		return []string{err}
	}
	method, rest, _ := strings.Cut(req, " ")
	target, text, hasBody := strings.Cut(rest, " ")
	var body []byte
	if hasBody {
		body = []byte(text)
	} else if method != "GET" {
		body = []byte{}
	}
	header := map[string]string{}
	if body != nil {
		header["Content-Type"] = "application/json"
	}
	code, _, raw := core.Handle(coreadapter.Call{Sock: "acc"}, method, target, header, body)
	act, perr := decode(raw)
	if perr != nil {
		return []string{fmt.Sprintf("body is not JSON (%v): %q", perr, clip(raw))}
	}
	var out []string
	if code != 200 {
		if o, ok := act.(*object); !ok || !isStr(o.get("error")) {
			out = append(out, "body.error: a fault must carry an error string (Н2)")
		}
	}
	if strings.HasPrefix(name, "22-") && st.step == "1" { // runner/run.py: the optional size of sc. 22 step 1
		if o, ok := act.(*object); ok && o.has("size") {
			size := o.get("size")
			o.del("size")
			if n, ok := size.(*number); !ok || n.isFloat || n.text != strconv.Itoa(len(body)) {
				out = append(out, fmt.Sprintf("body.size: want integer %d (sent body size) or absent, got %s", len(body), show(size)))
			}
		}
	}
	trial := copyEnv(env)
	out = append(out, checkResponse(code, act, st.expect, trial, method, target)...)
	if len(out) == 0 {
		for k, v := range trial {
			env[k] = v
		}
	}
	return out
}

func substitute(text string, env map[string]any) (string, string) {
	missing := ""
	text = varRx.ReplaceAllStringFunc(text, func(n string) string {
		v, ok := env[n]
		if !ok {
			if missing == "" {
				missing = n
			}
			return n
		}
		return v.(string)
	})
	if missing != "" {
		return "", "request uses unbound " + missing
	}
	return bigRx.ReplaceAllStringFunc(text, func(m string) string {
		n, _ := strconv.Atoi(bigRx.FindStringSubmatch(m)[1])
		return strings.Repeat("x", n)
	}), ""
}

func checkResponse(code int, act any, expect string, env map[string]any, method, target string) []string {
	// http_expect.choose: the first fully matching branch commits (one branch without @oneof).
	branches := []string{expect}
	var failures [][]string
	for _, br := range branches {
		trial := copyEnv(env)
		wanted, body, _ := strings.Cut(br, " ")
		body = strings.TrimSpace(body)
		var errs []string
		if !statusRx.MatchString(wanted) {
			return []string{"invalid expected HTTP status: " + wanted}
		}
		if strings.HasSuffix(wanted, "xx") {
			if code/100 != int(wanted[0]-'0') {
				errs = append(errs, fmt.Sprintf("status: want %s, got %d", wanted, code))
			}
		} else if strconv.Itoa(code) != wanted {
			errs = append(errs, fmt.Sprintf("status: want %s, got %d", wanted, code))
		}
		if body != "" {
			exp, err := decode([]byte(body))
			if err != nil {
				return []string{"the expectation is not JSON: " + err.Error()}
			}
			match(exp, act, trial, "body", &errs)
			if method == "GET" && strings.SplitN(target, "?", 2)[0] == "/v1/list" && code == 200 {
				eo, ok1 := exp.(*object)
				ao, ok2 := act.(*object)
				if ok1 && ok2 {
					ek, ok3 := eo.get("keys").(*object)
					ak, ok4 := ao.get("keys").(*object)
					if ok3 && ok4 && strings.Join(ek.keys, "\x00") != strings.Join(ak.keys, "\x00") {
						errs = append(errs, fmt.Sprintf("keys order: want %q, got %q", ek.keys, ak.keys))
					}
				}
			}
		}
		if len(errs) == 0 {
			for k, v := range trial {
				env[k] = v
			}
			return nil
		}
		failures = append(failures, errs)
	}
	return failures[0]
}

func match(exp, act any, env map[string]any, path string, out *[]string) {
	if s, ok := exp.(string); ok && varRx.FindString(s) == s && s != "" {
		as, ok := act.(string)
		switch {
		case !ok:
			*out = append(*out, fmt.Sprintf("%s: %s must be a JSON string, got %s", path, s, show(act)))
		case env[s] != nil:
			if env[s].(string) != as {
				*out = append(*out, fmt.Sprintf("%s: %s is %q, got %q", path, s, env[s], as))
			}
		default:
			env[s] = as
		}
		return
	}
	if eo, ok := exp.(*object); ok {
		ao, ok := act.(*object)
		if !ok {
			*out = append(*out, fmt.Sprintf("%s: want object, got %s", path, show(act)))
			return
		}
		for _, k := range eo.keys {
			v := eo.vals[k]
			if !ao.has(k) {
				*out = append(*out, fmt.Sprintf("%s.%s: missing", path, k))
			} else if vs, isS := v.(string); k == "error" && path == "body" && isS && strings.HasPrefix(vs, "!contains ") {
				needle := vs[len("!contains "):]
				if as, ok := ao.get(k).(string); !ok || strings.Contains(as, needle) {
					*out = append(*out, fmt.Sprintf("body.error must not contain %q, got %s", needle, show(ao.get(k))))
				}
			} else {
				match(v, ao.get(k), env, path+"."+k, out)
			}
		}
		for _, k := range ao.keys {
			if !eo.has(k) && !(path == "body" && k == "error") {
				*out = append(*out, fmt.Sprintf("%s.%s: unexpected field %s", path, k, show(ao.get(k))))
			}
		}
		return
	}
	if el, ok := exp.([]any); ok {
		al, ok := act.([]any)
		if !ok || len(al) != len(el) {
			*out = append(*out, fmt.Sprintf("%s: want %s, got %s", path, show(exp), show(act)))
			return
		}
		for i := range el {
			match(el[i], al[i], env, fmt.Sprintf("%s[%d]", path, i), out)
		}
		return
	}
	if !same(exp, act) {
		*out = append(*out, fmt.Sprintf("%s: want %s, got %s", path, show(exp), show(act)))
	}
}

func checkAssert(req string, env map[string]any) []string {
	toks := strings.Fields(req)[1:]
	if len(toks) > 3 && toks[1] == "!=" && allVars(append([]string{toks[0]}, toks[2:]...)) {
		names := append([]string{toks[0]}, toks[2:]...)
		var missing []string
		for _, n := range names {
			if _, ok := env[n]; !ok {
				missing = append(missing, n)
			}
		}
		if len(missing) > 0 {
			return []string{"ASSERT: unbound " + strings.Join(missing, " ")}
		}
		var out []string
		for i, a := range names {
			for _, b := range names[i+1:] {
				if same(env[a], env[b]) {
					out = append(out, fmt.Sprintf("ASSERT: %s == %s (%v)", a, b, env[a]))
				}
			}
		}
		return out
	}
	m := assertRx.FindStringSubmatch(req)
	if m == nil {
		return []string{"unknown ASSERT expression: " + req}
	}
	term := func(t string) (any, string) {
		if strings.HasPrefix(t, "$") {
			names := strings.Split(t, "-")
			for i := range names {
				names[i] = strings.TrimSpace(names[i])
				if _, ok := env[names[i]]; !ok {
					return nil, "ASSERT: unbound " + names[i]
				}
			}
			if len(names) == 2 {
				return nil, fmt.Sprintf("ASSERT: %s - %s: not numbers", names[0], names[1]) // env holds strings only
			}
			return env[names[0]], ""
		}
		v, err := decode([]byte(t))
		if err != nil {
			return nil, "ASSERT: " + err.Error()
		}
		return v, ""
	}
	x, e1 := term(m[1])
	if e1 != "" {
		return []string{e1}
	}
	y, e2 := term(m[3])
	if e2 != "" {
		return []string{e2}
	}
	op := m[2]
	xn, xok := x.(*number)
	yn, yok := y.(*number)
	var ok bool
	switch {
	case xok && yok:
		c := xn.cmp(yn)
		ok = map[string]bool{"==": c == 0, "!=": c != 0, "<": c < 0, "<=": c <= 0, ">": c > 0, ">=": c >= 0}[op]
	case op == "==":
		ok = same(x, y)
	case op == "!=":
		ok = !same(x, y)
	default:
		return []string{fmt.Sprintf("ASSERT %s: order is only for numbers (%s, %s)", op, show(x), show(y))}
	}
	if !ok {
		return []string{fmt.Sprintf("ASSERT %s %s %s: %s, %s", m[1], op, m[3], show(x), show(y))}
	}
	return nil
}

func allVars(ts []string) bool {
	for _, t := range ts {
		if varRx.FindString(t) != t {
			return false
		}
	}
	return true
}

// ---------------------------------------------------------------- JSON as the runner reads it (harness.loads_ordered)

type object struct {
	keys []string
	vals map[string]any
}

func (o *object) has(k string) bool { _, ok := o.vals[k]; return ok }
func (o *object) get(k string) any  { return o.vals[k] }
func (o *object) del(k string) {
	delete(o.vals, k)
	for i, x := range o.keys {
		if x == k {
			o.keys = append(o.keys[:i], o.keys[i+1:]...)
			break
		}
	}
}

// number — a JSON number by its writing: an integer (no . e E) or a float (Python int ≠ float: 1 ≠ 1.0).
type number struct {
	text    string
	isFloat bool
}

func (n *number) rat() *big.Rat { r, _ := new(big.Rat).SetString(n.text); return r }
func (n *number) cmp(m *number) int {
	if n.isFloat || m.isFloat {
		a, _ := strconv.ParseFloat(n.text, 64)
		b, _ := strconv.ParseFloat(m.text, 64)
		switch {
		case a < b:
			return -1
		case a > b:
			return 1
		}
		return 0
	}
	return n.rat().Cmp(m.rat())
}

type nullT struct{}

var null = nullT{}

func decode(raw []byte) (any, error) {
	if !utf8.Valid(raw) {
		return nil, fmt.Errorf("not UTF-8")
	}
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	v, err := value(dec)
	if err != nil {
		return nil, err
	}
	if dec.More() {
		return nil, fmt.Errorf("extra data after the value")
	}
	if _, err := dec.Token(); err == nil {
		return nil, fmt.Errorf("extra data after the value")
	}
	return v, nil
}

func value(dec *json.Decoder) (any, error) {
	tok, err := dec.Token()
	if err != nil {
		return nil, err
	}
	switch x := tok.(type) {
	case json.Delim:
		switch x {
		case '{':
			o := &object{vals: map[string]any{}}
			for dec.More() {
				kt, err := dec.Token()
				if err != nil {
					return nil, err
				}
				k := kt.(string)
				if o.has(k) {
					return nil, fmt.Errorf("duplicate name %q in response", k)
				}
				v, err := value(dec)
				if err != nil {
					return nil, err
				}
				o.keys = append(o.keys, k)
				o.vals[k] = v
			}
			_, err := dec.Token()
			return o, err
		case '[':
			l := []any{}
			for dec.More() {
				v, err := value(dec)
				if err != nil {
					return nil, err
				}
				l = append(l, v)
			}
			_, err := dec.Token()
			return l, err
		}
	case json.Number:
		s := string(x)
		return &number{text: s, isFloat: strings.ContainsAny(s, ".eE")}, nil
	case string, bool:
		return x, nil
	case nil:
		return null, nil
	}
	return nil, fmt.Errorf("unexpected token %v", tok)
}

// same — the runner's run.same: types differ → not equal (true ≠ 1, 1 ≠ 1.0); objects without order.
func same(a, b any) bool {
	switch x := a.(type) {
	case *object:
		y, ok := b.(*object)
		if !ok || len(x.keys) != len(y.keys) {
			return false
		}
		for _, k := range x.keys {
			if !y.has(k) || !same(x.vals[k], y.vals[k]) {
				return false
			}
		}
		return true
	case []any:
		y, ok := b.([]any)
		if !ok || len(x) != len(y) {
			return false
		}
		for i := range x {
			if !same(x[i], y[i]) {
				return false
			}
		}
		return true
	case *number:
		y, ok := b.(*number)
		return ok && x.isFloat == y.isFloat && x.cmp(y) == 0
	default:
		return a == b
	}
}

func isStr(v any) bool { _, ok := v.(string); return ok }

func bound(env map[string]any, name string) bool { _, ok := env[name]; return ok }

func copyEnv(env map[string]any) map[string]any {
	out := make(map[string]any, len(env))
	for k, v := range env {
		out[k] = v
	}
	return out
}

func show(v any) string {
	var b strings.Builder
	var w func(any)
	w = func(v any) {
		switch x := v.(type) {
		case *object:
			b.WriteByte('{')
			for i, k := range x.keys {
				if i > 0 {
					b.WriteString(", ")
				}
				kb, _ := json.Marshal(k)
				b.Write(kb)
				b.WriteString(": ")
				w(x.vals[k])
			}
			b.WriteByte('}')
		case []any:
			b.WriteByte('[')
			for i, e := range x {
				if i > 0 {
					b.WriteString(", ")
				}
				w(e)
			}
			b.WriteByte(']')
		case *number:
			b.WriteString(x.text)
		case nullT:
			b.WriteString("null")
		default:
			jb, _ := json.Marshal(x)
			b.Write(jb)
		}
	}
	w(v)
	s := b.String()
	if len(s) > 200 {
		s = s[:200] + "…"
	}
	return s
}

func clip(b []byte) string {
	if len(b) > 200 {
		return string(b[:200]) + "…"
	}
	return string(b)
}
'''
