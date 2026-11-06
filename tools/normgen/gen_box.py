"""Генератор части `box` (слово владельца В-24, Архитектор 2026-11-05): то в P/01.3 box, что детерминировано нормой и
формами, — закрытый пакет Go, модели остаётся дать индексы хранилища и читать/писать строки.

Запуск: python3 tools/normgen/gen_box.py [<out>]   (по умолчанию tools/normgen/out/p01-1)

Источники (только они; проза вне перечисленных мест не читается):
- `spec/01.3-store.norms.md` Н1.3 (блок yaml P/01.3-R006): `box` — Status (state, term, leader, leader_id, voters,
  members), значения /metrics одного участника, join/leave/admit/recover; `metrics` — закрытый список серий;
  `copy` — формат копии (шапка, строка на ключ, отказы входа); `floor` — поколение и floor; `admin_ops` — backup вне -dir;
- `spec/01.1-store.norms.md` Н1 `row.items` — потолок веса строки (ceiling);
- `forms/refusals.tsv` — отказы по имени (пакет refusals части refusals);
- `spec/01-store.api.openapi.yaml` — типы ответов (пакет apidoor части door: Status, Refused, Empty, Metrics200);
- `common/data/README.md` (таблица плейсхолдеров) — грамматика `<sub>`, `<id>` ключа `<sub>/epoch/<id>`.

Выход <out>/go/box (DO NOT EDIT): box.go — Config, Indices, Status, Metrics, Join, Leave, Admit, Recover, StartRefusal;
copy.go — Row, EncodeCopy, DecodeCopy (все проверки входа copy), Upper, Floor, BackupTarget, ImportRepeated.
Судья — test_gen_box.py (своя модель на Python по тем же местам нормы: обвес Go на случаях и мутанты).
"""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import lesson  # noqa: E402
L = lesson.CURRENT

DEFAULT_OUT = L.out
GO_MODULE = L.go_module
NORMS_13 = L.path("spec/01.3-store.norms.md")
NORMS_11 = L.path("spec/01.1-store.norms.md")
REFUSALS = L.form("refusals.tsv")
OPENAPI = L.openapi
KEYS_README = ROOT / "Platform/common/data/README.md"
JUDGE = HERE / "test_gen_box.py"
COPY_JUDGE = HERE / "test_copy_storage.py"
COPY_RUNTIME = {f"box/copy_{name}.go": HERE / f"copyrt/go/{name}.go"
                for name in ("storage", "validation", "import", "control")}
STATES = ("Leader", "Follower", "Candidate", "Shutdown", "Door")
REFUSAL_NAMES = ("box_no_raft", "box_last_voter", "box_admit", "join_parity", "recover_box", "service_body_form",
                 "backup_inside_dir", "import_repeated", "copy_input")


class GenError(Exception):
    pass


def go_str(s):
    return json.dumps(s, ensure_ascii=False)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def block_line(text, word):
    """Строки пункта `word:` блока yaml Н1.3 (до следующего пункта на том же отступе)."""
    m = re.search(r"^%s:\s+(.*?)(?=^[a-z_]+:\s)" % re.escape(word), text, re.M | re.S)
    if not m:
        raise GenError(f"{NORMS_13.name}: no item {word}: in the yaml block of Н1.3")
    return " ".join(x.strip() for x in m[1].split("\n"))


