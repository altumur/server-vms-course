"""Генератор № 4 ADR-0125: каталог отказов хранилища из `Platform/01-store/forms/refusals.tsv` — без модели.

Читает таблицу (колонки chapter row name surface code kind fields headers log norm; шапка — комментарии) и строит пакет
Go 1.22 только на стандартной библиотеке `<out>/go/refusals/refusals.go`: по переменной *Spec на строку (имя — name в
CamelCase), All, ByName, проверку полей тела (Check), строку лога и код выхода отказов запуска и CLI (LogLine, Exit).

Роли трёх (ADR-0125 доп. (1) п. 5): форма тела — OpenAPI *Fault, её кодирует часть door (apidoor.Refuse); каталог — эта
таблица; порядок и условия команды записи — write-checks.tsv (часть writecheck). Пакет тела не кодирует: он даёт
код, вид, поля и заголовок для apidoor.Refuse и проверяет набор полей. Причина словами и «что делает вызывающий» — проза
Н4, генератор её не читает (доп. (1) п. 4).

Запуск: python tools/normgen/gen_refusals.py [таблица.tsv [каталог_выхода]].
"""
import hashlib
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))

from gen_checks import GenError, camel, go_str, gofmt  # noqa: E402

import lesson  # noqa: E402 — урок (ADR-0125 доп. (5) п. 2)
L = lesson.CURRENT
DEFAULT_TABLE = L.form("refusals.tsv")
DEFAULT_OUT = L.out
COLUMNS = ["chapter", "row", "name", "surface", "code", "kind", "fields", "headers", "log", "norm"]
KIT_DIRS = ("refusals",)
JUDGE = HERE / "refusal_judge.py"
EXIT_ANY = 1          # «exit !0» — любой ненулевой; пакет отдаёт 1


class Table:
    def __init__(self, text, name="refusals.tsv"):
        self.name = name
        self.sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
        body = [line for line in text.splitlines() if not line.startswith("#")]
        if not body or body[0].split("\t") != COLUMNS:
            raise GenError(f"{name}: columns must be {COLUMNS}")
        self.rows, seen = [], set()
        for k, line in enumerate(body[1:], 2):
            cells = line.split("\t")
            if len(cells) != len(COLUMNS):
                raise GenError(f"{name}: line {k}: {len(cells)} cells, expected {len(COLUMNS)}")
            r = dict(zip(COLUMNS, cells))
            where = f"{name}: {r['name']}"
            if not re.fullmatch(r"[a-z][a-z0-9_]*", r["name"]) or r["name"] in seen:
                raise GenError(f"{where}: name — snake_case, unique")
            seen.add(r["name"])
            if not re.fullmatch(r"[0-9]+\.[0-9]+", r["chapter"]) or not re.fullmatch(r"[1-9][0-9]*", r["row"]):
                raise GenError(f"{where}: chapter {r['chapter']!r} / row {r['row']!r}")
            r["row"] = int(r["row"])
            s = r["surface"]
            if s == "http":
                if not re.fullmatch(r"[1-5][0-9]{2}", r["code"]) or not re.fullmatch(r"[a-z]+", r["kind"]):
                    raise GenError(f"{where}: an http row has a code NNN and a kind")
                r["status"] = int(r["code"])
            elif s in ("start", "cli"):
                if r["kind"] != "-" or r["fields"] != "-" or r["headers"] != "-":
                    raise GenError(f"{where}: a {s} row has no kind, fields, headers (-)")
                if r["code"] == "exit 2":
                    r["status"] = 2
                elif r["code"] == "exit !0":
                    r["status"] = EXIT_ANY
                else:
                    raise GenError(f"{where}: code {r['code']!r} — exit 2 or exit !0")
            else:
                raise GenError(f"{where}: surface {s!r} — http, start, cli")
            r["field_list"] = []
            if r["fields"] != "-":
                for f in r["fields"].split(","):
                    m = re.fullmatch(r"([a-z][a-z_]*)(\??)", f)
                    if not m or m[1] in ("kind", "error") or m[1] in [x for x, _ in r["field_list"]]:
                        raise GenError(f"{where}: field {f!r} — a name, ? for optional, not kind or error, no repeats")
                    r["field_list"].append((m[1], bool(m[2])))
            r["header_list"] = []
            if r["headers"] != "-":
                for h in r["headers"].split(";"):
                    m = re.fullmatch(r"\s*([A-Za-z][A-Za-z0-9-]*): (\S.*?)\s*", h)
                    if not m:
                        raise GenError(f"{where}: header {h!r} — Name: value")
                    r["header_list"].append((m[1], m[2]))
            r["log_names"], r["log_words"] = [], []
            if r["log"] != "-":
                if s == "http":
                    raise GenError(f"{where}: an http row has no log (-)")
                for item in r["log"].split(","):
                    item = item.strip()
                    if m := re.fullmatch(r"«([^«»]+)»", item):
                        r["log_words"].append(m[1])
                    elif re.fullmatch(r"-?[A-Za-z][A-Za-z ]*", item):
                        r["log_names"].append(item)
                    else:
                        raise GenError(f"{where}: log item {item!r} — a value name or «literal words»")
            r["var"] = camel(r["name"])
            self.rows.append(r)


