// Runtime of the part families (ADR-0125 № 5): the reading of a store row of a data family by its schema — hand-written
// environment of tools/normgen/gen_families.py, copied next to the generated families.go; DO NOT EDIT in the kit.
//
// The pass is that of the V7 stack (skills/lesson-spec/scripts/v7/stack.py Family.judge, kind row): the codec of items
// (Platform/common/data/codec.tsv, writer — strict, reader — tolerant), the words x-codec, x-whole, x-time, x-integer,
// x-max-bytes, then JSON Schema (type, minimum, maximum, enum, required, additionalProperties: false). A refusal is a
// set of JSON Pointer paths (the order — by UTF-8 bytes); the outcome of an unreadable row — the paths of the rows of
// <family>.outcomes.tsv that act for a reader (OutcomesFor). What the outcome does is the prose of the norm — not here.
package families

import (
	"encoding/json"
	"math"
	"math/big"
	"regexp"
	"sort"
	"strconv"
	"strings"
)

// Mode — who reads: the writer checks the strict notation before a write, the reader is tolerant (codec.tsv).
type Mode int

const (
	Writer Mode = iota
	Reader
)

// Item — a value of items. NotString — the value is not a JSON string (only in a text of items, never in the store).
type Item struct {
	Text      string
	NotString bool
}

// Items — the fields of a row as read from the store.
type Items map[string]Item

// ItemsOf — the items of a stored row (all values are strings).
func ItemsOf(m map[string]string) Items {
	out := make(Items, len(m))
	for k, v := range m {
		out[k] = Item{Text: v}
	}
	return out
}

// ParseItems — a JSON text of items → Items; nil — the text is not a JSON object (the row is refused whole).
func ParseItems(text []byte) Items {
	var raw json.RawMessage
	if json.Unmarshal(text, &raw) != nil {
		return nil
	}
	t := strings.TrimLeft(string(raw), " \t\r\n")
	if !strings.HasPrefix(t, "{") {
		return nil
	}
	var m map[string]json.RawMessage
	if json.Unmarshal(raw, &m) != nil {
		return nil
	}
	out := make(Items, len(m))
	for k, v := range m {
		var s string
		if strings.HasPrefix(strings.TrimLeft(string(v), " \t\r\n"), `"`) && json.Unmarshal(v, &s) == nil {
			out[k] = Item{Text: s}
		} else {
			out[k] = Item{Text: string(v), NotString: true}
		}
	}
	return out
}

// Prop — a field of the row by the schema (the words of its $ref chain, the place first).
type Prop struct {
	Name     string
	Codec    []string // x-codec: the notations tried in order
	Whole    bool     // x-whole: an integer only in integer notation, for the reader too
	Time     bool     // x-time
	Integer  bool     // x-integer
	Types    []string // JSON Schema type
	Min, Max string   // minimum, maximum (decimal integers); "" — none
	MaxBytes int      // x-max-bytes; -1 — none
	Enum     []string // enum of strings; nil — none
}

// Outcome — a row of <family>.outcomes.tsv without its prose: the path (JSON Pointer, "" — the whole row), the reader
// (a role or "*"), the priority (smaller — earlier), the unit (строка, поле, элемент).
type Outcome struct {
	Path     string
	Reader   string
	Priority int
	Unit     string
}

// Seg — a segment of the key template: a literal, or a placeholder with its grammar (Platform/common/data/README.md).
type Seg struct {
	Lit, Placeholder, Grammar string
}

// Family — a data family of the catalog (Platform/common/data/catalog.tsv) with a schema.
type Family struct {
	Key      string // the key template of the catalog
	Kind     string // row
	Schema   string // the schema path
	Norm     string
	Template []Seg
	Props    []Prop
	Required []string
	Closed   bool // additionalProperties: false
	Outcomes []Outcome
	key      *regexp.Regexp
}

// Result — the verdict of a reading: "ok" or "refused" with the refusal paths.
type Result struct {
	Verdict string
	Paths   []string
}

// OK — the row is readable.
func (r Result) OK() bool { return r.Verdict == "ok" }