def facts():
    """Числа и имена нормы, которые генератор вписывает в Go; каждое — регулярным выражением по месту нормы."""
    t13 = NORMS_13.read_text(encoding="utf-8")
    t11 = NORMS_11.read_text(encoding="utf-8")
    metrics, box, copy_, floor = (block_line(t13, w) for w in ("metrics", "box", "copy", "floor"))
    import yamlsub

    try:
        api = yamlsub.load(OPENAPI.read_text(encoding="utf-8"), OPENAPI.name)
    except yamlsub.YamlError as exc:
        raise GenError(str(exc)) from None
    status = api["components"]["schemas"]["Status"]
    body = status.get("properties", {}).get("max_body")
    if body is not None and ("max_body" not in status.get("required", []) or
                             body.get("type") != "integer" or body.get("minimum") != 1):
        raise GenError("Status.max_body must be a required positive integer")
    f = {"status_max_body": body is not None}
    m = re.match(r"(configstore_raft_term), (.*?), (configstore_doors);", metrics)
    if not m:
        raise GenError("Н1.3 metrics: the list «configstore_raft_term, …, configstore_doors;» is not found")
    series = [m[1]] + ["configstore_raft" + s if s.startswith("_") else s for s in m[2].split(", ")] + [m[3]]
    f["series"] = []
    for s in series:
        sm = re.fullmatch(r"([a-z_]+)(?:\{(\w+)(?:=([\w|]+))?\})?", s)
        if not sm:
            raise GenError(f"Н1.3 metrics: series {s!r}")
        f["series"].append((sm[1], sm[2], sm[3].split("|") if sm[3] else None))
    vm = re.search(r"\(term (\d+), elections_total (\d+), last_contact (\d+), voters (\d+), voters_expected (\d+), "
                   r"doors (\d+)\)", box)
    if not vm:
        raise GenError("Н1.3 box: the values of one member «(term …, doors …)» are not found")
    f["values"] = dict(zip(("term", "elections_total", "last_contact_seconds", "voters", "voters_expected", "doors"),
                           map(int, vm.groups())))
    sm = re.search(r"/v1/status — state (\w+), term (\d+), leader — its -api address \(empty without -api\), "
                   r"leader_id — its id, voters \[<id>\], members \{<id>: <api>\} \(without -api — \{\}", box)
    if not sm or sm[1] not in STATES or int(sm[2]) != f["values"]["term"]:
        raise GenError("Н1.3 box: the form of /v1/status of a box is not found")
    f["state"] = sm[1]
    for k, pat in (("join", r"join of its own id — 200 \{\}, of a foreign one — 409 refused even with -force"),
                   ("leave", r"leave — 409 refused \(«the last voter»\)"),
                   ("admit", r"admit — a refusal, code ≠ 0"),
                   ("recover", r"recover — a refusal, code 2 \(«this build has no raft»\)"),
                   ("noraft", r"-group-size 3 or 5, -join and -door — a start refusal with code 2")):
        if not re.search(pat, box):
            raise GenError(f"Н1.3 box: {k} is not found by {pat!r}")
    hm = re.search(r'\{"format": "([\w-]+)", "version": (\d+), "index": <version>\}', copy_)
    if not hm:
        raise GenError("Н1.3 copy: the header line is not found")
    f["copy_format"], f["copy_version"] = hm[1], int(hm[2])
    for pat in (r"then — a line per key: \{key, items, index\}", r"\{key, items: null, index, unreadable: true\}",
                r"ascending order of UTF-8 bytes", r"a repeated key", r"an index of a row higher than the index of the header",
                r"an unreadable row in the input — also a refusal"):
        if not re.search(pat, copy_):
            raise GenError(f"Н1.3 copy: {pat!r} is not found")
    import_ = block_line(t13, "import")
    copy_rules = ("Transfer excludes the input platform/epoch_floor: the first write is the new floor F1",
                  "a partial replay preserves the exact saved F1 row (items and index)")
    f["copy_storage"] = all(phrase in import_ for phrase in copy_rules)
    if any(phrase in import_ for phrase in copy_rules) and not f["copy_storage"]:
        raise GenError("Н1.3 import: incomplete published F1/continuation rule")
    if not f["copy_storage"] and "platform/epoch_floor is an ordinary row" not in copy_:
        raise GenError("Н1.3 copy: neither the known earlier form nor the complete F1 rule")
    if f["copy_storage"]:
        for pattern in (r"^(0|[1-9][0-9]*)(\.[0-9]+)?$", r"^(0|[1-9][0-9]*)(\.[0-9]{1,3})?$"):
            if pattern not in t11:
                raise GenError("Н0 time: the reader/writer notation used by the copy environment is absent")
    gm = re.search(r"generation: max\(\(upper >> (\d+)\) \+ 1, whole hours of UTC since (\d{4})-(\d\d)-(\d\d)\); "
                   r"floor = generation << (\d+);", floor)
    bm = re.search(r"1 … 2\^53 − 2\^32", floor)
    lm = re.search(r"generation ≤ 2\^21 − 1", floor)
    if not gm or gm[1] != gm[5] or not bm or not lm:
        raise GenError("Н1.3 floor: the formula of generation and floor is not found")
    f["shift"], f["since"] = int(gm[1]), (int(gm[2]), int(gm[3]), int(gm[4]))
    f["max_generation"] = 2 ** 21 - 1
    cm = re.search(r"ceiling: (\d+)\s+# 512 KiB", t11)
    if not cm or not re.search(r"weight \(sum of byte lengths of every key and every value\) at most the store's ceiling",
                               t11):
        raise GenError(f"{NORMS_11.name}: row.items ceiling is not found")
    f["ceiling"] = int(cm[1])
    if not re.search(r"backup <file>: the file path \(after resolving links\) outside -dir of the daemon", block_line(
            t13, "admin_ops")):
        raise GenError("Н1.3 admin_ops: backup outside -dir is not found")
    keys = KEYS_README.read_text(encoding="utf-8")
    for ph in ("<sub>", "<id>"):
        km = re.search(r"^\| `%s` \| `(.+?)` \| " % re.escape(ph), keys, re.M)
        if not km:
            raise GenError(f"{KEYS_README.name}: no grammar of {ph}")
        f[ph] = km[1].replace("\\|", "|")
    rows = {}
    for line in REFUSALS.read_text(encoding="utf-8").split("\n"):
        c = line.split("\t")
        if len(c) > 4 and c[0] == "1.3":
            rows[c[2]] = c
    for n in REFUSAL_NAMES:
        if n not in rows:
            raise GenError(f"{REFUSALS.name}: no row {n}")
    f["refusals"] = {g: g for g in ("".join(w.capitalize() for w in n.split("_")) for n in REFUSAL_NAMES)}
    return f