def go_spec(r):
    fields = ", ".join(f"{{{go_str(n)}, {'true' if o else 'false'}}}" for n, o in r["field_list"])
    headers = ", ".join(f"{{{go_str(n)}, {go_str(v)}}}" for n, v in r["header_list"])
    retry = any(n.lower() == "retry-after" for n, _ in r["header_list"])
    lst = lambda xs: "[]string{" + ", ".join(go_str(x) for x in xs) + "}" if xs else "nil"  # noqa: E731
    return (f"// {r['var']} — {r['chapter']} row {r['row']}: {r['surface']} {r['code']}"
            f"{' ' + r['kind'] if r['kind'] != '-' else ''}; {r['norm']}\n"
            f"var {r['var']} = &Spec{{Chapter: {go_str(r['chapter'])}, Row: {r['row']}, Name: {go_str(r['name'])}, "
            f"Surface: {go_str(r['surface'])}, Code: {r['status']}, "
            f"Kind: {go_str(r['kind'] if r['kind'] != '-' else '')}, "
            f"Fields: {('[]Field{' + fields + '}') if fields else 'nil'}, "
            f"Headers: {('[][2]string{' + headers + '}') if headers else 'nil'}, RetryAfter: {'true' if retry else 'false'}, "
            f"Log: {lst(r['log_names'])}, Words: {lst(r['log_words'])}, Norm: {go_str(r['norm'])}}}")


GO_API = '''
// Field — поле тела отказа помимо kind и error; Optional — «?» таблицы.
type Field struct {
	Name     string
	Optional bool
}

// Spec — строка каталога.
type Spec struct {
	Chapter    string      // глава урока: 1.1, 1.2, 1.3
	Row        int         // строка таблицы Н4 главы
	Name       string      // условие; у строк write-checks.tsv — имя её check
	Surface    string      // http (дверь), start (запуск демона), cli (команда администратора)
	Code       int         // http — статус HTTP; start, cli — код выхода (2; «!0» — 1)
	Kind       string      // http — слово kind на проводе; иначе ""
	Fields     []Field     // http — поля тела помимо kind и error
	Headers    [][2]string // http — заголовки ответа
	RetryAfter bool        // среди Headers есть Retry-After (для apidoor.Answer.RetryAfter)
	Log        []string    // start, cli — значения, которые называет лог
	Words      []string    // start, cli — слова, которые лог несёт дословно
	Norm       string
}

// ByName — строка каталога по имени; nil — нет такой.
func ByName(name string) *Spec { return byName[name] }

// Check — набор полей тела отказа http: все обязательные есть, лишних нет, значения — целое (int, int64) или строка.
// Тело кодирует apidoor.Refuse(op, s.Code, s.Kind, msg, values) по схеме *Fault OpenAPI.
func (s *Spec) Check(values map[string]any) error {
	if s.Surface != "http" {
		return fmt.Errorf("refusal %s: surface %s has no body", s.Name, s.Surface)
	}
	for _, f := range s.Fields {
		if _, ok := values[f.Name]; !ok && !f.Optional {
			return fmt.Errorf("refusal %s: no field %s", s.Name, f.Name)
		}
	}
	for k, v := range values {
		known := false
		for _, f := range s.Fields {
			known = known || f.Name == k
		}
		if !known {
			return fmt.Errorf("refusal %s: field %s is not of the catalogue", s.Name, k)
		}
		switch v.(type) {
		case int, int64, string:
		default:
			return fmt.Errorf("refusal %s: field %s is %T, not an integer or a string", s.Name, k, v)
		}
	}
	return nil
}

// LogLine — строка лога отказа start или cli: имя, слова Words дословно, затем name=value каждого данного значения.
// Значение, которого нет в Log, — ошибка; при непустом Log нужно хотя бы одно (лог называет флаг или сокет и т. п.).
func (s *Spec) LogLine(values map[string]string) (string, error) {
	if s.Surface == "http" {
		return "", fmt.Errorf("refusal %s: an http refusal has no log line", s.Name)
	}
	parts := []string{s.Name + ":"}
	parts = append(parts, s.Words...)
	given := 0
	for _, n := range s.Log {
		if v, ok := values[n]; ok {
			parts = append(parts, n+"="+strconv.Quote(v))
			given++
		}
	}
	if given != len(values) {
		for k := range values {
			if !contains(s.Log, k) {
				return "", fmt.Errorf("refusal %s: %s is not a value of its log %v", s.Name, k, s.Log)
			}
		}
	}
	if len(s.Log) > 0 && given == 0 {
		return "", fmt.Errorf("refusal %s: the log names none of %v", s.Name, s.Log)
	}
	return strings.Join(parts, " "), nil
}

// Exit — logf(строка лога) и код выхода s.Code; ошибка LogLine попадает в лог вместе с тем, что есть.
func (s *Spec) Exit(logf func(string), values map[string]string) int {
	line, err := s.LogLine(values)
	if err != nil {
		line = s.Name + ": " + err.Error()
	}
	logf(line)
	return s.Code
}

func contains(xs []string, x string) bool {
	for _, y := range xs {
		if y == x {
			return true
		}
	}
	return false
}
'''