// Matches — the key belongs to the family: the literals exactly, each placeholder by a full match of its grammar.
func (f *Family) Matches(key string) bool {
	if f.key == nil {
		var b strings.Builder
		b.WriteString("^")
		for _, s := range f.Template {
			if s.Placeholder == "" {
				b.WriteString(regexp.QuoteMeta(s.Lit))
			} else {
				b.WriteString("(?:" + strings.TrimSuffix(strings.TrimPrefix(s.Grammar, "^"), "$") + ")")
			}
		}
		b.WriteString("$")
		f.key = regexp.MustCompile(b.String())
	}
	return f.key.MatchString(key)
}

// Judge — the reading of the row key with items: a key not by the template — refused on "" (the value is not judged).
func (f *Family) Judge(key string, items Items, mode Mode) Result {
	if !f.Matches(key) {
		return Result{"refused", []string{""}}
	}
	r, _ := f.judge(items, mode)
	return r
}

// JudgeItems — the reading of items alone (the key is already the family's).
func (f *Family) JudgeItems(items Items, mode Mode) Result {
	r, _ := f.judge(items, mode)
	return r
}

// Readers — the readers of the family: the rows of the empty path of outcomes.tsv, in the order of the file.
func (f *Family) Readers() []string {
	var out []string
	for _, o := range f.Outcomes {
		if o.Path == "" && !contains(out, o.Reader) {
			out = append(out, o.Reader)
		}
	}
	return out
}

// OutcomesFor — the paths of the outcome rows that act at the reader for these refusal paths (DIALECT § 9, the V7 rule):
// for each path the rows whose path is its prefix; when the deepest of them has the unit поле or элемент, only the
// deepest act, else all; of the rows of all paths act those of the least priority, in the order of the file.
func (f *Family) OutcomesFor(paths []string, reader string) []string {
	var own []Outcome
	for _, o := range f.Outcomes {
		if o.Reader == reader || o.Reader == "*" {
			own = append(own, o)
		}
	}
	keep := map[int]bool{}
	for _, q := range paths {
		var cov []int
		deep := 0
		for i, o := range own {
			if covers(o.Path, q) {
				cov = append(cov, i)
				if n := len(unpointer(o.Path)); n > deep {
					deep = n
				}
			}
		}
		var top []int
		field := false
		for _, i := range cov {
			if len(unpointer(own[i].Path)) == deep {
				top = append(top, i)
				field = field || own[i].Unit != unitRow
			}
		}
		if !field {
			top = cov
		}
		for _, i := range top {
			keep[i] = true
		}
	}
	if len(paths) == 0 || len(keep) == 0 {
		return []string{}
	}
	low := math.MaxInt
	for i := range keep {
		if own[i].Priority < low {
			low = own[i].Priority
		}
	}
	out := []string{}
	for i, o := range own {
		if keep[i] && o.Priority == low {
			out = append(out, o.Path)
		}
	}
	return out
}

func covers(path, q string) bool {
	if path == "" {
		return true
	}
	if !strings.HasPrefix(q, "/") {
		return false
	}
	ps, qs := unpointer(path), unpointer(q)
	if len(qs) < len(ps) {
		return false
	}
	for i, s := range ps {
		if qs[i] != s {
			return false
		}
	}
	return true
}

func unpointer(p string) []string {
	if p == "" {
		return nil
	}
	parts := strings.Split(p, "/")[1:]
	for i, s := range parts {
		parts[i] = strings.ReplaceAll(strings.ReplaceAll(s, "~1", "/"), "~0", "~")
	}
	return parts
}

// Pointer — the JSON Pointer of a field of the row.
func Pointer(name string) string {
	return "/" + strings.ReplaceAll(strings.ReplaceAll(name, "~", "~0"), "/", "~1")
}

// ---------------------------------------------------------------- the pass

var (
	reNum  = regexp.MustCompile(`^-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][-+]?[0-9]+)?$`)
	reInt  = regexp.MustCompile(`^-?(0|[1-9][0-9]*)$`)
	reDec  = regexp.MustCompile(`^-?(0|[1-9][0-9]*)(\.[0-9]+)?$`)
	reTime = map[Mode]*regexp.Regexp{
		Writer: regexp.MustCompile(`^(0|[1-9][0-9]*)(\.[0-9]{1,3})?$`),
		Reader: regexp.MustCompile(`^(0|[1-9][0-9]*)(\.[0-9]+)?$`),
	}
	intMax = big.NewInt(1<<53 - 1)
)