BOX_GO = r'''// Code generated by tools/normgen/gen_box.py; DO NOT EDIT.
// Source %(norms)s sha256 %(norms_sha)s, %(refusals)s sha256 %(refusals_sha)s.

// Package box — то в P/01.3 box (Н1.3 `box`, `metrics`), что задано нормой целиком: ответ /v1/status, серии /metrics
// одного участника, join/leave/admit/recover и отказ старта сборки без raft. Индексы хранилища (last, commit, applied)
// даёт ваша реализация; остальное — здесь.
package box

import (
	"fmt"
	"strings"

	"%(module)s/apidoor"
	"%(module)s/flags"
	"%(module)s/jsonstrict"
	"%(module)s/refusals"
)

// Config — что box знает о себе: -id (или SERVER_NAME), -api, -tls и -max-value (max_value статуса — действующий
// потолок веса строки в байтах; spec103 2026-11-05) из флагов демона.
%(max_body_comment)stype Config struct {
	ID       string
	API      string // пусто — демон без -api: leader "" и members {} (C01-STATUS-MEMBERS-NOAPI)
	TLS      bool
	MaxValue int64
%(max_body_field)s}

// ConfigOf — Config из разобранных флагов демона (ID уже с умолчанием SERVER_NAME у разбора launch).
func ConfigOf(f *flags.Flags) Config {
	return Config{ID: f.ID, API: f.API, TLS: f.TLS != "", MaxValue: f.MaxValue%(max_body_flags)s}
}

// Indices — индексы хранилища: last — последний записанный, commit, applied (на box все три обычно равны).
type Indices struct {
	Last, Commit, Applied uint64
}

// Status — 200 Status box (Н1.3 `box`): state %(state)s, term %(term)d, leader — -api (пусто без -api), leader_id — id,
// voters [id], members {id: api} или {} без -api; admissionAhead — поле admission_ahead (Н1.3 `admission`), nil — нет.
func Status(c Config, ix Indices, admissionAhead *float64) apidoor.Answer {
	members := map[string]string{}
	if c.API != "" {
		members[c.ID] = c.API
	}
	st := apidoor.Status{Id: c.ID, State: %(state_go)s, Leader: c.API, LeaderId: c.ID, Term: %(term)d, Commit: ix.Commit,
		Applied: ix.Applied, Voters: []string{c.ID}, Members: members, Tls: c.TLS, MaxValue: c.MaxValue,%(max_body_status)s
		AdmissionAhead: admissionAhead}
	return apidoor.Answer{Code: 200, Body: st}
}

// Series — закрытый список серий /metrics хранилища-голосующего (Н1.3 `metrics`), в порядке нормы.
var Series = []string{%(series_names)s}

// MetricsText — текст /metrics box: серии нормы со значениями одного участника (Н1.3 `box`), индексы — ix; метка
// state — состояние нижним регистром (sc. 17 шаги 6/7: state="leader"), одна строка текущего состояния; без # TYPE.
func MetricsText(ix Indices) string {
	var b strings.Builder
%(metrics_body)s	return b.String()
}

// Metrics — 200 text/plain MetricsText.
func Metrics(ix Indices) apidoor.Answer {
	return apidoor.Answer{Code: 200, Body: apidoor.Metrics200(MetricsText(ix))}
}

func line(b *strings.Builder, name, labels string, v uint64) {
	b.WriteString(name)
	if labels != "" {
		b.WriteString("{" + labels + "}")
	}
	fmt.Fprintf(b, " %%d\n", v)
}

// label — пара метки с экранированием значения по формату текста Prometheus (\\, ", перевод строки).
func label(k, v string) string {
	r := strings.NewReplacer(`\`, `\\`, `"`, `\"`, "\n", `\n`)
	return k + `="` + r.Replace(v) + `"`
}

// body — тело служебного POST (P/01.3-R017): один объект JSON строго; иначе 400 service_body_form.
func body(op apidoor.Op, raw []byte) (any, *apidoor.Answer) {
	v, _, err := jsonstrict.Decode(raw, 64)
	if err != nil {
		a := refuse(op, refusals.%(ServiceBodyForm)s, "the body is not one JSON object: "+err.Error())
		return nil, &a
	}
	return v, nil
}

func refuse(op apidoor.Op, s *refusals.Spec, msg string) apidoor.Answer {
	a, err := apidoor.Refuse(op, s.Code, s.Kind, msg, nil)
	if err != nil {
		return apidoor.Answer{Code: s.Code}
	}
	return a
}

// Join — POST /v1/join на box (Н1.3 `box`; личность — до вызова, ваша): тело по схеме Join (иначе 400); свой id —
// 200 {}; чужой — 409 refused (join_parity: группа больше объявленной), и с -force.
func Join(c Config, raw []byte) apidoor.Answer {
	v, bad := body(apidoor.OpJoin, raw)
	if bad != nil {
		return *bad
	}
	j, vio := apidoor.DecodeJoin(v)
	if vio != nil {
		return refuse(apidoor.OpJoin, refusals.%(ServiceBodyForm)s, "join: "+vio.Error())
	}
	if j.Id == c.ID {
		a, err := apidoor.AnswerOf(apidoor.OpJoin, 200, map[string]any{})
		if err != nil {
			return apidoor.Answer{Code: 200}
		}
		return a
	}
	return refuse(apidoor.OpJoin, refusals.%(JoinParity)s, "a box has one voter: "+j.Id+" cannot join")
}

// Leave — POST /v1/leave на box: тело по схеме Leave (иначе 400); всегда 409 refused «the last voter» (box_last_voter).
func Leave(c Config, raw []byte) apidoor.Answer {
	v, bad := body(apidoor.OpLeave, raw)
	if bad != nil {
		return *bad
	}
	if _, vio := apidoor.DecodeLeave(v); vio != nil {
		return refuse(apidoor.OpLeave, refusals.%(ServiceBodyForm)s, "leave: "+vio.Error())
	}
	return refuse(apidoor.OpLeave, refusals.%(BoxLastVoter)s, "the last voter")
}

// Admit — подкоманда admit на box: отказ box_admit «the last voter», код ≠ 0.
func Admit(logf func(string), id string) int {
	return refusals.%(BoxAdmit)s.Exit(logf, map[string]string{})
}

// Recover — подкоманда recover на box: отказ recover_box «this build has no raft», код 2.
func Recover(logf func(string)) int {
	return refusals.%(RecoverBox)s.Exit(logf, map[string]string{})
}

// StartRefusal — отказ старта сборки без raft (box_no_raft, код 2): -group-size 3 или 5, -join, -door; ok=false — старт
// разрешён этим правилом (прочие отказы старта — ваши).
func StartRefusal(f *flags.Flags, logf func(string)) (code int, refused bool) {
	if f.GroupSize == 3 || f.GroupSize == 5 || f.Join != "" || f.Door {
		return refusals.%(BoxNoRaft)s.Exit(logf, map[string]string{}), true
	}
	return 0, false
}
'''

