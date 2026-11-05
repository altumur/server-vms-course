"""Генератор части пакета `core` (ADR-0083 доп. (95) п. 3, тот же принцип, что launch): заготовка ядра, РЕДАКТИРУЕМАЯ
моделью (как vectoradapter).

Запуск: python3 tools/normgen/gen_core.py [<out>]   (по умолчанию tools/normgen/out/p01-1)

Выход в <out>/core/coreadapter — вне модуля <out>/go: там open.go — заглушка части stagetests; пакет кладёт оба файла
в internal/coreadapter (пакет coreadapter части stagetests) один раз и не перетирает — они реализации:
- core.go — тип Store (состояние, newStore, Context, Close); <операция>.go — по файлу на метод apidoor.Handler[Ctx]
  (get.go, list.go, write.go, queryrefused.go, rights.go, status.go, join.go, leave.go, metrics.go: правка одной
  операции не затирает другую — Qwen 18q, 23q на целом файле адаптера) по интерфейсу Handler выхода gen_door
  (сигнатуры оттуда, не по памяти); над методом главы 1.1 — путь Н3 и якоря требований (req: P/01.1-RNNN, первая строка текста нормы) из
  spec/01.1-store.norms.md; тела — 503 «not implemented» (Get — пустое хранилище: every key absent, как launch.Empty,
  чтобы этап launch оставался закрытым пакетом); методы глав 1.2/1.3 — notInStage (NotInStage пакета), над ними места норм (STUBS: пункты Н2 и строка таблицы
  дверей P/01.3-R016) и строки refusals.tsv двери (STUB_REFUSALS) — привязка мест, не код решения;
- open.go — Open(Config) возвращает это ядро (вместо заглушки ErrNotImplemented части stagetests).
Ядро лежит в пакете coreadapter: Ctx = *coreadapter.Request читает и каркас launch, отдельный пакет ядра дал бы цикл
импорта (coreadapter.Open → core → coreadapter.Ctx).
Таблица «операция → глава, разделы норм» — объявление этого генератора (OpenAPI формой её не говорит); генератор
отказывает, если метод Handler не назван в таблице, раздел не найден в нормах или у раздела нет якорей.
Судья — test_gen_core.py (сборка, тесты этапов идут и красные без паники, каркас: 01-absent) и раннер на пакете.
"""
import hashlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import lesson  # noqa: E402 — урок (ADR-0125 доп. (5) п. 2)
L = lesson.CURRENT
DEFAULT_OUT = L.out
NORMS = L.norms("1")
OPENAPI = L.openapi
DOOR = L.out / "go/apidoor/door.go"
JUDGE = HERE / "test_gen_core.py"
GO_MODULE = L.go_module

# Операция Handler → (глава, [(раздел норм: заголовок или его начало до «(», отбор пунктов)]). Отбор "query" — пункты
# раздела от «**Query.**» до следующего жирного пункта.
OPS = {
    "Get": ("1.1", [("Н3 Procedures", "intro"), ("read", None)]),
    "List": ("1.1", [("list", None)]),
    "Write": ("1.1", [("write", None), ("delete", None), ("write batch", None), ("Admission time", None),
                      ("Replay by identifier — store memory", None)]),
    "QueryRefused": ("1.1", [("Н2.1 Request parsing", "query")]),
    "Rights": ("1.2", []),
    "Status": ("1.3", []),
    "Join": ("1.3", []),
    "Leave": ("1.3", []),
    "Metrics": ("1.3", []),
}
LINE = 116      # ширина строки комментария якоря

# Методы глав 1.2/1.3 → места норм над заглушкой: (файл норм, якорь, отбор) — None: пункт целиком; "door:<дверь>":
# строка таблицы дверей P/01.3-R016; иначе выражение (группа 1). Объявление генератора, как OPS: OpenAPI мест не говорит.