def go_module(table, rel):
    parts = [f"// Code generated by tools/normgen/gen_refusals.py from {rel}; DO NOT EDIT.\n"
             f"// Таблица sha256 {table.sha256}.\n\n"
             "// Package refusals — каталог отказов хранилища P/01.1–P/01.3 Н4 (ADR-0125 № 4).\n"
             "package refusals\n\n"
             'import (\n"fmt"\n"strconv"\n"strings"\n)',
             GO_API.strip("\n")]
    parts += [go_spec(r) for r in table.rows]
    parts.append("// All — строки каталога в порядке таблицы.\nvar All = []*Spec{" +
                 ", ".join(r["var"] for r in table.rows) + "}")
    parts.append("var byName = map[string]*Spec{" + ", ".join(f"{go_str(r['name'])}: {r['var']}"
                                                              for r in table.rows) + "}")
    return "\n\n".join(parts) + "\n"


# ---------------------------------------------------------------- каталог без HTTP (P/02: 15 колонок)

PLAIN_COLUMNS = ["chapter", "row", "name", "surface", "code", "kind", "fields", "headers", "log", "norm", "word",
                 "cause", "outcome", "diagnostic", "caller"]
PLAIN_SURFACES = ("call", "cli", "start", "process", "peer")
# P/05: дверь урока с телом-текстом ResourceError — колонка response_schema после word, поверхность http
RESPONSE_COLUMNS = PLAIN_COLUMNS[:11] + ["response_schema"] + PLAIN_COLUMNS[11:]