// value — a decoded field: kind 's' string, 'i' integer (huge — beyond 10^hugeDigits, only its sign), 'f' number, 'b'.
type value struct {
	kind byte
	s    string
	i    *big.Int
	huge int
	f    float64
	b    bool
}

const hugeDigits = 4096

func (f *Family) prop(k string) *Prop {
	for i := range f.Props {
		if f.Props[i].Name == k {
			return &f.Props[i]
		}
	}
	return nil
}

func (f *Family) judge(items Items, mode Mode) (Result, map[string]value) {
	if items == nil {
		return result([]string{""}), nil
	}
	var fails []string
	vals := map[string]value{}
	present := map[string]bool{}
	for k, it := range items {
		p := f.prop(k)
		if p == nil {
			present[k] = true
			if f.Closed {
				fails = append(fails, Pointer(k)) // additionalProperties: false — the path of the extra key
			}
			continue
		}
		if it.NotString {
			fails = append(fails, Pointer(k))
			continue
		}
		v, ok := decode(p, it.Text, mode)
		if !ok {
			fails = append(fails, Pointer(k))
			continue
		}
		present[k] = true
		if !p.check(v, mode) {
			fails = append(fails, Pointer(k))
			continue
		}
		vals[k] = v
	}
	for _, k := range f.Required {
		if !present[k] {
			fails = append(fails, Pointer(k))
		}
	}
	return result(fails), vals
}

func result(paths []string) Result {
	set := map[string]bool{}
	out := []string{}
	for _, p := range paths {
		if !set[p] {
			set[p] = true
			out = append(out, p)
		}
	}
	sort.Strings(out) // Go compares strings by bytes: the UTF-8 order of the V7 stack
	if len(out) == 0 {
		return Result{"ok", out}
	}
	return Result{"refused", out}
}

func decode(p *Prop, t string, mode Mode) (value, bool) {
	for _, ty := range p.Codec {
		if v, ok := decodeAs(ty, t, mode, p.Whole); ok {
			return v, true
		}
	}
	return value{}, false
}

func decodeAs(ty, t string, mode Mode, whole bool) (value, bool) {
	w := mode == Writer
	switch ty {
	case "string", "any":
		return value{kind: 's', s: t}, true
	case "integer":
		if w || whole {
			if !reInt.MatchString(t) {
				return value{}, false
			}
			i, _ := new(big.Int).SetString(t, 10)
			if w && new(big.Int).Abs(i).Cmp(intMax) > 0 {
				return value{}, false
			}
			return value{kind: 'i', i: i}, true
		}
		if !reNum.MatchString(t) {
			return value{}, false
		}
		return exactInteger(t)
	case "number":
		re := reNum
		if w {
			re = reDec
		}
		if !re.MatchString(t) {
			return value{}, false
		}
		x, _ := strconv.ParseFloat(t, 64) // the record is by the regexp: an error is only the range (±Inf)
		if math.IsInf(x, 0) {
			return value{}, false
		}
		if w && plainDecimal(x) != t {
			return value{}, false
		}
		if reInt.MatchString(t) {
			i, _ := new(big.Int).SetString(t, 10)
			return value{kind: 'i', i: i}, true
		}
		return value{kind: 'f', f: x}, true
	case "boolean":
		if t != "true" && t != "false" {
			return value{}, false
		}
		return value{kind: 'b', b: t == "true"}, true
	case "time":
		if !reTime[mode].MatchString(t) {
			return value{}, false
		}
		x, _ := strconv.ParseFloat(t, 64) // an overflow — +Inf: refused by the place (not finite)
		return value{kind: 'f', f: x}, true
	}
	return value{}, false
}