COPY_GO = r'''// Code generated by tools/normgen/gen_box.py; DO NOT EDIT.
// Source %(norms)s sha256 %(norms_sha)s.

package box

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"

	"%(module)s/apidoor"
	"%(module)s/jsonstrict"
	"%(module)s/refusals"
)

// Формат копии (Н1.3 `copy`): JSON Lines, первая строка — шапка {"format": %(format_go)s, "version": %(version)d,
// "index": "<версия>"}, затем строка на ключ {key, items, index} (Row главы 1.1); ключи по возрастанию байтов UTF-8.
const (
	CopyFormat  = %(format_go)s
	CopyVersion = %(version)d
	RowCeiling  = %(ceiling)d // P/01.1 Н1 row.items.ceiling по умолчанию; действующий — -max-value демона
)

// Row — строка копии: ключ, items и версия (Index); Unreadable — повреждённая строка «как прочитана» (items null).
type Row struct {
	Key        string
	Items      map[string]string
	Index      uint64
	Unreadable bool
}

// CopyError — отказ входа copy (copy_input, код ≠ 0): строка входа (1 — шапка, 0 — весь вход) и причина.
type CopyError struct {
	Line  int
	Cause string
}

func (e *CopyError) Error() string { return "line " + strconv.Itoa(e.Line) + ": " + e.Cause }

// Exit — лог отказа copy_input с причиной и код выхода.
func (e *CopyError) Exit(logf func(string)) int {
	return refusals.%(CopyInput)s.Exit(logf, map[string]string{"cause": e.Error()})
}

// EncodeCopy — байты копии на версии index: шапка, строки по возрастанию ключа (байты UTF-8); версия строки выше
// index — ошибка (копия берётся между пакетами, index не меньше версии любой строки).
func EncodeCopy(index uint64, rows []Row) ([]byte, error) {
	rs := append([]Row(nil), rows...)
	sort.Slice(rs, func(i, j int) bool { return rs[i].Key < rs[j].Key })
	var b bytes.Buffer
	b.WriteString(`{"format":` + jsonString(CopyFormat) + `,"version":` + strconv.Itoa(CopyVersion) + `,"index":"` +
		strconv.FormatUint(index, 10) + "\"}\n")
	for i, r := range rs {
		if i > 0 && rs[i-1].Key == r.Key {
			return nil, &CopyError{0, "a repeated key " + strconv.Quote(r.Key)}
		}
		if r.Index > index {
			return nil, &CopyError{0, "the version of " + strconv.Quote(r.Key) + " is above the index of the copy"}
		}
		b.WriteString(`{"key":` + jsonString(r.Key) + `,"items":`)
		if r.Unreadable {
			b.WriteString("null")
		} else {
			names := make([]string, 0, len(r.Items))
			for k := range r.Items {
				names = append(names, k)
			}
			sort.Strings(names)
			b.WriteByte('{')
			for j, k := range names {
				if j > 0 {
					b.WriteByte(',')
				}
				b.WriteString(jsonString(k) + ":" + jsonString(r.Items[k]))
			}
			b.WriteByte('}')
		}
		b.WriteString(`,"index":"` + strconv.FormatUint(r.Index, 10) + `"`)
		if r.Unreadable {
			b.WriteString(`,"unreadable":true`)
		}
		b.WriteString("}\n")
	}
	return b.Bytes(), nil
}

func jsonString(s string) string {
	var b bytes.Buffer
	enc := json.NewEncoder(&b)
	enc.SetEscapeHTML(false)
	_ = enc.Encode(s)
	return strings.TrimSuffix(b.String(), "\n")
}

var (
	epochKey = regexp.MustCompile(`^%(sub)s/epoch/%(id)s$`)
	decimal  = regexp.MustCompile(`^(?:0|[1-9][0-9]*)$`)
)

// FloorKey — строка floor (Н1.3 `floor`): обычная строка копии.
const FloorKey = "platform/epoch_floor"

// DecodeCopy — вход import/restore (Н1.3 `copy`, `import`): полная предварительная проверка до первой записи — шапка
// (формат, версия, поля), каждая строка — объект JSON по Row с ключом по главе 1.1 Н1, без лишних и недостающих полей,
// не unreadable, вес (сумма длин байтов ключей и значений items) не выше ceiling — действующего -max-value, ключ не повторён, версия не выше index шапки; строки эпох и floor — десятичные
// числа (иначе upper не надёжен). Порядок строк не требуется. → (index шапки, строки) или отказ copy_input.
func DecodeCopy(data []byte, ceiling int64) (uint64, []Row, *CopyError) {
	if len(data) == 0 {
		return 0, nil, &CopyError{0, "the input is empty: no header"}
	}
	if !bytes.HasSuffix(data, []byte("\n")) {
		return 0, nil, &CopyError{0, "the last line has no LF"}
	}
	lines := bytes.Split(data[:len(data)-1], []byte("\n"))
	head, err := object(lines[0])
	if err != "" {
		return 0, nil, &CopyError{1, "the header: " + err}
	}
	if !sameKeys(head, "format", "version", "index") {
		return 0, nil, &CopyError{1, "the header: fields are not {format, version, index}"}
	}
	if f, ok := head["format"].(string); !ok || f != CopyFormat {
		return 0, nil, &CopyError{1, "the header: format is not " + CopyFormat}
	}
	if v, ok := head["version"].(int64); !ok || v != CopyVersion { // jsonstrict: целое без '.', 'e' — int64
		return 0, nil, &CopyError{1, "the header: version is not " + strconv.Itoa(CopyVersion)}
	}
	index, ok := version(head["index"])
	if !ok {
		return 0, nil, &CopyError{1, "the header: index is not a version"}
	}
	seen := map[string]bool{}
	var rows []Row
	for i, ln := range lines[1:] {
		no := i + 2
		m, err := object(ln)
		if err != "" {
			return 0, nil, &CopyError{no, err}
		}
		key, ok := m["key"].(string)
		if !ok {
			return 0, nil, &CopyError{no, "no key or the key is not a string"}
		}
		if e, ok := apidoor.CheckSchema("Key", key); !ok || e != nil {
			return 0, nil, &CopyError{no, "the key " + strconv.Quote(key) + " is not by chapter 1.1 Н1"}
		}
		if seen[key] {
			return 0, nil, &CopyError{no, "a repeated key " + strconv.Quote(key)}
		}
		seen[key] = true
		delete(m, "key")
		if u, isU := m["unreadable"]; isU {
			if u == true {
				return 0, nil, &CopyError{no, "an unreadable row " + strconv.Quote(key)}
			}
			return 0, nil, &CopyError{no, "the row " + strconv.Quote(key) + " is not by Row"}
		}
		if e, ok := apidoor.CheckSchema("Row", m); !ok || e != nil || m["items"] == nil {
			return 0, nil, &CopyError{no, "the row " + strconv.Quote(key) + " is not by Row"}
		}
		ix, _ := version(m["index"])
		if ix > index {
			return 0, nil, &CopyError{no, "the version of " + strconv.Quote(key) + " is above the index of the header"}
		}
		items := map[string]string{}
		var weight int64
		for k, v := range m["items"].(map[string]any) {
			items[k] = v.(string)
			weight += int64(len(k) + len(items[k]))
		}
		if weight > ceiling {
			return 0, nil, &CopyError{no, "the row " + strconv.Quote(key) + " is larger than the row ceiling"}
		}
		if epochKey.MatchString(key) && !decimalItem(items, "epoch") {
			return 0, nil, &CopyError{no, "the epoch of " + strconv.Quote(key) + " is not decimal: upper is not reliable"}
		}
		if key == FloorKey && !decimalItem(items, "floor") {
			return 0, nil, &CopyError{no, "the floor is not decimal: upper is not reliable"}
		}
		rows = append(rows, Row{Key: key, Items: items, Index: ix})
	}
	return index, rows, nil
}

func object(ln []byte) (map[string]any, string) {
	v, _, err := jsonstrict.Decode(ln, 64)
	if err != nil {
		return nil, "not JSON: " + err.Error()
	}
	m, ok := v.(map[string]any)
	if !ok {
		return nil, "not a JSON object"
	}
	return m, ""
}

func sameKeys(m map[string]any, keys ...string) bool {
	if len(m) != len(keys) {
		return false
	}
	for _, k := range keys {
		if _, ok := m[k]; !ok {
			return false
		}
	}
	return true
}

func version(v any) (uint64, bool) {
	s, ok := v.(string)
	if !ok || !decimal.MatchString(s) {
		return 0, false
	}
	n, err := strconv.ParseUint(s, 10, 64)
	return n, err == nil
}

func decimalItem(items map[string]string, name string) bool {
	_, ok := version(items[name])
	return ok
}

// Upper — upper (Н1.3 `floor`): максимум floor строки platform/epoch_floor и epoch каждой строки <sub>/epoch/<id>
// входа и сохранённого состояния (saved — строки демона; у свежего каталога нет); ни одной — 0. Строки — уже
// проверенные DecodeCopy (десятичные).
func Upper(rows []Row, saved []Row) uint64 {
	var up uint64
	for _, rs := range [][]Row{rows, saved} {
		for _, r := range rs {
			var s string
			switch {
			case r.Key == FloorKey:
				s = r.Items["floor"]
			case epochKey.MatchString(r.Key):
				s = r.Items["epoch"]
			default:
				continue
			}
			if n, ok := version(s); ok && n > up {
				up = n
			}
		}
	}
	return up
}

// Since — начало счёта часов поколения (Н1.3 `floor`).
var Since = time.Date(%(since_y)d, %(since_m)d, %(since_d)d, 0, 0, 0, 0, time.UTC)

// MaxGeneration — наибольшее поколение: floor = generation << %(shift)d не выше 2^53 − 2^32.
const MaxGeneration = %(max_generation)d

// Floor — новое поколение и floor по upper и часам now (Н1.3 `floor`): generation = max((upper >> %(shift)d) + 1, целые
// часы UTC с Since), floor = generation << %(shift)d; поколение выше MaxGeneration — отказ (переполнение), ok=false.
func Floor(upper uint64, now time.Time) (generation, floor uint64, ok bool) {
	generation = (upper >> %(shift)d) + 1
	if h := now.UTC().Sub(Since); h > 0 {
		if hours := uint64(h / time.Hour); hours > generation {
			generation = hours
		}
	}
	if generation > MaxGeneration {
		return 0, 0, false
	}
	return generation, generation << %(shift)d, true
}

// BackupTarget — путь файла backup вне -dir демона (Н1.3 `admin_ops`, B8): пути с разрешёнными ссылками (у файла,
// которого ещё нет, — его каталога); внутри dir (или равен ему) — отказ backup_inside_dir до записи, иначе nil.
func BackupTarget(file, dir string) error {
	d, err := realPath(dir)
	if err != nil {
		return err
	}
	f, err := realPath(file)
	if err != nil {
		return err
	}
	if d == string(filepath.Separator) { // the filesystem root has no outside target
		return &InsideDir{File: f, Dir: d}
	}
	if f == d || strings.HasPrefix(f, d+string(filepath.Separator)) {
		return &InsideDir{File: f, Dir: d}
	}
	return nil
}

// InsideDir — отказ backup_inside_dir: путь копии внутри каталога данных.
type InsideDir struct{ File, Dir string }

func (e *InsideDir) Error() string { return "backup " + e.File + " is inside the data directory " + e.Dir }

// Exit — лог отказа backup_inside_dir (path, dir) и код выхода.
func (e *InsideDir) Exit(logf func(string)) int {
	return refusals.%(BackupInsideDir)s.Exit(logf, map[string]string{"path": e.File, "dir": e.Dir})
}

func realPath(p string) (string, error) {
	abs, err := filepath.Abs(p)
	if err != nil {
		return "", err
	}
	if r, err := filepath.EvalSymlinks(abs); err == nil {
		return r, nil
	} else if !os.IsNotExist(err) {
		return "", err
	}
	parent, err := realPath(filepath.Dir(abs))
	if err != nil {
		return "", err
	}
	return filepath.Join(parent, filepath.Base(abs)), nil
}

// ImportRepeated — повтор import после завершённого (фаза «Done» Н3 — её отметку хранит ваша реализация): отказ
// import_repeated, код ≠ 0, ничего не меняется.
func ImportRepeated(logf func(string)) int {
	return refusals.%(ImportRepeated)s.Exit(logf, map[string]string{"phase": "Done"})
}
'''


