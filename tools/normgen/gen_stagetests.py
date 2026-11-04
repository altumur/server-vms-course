"""Генератор № 6 ADR-0125, доп. (3), (4); ADR-0126 доп. (7): тесты этапов из сценариев — часть `stagetests` пакета Б.

Источники: `Platform/01-store/acceptance/<глава>/scenarios.tsv` (раннер и тесты пакета) и `seams.tsv` (швы процесса —
только тесты пакета), `forms/stages.tsv`, `forms/refusals.tsv`. Проза не читается.

Выбор сценариев (ADR-0126 доп. (7) пп. 2, 3): `gate` — список через `;`, элемент `tests:<глава>:<сценарии|*>[:seams]`
(`:seams` — файл швов); имя этапа — строка формы. Пока форма не поправлена дельтой — переходное объявление
TRANSITIONAL (параметр генератора), только для этапа без элементов `tests:` в форме.

Правила:
- сценарий переводится префиксом (ADR-0125 доп. (4) п. 2): до первого шага, который процесс не исполняет (директива
  стенда, форма ожидания вне движка, отказ позднего этапа — ADR-0126 доп. (7) п. 6); остаток исключён с причиной;
- отказ позднего этапа: ожидание `<код> {"kind": …}`, у которого все строки `refusals.tsv` главы сценария с этим кодом и
  kind нормированы главой урока, впервые названной в `norms` этапа с большим n (403 по файлу прав — P/01.2);
- швы (`seams.tsv`, ADR-0126 доп. (7) п. 1, грамматика «Спецификации»): `@clock +N | -N` (секунды, накопительно; часы
  теста от T0 = 2000000000 с), `@reopen` (Close + Open с тем же DataDir и часами), `@parallel K` (K ≥ 2; следующий
  шаг K раз одновременно; его ожидание `each <ож>` | `one <ож>; rest <ож>`, новые $имена — только в `one`);
- опись `stagetests/inventory.tsv` — по id шага `<глава>/<файл>/<сценарий>/<шаг>`: переведён | исключён (причина),
  колонка `race` (тест с `@parallel` — судья гоняет его с -race); пустая проекция этапа — отказ генератора;
- сценарий — тест `Test<Этап>_<Сценарий>`, шаги — последовательные подтесты; сравнение — как у раннера (`runner/run.py`).

Выход (`out/p01-1/go/`): `coreadapter/coreadapter.go` (пакет: Config, Call, Core, Handle, NotInStage),
`coreadapter/open.go` (заглушка `Open` и `Ctx` — своё у реализации), `stagetests/*_test.go`, `stagetests/doc.go`,
`stagetests/inventory.tsv`.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate  # noqa: E402 — общий разбор gate (ревью Codex С4)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent

ENGINES = {"1.1": "runner/run.py"}          # главы с перенесённым движком
# Переходное объявление: этап → [(глава, [сценарии], seams)] — только для этапа без элементов tests: в форме.
TRANSITIONAL = {}       # форма P/01 несёт tests:<глава>:… (дельта 0125-p01-stages-seams, main 322d2cfb8)
METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD")
VAR = re.compile(r"\$[A-Za-z0-9_]+")
CLOCK = re.compile(r"@clock [+-](0|[1-9][0-9]*)")
PARALLEL = re.compile(r"@parallel ([2-9]|[1-9][0-9]+)")
ONE_REST = re.compile(r"one (.+?); rest (.+)")


class GenError(Exception):
    pass


def camel_name(name):
    """02-create-once → 02CreateOnce; rights_eval → RightsEval."""
    return "".join(p[:1].upper() + p[1:] for p in re.split(r"[-_]", name) if p)


def read_table(root, chapter, file):
    rel = f"Platform/01-store/acceptance/{chapter.split('.')[1]}/{file}"
    path = Path(root) / rel
    if not path.is_file():
        return {}, rel, None
    data = path.read_bytes()
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


def read_scenarios(root, chapter):
    """Совместимость: только scenarios.tsv."""
    return read_table(root, chapter, "scenarios.tsv")


def late_refusals(root, stages, chapter):
    """{(код, kind): n этапа, чьи нормы впервые называют главу всех строк отказа} по refusals.tsv главы."""
    path = Path(root) / "Platform/01-store/forms/refusals.tsv"
    rows = [line.split("\t") for line in path.read_text(encoding="utf-8").split("\n")
            if line and not line.startswith("#")]
    head = rows[0]
    first = {}                                   # «P/01.2» → наименьшее n этапа, в norms которого она есть
    for st in stages.values():
        for m in re.finditer(r"P/\d\d\.\d", st["norms"]):
            first[m[0]] = min(first.get(m[0], 10 ** 6), int(st["n"]))
    by = {}
    for cells in rows[1:]:
        r = dict(zip(head, cells))
        if r["chapter"] != chapter or r["surface"] != "http":
            continue
        m = re.match(r"P/\d\d\.\d", r["norm"])
        n = first.get(m[0], 0) if m else 0
        key = (int(r["code"]), r["kind"])
        by[key] = min(by.get(key, 10 ** 6), n)   # поздний — только если поздние все строки
    return by


def step_blocker(chapter, step, seams, late, stage_n):
    """Почему шаг не исполняется в процессе (None — исполняется)."""
    st, req, exp, _ = step
    if chapter not in ENGINES:
        return f"the engine of chapter {chapter} is not ported yet"
    if req.startswith("ASSERT "):
        return None
    if seams and (CLOCK.fullmatch(req) or req == "@reopen" or PARALLEL.fullmatch(req)):
        if exp != "ok":
            raise GenError(f"step {st}: a seam directive {req!r} expects ok, not {exp!r}")
        return None
    method = req.split(" ", 1)[0]
    if method not in METHODS:
        return f"step {st}: the stand directive or door {method!r}"
    # в запросе директива одна — @big(N) (раннер run.py, README 01); прочий «@» — данные (ревью Codex С5)
    for e in (ONE_REST.fullmatch(exp).groups() if seams and ONE_REST.fullmatch(exp) else
              [exp[5:]] if seams and exp.startswith("each ") else [exp]):
        mark = expect_directive(e)
        if mark:
            return f"step {st}: an expectation form the engine does not port ({mark!r} in {e[:30]!r})"
        m = re.match(r"([1-5][0-9]{2}) \{.*\"kind\":\s*\"([a-z]+)\"", e)
        if m and late.get((int(m[1]), m[2]), 0) > stage_n:
            return f"step {st}: a refusal of a later stage ({m[1]} {m[2]}, stage n {late[int(m[1]), m[2]]})"
    return None


VALUE_MARK = re.compile(r"@[a-z]+")


def expect_directive(e):
    """Директива ожидания по грамматике и позиции (None — нет): вся ячейка с «@» (@oneof, @exit, @empty…), тело с «@»
    или «~» (http_expect), строковое значение JSON целиком вида @имя (@time, @any, @absent — README 01). Строка с «@»
    внутри («a@b», почта) — данные, движок сличает её как есть."""
    if e.startswith("@"):
        return e.split(" ", 1)[0]
    body = e[4:]
    if body.startswith(("@", "~")):
        return body.split(" ", 1)[0]
    try:
        value = json.loads(body) if body else None
    except ValueError:
        return None
    todo = [value]
    while todo:
        v = todo.pop()
        if isinstance(v, str) and VALUE_MARK.fullmatch(v):
            return v
        if isinstance(v, dict):
            todo += v.values()
        elif isinstance(v, list):
            todo += v
    return None


def check_parallel(name, steps):
    """@parallel K: следующий шаг — запрос с ожиданием each | one…; rest; новые $имена — только в one."""
    bound = set()
    for k, (st, req, exp, _) in enumerate(steps):
        if PARALLEL.fullmatch(req):
            if k + 1 >= len(steps):
                raise GenError(f"{name} step {st}: @parallel is the last step")
            nst, nreq, nexp, _ = steps[k + 1]
            if nreq.split(" ", 1)[0] not in METHODS:
                raise GenError(f"{name} step {nst}: @parallel runs a request, not {nreq!r}")
            m = ONE_REST.fullmatch(nexp)
            if m:
                one, rest = m.groups()
                if set(VAR.findall(rest)) - bound - set(VAR.findall(one)):
                    raise GenError(f"{name} step {nst}: rest binds a new $name")
            elif nexp.startswith("each "):
                if set(VAR.findall(nexp)) - bound:
                    raise GenError(f"{name} step {nst}: each binds a new $name")
            else:
                raise GenError(f"{name} step {nst}: after @parallel the expectation is each … | one …; rest …")
        elif not req.startswith(("@", "ASSERT ")):
            if (k == 0 or not PARALLEL.fullmatch(steps[k - 1][1])) and (exp.startswith("each ") or ONE_REST.fullmatch(exp)):
                raise GenError(f"{name} step {st}: each/one…rest only after @parallel")
        bound |= set(VAR.findall(exp))


def prefix(chapter, steps, seams, late, stage_n):
    """→ (переведённые шаги, причина остатка | None)."""
    for k, step in enumerate(steps):
        why = step_blocker(chapter, step, seams, late, stage_n)
        if why:
            done = steps[:k]
            if done and PARALLEL.fullmatch(done[-1][1]):     # @parallel без своего шага не переводится
                done = done[:-1]
            return done, why
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


def stage_items(stage, gate_text, transitional):
    """→ [(глава, [сценарии] | '*', seams)] — элементы tests: формы (общий разбор gate.py), иначе переходное объявление."""
    try:
        checks = gate.parse(gate_text, f"stage {stage}")
    except gate.GateError as exc:
        raise GenError(str(exc)) from None
    items = [(c.chapter, "*" if c.names is None else list(c.names), c.seams) for c in checks if c.kind == "tests"]
    if not items and stage in transitional:
        items = [(ch, names, seams) for ch, names, seams in transitional[stage]]
    return items


def build(root=ROOT, stages_text=None, transitional=TRANSITIONAL):
    """→ ({путь в out: текст}, строки описи)."""
    root = Path(root)
    stages_rel = "Platform/01-store/forms/stages.tsv"
    text = stages_text if stages_text is not None else (root / stages_rel).read_text(encoding="utf-8")
    rows = [line.split("\t") for line in text.split("\n") if line and not line.startswith("#")]
    head = rows[0]
    stages = {dict(zip(head, r))["stage"]: dict(zip(head, r)) for r in rows[1:]}
    for stage in transitional:
        if stage not in stages:
            raise GenError(f"{stages_rel}: no stage {stage!r} of the transitional declaration")
    tables, files, inventory, tests = {}, {}, [], {}
    for stage, row in stages.items():
        items = stage_items(stage, row["gate"], transitional)
        if not items:
            continue
        translated = []
        for chapter, names, seams in items:
            fname = "seams.tsv" if seams else "scenarios.tsv"
            if (chapter, fname) not in tables:
                tables[chapter, fname] = read_table(root, chapter, fname)
                other = "scenarios.tsv" if seams else "seams.tsv"
                both = set(tables[chapter, fname][0]) & set(read_table(root, chapter, other)[0])
                if both:
                    raise GenError(f"chapter {chapter}: names in both scenarios.tsv and seams.tsv: {sorted(both)}")
            scenarios, rel, _ = tables[chapter, fname]
            if names == "*":
                names = list(scenarios)
            if len(set(names)) != len(names):
                raise GenError(f"stage {stage}: a scenario repeats in its gate")
            late = late_refusals(root, stages, chapter)
            for name in names:
                if name not in scenarios:
                    raise GenError(f"stage {stage}: no scenario {name!r} in {rel}")
                if seams:
                    check_parallel(name, scenarios[name])
                done, reason = prefix(chapter, scenarios[name], seams, late, int(row["n"]))
                test = f"Test{camel_name(stage)}_{camel_name(name)}"
                race = "yes" if any(PARALLEL.fullmatch(s[1]) for s in done) else "no"
                for k, (step, _, _, _) in enumerate(scenarios[name]):
                    inventory.append((f"{chapter}/{fname}/{name}/{step}", stage, test if k < len(done) else "-",
                                      "translated" if k < len(done) else "excluded", race if k < len(done) else "-",
                                      "-" if k < len(done) else f"the rest of the scenario from {reason}"))
                if done:
                    translated.append((chapter, fname, name, len(done)))
        if not translated:
            raise GenError(f"stage {stage}: the projection is empty (no scenario of its gate runs in process)")
        tests[stage] = translated
    for (chapter, fname), (scenarios, rel, sha) in tables.items():
        used = {}
        for ns in tests.values():
            for ch, fn, n, cnt in ns:
                if (ch, fn) == (chapter, fname):
                    used[n] = max(used.get(n, 0), cnt)
        if not used:
            continue
        var = f"{fname.split('.')[0]}{chapter.replace('.', '_')}"
        body = [f"// Code generated by tools/normgen/gen_stagetests.py from {rel} (sha256 {sha}); DO NOT EDIT.", "",
                "package stagetests", "",
                f"// {fname} of chapter {chapter}: the steps as the table writes them (request, expect, line).",
                f"var {var} = map[string][]step{{"]
        for name in sorted(used):
            body.append(f"\t{go_raw(name)}: {{")
            for st, req, exp, no in scenarios[name][:used[name]]:
                body.append(f"\t\t{{{go_raw(st)}, {go_raw(req)}, {go_raw(exp)}, {no}}},")
            body.append("\t},")
        body.append("}")
        files[f"go/stagetests/{fname.split('.')[0]}_{chapter.replace('.', '_')}_test.go"] = "\n".join(body) + "\n"
    for stage, names in tests.items():
        body = [f"// Code generated by tools/normgen/gen_stagetests.py (stage {stage} of forms/stages.tsv); DO NOT EDIT.",
                "", "package stagetests", "", 'import "testing"', ""]
        for chapter, fname, name, cnt in names:
            var = f"{fname.split('.')[0]}{chapter.replace('.', '_')}"
            body += [f"// Test{camel_name(stage)}_{camel_name(name)} — chapter {chapter}, {fname}, scenario {name}: "
                     f"steps 1…{cnt} of the projection.",
                     f"func Test{camel_name(stage)}_{camel_name(name)}(t *testing.T) {{",
                     f"\trunScenario(t, {go_raw(chapter)}, {go_raw(name)}, {'true' if fname == 'seams.tsv' else 'false'}, "
                     f"{var}[{go_raw(name)}][:{cnt}])",
                     "}", ""]
        files[f"go/stagetests/{stage}_test.go"] = "\n".join(body)
    files["go/stagetests/engine_test.go"] = ENGINE_GO
    files["go/stagetests/doc.go"] = DOC_GO
    files["go/coreadapter/coreadapter.go"] = ADAPTER_GO
    files["go/coreadapter/open.go"] = OPEN_GO
    inv = ["# Inventory of the stage tests (ADR-0125 addenda (3), (4); ADR-0126 addendum (7)): every step of a selected "
           "scenario — translated or excluded (the reason); race — the test has @parallel (the judge runs it with -race). "
           "Generated by tools/normgen/gen_stagetests.py; the kit's test set is this list.",
           "step\tstage\ttest\tstatus\trace\treason"]
    inv += ["\t".join(r) for r in inventory]
    files["go/stagetests/inventory.tsv"] = "\n".join(inv) + "\n"
    return files, inventory


ADAPTER_GO = '''// Code generated by tools/normgen/gen_stagetests.py (ADR-0125 addenda (3), (4); ADR-0126 addendum (7)); DO NOT EDIT.

// Package coreadapter — the adapter of the stage tests (stagetests) to the store core of an implementation. The kit's
// part: Config, Call, Core, Handle (apidoor.Route → Dispatch → Encode over your Core) and NotInStage. Yours (open.go):
// Open, the context type Ctx, and the Core — Context, Close and the methods of apidoor.Handler[Ctx].
package coreadapter

import (
	"encoding/json"
	"errors"
	"time"

	"normgen/p01-1/apidoor"
)

// ErrNotImplemented — what the kit's open.go stub returns until your Open exists; the daemon frame (part launch)
// answers with its empty core then (every key absent), the stage tests fail.
var ErrNotImplemented = errors.New("coreadapter: not implemented")

// Config — the stand of one scenario.
type Config struct {
	BodyLimit  int64            // the read limit of the HTTP body (1048576 on the stand)
	RowCeiling int64            // the row ceiling (524288 on the stand)
	Rights     []byte           // the rights file (P/01.2 Н1.2): the role acc with read, write, delete on acc/*
	Now        func() time.Time // the clock of the test: take every time of the core from it (seams @clock)
	DataDir    string           // the data directory of the scenario: fresh per scenario; @reopen opens it again
}

// Call — the identity of a call, apart from the HTTP headers: Sock is the socket ("acc" — the role socket of the
// stand, "admin" — admin.sock); a role header of the request stays a header (a forged one is the scenario's check).
type Call struct {
	Sock string
}

// Request — a ready context type for Ctx: the identity and the headers of the request.
type Request struct {
	Call   Call
	Header map[string]string
}

// Core — one open store instance: your Handler over your core of Н3. Handle may be called concurrently
// (seams @parallel): the core must hold that.
type Core interface {
	apidoor.Handler[Ctx]
	Context(call Call, header map[string]string) Ctx
	Close()
}

// Handle — one HTTP request in process: the body limit (413 before the route, Н2.1 order «frame → route → identity →
// body»), apidoor.Route, apidoor.Dispatch to c with c.Context(call, header), apidoor.Encode of the answer.
func Handle(c Core, cfg Config, call Call, method, target string, header map[string]string, body []byte) (int, map[string]string, []byte) {
	if body != nil && int64(len(body)) > cfg.BodyLimit {
		b, _ := json.Marshal(map[string]any{"kind": "toolarge", "error": "the body is larger than the limit",
			"limit": cfg.BodyLimit, "size": len(body)})
		return 413, map[string]string{"Content-Type": "application/json", "Connection": "close"}, b
	}
	op, query, refusal := apidoor.Route(method, target)
	if refusal != nil {
		return refusal.Code, headers(refusal.Header), refusal.Body
	}
	resp, err := apidoor.Encode(op, apidoor.Dispatch[Ctx](c, c.Context(call, header), op, query, body))
	if err != nil {
		b, _ := json.Marshal(map[string]any{"kind": "unavailable", "error": "coreadapter: " + err.Error()})
		return 500, map[string]string{"Content-Type": "application/json"}, b
	}
	return resp.Code, headers(resp.Header), resp.Body
}

// NotInStage — the five methods of apidoor.Handler outside the store core (Rights of chapter 1.2; Status, Join,
// Leave, Metrics of chapter 1.3): embed it in your Core until your stage needs them; they answer 503 «not in this
// stage».
type NotInStage struct{}

func notInStage(op apidoor.Op) apidoor.Answer {
	a, err := apidoor.Refuse(op, 503, "unavailable", "not in this stage", nil)
	if err != nil {
		return apidoor.Answer{Code: 503}
	}
	return a
}

func (NotInStage) Rights(Ctx) apidoor.Answer          { return notInStage(apidoor.OpRights) }
func (NotInStage) Status(Ctx) apidoor.Answer          { return notInStage(apidoor.OpStatus) }
func (NotInStage) Join(Ctx, []byte) apidoor.Answer    { return notInStage(apidoor.OpJoin) }
func (NotInStage) Leave(Ctx, []byte) apidoor.Answer   { return notInStage(apidoor.OpLeave) }
func (NotInStage) Metrics(Ctx) apidoor.Answer         { return notInStage(apidoor.OpMetrics) }

func headers(h [][2]string) map[string]string {
	out := map[string]string{}
	for _, kv := range h {
		out[kv[0]] = kv[1]
	}
	return out
}
'''

OPEN_GO = '''// Package coreadapter: Open and Ctx — yours (ADR-0126 addendum (7) item 5). The kit puts this stub once and never
// overwrites it.
package coreadapter

// Ctx — the context type of your Handler: what Context(call, header) gives each request. Request is ready to use;
// replace the alias with your own type if you need more.
type Ctx = *Request

// Open — a fresh core for cfg: your store in cfg.DataDir with the clock cfg.Now and the rights cfg.Rights. Return a
// value that implements Core: Context, Close and apidoor.Handler[Ctx] (Get, List, Write, QueryRefused over your core
// of Н3; embed NotInStage for Rights, Status, Join, Leave, Metrics until your stage needs them).
func Open(cfg Config) (Core, error) {
	return nil, ErrNotImplemented
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
	"sync"
	"sync/atomic"
	"testing"
	"time"
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

// openCore, handleCall — the kit's adapter (a test of the generator substitutes them to judge the engine alone).
var (
	openCore   = coreadapter.Open
	handleCall = coreadapter.Handle
)

// t0 — the clock of a seam scenario at the first Open: 2000000000 wall seconds («Спецификация», seams of P/01).
var t0 = time.Unix(2000000000, 0)

// clock — the test clock: for seams.tsv t0 plus the accumulated @clock shifts; for scenarios.tsv the wall clock, as
// the runner's stand has; safe for concurrent use.
type clock struct {
	shift atomic.Int64
	wall  bool
}

func (c *clock) now() time.Time {
	base := t0
	if c.wall {
		base = time.Now()
	}
	return base.Add(time.Duration(c.shift.Load()) * time.Second)
}

// scenario — the state of one scenario: the core (reopened by @reopen), its config, the bound $names, the next step's
// parallelism.
type scenario struct {
	core     coreadapter.Core
	cfg      coreadapter.Config
	clk      *clock
	env      map[string]any
	parallel int
	name     string
}

// runScenario — one scenario on a fresh core: the steps in order as subtests; a failed step does not bind and the
// next steps go on (as the runner does).
func runScenario(t *testing.T, chapter, name string, seams bool, steps []step) {
	clk := &clock{wall: !seams}
	cfg := coreadapter.Config{BodyLimit: 1048576, RowCeiling: 524288, Rights: []byte(standRights), Now: clk.now,
		DataDir: t.TempDir()}
	core, err := openCore(cfg)
	if err != nil || core == nil {
		t.Fatalf("coreadapter.Open: %v", err)
	}
	sc := &scenario{core: core, cfg: cfg, clk: clk, env: map[string]any{}, name: name}
	defer func() {
		if sc.core != nil {
			sc.core.Close()
		}
	}()
	if strings.HasPrefix(name, "21-") { // runner/run.py: the preparation of sc. 21 through admin.sock
		code, _, body := sc.handle(coreadapter.Call{Sock: "admin"}, "POST", "/v1/write", map[string]string{"Content-Type": "application/json"},
			[]byte(`{"op":"put","key":"other/21-rights/c9","items":{"n":"1"}}`))
		if code != 200 {
			t.Errorf("preparation via admin.sock: %d %q", code, clip(body))
		}
	}
	for _, st := range steps {
		st := st
		t.Run(st.step, func(t *testing.T) {
			for _, why := range sc.runStep(st) {
				t.Errorf("%s step %s (line %d): %s", name, st.step, st.line, why)
			}
		})
	}
}

func (sc *scenario) handle(call coreadapter.Call, method, target string, header map[string]string, body []byte) (int, map[string]string, []byte) {
	if sc.core == nil {
		return 599, nil, []byte(`{"error":"the core is closed (a failed @reopen)"}`)
	}
	return handleCall(sc.core, sc.cfg, call, method, target, header, body)
}

func (sc *scenario) runStep(st step) []string {
	env := sc.env
	switch {
	case strings.HasPrefix(st.request, "ASSERT "):
		return checkAssert(st.request, env)
	case strings.HasPrefix(st.request, "@clock "): // seams: the clock shift in seconds, accumulated
		n, _ := strconv.ParseInt(st.request[len("@clock "):], 10, 64)
		sc.clk.shift.Add(n)
		return nil
	case st.request == "@reopen": // seams: Close and Open on the same DataDir with the same clock
		if sc.core != nil {
			sc.core.Close()
		}
		core, err := openCore(sc.cfg)
		if err != nil || core == nil {
			sc.core = nil
			return []string{fmt.Sprintf("@reopen: coreadapter.Open: %v", err)}
		}
		sc.core = core
		return nil
	case strings.HasPrefix(st.request, "@parallel "): // seams: the next step K times at once
		sc.parallel, _ = strconv.Atoi(st.request[len("@parallel "):])
		return nil
	}
	if sc.parallel > 0 {
		k := sc.parallel
		sc.parallel = 0
		return sc.runParallel(st, k)
	}
	name := sc.name
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
	code, _, raw := sc.handle(coreadapter.Call{Sock: "acc"}, method, target, header, body)
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

type reply struct {
	code int
	act  any
	errs []string
}

// runParallel — seams @parallel K: the request K times at once; expect «each <e>» — every answer matches e;
// «one <e1>; rest <e2>» — exactly one answer matches e1 (it may bind), all the others match e2 (no new names).
func (sc *scenario) runParallel(st step, k int) []string {
	req, err := substitute(st.request, sc.env)
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
	replies := make([]reply, k)
	var wg sync.WaitGroup
	for i := 0; i < k; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			code, _, raw := sc.handle(coreadapter.Call{Sock: "acc"}, method, target, header, append([]byte(nil), body...))
			act, perr := decode(raw)
			if perr != nil {
				replies[i] = reply{code, nil, []string{fmt.Sprintf("body is not JSON (%v): %q", perr, clip(raw))}}
				return
			}
			replies[i] = reply{code: code, act: act}
		}(i)
	}
	wg.Wait()
	for i, r := range replies {
		if len(r.errs) > 0 {
			return append([]string{fmt.Sprintf("answer %d of %d:", i+1, k)}, r.errs...)
		}
	}
	judge := func(expect string, r reply, env map[string]any) []string {
		var out []string
		if r.code != 200 {
			if o, ok := r.act.(*object); !ok || !isStr(o.get("error")) {
				out = append(out, "body.error: a fault must carry an error string (Н2)")
			}
		}
		return append(out, checkResponse(r.code, r.act, expect, env, method, target)...)
	}
	if strings.HasPrefix(st.expect, "each ") {
		var out []string
		for i, r := range replies {
			for _, e := range judge(st.expect[len("each "):], r, copyEnv(sc.env)) {
				out = append(out, fmt.Sprintf("answer %d of %d: %s", i+1, k, e))
			}
		}
		return out
	}
	one, restExp, _ := strings.Cut(strings.TrimPrefix(st.expect, "one "), "; rest ")
	var hits []int
	var bound map[string]any
	for i, r := range replies {
		trial := copyEnv(sc.env)
		if len(judge(one, r, trial)) == 0 {
			hits = append(hits, i)
			bound = trial
		}
	}
	if len(hits) != 1 {
		codes := make([]int, k)
		for i, r := range replies {
			codes[i] = r.code
		}
		return []string{fmt.Sprintf("want exactly one answer of %d to match %q, got %d (codes %v)", k, one, len(hits), codes)}
	}
	var out []string
	for i, r := range replies {
		if i == hits[0] {
			continue
		}
		for _, e := range judge(restExp, r, copyEnv(bound)) {
			out = append(out, fmt.Sprintf("answer %d of %d (rest): %s", i+1, k, e))
		}
	}
	if len(out) == 0 {
		for kk, v := range bound {
			sc.env[kk] = v
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