# Личность вызова над Context (core.go): места норм, не код решения (Архитектор 2026-11-05: 26 — R38-06).
# (файл норм, якорь, выражение отбора текста пункта или None — первая строка пункта).
NORMS_12 = L.norms("2")
NORMS_13 = L.norms("3")
REFUSALS = L.form("refusals.tsv")
ACCEPT_2 = L.path("acceptance/2/README.md")
IDENTITY = [
    (NORMS_12, "Н1.1 «Roles» identity, box", "P/01.2-R006", r"\bbox:\s*(.*?)\s+doors:"),
    (NORMS_12, "Н3 «check(role, action, key)» steps 1–3", "P/01.2-R017", None),
    (NORMS_12, None, "P/01.2-R018", None),
    (NORMS_12, None, "P/01.2-R019", None),
    (NORMS, "Н2.1 «Request parsing» (a refusal before the body)", "P/01.1-R050", None),
    (NORMS, "Н3 «list»", "P/01.1-R066", r"(Identity is checked before the operation.*?403 forbidden\.)"),
]
ORDER = (NORMS_13, r"\*\*(P/01\.3-07)\*\*[^«]*the order «([^»]+)»")
ROLE_HEADER = (ACCEPT_2, r"the name (X-[A-Za-z-]+) is a designation of the header of trusted role forwarding")
IDENTITY_REFUSALS = ("role_header", "identity", "forwarding_untrusted")
ORDER_13 = r"(The order of checks: .*?→ body and membership \(400, 409\))"
STUBS = {
    "Rights": [(NORMS_12, "P/01.2-R012", None), (NORMS_12, "P/01.2-R014", None), (NORMS_12, "P/01.2-R015", None),
               (NORMS_13, "P/01.3-R016", "door:GET `/v1/rights`")],
    "Status": [(NORMS_13, "P/01.3-R013", None), (NORMS_13, "P/01.3-R015", None),
               (NORMS_13, "P/01.3-R016", "door:GET `/v1/status`"), (NORMS_13, "P/01.3-R017", ORDER_13)],
    "Join": [(NORMS_13, "P/01.3-R013", None), (NORMS_13, "P/01.3-R016", "door:POST `/v1/join`"),
             (NORMS_13, "P/01.3-R017", ORDER_13)],
    "Leave": [(NORMS_13, "P/01.3-R013", None), (NORMS_13, "P/01.3-R016", "door:POST `/v1/leave`"),
              (NORMS_13, "P/01.3-R017", ORDER_13), (NORMS_13, "P/01.3-R023", None)],
    "Metrics": [(NORMS_13, "P/01.3-R015", None), (NORMS_13, "P/01.3-R016", "door:GET `/metrics`")],
}
# Строки forms/refusals.tsv (по имени) над заглушкой — отказы, которые называют эту дверь.
STUB_REFUSALS = {
    "Rights": ("rights_no_route", "rights_store_unavailable", "rights_not_admin", "rights_not_loaded",
               "forwarding_untrusted"),
    "Status": ("service_method",),
    "Join": ("service_body_form", "service_body_limit", "join_role_socket", "join_parity", "join_left"),
    "Leave": ("service_body_form", "service_body_limit", "join_role_socket", "box_last_voter"),
    "Metrics": ("service_method",),
}


class GenError(Exception):
    pass


def gofmt(src):
    exe = shutil.which("gofmt")
    if not exe:
        raise GenError("gofmt is not in PATH")
    done = subprocess.run([exe], input=src, capture_output=True, text=True)
    if done.returncode:
        raise GenError(f"gofmt rejects generated Go: {done.stderr[:2000]}\n{src}")
    return done.stdout


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sections(text):
    """→ [(заголовок без #, уровень, [(якорь, текст пункта)])] по порядку; текст до следующего якоря или заголовка."""
    out, cur, anchor, buf = [], None, None, []

    def flush():
        if cur is not None and anchor:
            cur[2].append((anchor, " ".join(buf).strip()))
    for line in text.split("\n"):
        h = re.match(r"^(#{2,4}) (.+)$", line)
        a = re.match(r"^<!-- req: (P/\d+\.\d+-R\d+) -->$", line)
        if h:
            flush()
            anchor, buf = None, []
            cur = (h[2].strip(), len(h[1]), [])
            out.append(cur)
        elif a:
            flush()
            anchor, buf = a[1], []
        elif anchor and line.strip() and not line.startswith("```"):
            buf.append(line.strip())
    flush()
    return out