def metrics_body(f):
    v, out = f["values"], []
    for name, lab, vals in f["series"]:
        short = name[len("configstore_raft_"):] if name.startswith("configstore_raft_") else name[len("configstore_"):]
        if lab == "state":
            out.append(f'\tline(&b, {go_str(name)}, label("state", {go_str(f["state"].lower())}), 1)\n')
        elif lab == "kind":
            for k in vals:
                field = {"last": "Last", "commit": "Commit", "applied": "Applied"}.get(k)
                if field is None:
                    raise GenError(f"Н1.3 metrics: {name}{{kind={k}}} has no index")
                out.append(f'\tline(&b, {go_str(name)}, label("kind", {go_str(k)}), ix.{field})\n')
        elif lab is None and short in v:
            out.append(f'\tline(&b, {go_str(name)}, "", {v[short]})\n')
        elif lab is None and name == "configstore_raft_term":
            out.append(f'\tline(&b, {go_str(name)}, "", {v["term"]})\n')
        else:
            raise GenError(f"Н1.3 metrics: {name} has no value of one member in «box»")
    return "".join(out)


def gofmt(src):
    done = subprocess.run(["gofmt"], input=src.encode(), capture_output=True)
    if done.returncode:
        raise GenError("gofmt: " + done.stderr.decode())
    return done.stdout.decode()