class PlainTable:
    """refusals.tsv урока без своей двери (P/02 forms README «Refusal catalogue»): генератор читает только закрытые
    колонки (chapter, row, name, surface, code, word, log, norm); kind, fields, headers — «-»; четыре последние —
    проза нормы, из неё ничего не выводится."""

    def __init__(self, text, name="refusals.tsv"):
        self.name = name
        self.sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
        body = [line for line in text.splitlines() if line and not line.startswith("#")]
        head = body[0].split("\t") if body else []
        self.response = head == RESPONSE_COLUMNS
        cols = RESPONSE_COLUMNS if self.response else PLAIN_COLUMNS
        if head != cols:
            raise GenError(f"{name}: columns must be {PLAIN_COLUMNS} (or with response_schema after word)")
        schemas = response_schemas() if self.response else set()
        surfaces = PLAIN_SURFACES + (("http",) if self.response else ())
        body_at = ("peer", "http") if self.response else ("peer",)
        self.rows, seen = [], set()
        for k, line in enumerate(body[1:], 2):
            cells = line.split("\t")
            if len(cells) != len(cols):
                raise GenError(f"{name}: line {k}: {len(cells)} cells, expected {len(cols)}")
            r = dict(zip(cols, cells))
            where = f"{name}: {r['name']}"
            if not re.fullmatch(r"[a-z][a-z0-9_]*", r["name"]) or r["name"] in seen:
                raise GenError(f"{where}: name — snake_case, unique")
            seen.add(r["name"])
            if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", r["chapter"]) or not re.fullmatch(r"[1-9][0-9]*", r["row"]):
                raise GenError(f"{where}: chapter {r['chapter']!r} / row {r['row']!r}")
            r["row"] = int(r["row"])
            if r["surface"] not in surfaces:
                raise GenError(f"{where}: surface {r['surface']!r} — one of {surfaces}")
            if self.response:
                rs = r["response_schema"]
                if rs != "-" and (r["surface"] != "http" or rs not in schemas):
                    raise GenError(f"{where}: response_schema {rs!r} — a components/schemas of the lesson OpenAPI at http, or -")
            if r["kind"] != "-":
                raise GenError(f"{where}: kind is - (no HTTP Fault of the lesson)")
            r["field_list"] = []
            if r["fields"] != "-":                 # поля тела ответа двери соседа (P/03 door_token_forbidden: error)
                if r["surface"] not in body_at:
                    raise GenError(f"{where}: fields only at the surface {'/'.join(body_at)} (no HTTP body of the lesson)")
                r["field_list"] = [x.strip() for x in r["fields"].split(",")]
                if not all(re.fullmatch(r"[a-z][a-z0-9_]*", x) for x in r["field_list"]) or \
                        len(set(r["field_list"])) != len(r["field_list"]):
                    raise GenError(f"{where}: fields {r['fields']!r} — a comma list of names without repeats")
            r["header_list"] = []
            if r["headers"] != "-":                # заголовки двери соседа (P/03 process_busy: Retry-After)
                if r["surface"] not in body_at:
                    raise GenError(f"{where}: headers only at the surface {'/'.join(body_at)}")
                for h in r["headers"].split(";"):
                    m = re.fullmatch(r"\s*([A-Za-z][A-Za-z0-9-]*): (\S.*?)\s*", h)
                    if not m:
                        raise GenError(f"{where}: header {h!r} — Name: value")
                    r["header_list"].append((m[1], m[2]))
            code = r["code"]
            r["status"], r["exit"], r["any"] = 0, -1, False
            if code == "-":
                pass
            elif m := re.fullmatch(r"exit (0|[1-9][0-9]*)", code):
                r["exit"] = int(m[1])
            elif code == "exit !0":
                r["any"] = True
            elif re.fullmatch(r"[1-5][0-9]{2}", code):
                if r["surface"] not in body_at:
                    raise GenError(f"{where}: an HTTP status only at the surface {'/'.join(body_at)}")
                r["status"] = int(code)
            else:
                raise GenError(f"{where}: code {code!r} — exit N, exit !0, NNN (peer) or -")
            if r["surface"] == "peer" and (r["exit"] >= 0 or r["any"]):
                raise GenError(f"{where}: a peer row has no exit code")
            r["word_any"], r["word_cell"] = [], r["word"]
            if L.key != "02-installer" and r["word"] != "-":    # P/03+: word — сохранённая нормативная ячейка (spec103)
                toks = re.findall(r"`([^`]+)`", r["word"])   # токен — и фраза: точный текст отказа (P/06.7)
                if toks and re.sub(r"`[^`]+`|,|\s", "", r["word"]) == "":
                    # токены `…` — производный индекс: один токен | названные исходы
                    r["word"], r["word_any"] = (toks[0], []) if len(toks) == 1 else ("-", toks)
                else:
                    r["word"] = "-"                                # проза ячейки — без проекции
            if r["word"] != "-" and not r["word"].strip():
                raise GenError(f"{where}: word {r['word']!r} — one token or -")
            r["log_names"], r["log_words"] = [], []
            if r["log"] != "-":
                items = re.findall(r"\s*(«[^«»]*»|[^,«»]+?)\s*(?:,|$)", r["log"])  # запятая внутри «…» — часть фрагмента
                for item in items:
                    if m := re.fullmatch(r"«([^«»]+)»", item):
                        r["log_words"].append(m[1])
                    elif item:
                        r["log_names"].append(item)
                    else:
                        raise GenError(f"{where}: an empty log item")
            r["var"] = camel(r["name"])
            self.rows.append(r)
        self.headers = any(r["header_list"] or r["field_list"] for r in self.rows)
        self.word_any = L.key != "02-installer"             # P/03+: Named и WordCell у каждой строки
        whole = [r["chapter"] for r in self.rows if "." not in r["chapter"]]
        if whole and len(whole) != len(self.rows):
            raise GenError(f"{name}: chapters of a lesson in one chapter and of chapters NN.K together")