// exactInteger — a decimal record equal to an integer by its exact decimal value (codec.tsv integer, the reader).
func exactInteger(t string) (value, bool) {
	neg := strings.HasPrefix(t, "-")
	t = strings.TrimPrefix(t, "-")
	mant, exp := t, 0
	if i := strings.IndexAny(t, "eE"); i >= 0 {
		mant = t[:i]
		e, err := strconv.Atoi(strings.TrimPrefix(t[i+1:], "+"))
		if err != nil {
			e = math.MaxInt32 // beyond int: by its sign only
			if strings.HasPrefix(t[i+1:], "-") {
				e = math.MinInt32
			}
		}
		exp = e
	}
	digits := mant
	if i := strings.IndexByte(mant, '.'); i >= 0 {
		digits = mant[:i] + mant[i+1:]
		exp -= len(mant) - i - 1
	}
	digits = strings.TrimLeft(digits, "0")
	if digits == "" {
		return value{kind: 'i', i: new(big.Int)}, true
	}
	for exp < 0 && strings.HasSuffix(digits, "0") {
		digits = digits[:len(digits)-1]
		exp++
	}
	if exp < 0 {
		return value{}, false
	}
	sign := 1
	if neg {
		sign = -1
	}
	if len(digits)+exp > hugeDigits {
		return value{kind: 'i', huge: sign}, true
	}
	i, _ := new(big.Int).SetString(digits+strings.Repeat("0", exp), 10)
	if neg {
		i.Neg(i)
	}
	return value{kind: 'i', i: i}, true
}

func plainDecimal(x float64) string {
	s := strconv.FormatFloat(x, 'f', -1, 64)
	if s == "-0" {
		return "0"
	}
	return s
}

// check — layer 3 and JSON Schema on the decoded value of the place.
func (p *Prop) check(v value, mode Mode) bool {
	if v.kind == 'f' && (math.IsInf(v.f, 0) || math.IsNaN(v.f)) {
		return false // a number beyond binary64: not by the grammar (codec.tsv)
	}
	if p.Time && !isTime(v, mode) {
		return false
	}
	if p.Integer && v.kind == 'f' && v.f == math.Trunc(v.f) && (mode == Writer || p.Whole) {
		return false
	}
	if p.MaxBytes >= 0 && v.kind == 's' && len(v.s) > p.MaxBytes {
		return false
	}
	if !typeOK(p.Types, v) {
		return false
	}
	if p.Min != "" && cmp(v, p.Min) < 0 || p.Max != "" && cmp(v, p.Max) > 0 {
		return false
	}
	if p.Enum != nil && (v.kind != 's' || !contains(p.Enum, v.s)) {
		return false
	}
	return true
}

func isTime(v value, mode Mode) bool {
	switch v.kind {
	case 's':
		return reTime[mode].MatchString(v.s)
	case 'i':
		return v.huge == 0 && v.i.Sign() >= 0
	case 'f':
		if math.IsInf(v.f, 0) || math.IsNaN(v.f) || v.f < 0 {
			return false
		}
		if mode == Reader {
			return true
		}
		r, _ := strconv.ParseFloat(strconv.FormatFloat(v.f, 'f', 3, 64), 64)
		return r == v.f
	}
	return false
}

func typeOK(types []string, v value) bool {
	if len(types) == 0 {
		return true
	}
	for _, t := range types {
		switch {
		case t == "string" && v.kind == 's', t == "boolean" && v.kind == 'b',
			t == "number" && (v.kind == 'i' || v.kind == 'f'), t == "integer" && v.kind == 'i',
			t == "integer" && v.kind == 'f' && v.f == math.Trunc(v.f):
			return true
		}
	}
	return false
}

// cmp — the value against a decimal integer bound; a non-number — 0 (the bound does not judge it).
func cmp(v value, bound string) int {
	b, _ := new(big.Int).SetString(bound, 10)
	switch v.kind {
	case 'i':
		if v.huge != 0 {
			return v.huge
		}
		return v.i.Cmp(b)
	case 'f':
		return new(big.Rat).SetFloat64(v.f).Cmp(new(big.Rat).SetInt(b))
	}
	return 0
}

func contains(xs []string, x string) bool {
	for _, y := range xs {
		if y == x {
			return true
		}
	}
	return false
}

// ---------------------------------------------------------------- typed access (the generated readers use these)

func intOf(v value) int64 { return v.i.Int64() }

func floatOf(v value) float64 {
	if v.kind == 'i' {
		f, _ := new(big.Float).SetInt(v.i).Float64()
		return f
	}
	return v.f
}

func textTime(x float64) string {
	s := strconv.FormatFloat(x, 'f', -1, 64)
	if i := strings.IndexByte(s, '.'); i >= 0 && len(s)-i-1 > 3 {
		s = strings.TrimRight(strings.TrimRight(strconv.FormatFloat(x, 'f', 3, 64), "0"), ".")
	}
	return s
}

func textInt(x int64) string { return strconv.FormatInt(x, 10) }