def render():
    f = facts()
    common = {"module": GO_MODULE, "norms": str(NORMS_13.relative_to(ROOT)), "norms_sha": sha(NORMS_13),
              "refusals": str(REFUSALS.relative_to(ROOT)), "refusals_sha": sha(REFUSALS), **f["refusals"]}
    body = {"max_body_comment": "// MaxBody is this instance's configured HTTP entity-body byte ceiling.\n",
            "max_body_field": "\tMaxBody int64\n", "max_body_flags": ", MaxBody: f.MaxBody",
            "max_body_status": " MaxBody: c.MaxBody,"}
    if not f["status_max_body"]:
        body = {name: "" for name in body}
    box = BOX_GO % dict(common, **body, state=f["state"], state_go=go_str(f["state"]), term=f["values"]["term"],
                        series_names=", ".join(go_str(n) for n, _, _ in f["series"]), metrics_body=metrics_body(f))
    cp = COPY_GO % dict(common, format_go=go_str(f["copy_format"]), version=f["copy_version"], ceiling=f["ceiling"],
                        sub=f["<sub>"][4:-2], id=f["<id>"][4:-2], since_y=f["since"][0], since_m=f["since"][1],
                        since_d=f["since"][2], shift=f["shift"], max_generation=f["max_generation"])
    files = {"box/box.go": gofmt(box), "box/copy.go": gofmt(cp)}
    if f["copy_storage"]:
        files.update({rel: gofmt(source.read_text(encoding="utf-8")) for rel, source in COPY_RUNTIME.items()})
    return files, f