PLAIN_API = """
// Spec — a row of the refusal catalogue of the lesson (forms/refusals.tsv; the closed columns only — the prose
// columns cause, outcome, diagnostic, caller stay in the norm).
type Spec struct {
	Chapter string   // the chapter of the lesson: 2.1 … 2.5
	Row     int      // the row of the Н4 catalogue of the chapter (two outcomes of one prose row — two Specs)
	Name    string   // the condition
	Surface string   // call (a pure procedure), cli (an operator command), start, process (a running process), peer
	Exit    int      // cli, start, process: the exit code fixed by the form; -1 — none fixed (see AnyNonZero)
	AnyNonZero bool  // «exit !0»: any nonzero exit code (2 included) — the code is yours, never 0
	Status  int      // peer: the HTTP status of the peer's door (its owner is another lesson); 0 — none
	Word    string   // a fixed refusal/diagnostic token; "" — none
	Log     []string // the subjects the diagnostic must name; it fixes no stdout/stderr format
	Words   []string // the fixed fragments «…» the diagnostic must carry
	Norm    string
}

// ByName — the row by its name; nil — none.
func ByName(name string) *Spec { return byName[name] }

// ExitCode — the exit code of the refusal: the fixed one, or 1 for «exit !0» (the kit's choice of a nonzero code —
// any nonzero code is the norm); ok false — the form fixes no exit code (call, peer, a «-» code).
func (s *Spec) ExitCode() (code int, ok bool) {
	switch {
	case s.Exit >= 0:
		return s.Exit, true
	case s.AnyNonZero:
		return 1, true
	}
	return 0, false
}
"""


def response_schemas():
    """Имена components/schemas OpenAPI урока (для колонки response_schema)."""
    import yamlsub
    doc = yamlsub.load(L.openapi.read_text(encoding="utf-8"), L.openapi.name)
    return set((doc.get("components") or {}).get("schemas") or {})


def go_spec_plain(r, headers=False, word_any=False, response=False):
    lst = lambda xs: "[]string{" + ", ".join(go_str(x) for x in xs) + "}" if xs else "nil"  # noqa: E731
    return (f"// {r['var']} — {r['chapter']} row {r['row']}: {r['surface']} {r['code']}"
            f"{' ' + r['word'] if r['word'] != '-' else ''}; {r['norm']}\n"
            f"var {r['var']} = &Spec{{Chapter: {go_str(r['chapter'])}, Row: {r['row']}, Name: {go_str(r['name'])}, "
            f"Surface: {go_str(r['surface'])}, Exit: {r['exit']}, AnyNonZero: {'true' if r['any'] else 'false'}, "
            f"Status: {r['status']}, Word: {go_str('' if r['word'] == '-' else r['word'])}, "
            f"Log: {lst(r['log_names'])}, Words: {lst(r['log_words'])}, Norm: {go_str(r['norm'])}"
            + (f", Fields: {lst(r['field_list'])}, Headers: {go_headers(r['header_list'])}" if headers else "")
            + (f", Named: {lst(r['word_any'])}, WordCell: {go_str(r['word_cell'])}" if word_any else "")
            + (f", Response: {go_str('' if r['response_schema'] == '-' else r['response_schema'])}" if response else "") + "}")


def go_headers(hs):
    return "[][2]string{" + ", ".join(f"{{{go_str(n)}, {go_str(v)}}}" for n, v in hs) + "}" if hs else "nil"