def find(secs, name):
    # номер раздела — Н… или N… (ADR-0121 доп. (5) п. 1: N0–N5 латиницей): имя в коде сверяется с обоими
    lat = lambda x: re.sub(r"^Н(?=[0-9])", "N", x)    # noqa: E731
    hits = [s for s in secs if lat(s[0]) == lat(name) or lat(s[0]).startswith(lat(name) + "(")]
    if len(hits) != 1:
        raise GenError(f"{NORMS.name}: section {name!r} — {len(hits)} found, want 1")
    return hits[0]


def pick(sec, how):
    items = sec[2]
    if how == "intro":                      # пункты раздела до его первого подраздела: у секций они свои
        return items
    if how == "query":
        start = [i for i, (_, t) in enumerate(items) if t.startswith("- **Query.**")]
        if len(start) != 1:
            raise GenError(f"{NORMS.name}: «{sec[0]}» — no single «- **Query.**» item")
        end = next((j for j in range(start[0] + 1, len(items)) if items[j][1].startswith("- **")), len(items))
        return items[start[0]:end]
    return items


def brief(text):
    t = re.sub(r"\*\*|\[([^\]]+)\]\([^)]+\)", lambda m: m[1] or "", text)
    t = re.sub(r"^(- |\d+\. )", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t if len(t) <= LINE else t[:LINE - 1].rstrip() + "…"


HANDLER = re.compile(r"^type Handler\[C any\] interface \{\n(.*?)^\}", re.M | re.S)
METHOD = re.compile(r"^\t([A-Z]\w*)\(([^)]*)\) (\w+)", re.M)
DOOR_TYPES = re.compile(r"\b(Answer|Op|GetQuery|ListQuery|QueryError)\b")


def handler_methods(door):
    m = HANDLER.search(door)
    if not m:
        raise GenError(f"{DOOR}: no `type Handler[C any] interface`")
    out = []
    for name, params, result in METHOD.findall(m[1]):
        args = []
        for p in [p.strip() for p in params.split(",") if p.strip()]:
            var, typ = p.split(" ", 1)
            typ = "Ctx" if typ == "C" else DOOR_TYPES.sub(r"apidoor.\1", typ)
            args.append((var, typ))
        out.append((name, args, DOOR_TYPES.sub(r"apidoor.\1", result)))
    return out


OP_CONST = {"Get": "OpGet", "List": "OpList", "Write": "OpWrite", "Rights": "OpRights", "Status": "OpStatus",
            "Join": "OpJoin", "Leave": "OpLeave", "Metrics": "OpMetrics"}

CORE_HEAD = '''// Generated by tools/normgen/gen_core.py (kit part core) on spec/{norms_name} sha256 {norms_sha} and
// spec/{openapi_name} sha256 {openapi_sha}. YOURS from here: the kit puts this file once and never
// overwrites it — fill it (KIT.md «Part core: what to fill»). The state and the lifecycle are here; every operation of
// apidoor.Handler is in its own file (get.go, list.go, write.go, …): edit one without rewriting the others.

package coreadapter

import (
	"sync"

	"{module}/apidoor"
)

// Store — your core of P/01.1 Н3: one store instance over cfg.DataDir. Every method of apidoor.Handler[Ctx] has its
// own file with its signature from the door; above each method of chapter 1.1 — the path in the norms and the
// requirement anchors (req: …) it must meet. Bodies answer 503 «not implemented» (Get — the empty store) until you write them.
// Methods of chapters 1.2 and 1.3 answer 503 «not in this stage» (notInStage): replace them when your stage needs them.
// Handle may call the methods concurrently (seams @parallel): guard the state (mu, or your own discipline).
type Store struct {
	cfg Config     // the stand: BodyLimit, RowCeiling, Rights, Now (take every time from it), DataDir
	mu  sync.Mutex // one operation is one indivisible action (P/01.1-R056): under one lock on one box
	// your state: rows, the index, the id memory, …
}

// newStore — opens the store in cfg.DataDir (Open in open.go calls it). @reopen: Close, then newStore on the same
// DataDir must see what was written.
func newStore(cfg Config) (*Store, error) {
	return &Store{cfg: cfg}, nil
}

{identity}
func (s *Store) Context(call Call, header map[string]string) Ctx {
	return &Request{Call: call, Header: header}
}

// Close — releases the store (files, goroutines); the stage tests call it at the end of a scenario and at @reopen.
func (s *Store) Close() {}

func notImplemented(op apidoor.Op) apidoor.Answer {
	a, err := apidoor.Refuse(op, 503, "unavailable", "not implemented", nil)
	if err != nil {
		return apidoor.Answer{Code: 503}
	}
	return a
}
'''

GET_STUB = '''	// STUB — the empty store (every key absent), as the daemon frame's launch.Empty: keeps stage launch
	// (accept:1.1:01-absent) green. Replace with read of Н3.
	a, err := apidoor.AnswerOf(apidoor.OpGet, 200, map[string]any{"items": nil, "index": ""})
	if err != nil {
		return notImplemented(apidoor.OpGet)
	}
	return a'''

METHOD_HEAD = '''// Generated by tools/normgen/gen_core.py (kit part core). YOURS from here: the kit puts this file once and never
// overwrites it. One operation per file: this file is {name} only (the state of Store — core.go).

package coreadapter

import "{module}/apidoor"

'''

OPEN = '''// Generated by tools/normgen/gen_core.py (kit part core). YOURS from here: the kit puts this file once and never
// overwrites it.

package coreadapter

// Ctx — the context type of your Handler: what Context(call, header) gives each request (the daemon frame reads it
// too: keep it *Request, add fields to Request's neighbour types in core.go if you need more).
type Ctx = *Request

// Open — a fresh core for cfg: your Store of core.go (the stage tests and the daemon frame both call it).
func Open(cfg Config) (Core, error) {
	s, err := newStore(cfg)
	if err != nil {
		return nil, err
	}
	return s, nil
}
'''


def plain(text):
    t = re.sub(r"\*\*|\[([^\]]+)\]\([^)]+\)", lambda m: m[1] or "", text)
    return re.sub(r"\s+", " ", re.sub(r"^(- |\d+\. )", "", t)).strip()


def wrap(text, first, rest):
    """Текст пункта целиком (без обрезки brief): строки комментария не шире LINE + отступ."""
    out, cur = [], first
    for w in text.split(" "):
        if len(cur) + len(w) + 1 > LINE + len(first) and cur.strip("/ "):
            out.append(cur.rstrip())
            cur = rest
        cur += w + " "
    out.append(cur.rstrip())
    return out


def anchored(path):
    return {a: t for _, _, items in sections(path.read_text(encoding="utf-8")) for a, t in items}


def identity_comment():
    """Комментарий над Context: личность вызова — якоря норм, порядок, заголовок, строки отказа refusals.tsv."""
    lines = ["// Context — the identity of the call (KIT.md «Context — the identity of the call: what to check»): the socket",
             "// (Call.Sock: \"admin\" or a role) and the headers. Context cannot refuse: every method gets c — check c first, before",
             "// the body or the query is used (QueryRefused too: the query is parsed before your method). By the norms:"]
    texts = {}
    for path, where, anchor, expr in IDENTITY:
        if path not in texts:
            texts[path] = anchored(path)
        text = texts[path].get(anchor)
        if text is None:
            raise GenError(f"{path.name}: no req anchor {anchor}")
        if expr is not None:
            m = re.search(expr, text, re.S)
            if not m:
                raise GenError(f"{path.name}: {anchor} — no text by {expr!r}")
            text = m[1]
        if where:
            lines.append(f"//   spec/{path.name} {where}:")
        lines += wrap(f"req: {anchor} — {plain(text)}", "//     ", "//       ")
    path, expr = ORDER
    m = re.search(expr, path.read_text(encoding="utf-8"))
    if not m:
        raise GenError(f"{path.name}: no order «… → …» in the checklist")
    lines.append(f"//   the order «{m[2]}» — spec/{path.name} readiness {m[1]} (no req anchor; coreadapter.Handle does")
    lines.append("//     frame (413) → route; identity is yours, before the body)")
    path, expr = ROLE_HEADER
    m = re.search(expr, path.read_text(encoding="utf-8"))
    if not m:
        raise GenError(f"{path.name}: no name of the role forwarding header")
    lines.append(f"//   the role forwarding header: {m[1]} (acceptance/2/README.md), in c.Header")
    lines.append("//   the refusal — forms/refusals.tsv:")
    lines += refusal_lines(IDENTITY_REFUSALS)
    lines.append("//     apidoor.Refuse(op, 403, \"forbidden\", msg, nil)")
    return "\n".join(lines)


def stub_comment(name, chapter):
    """Комментарий над методом главы 1.2/1.3 (Архитектор 2026-11-05, 28-я — посев 27-й): места норм по STUBS, текст
    пункта целиком (или отобранный выражением, или строка таблицы дверей); тело — notInStage, не код решения."""
    lines = [f"// {name} — chapter {chapter} (P/0{chapter}), not in the store core stage: 503 «not in this stage» until your",
             "// stage needs it; then replace the body (the signature stays: Store is a coreadapter.Core). Identity first —",
             "// Context (core.go). By the norms:"]
    count, cache = 0, {}
    for path, anchor, sel in STUBS[name]:
        if path not in cache:
            text = path.read_text(encoding="utf-8")
            cache[path] = ({a: (h, t) for h, _, items in sections(text) for a, t in items}, text)
        items, text = cache[path]
        if anchor not in items:
            raise GenError(f"{path.name}: no req anchor {anchor} (gen_core STUBS {name})")
        head, item = items[anchor]
        if sel is None:
            item = plain(item)
        elif sel.startswith("door:"):
            door = sel[5:]
            rows = re.findall(r"\| " + re.escape(door) + r" \| (.*?) \|(?= \||$)", item)
            if len(rows) != 1:
                raise GenError(f"{path.name}: {anchor} — {len(rows)} rows of the door {door}, want 1")
            item = f"{door}: {plain(rows[0])}"
        else:
            m = re.search(sel, item, re.S)
            if not m:
                raise GenError(f"{path.name}: {anchor} — no text by {sel!r}")
            item = plain(m[1])
        lines.append(f"//   spec/{path.name} «{head}»:")
        lines += wrap(f"req: {anchor} — {item}", "//     ", "//       ")
        count += 1
    lines.append("//   the refusals — forms/refusals.tsv:")
    lines += refusal_lines(STUB_REFUSALS[name])
    return lines, count


def refusal_lines(names):
    """Строки refusals.tsv по именам: «глава row N имя — код вид (норма); with part refusals: refusals.Имя»."""
    rows = {}
    for line in REFUSALS.read_text(encoding="utf-8").split("\n"):
        cols = line.split("\t")
        if len(cols) == 10 and cols[2] in names:
            rows[cols[2]] = cols
    if set(rows) != set(names):
        raise GenError(f"{REFUSALS.name}: rows {sorted(set(names) - set(rows))} not found")
    out = []
    for name in names:
        ch, row, _, _, code, kind, _, _, _, norm = rows[name]
        var = "".join(w[:1].upper() + w[1:] for w in name.split("_"))
        out.append(f"//     {ch} row {row} {name} — {code} {kind} ({norm}); with part refusals: refusals.{var}")
    return out


def render():
    """→ ({путь от core/: текст}, [(метод, глава, число якорей)])."""
    try:
        lesson.require(L, "gen_core (OPS, STUBS, IDENTITY)")
    except lesson.LessonError as exc:
        raise GenError(str(exc)) from None
    for p in (NORMS, OPENAPI, DOOR, NORMS_12, NORMS_13, REFUSALS, ACCEPT_2):
        if not p.is_file():
            raise GenError(f"no {p}" + (": run tools/normgen/gen_door.py" if p == DOOR else ""))
    secs = sections(NORMS.read_text(encoding="utf-8"))
    methods = handler_methods(DOOR.read_text(encoding="utf-8"))
    names = [m[0] for m in methods]
    if set(names) != set(OPS):
        raise GenError(f"apidoor.Handler methods {sorted(names)} != the table of gen_core {sorted(OPS)}")
    body, report = [], []
    for name, args, result in methods:
        chapter, refs = OPS[name]
        sig = f"func (s *Store) {name}(" + ", ".join(f"{v} {t}" for v, t in args) + f") {result}"
        op = "op" if name == "QueryRefused" else f"apidoor.{OP_CONST[name]}"
        if chapter != "1.1":
            lines, count = stub_comment(name, chapter)
            body.append((name, "\n".join(lines) + f"\n{sig} {{\n\treturn notInStage({op})\n}}\n"))
            report.append((name, chapter, count))
            continue
        lines, count = [f"// {name} — P/01.1:"], 0
        for sec_name, how in refs:
            sec = find(secs, sec_name)
            items = pick(sec, how)
            if not items:
                raise GenError(f"{NORMS.name}: «{sec[0]}» has no req anchors")
            where = "Н3" if sec_name not in ("Н3 Procedures", "Н2.1 Request parsing") else ""
            lines.append(f"//   spec/{NORMS.name} {where + ' ' if where else ''}«{sec[0]}»"
                         + (" (the query items)" if how == "query" else "") + ":")
            for anchor, text in items:
                lines.append(f"//     req: {anchor} — {brief(text)}")
                count += 1
        if name == "Write":
            lines.append("//   the body first: writecheck.Check(body, c.Call.Sock, lim, allowed) — the form of Н2.1/Н1 "
                         "(KIT.md, writecheck)")
        if name == "QueryRefused":
            lines.append("//   the refusal: Н4 «Refusals» and forms/refusals.tsv (code, kind) — apidoor.Refuse(op, 400, …)")
        stub = GET_STUB if name == "Get" else f"\treturn notImplemented({op})"
        body.append((name, "\n".join(lines) + f"\n{sig} {{\n{stub}\n}}\n"))
        report.append((name, chapter, count))
    core = CORE_HEAD.replace("{identity}", identity_comment()).replace("{norms_name}", NORMS.name).replace("{norms_sha}", sha(NORMS)).replace("{openapi_name}", OPENAPI.name).replace("{openapi_sha}", sha(OPENAPI)).replace("{module}", GO_MODULE)
    files = {"coreadapter/core.go": gofmt(core), "coreadapter/open.go": gofmt(OPEN)}
    for name, text in body:
        rel = f"coreadapter/{name.lower()}.go"
        if rel in files:
            raise GenError(f"{rel}: two operations in one file")
        files[rel] = gofmt(METHOD_HEAD.replace("{name}", name).replace("{module}", GO_MODULE) + text)
    return files, report


def generate(out=DEFAULT_OUT):
    gdir = Path(out) / "core"
    files, report = render()
    for rel, text in files.items():
        (gdir / rel).parent.mkdir(parents=True, exist_ok=True)
        (gdir / rel).write_text(text, encoding="utf-8")
    return gdir, report


def kit_files(module, out=DEFAULT_OUT):
    """→ [(каталог в internal, имя, байты, происхождение, источник, своё у реализации)]; GenError — out устарел."""
    files = []
    for rel, text in sorted(render()[0].items()):
        kept = Path(out) / "core" / rel
        if not kept.is_file() or kept.read_text(encoding="utf-8") != text:
            raise GenError(f"{kept} is stale: run tools/normgen/gen_core.py")
        data = kept.read_bytes().replace(f'"{GO_MODULE}/'.encode(), f'"{module}/internal/'.encode())
        sub, name = rel.rsplit("/", 1)
        files.append((sub, name, data, "generated", str(kept.relative_to(ROOT)), True))
    return files


def provenance():
    """Паспорт части (ADR-0125 доп. (1) п. 6 (а)): формы, генератор, ручная среда (нет), судья."""
    def entry(path):
        return {"path": str(Path(path).relative_to(ROOT)), "sha256": sha(path)}
    return {"form": [entry(p) for p in (NORMS, OPENAPI, NORMS_12, NORMS_13, REFUSALS, ACCEPT_2)], "generator": entry(Path(__file__).resolve()),
            "handwritten": [], "judge": entry(JUDGE)}


KIT_MD = """
## Part `core`: the core stub — what to fill (generated, **yours**)

| File | Origin |
|---|---|
| `{module}/internal/coreadapter/core.go` | **yours**: `Store` — its state, `newStore`, `Context`, `Close` |
| `{module}/internal/coreadapter/get.go`, `list.go`, `write.go`, `queryrefused.go` | **yours**: one operation of chapter 1.1 per file, the body to write |
| `{module}/internal/coreadapter/rights.go`, `status.go`, `join.go`, `leave.go`, `metrics.go` | **yours**: chapters 1.2, 1.3 — 503 «not in this stage» for now |
| `{module}/internal/coreadapter/open.go` | **yours**: `Open(cfg)` already returns `newStore(cfg)`; `Ctx = *Request` |

The kit puts each file once and never overwrites it. **One operation per file**: to write `Write`, edit `write.go`
only — never rewrite a file to change another operation, never delete a method (the build breaks: `Store` must stay
a `coreadapter.Core`). Everything compiles and runs from the start: the stage tests
(`go test ./internal/stagetests/`) run and fail until the bodies exist; the daemon (`cmd/configstore`) serves this core.

**What to fill** — these files, nothing else is needed for stage `store_core`:

1. `core.go`: `Store` — your state (rows, the index, the `id` memory) under `mu`; `newStore(cfg)` opens it in `cfg.DataDir`
   (`@reopen` — `Close`, then `newStore` on the same directory sees what was written); take every time from `cfg.Now`.
2. `get.go`, `list.go`, `write.go`, `queryrefused.go` — chapter 1.1. Above each method: the path in
   `Platform/01-store/spec/01.1-store.norms.md` (Н3 «read», «list», «write», «delete», «write batch», «Admission time»,
   «Replay by identifier»; Н2.1 query items) and every `req: P/01.1-RNNN` anchor it must meet, with its first line.
   Write the body by those anchors, in that order. `Get` is a stub of the empty store (every key absent) so that stage
   `launch` stays green; it is not the read of Н3.
3. `write.go`: first `writecheck.Check(body, c.Call.Sock, lim, allowed)` (the form of the body — part writecheck), then
   the command by Н3 on its parsed body. Answers: `apidoor.AnswerOf(op, code, value)`, refusals
   `apidoor.Refuse(op, code, kind, msg, fields)` (codes and kinds — Н4 and `forms/refusals.tsv`).
4. **Context — the identity of the call: what to check.** `Context(call, header)` in `core.go` gives `c` to every
   method; it cannot refuse, so each method checks `c` first, before the body or the query is used (`QueryRefused` too).
   Above `Context` — the places: P/01.2 Н1.1 `identity` (box: a role header on any socket — 403 with the role of the
   socket), P/01.2 Н3 «check» steps 1–3 (a role header on a role socket — `403` before the body is parsed; a listing —
   after the identity check), P/01.1 Н2.1 (a refusal before the body), P/01.1 Н3 «list», the order «frame → route →
   identity → body», the header name and the rows of `forms/refusals.tsv` (403 `forbidden`). The check itself is yours.
5. `rights.go` (chapter 1.2), `status.go`, `join.go`, `leave.go`, `metrics.go` (chapter 1.3) answer 503 «not in this stage»: leave
   them until your stage needs them. Keep the signatures: `Store` must stay a `coreadapter.Core`.

Do not study `apidoor` or `coreadapter.Handle` beyond the signatures in these files: the route, the query parse, the body
limit and the encoding of the answer are done before and after your method.
"""


def main(argv):
    out = argv[1] if len(argv) > 1 else DEFAULT_OUT
    try:
        gdir, report = generate(out)
    except GenError as exc:
        print(f"gen_core: {exc}", file=sys.stderr)
        return 1
    print(gdir, " ".join(f"{n}:{c}/{k}" for n, c, k in report))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