def generate(out=DEFAULT_OUT):
    gdir = Path(out) / "go"
    files, _ = render()
    for rel in COPY_RUNTIME:
        if rel not in files:
            (gdir / rel).unlink(missing_ok=True)  # an older export must not retain a newer procedure
    for rel, text in files.items():
        (gdir / rel).parent.mkdir(parents=True, exist_ok=True)
        (gdir / rel).write_text(text, encoding="utf-8")
    return gdir


def kit_files(module, out=DEFAULT_OUT):
    """→ [(каталог в internal, имя, байты, происхождение, источник, своё у реализации)]; GenError — out устарел."""
    files = []
    for rel, text in sorted(render()[0].items()):
        kept = Path(out) / "go" / rel
        if not kept.is_file() or kept.read_text(encoding="utf-8") != text:
            raise GenError(f"{kept} is stale: run tools/normgen/gen_box.py")
        data = kept.read_bytes().replace(f'"{GO_MODULE}/'.encode(), f'"{module}/internal/'.encode())
        sub, name = rel.rsplit("/", 1)
        origin = "handwritten" if rel in COPY_RUNTIME else "generated"
        source = COPY_RUNTIME.get(rel, kept)
        files.append((sub, name, data, origin, str(source.relative_to(ROOT)), False))
    return files


def provenance():
    import tsv_input

    def entry(path):
        return {"path": str(Path(path).relative_to(ROOT)), "sha256": sha(path)}
    storage = facts()["copy_storage"]
    def entries(sources):
        return [entry(p) for p in dict.fromkeys(p for src in sources for p in
                (tsv_input.source_files(src, root=ROOT) if src.suffix == ".tsv" else [src]))]
    judge_inputs = [L.form("stages.tsv"), *sorted(L.path("acceptance/3").glob("*.tsv")),
                    L.path("acceptance/3/README.md"),
                    *sorted(L.path("acceptance/3/inputs").glob("*.jsonl")),
                    ROOT / "Source/tests/testdata/testsub.subsystem.yaml",
                    ROOT / "Source/tests/testdata/testsub2.subsystem.yaml"] if storage else []
    status_cases = L.path("acceptance/3/inputs/status-body-limits.json")
    if status_cases.is_file():
        judge_inputs.append(status_cases)
    return {"form": entries([NORMS_13, NORMS_11, REFUSALS, OPENAPI, KEYS_README]),
            "generator": entry(Path(__file__).resolve()), "handwritten": [entry(p) for p in COPY_RUNTIME.values()] if storage else [],
            "generators": [entry(Path(__file__).resolve()), entry(Path(tsv_input.__file__))],
            "judge": entry(JUDGE), "judges": [entry(JUDGE), entry(COPY_JUDGE)] if storage else [entry(JUDGE)],
            "judge_inputs": entries(judge_inputs)}