def plain_api(table):
    """API каталога: у P/02 — прежние байты; глава урока и поле Headers — по таблице."""
    api = PLAIN_API.strip("\n")
    chapters = list(dict.fromkeys(r["chapter"] for r in table.rows))
    if L.key != "02-installer":
        api = api.replace("// the chapter of the lesson: 2.1 … 2.5",
                          "// the chapter of the lesson: " + (" … ".join([chapters[0], chapters[-1]])
                                                               if len(chapters) > 1 else chapters[0]))
    if table.headers:
        api = api.replace("\tNorm    string\n}", "\tNorm    string\n\tFields  []string    // peer: the HTTP body fields of the imported door's "
                          "answer fixed by the form; nil — none\n\tHeaders [][2]string // peer: the headers of the imported door's "
                          "answer fixed by the form; nil — none\n}", 1)
    if table.response:
        api = api.replace("\n}", "\n\tResponse string // http: the components/schemas of the body in the lesson OpenAPI; \"\" — "
                          "no body or text\n}", 1)
        api = api.replace("// call (a pure procedure), cli (an operator command), start, process (a running process), peer",
                          "// call (a pure procedure), cli, start, process, peer, http (the lesson's own door)", 1)
        api = api.replace("// peer: the HTTP status of the peer's door (its owner is another lesson); 0 — none",
                          "// http, peer: the HTTP status (peer — the imported door); 0 — none", 1)
    if table.word_any:
        api = api.replace("\n}", "\n\tNamed   []string // the named outcomes the word cell lists (two or more `…`): a "
                          "catalogue index — which applies is the norm's, not «any of»\n\tWordCell string  // the "
                          "word cell of the norm as it is (\"-\" — none); Word and Named only index it\n}", 1)
        api = api.replace("// the subjects the diagnostic must name; it fixes no stdout/stderr format",
                          "// the log cell: the subjects or the diagnostic index of the row; no log line format", 1)
    return api


def go_module_plain(table, rel):
    parts = [f"// Code generated by tools/normgen/gen_refusals.py from {rel}; DO NOT EDIT.\n"
             f"// Таблица sha256 {table.sha256}.\n\n"
             f"// Package refusals — the refusal catalogue of {L.code} (ADR-0125 № 4, addendum (5)): no HTTP body of the lesson.\n"
             "package refusals",
             plain_api(table)]
    parts += [go_spec_plain(r, table.headers, table.word_any, table.response) for r in table.rows]
    parts.append("// All — the rows of the catalogue in the order of the table.\nvar All = []*Spec{" +
                 ", ".join(r["var"] for r in table.rows) + "}")
    parts.append("var byName = map[string]*Spec{" + ", ".join(f"{go_str(r['name'])}: {r['var']}"
                                                              for r in table.rows) + "}")
    return "\n\n".join(parts) + "\n"


def render(table_path=DEFAULT_TABLE):
    table_path = Path(table_path).resolve()
    try:
        rel = table_path.relative_to(ROOT).as_posix()
    except ValueError:
        rel = table_path.name
    text = table_path.read_text(encoding="utf-8")
    head = next((ln for ln in text.splitlines() if ln and not ln.startswith("#")), "")
    if head.split("\t") in (PLAIN_COLUMNS, RESPONSE_COLUMNS):  # урок без своей двери (P/02) или с телом-текстом (P/05)
        return {"refusals.go": gofmt(go_module_plain(PlainTable(text, table_path.name), rel))}
    table = Table(text, table_path.name)
    return {"refusals.go": gofmt(go_module(table, rel))}


def generate(table_path=DEFAULT_TABLE, out=DEFAULT_OUT):
    gdir = Path(out) / "go/refusals"
    gdir.mkdir(parents=True, exist_ok=True)
    for name, text in render(table_path).items():
        (gdir / name).write_text(text, encoding="utf-8")
    mod = Path(out) / "go/go.mod"                     # модуль выхода урока (у P/01 его пишет gen_tests)
    if not mod.exists():
        mod.write_text(f"module {L.go_module}\n\ngo 1.22\n", encoding="utf-8")
    return gdir


def kit_files(out=DEFAULT_OUT):
    """→ [(каталог в internal, имя, байты, происхождение, источник)]; GenError — out устарел."""
    files = []
    for name, text in sorted(render().items()):
        kept = Path(out) / "go/refusals" / name
        if not kept.is_file() or kept.read_text(encoding="utf-8") != text:
            raise GenError(f"{kept} is stale: run tools/normgen/gen_refusals.py")
        files.append(("refusals", name, kept.read_bytes(), "generated", str(kept.relative_to(ROOT))))
    return files