KIT_MD = """
## Part `box`: what the norm fixes on one box (generated code with a handwritten store environment, closed)

| File | Origin |
|---|---|
| `{module}/internal/box/box.go` | kit (closed): `Status`, `Metrics`, `Join`, `Leave`, `Admit`, `Recover`, `StartRefusal` |
| `{module}/internal/box/copy.go` | kit (closed): the copy format — `EncodeCopy`, `DecodeCopy`, `Upper`, `Floor`, `BackupTarget`, `ImportRepeated` |
| `{module}/internal/box/copy_storage.go`, `copy_validation.go`, `copy_import.go`, `copy_control.go` | handwritten kit environment (closed): `CopyStorage`, `ImportCopy`, `BackupCopy`, `CopyControl`, `CopyStartAllowed` |

The store of a box (P/01.3 N1.3 `box`) answers its service doors by the norm alone; you give it only the indices of
your store. Wire it from your files (one line each), after your identity check (a role socket — 403 before the body):

```go
// coreadapter/status.go, metrics.go, join.go, leave.go
return box.Status(box.ConfigOf(f), box.Indices{Last: …, Commit: …, Applied: …}, nil)
return box.Metrics(box.Indices{…})
return box.Join(cfg, body)      // own id — 200 {}, a foreign id — 409 refused, a body out of form — 400
return box.Leave(cfg, body)     // 409 refused «the last voter»
// admin/admit.go, recover.go; the daemon start
return box.Admit(logf, id)      // code ≠ 0 «the last voter»
return box.Recover(logf)        // code 2 «this build has no raft»
if code, refused := box.StartRefusal(f, logf); refused { return code }   // -group-size 3|5, -join, -door
```

**The copy** (N1.3 `copy`, `import`, `floor`; N3 phases; `admin_ops` backup): implement `box.CopyStorage` over your actual
store. `WithCopyLock` excludes ordinary writers/batches for the whole callback. Inside it, `CopyTxn.Snapshot` reads actual
rows and the index; `BeginImport` atomically makes the new F1 and progress durable and advances the index;
`WriteImport` durably writes one supplied row with its exact version; `FinishImport` persists Done. Source replay/admission
memory is not an input: retain the normal metadata of YOUR new floor operation, not that of the source store.
Use your ordinary durability barriers. Save the complete progress and F1 in your on-disk metadata. After reopening,
read the same metadata; do not reconstruct a new F1. `box.CopyStartAllowed(progress)` gates ordinary startup (exit 2)
and in-process reads/writes (503) while Transfer is pending. Only continuation bypasses that gate.

The kit owns `box.ImportCopy`/`BackupCopy`/`CopyControl`: complete preflight, upper/clock/overflow, first F1, immutable-input
identity, continuation and actual completeness; the input floor participates in upper/clock checks and is NEVER
transferred. Other rows keep their versions. Backup takes one snapshot between batches, has no replay/admission memory,
and writes an external 0600 file with sync/temp/rename/directory-sync. A repeated completed import refuses.

Connect `admin.Env.Copy` to a `box.CopyControl` with the ACTUAL store Dir/Ceiling, your wall clock and `Open(command)`.
For import/restore the target directory is `f.Dir`. Backup has no -dir flag: its Dir must be the LIVE daemon's actual
data directory, not the empty CLI field; missing Dir refuses. Ceiling is the operative row ceiling (zero uses the
normative default), not a guessed limit from an unrelated process.
The opener gives the actual live store for backup (through YOUR admin transport), or an exclusive stopped target for
box import/restore; it also supplies close. No private socket protocol or storage format is chosen by the kit.
Use the existing `launch.App.Admin` hook to call `admin.Run` with that environment. Fresh Backup/Import/Restore wrappers
delegate when Copy is connected; existing YOURS wrappers remain yours and can call the same port. Without a connection
they fail explicitly. You still implement the storage/CLI transport connection; this kit is not a complete store core.
"""


def kit_md():
    if facts()["copy_storage"]:
        return KIT_MD
    return """\n## Part `box`: the earlier form of the box primitives (closed)

`box.go`: Status/Metrics/Join/Leave/Admit/Recover/StartRefusal. `copy.go`: EncodeCopy/DecodeCopy/Upper/Floor/BackupTarget.
This export predates the complete F1 continuation rule. It receives these earlier primitives, not the new store
procedure; the implementation connects the copy to its store under this export's own norms.
"""


def main(argv):
    out = Path(argv[0]) if argv else DEFAULT_OUT
    try:
        gdir = generate(out)
    except GenError as exc:
        print(f"gen_box: {exc}", file=sys.stderr)
        return 2
    print(gdir / "box")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