def provenance():
    """Паспорт части (ADR-0125 доп. (1) п. 6 (а)): форма, генератор, судья — пути и sha256."""
    def entry(path):
        return {"path": str(path.relative_to(ROOT)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    return {"form": entry(DEFAULT_TABLE), "generator": entry(Path(__file__).resolve()), "judge": entry(JUDGE)}


KIT_MD = """
## Part `refusals`: the refusal catalogue (generated from `forms/refusals.tsv`)

| Package | Import path | Origin |
|---|---|---|
| `refusals` | `{module}/internal/refusals` | generated from `Platform/01-store/forms/refusals.tsv` (N4 of chapters 1.1–1.3) |

One `*refusals.Spec` per row, named after the row (`refusals.KeyRules`, `refusals.ConnectionLimit`,
`refusals.StartFlags`, …); `refusals.All`, `refusals.ByName(name)`.

```go
type Spec struct {
    Chapter string; Row int; Name string
    Surface string      // "http" (a door), "start" (the daemon start), "cli" (an administrative command)
    Code int            // http — the HTTP status; start, cli — the exit code (2; «non-zero» — 1)
    Kind string         // http — the wire kind
    Fields []Field      // http — the fields besides kind and error; Field{Name string; Optional bool}
    Headers [][2]string // http — the headers of the answer
    RetryAfter bool     // Headers carry Retry-After
    Log, Words []string // start, cli — the values the log names, the words it carries literally
    Norm string
}
func (s *Spec) Check(values map[string]any) error                // http: the field set of the body
func (s *Spec) LogLine(values map[string]string) (string, error) // start, cli: the log line
func (s *Spec) Exit(logf func(string), values map[string]string) int // logs LogLine, returns Code
```

- An http refusal: pick the row by its condition (the names are the conditions of N4; the rows of the write command
  carry the names of `write-checks.tsv` checks), then with part `door`:
  `a, err := apidoor.Refuse(op, s.Code, s.Kind, msg, values)`; `a.RetryAfter = s.RetryAfter`. `Check(values)` first if
  you want the catalogue to judge the fields; the door judges the body against the OpenAPI `*Fault`.
- A start refusal: `os.Exit(refusals.StartFlags.Exit(log.Print, map[string]string{"flag": r.Flag}))` (with part
  `flags`: `r` is the `*flags.Refusal`).
- The catalogue says the code, the kind, the fields, the header and what the log names — not when a refusal happens:
  the conditions in words are the prose of N4, the write command order is `write-checks.tsv` (part `writecheck`).
"""


KIT_MD = KIT_MD.replace("Platform/01-store/", L.rel + "/")      # пути урока; прочий текст — урока P/01

KIT_MD_PLAIN = """
## Part `refusals`: the refusal catalogue (generated from `forms/refusals.tsv`; the lesson has no HTTP door)

| Package | Import path | Origin |
|---|---|---|
| `refusals` | `{module}/internal/refusals` | generated from the closed columns of `forms/refusals.tsv`; closed |

```go
type Spec struct {
    Chapter, Name, Surface string // surface: call | cli | start | process | peer
    Row        int
    Exit       int      // the exit code the form fixes; -1 — none
    AnyNonZero bool     // «exit !0»: any nonzero code (yours), never 0
    Status     int      // peer: the HTTP status of the other lesson's door
    Word       string   // a fixed refusal/diagnostic token, "" — none
    Log, Words []string // the subjects and «fragments» the diagnostic names; no stdout/stderr format
    Norm       string
}
var All []*Spec; func ByName(name string) *Spec
func (s *Spec) ExitCode() (code int, ok bool) // the fixed code, 1 for «exit !0» (the kit's choice), ok false — none fixed
```

The prose of a row (its cause, outcome, diagnostic and caller action) stays in the norm (`norm`): read it there; the
package carries only what the form fixes.
"""


def kit_md():
    """Справка части: каталог без двери (15 колонок, P/02) — KIT_MD_PLAIN; иначе каталог P/01 с HTTP."""
    head = next((x for x in DEFAULT_TABLE.read_text(encoding="utf-8").splitlines() if x and not x.startswith("#")), "")
    return KIT_MD_PLAIN if head.split("\t") == PLAIN_COLUMNS else KIT_MD


def main(argv):
    table = argv[1] if len(argv) > 1 else DEFAULT_TABLE
    out = argv[2] if len(argv) > 2 else DEFAULT_OUT
    try:
        print(generate(table, out))
    except GenError as exc:
        print(f"gen_refusals: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
