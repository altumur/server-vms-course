// Runtime of the part families for a lesson whose family schemas go beyond flat rows (ADR-0125 № 5, addendum (5)):
// hand-written environment of tools/normgen/gen_families.py (the schema mode), copied next to the generated
// families.go; DO NOT EDIT in the kit. The schema of each family is data (families.go carries its JSON text); this
// file executes it.
//
// The pass is that of the V7 stack (skills/lesson-spec/scripts/v7/stack.py Family.judge, kind row): the codec of items
// (x-encoding json|jcs, x-codec; Platform/common/data/codec.tsv: the writer strict, the reader tolerant), layer 3
// (x-time, x-integer, x-whole, x-max-bytes, x-max-names, $defs.writer, numbers outside binary64), then JSON Schema
// 2020-12 over the closed set of words of the schemas ($ref, type, enum, pattern — a full match, minLength, maxLength,
// minimum, maximum, exclusiveMinimum, exclusiveMaximum, minItems, maxItems, uniqueItems, items, properties,
// patternProperties, additionalProperties, propertyNames, required, anyOf, allOf, not, if/then/else), the refusal
// places by the dialect (stack.norm): required and additionalProperties — the path of the key, propertyNames — the
// path of the name (nothing below it), uniqueItems — the path of each repeat; the paths are JSON Pointers ordered by
// UTF-8 bytes. The outcome of an unreadable row — OutcomesFor (the V7 rule).
package heartbeat

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"math"
	"math/big"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"sync"
	"unicode/utf16"
	"unicode/utf8"
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

// Outcome — a row of <family>.outcomes.tsv without its prose.
type Outcome struct {
	Path     string
	Reader   string
	Priority int
	Unit     string
	// Wild — the segments «*» of Path (V7, DIALECT § 9): number of the segment → the names of properties of that
	// place; «*» matches any one segment except these names (an author name or any item of a list).
	Wild map[int][]string
}

// Seg — a segment of the key template: a literal, or a placeholder with its grammar.
type Seg struct {
	Lit, Placeholder, Grammar string
}

// Family — a data family of the catalog with its schema as data.
type Family struct {
	Key      string // the key template of the catalog
	Kind     string // row
	Schema   string // the schema path
	Norm     string
	Template []Seg
	Doc      string // the JSON text of the schema
	Outcomes []Outcome
	key      *regexp.Regexp
	once     sync.Once
	sch      *schema
	err      error
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
	return f.JudgeItems(items, mode)
}

// JudgeItems — the reading of items alone (the key is already the family's).
func (f *Family) JudgeItems(items Items, mode Mode) Result {
	f.once.Do(func() { f.sch, f.err = compile(f.Doc) })
	if f.err != nil {
		panic("families: the schema of " + f.Key + ": " + f.err.Error())
	}
	return f.sch.judgeRow(items, mode)
}

// JudgeText — the reading of an object or file family (kind object | file) by its key and text: object — a JSON text
// (not JSON — refused on ""), file — the text in UTF-8 (not UTF-8 — refused on ""); a key not by the template —
// refused on "". For a row family use Judge.
func (f *Family) JudgeText(key string, text []byte, mode Mode) Result {
	if !f.Matches(key) {
		return Result{"refused", []string{""}}
	}
	f.once.Do(func() { f.sch, f.err = compile(f.Doc) })
	if f.err != nil {
		panic("families: the schema of " + f.Key + ": " + f.err.Error())
	}
	return f.sch.judgeText(f.Kind, text, mode)
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

// OutcomesFor — the paths of the outcome rows that act at the reader for these refusal paths (DIALECT § 9, the V7
// rule): for each path the rows whose path is its prefix; when the deepest of them has the unit поле or элемент, only
// the deepest act, else all; of the rows of all paths act those of the least priority, in the order of the file.
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
			if coversWild(o, q) {
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

func coversWild(o Outcome, q string) bool {
	if len(o.Wild) == 0 {
		return covers(o.Path, q)
	}
	if !strings.HasPrefix(q, "/") {
		return false
	}
	ps, qs := unpointer(o.Path), unpointer(q)
	if len(qs) < len(ps) {
		return false
	}
	for i, s := range ps {
		if names, ok := o.Wild[i]; ok {
			if contains(names, qs[i]) {
				return false
			}
		} else if qs[i] != s {
			return false
		}
	}
	return true
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

func contains(xs []string, x string) bool {
	for _, y := range xs {
		if y == x {
			return true
		}
	}
	return false
}

// Pointer — the JSON Pointer of a field of the row.
func Pointer(name string) string {
	return "/" + strings.ReplaceAll(strings.ReplaceAll(name, "~", "~0"), "/", "~1")
}

// ---------------------------------------------------------------- values

// num — a JSON number: an integer (exact) or a binary64; lex — its notation in the text ("" — computed).
type num struct {
	isInt bool
	i     *big.Int
	f     float64
	lex   string
}

// obj — a JSON object (keys unordered: the refusal paths are sorted at the end).
type obj map[string]any

func (n num) rat() *big.Rat {
	if n.isInt {
		return new(big.Rat).SetInt(n.i)
	}
	r := new(big.Rat)
	if math.IsInf(n.f, 0) || math.IsNaN(n.f) {
		return nil
	}
	r.SetFloat64(n.f)
	return r
}

func (n num) float() float64 {
	if n.isInt {
		f, _ := new(big.Float).SetInt(n.i).Float64()
		return f
	}
	return n.f
}

func (n num) finite() bool { return n.isInt || (!math.IsInf(n.f, 0) && !math.IsNaN(n.f)) }

// isInteger — the JSON Schema integer: an int, or a finite float equal to an integer (Draft 2020-12).
func (n num) isInteger() bool {
	if n.isInt {
		return true
	}
	return n.finite() && n.f == math.Trunc(n.f)
}

func cmpNum(a, b num) (int, bool) {
	ra, rb := a.rat(), b.rat()
	if ra == nil || rb == nil {
		fa, fb := a.float(), b.float()
		switch {
		case math.IsNaN(fa) || math.IsNaN(fb):
			return 0, false
		case fa < fb:
			return -1, true
		case fa > fb:
			return 1, true
		}
		return 0, true
	}
	return ra.Cmp(rb), true
}

// equal — jsonschema equal: bool only equals bool; numbers by value (1 == 1.0); lists and objects deep.
func equal(a, b any) bool {
	switch x := a.(type) {
	case nil:
		return b == nil
	case bool:
		y, ok := b.(bool)
		return ok && x == y
	case string:
		y, ok := b.(string)
		return ok && x == y
	case num:
		y, ok := b.(num)
		if !ok {
			return false
		}
		c, ok := cmpNum(x, y)
		return ok && c == 0
	case []any:
		y, ok := b.([]any)
		if !ok || len(x) != len(y) {
			return false
		}
		for i := range x {
			if !equal(x[i], y[i]) {
				return false
			}
		}
		return true
	case obj:
		y, ok := b.(obj)
		if !ok || len(x) != len(y) {
			return false
		}
		for k, v := range x {
			w, has := y[k]
			if !has || !equal(v, w) {
				return false
			}
		}
		return true
	}
	return false
}

var errBad = errors.New("bad")

// strictJSON — JSON by the grammar json of codec.tsv: no NaN, no repeated key; numbers keep their notation. finite —
// a number outside binary64 is a refusal of the text (an encoding place); otherwise it stays (±Inf) for layer 3.
func strictJSON(text string, finite bool) (any, error) {
	dec := json.NewDecoder(strings.NewReader(text))
	dec.UseNumber()
	v, err := strictValue(dec, finite, 0)
	if err != nil {
		return nil, err
	}
	if _, err := dec.Token(); err == nil {
		return nil, errBad
	}
	return v, nil
}

func strictValue(dec *json.Decoder, finite bool, depth int) (any, error) {
	if depth > 900 {
		return nil, errBad
	}
	tok, err := dec.Token()
	if err != nil {
		return nil, errBad
	}
	switch t := tok.(type) {
	case json.Delim:
		switch t {
		case '{':
			o := obj{}
			for dec.More() {
				kt, err := dec.Token()
				if err != nil {
					return nil, errBad
				}
				k, ok := kt.(string)
				if !ok {
					return nil, errBad
				}
				if _, dup := o[k]; dup {
					return nil, errBad
				}
				v, err := strictValue(dec, finite, depth+1)
				if err != nil {
					return nil, err
				}
				o[k] = v
			}
			if _, err := dec.Token(); err != nil {
				return nil, errBad
			}
			return o, nil
		case '[':
			l := []any{}
			for dec.More() {
				v, err := strictValue(dec, finite, depth+1)
				if err != nil {
					return nil, err
				}
				l = append(l, v)
			}
			if _, err := dec.Token(); err != nil {
				return nil, errBad
			}
			return l, nil
		}
		return nil, errBad
	case json.Number:
		return lexNum(string(t), finite)
	case string, bool, nil:
		return t, nil
	}
	return nil, errBad
}

// lexNum — a JSON number literal: an integer literal (no fraction, no exponent) is exact; another — binary64.
func lexNum(t string, finite bool) (any, error) {
	if reInt.MatchString(t) {
		i, ok := new(big.Int).SetString(t, 10)
		if !ok {
			return nil, errBad
		}
		return num{isInt: true, i: i, lex: t}, nil
	}
	f, err := strconv.ParseFloat(t, 64)
	if err != nil {
		var ne *strconv.NumError
		if errors.As(err, &ne) && ne.Err == strconv.ErrRange {
			if finite && math.IsInf(f, 0) {
				return nil, errBad
			}
			return num{f: f, lex: t}, nil // an underflow is 0, an overflow ±Inf — as Python float()
		}
		return nil, errBad
	}
	return num{f: f, lex: t}, nil
}

// ---------------------------------------------------------------- JCS (RFC 8785)

func jcsNumber(n num) (string, error) {
	if n.isInt {
		return n.i.String(), nil
	}
	x := n.f
	if math.IsInf(x, 0) || math.IsNaN(x) {
		return "", errBad
	}
	if x == 0 {
		return "0", nil
	}
	r := strconv.FormatFloat(x, 'e', -1, 64) // the shortest digits: d.ddde±x
	mant, exp, _ := strings.Cut(r, "e")
	e, _ := strconv.Atoi(exp)
	sign := ""
	if strings.HasPrefix(mant, "-") {
		sign, mant = "-", mant[1:]
	}
	digits := strings.TrimRight(strings.Replace(mant, ".", "", 1), "0")
	if digits == "" {
		digits = "0"
	}
	if -7 < e && e < 21 {
		k := e + 1
		switch {
		case k <= 0:
			return sign + "0." + strings.Repeat("0", -k) + digits, nil
		case k >= len(digits):
			return sign + digits + strings.Repeat("0", k-len(digits)), nil
		}
		return sign + digits[:k] + "." + digits[k:], nil
	}
	m := digits[:1]
	if len(digits) > 1 {
		m += "." + digits[1:]
	}
	es := "+"
	if e < 0 {
		es = "-"
		e = -e
	}
	return sign + m + "e" + es + strconv.Itoa(e), nil
}

func jcsString(s string) string {
	var b strings.Builder
	b.WriteByte('"')
	for _, r := range s {
		switch r {
		case '"':
			b.WriteString(`\"`)
		case '\\':
			b.WriteString(`\\`)
		case '\n':
			b.WriteString(`\n`)
		case '\r':
			b.WriteString(`\r`)
		case '\t':
			b.WriteString(`\t`)
		case '\b':
			b.WriteString(`\b`)
		case '\f':
			b.WriteString(`\f`)
		default:
			if r < 0x20 {
				fmt.Fprintf(&b, `\u%04x`, r)
			} else {
				b.WriteRune(r)
			}
		}
	}
	b.WriteByte('"')
	return b.String()
}

func jcs(v any) (string, error) {
	switch x := v.(type) {
	case nil:
		return "null", nil
	case bool:
		if x {
			return "true", nil
		}
		return "false", nil
	case num:
		return jcsNumber(x)
	case string:
		return jcsString(x), nil
	case []any:
		parts := make([]string, len(x))
		for i, e := range x {
			s, err := jcs(e)
			if err != nil {
				return "", err
			}
			parts[i] = s
		}
		return "[" + strings.Join(parts, ",") + "]", nil
	case obj:
		keys := make([]string, 0, len(x))
		for k := range x {
			keys = append(keys, k)
		}
		sort.Slice(keys, func(i, j int) bool { return utf16Less(keys[i], keys[j]) })
		parts := make([]string, len(keys))
		for i, k := range keys {
			s, err := jcs(x[k])
			if err != nil {
				return "", err
			}
			parts[i] = jcsString(k) + ":" + s
		}
		return "{" + strings.Join(parts, ",") + "}", nil
	}
	return "", errBad
}

func utf16Less(a, b string) bool {
	ua, ub := utf16.Encode([]rune(a)), utf16.Encode([]rune(b))
	for i := 0; i < len(ua) && i < len(ub); i++ {
		if ua[i] != ub[i] {
			return ua[i] < ub[i]
		}
	}
	return len(ua) < len(ub)
}

// ---------------------------------------------------------------- the schema

type node = map[string]any

type schema struct {
	doc    node
	writer node
	rx     map[string]*regexp.Regexp
}

func compile(text string) (*schema, error) {
	dec := json.NewDecoder(strings.NewReader(text))
	dec.UseNumber()
	var d node
	if err := dec.Decode(&d); err != nil {
		return nil, err
	}
	s := &schema{doc: d, rx: map[string]*regexp.Regexp{}}
	if defs, ok := d["$defs"].(node); ok {
		if w, ok := defs["writer"].(node); ok {
			s.writer = w
		}
	}
	return s, nil
}

func (s *schema) regex(p string) *regexp.Regexp {
	if r, ok := s.rx[p]; ok {
		return r
	}
	r := regexp.MustCompile(p) // the portable subset (ADR-0092 item 14): `$` matches only at the end, as Python \Z
	s.rx[p] = r
	return r
}

func (s *schema) sub(ref string) node {
	var n any = s.doc
	for _, seg := range strings.Split(strings.TrimPrefix(ref, "#/"), "/") {
		seg = strings.ReplaceAll(strings.ReplaceAll(seg, "~1", "/"), "~0", "~")
		m, ok := n.(node)
		if !ok {
			return nil
		}
		n = m[seg]
	}
	m, _ := n.(node)
	return m
}

// resolve — the nodes of the $ref chain (the place first: its marks weigh more), with allOf references without if.
func (s *schema) resolve(n node) []node {
	var out []node
	for n != nil {
		out = append(out, n)
		if all, ok := n["allOf"].([]any); ok {
			for _, x := range all {
				if xn, ok := x.(node); ok {
					if _, hasRef := xn["$ref"]; hasRef {
						if _, hasIf := xn["if"]; !hasIf {
							out = append(out, s.resolve(xn)...)
						}
					}
				}
			}
		}
		ref, ok := n["$ref"].(string)
		if !ok {
			break
		}
		n = s.sub(ref)
	}
	return out
}

func word(chain []node, k string) (any, bool) {
	for _, n := range chain {
		if v, ok := n[k]; ok {
			return v, true
		}
	}
	return nil, false
}

func truthy(v any, ok bool) bool {
	if !ok {
		return false
	}
	switch x := v.(type) {
	case bool:
		return x
	case nil:
		return false
	case string:
		return x != ""
	case json.Number:
		return x.String() != "0"
	case []any:
		return len(x) > 0
	}
	return true
}

func (s *schema) valid(n node, v any) bool { return len(s.records(n, v, nil, false)) == 0 }

// variant — the node of the chosen variant (allOf of if: {type} / then) or nil.
func (s *schema) variant(chain []node, v any) node {
	for _, n := range chain {
		all, _ := n["allOf"].([]any)
		for _, x := range all {
			xn, ok := x.(node)
			if !ok {
				continue
			}
			ifn, ok := xn["if"].(node)
			then, ok2 := xn["then"].(node)
			if ok && ok2 && len(ifn) == 1 {
				if _, ty := ifn["type"]; ty && s.valid(ifn, v) {
					return then
				}
			}
		}
	}
	return nil
}

// child — the node of the place of key k (an object) or index k (a list); nil — no place or the name is not by form.
func (s *schema) child(chain []node, v any, k any) node {
	for _, n := range chain {
		switch v.(type) {
		case obj:
			key := k.(string)
			if props, ok := n["properties"].(node); ok {
				if c, ok := props[key].(node); ok {
					return c
				}
			}
			if pp, ok := n["patternProperties"].(node); ok {
				for p, c := range pp {
					if s.regex(p).MatchString(key) {
						if cn, ok := c.(node); ok {
							return cn
						}
					}
				}
			}
			if ap, ok := n["additionalProperties"].(node); ok {
				if pn, ok := n["propertyNames"].(node); ok && !s.valid(pn, key) {
					return nil
				}
				return ap
			}
		case []any:
			if it, ok := n["items"].(node); ok {
				return it
			}
		}
	}
	return nil
}

// ---------------------------------------------------------------- JSON Schema: error records (python jsonschema)

type rec struct {
	path  []any
	kw    string
	extra any
}

func isType(v any, ty string) bool {
	switch ty {
	case "null":
		return v == nil
	case "boolean":
		_, ok := v.(bool)
		return ok
	case "string":
		_, ok := v.(string)
		return ok
	case "array":
		_, ok := v.([]any)
		return ok
	case "object":
		_, ok := v.(obj)
		return ok
	case "number":
		_, ok := v.(num)
		return ok
	case "integer":
		n, ok := v.(num)
		return ok && n.isInteger()
	}
	return false
}

func schemaNum(v any) (num, bool) {
	jn, ok := v.(json.Number)
	if !ok {
		return num{}, false
	}
	x, err := lexNum(jn.String(), false)
	if err != nil {
		return num{}, false
	}
	return x.(num), true
}

func schemaValue(v any) any {
	switch x := v.(type) {
	case json.Number:
		n, _ := schemaNum(x)
		return n
	case []any:
		out := make([]any, len(x))
		for i, e := range x {
			out[i] = schemaValue(e)
		}
		return out
	case node:
		o := obj{}
		for k, e := range x {
			o[k] = schemaValue(e)
		}
		return o
	}
	return v
}

func extend(path []any, k any) []any {
	out := make([]any, len(path)+1)
	copy(out, path)
	out[len(path)] = k
	return out
}

// records — the errors of the instance v at path against the schema node n: (path, keyword, data) as py_records;
// inNames — the error is under propertyNames (its records carry the name).
func (s *schema) records(n node, v any, path []any, inNames bool) []rec {
	var out []rec
	add := func(kw string, extra any) { out = append(out, rec{path, kw, extra}) }
	for k, w := range n {
		switch k {
		case "$ref":
			if ref, ok := w.(string); ok {
				if t := s.sub(ref); t != nil {
					out = append(out, s.records(t, v, path, inNames)...)
				}
			}
		case "allOf":
			for _, x := range w.([]any) {
				if xn, ok := x.(node); ok {
					out = append(out, s.records(xn, v, path, inNames)...)
				}
			}
		case "anyOf":
			ok := false
			for _, x := range w.([]any) {
				if xn, isN := x.(node); isN && s.valid(xn, v) {
					ok = true
					break
				}
			}
			if !ok {
				add("anyOf", nil)
			}
		case "oneOf":
			n := 0
			for _, x := range w.([]any) {
				if xn, isN := x.(node); isN && s.valid(xn, v) {
					n++
				}
			}
			if n != 1 {
				add("oneOf", nil) // python-jsonschema: none valid or more than one — one error at the place
			}
		case "not":
			if xn, ok := w.(node); ok && s.valid(xn, v) {
				add("not", nil)
			}
		case "if":
			ifn, _ := w.(node)
			if ifn == nil {
				continue
			}
			if s.valid(ifn, v) {
				if t, ok := n["then"].(node); ok {
					out = append(out, s.records(t, v, path, inNames)...)
				}
			} else if e, ok := n["else"].(node); ok {
				out = append(out, s.records(e, v, path, inNames)...)
			}
		case "type":
			var types []string
			switch t := w.(type) {
			case string:
				types = []string{t}
			case []any:
				for _, x := range t {
					types = append(types, x.(string))
				}
			}
			okT := false
			for _, ty := range types {
				okT = okT || isType(v, ty)
			}
			if !okT {
				add("type", nil)
			}
		case "enum":
			found := false
			for _, e := range w.([]any) {
				if equal(schemaValue(e), v) {
					found = true
					break
				}
			}
			if !found {
				add("enum", nil)
			}
		case "const":
			if !equal(schemaValue(w), v) {
				add("const", nil)
			}
		case "pattern":
			if str, ok := v.(string); ok && !s.regex(w.(string)).MatchString(str) {
				add("pattern", nil)
			}
		case "minLength", "maxLength":
			if str, ok := v.(string); ok {
				lim, _ := schemaNum(w)
				l := int64(utf8.RuneCountInString(str))
				if (k == "minLength" && big.NewInt(l).Cmp(lim.i) < 0) || (k == "maxLength" && big.NewInt(l).Cmp(lim.i) > 0) {
					add(k, nil)
				}
			}
		case "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum":
			x, ok := v.(num)
			lim, ok2 := schemaNum(w)
			if !ok || !ok2 {
				continue
			}
			c, comparable := cmpNum(x, lim)
			if !comparable {
				continue
			}
			bad := (k == "minimum" && c < 0) || (k == "maximum" && c > 0) ||
				(k == "exclusiveMinimum" && c <= 0) || (k == "exclusiveMaximum" && c >= 0)
			if bad {
				add(k, nil)
			}
		case "minItems", "maxItems":
			if l, ok := v.([]any); ok {
				lim, _ := schemaNum(w)
				n := big.NewInt(int64(len(l)))
				if (k == "minItems" && n.Cmp(lim.i) < 0) || (k == "maxItems" && n.Cmp(lim.i) > 0) {
					add(k, nil)
				}
			}
		case "minProperties", "maxProperties":
			if o, ok := v.(obj); ok {
				lim, _ := schemaNum(w)
				n := big.NewInt(int64(len(o)))
				if (k == "minProperties" && n.Cmp(lim.i) < 0) || (k == "maxProperties" && n.Cmp(lim.i) > 0) {
					add(k, nil)
				}
			}
		case "uniqueItems":
			if b, _ := w.(bool); b {
				if l, ok := v.([]any); ok {
					var reps []int
					for i := range l {
						for j := 0; j < i; j++ {
							if equal(l[i], l[j]) {
								reps = append(reps, i)
								break
							}
						}
					}
					if len(reps) > 0 {
						add("uniqueItems", reps)
					}
				}
			}
		case "items":
			if l, ok := v.([]any); ok {
				if it, ok := w.(node); ok {
					for i, e := range l {
						out = append(out, s.records(it, e, extend(path, i), inNames)...)
					}
				} else if b, ok := w.(bool); ok && !b && len(l) > 0 {
					add("items", nil)
				}
			}
		case "properties":
			if o, ok := v.(obj); ok {
				for pk, pw := range w.(node) {
					if e, has := o[pk]; has {
						if pn, ok := pw.(node); ok {
							out = append(out, s.records(pn, e, extend(path, pk), inNames)...)
						}
					}
				}
			}
		case "patternProperties":
			if o, ok := v.(obj); ok {
				for p, pw := range w.(node) {
					for ok2, e := range o {
						if s.regex(p).MatchString(ok2) {
							if pn, ok := pw.(node); ok {
								out = append(out, s.records(pn, e, extend(path, ok2), inNames)...)
							}
						}
					}
				}
			}
		case "additionalProperties":
			o, ok := v.(obj)
			if !ok {
				continue
			}
			var extras []string
			props, _ := n["properties"].(node)
			pp, _ := n["patternProperties"].(node)
			for ek := range o {
				if _, has := props[ek]; has {
					continue
				}
				matched := false
				for p := range pp {
					if s.regex(p).MatchString(ek) {
						matched = true
						break
					}
				}
				if !matched {
					extras = append(extras, ek)
				}
			}
			switch ap := w.(type) {
			case bool:
				if !ap && len(extras) > 0 {
					add("additionalProperties", extras)
				}
			case node:
				for _, ek := range extras {
					out = append(out, s.records(ap, o[ek], extend(path, ek), inNames)...)
				}
			}
		case "propertyNames":
			o, ok := v.(obj)
			pn, ok2 := w.(node)
			if !ok || !ok2 {
				continue
			}
			for name := range o {
				for range s.records(pn, name, path, true) {
					add("propertyNames", name)
				}
			}
		case "required":
			if o, ok := v.(obj); ok {
				var missing []string
				for _, r := range w.([]any) {
					if _, has := o[r.(string)]; !has {
						missing = append(missing, r.(string))
					}
				}
				if len(missing) > 0 {
					add("required", missing)
				}
			}
		}
	}
	if inNames {
		for i := range out {
			out[i].kw = "inNames"
		}
	}
	return out
}

// norm — the records → the refusal paths of the dialect (stack.norm).
func norm(recs []rec) [][]any {
	var out, bad [][]any
	for _, r := range recs {
		switch r.kw {
		case "required":
			for _, k := range r.extra.([]string) {
				out = append(out, extend(r.path, k))
			}
		case "additionalProperties":
			for _, k := range r.extra.([]string) {
				out = append(out, extend(r.path, k))
			}
		case "propertyNames":
			p := extend(r.path, r.extra.(string))
			out = append(out, p)
			bad = append(bad, p)
		case "uniqueItems":
			for _, i := range r.extra.([]int) {
				out = append(out, extend(r.path, i))
			}
		default:
			out = append(out, r.path)
		}
	}
	var keep [][]any
	for _, p := range out {
		below := false
		for _, b := range bad {
			if len(p) > len(b) && samePrefix(p, b) {
				below = true
				break
			}
		}
		if !below {
			keep = append(keep, p)
		}
	}
	return keep
}

func samePrefix(p, b []any) bool {
	for i := range b {
		if fmt.Sprint(p[i]) != fmt.Sprint(b[i]) || isIndex(p[i]) != isIndex(b[i]) {
			return false
		}
	}
	return true
}

func isIndex(x any) bool { _, ok := x.(int); return ok }

func pointer(p []any) string {
	var b strings.Builder
	for _, s := range p {
		b.WriteString("/" + strings.ReplaceAll(strings.ReplaceAll(fmt.Sprint(s), "~", "~0"), "/", "~1"))
	}
	return b.String()
}

func canonical(paths [][]any) []string {
	seen := map[string]bool{}
	var out []string
	for _, p := range paths {
		k := pointer(p)
		if !seen[k] {
			seen[k] = true
			out = append(out, k)
		}
	}
	sort.Slice(out, func(i, j int) bool { return bytes.Compare([]byte(out[i]), []byte(out[j])) < 0 })
	return out
}

// ---------------------------------------------------------------- the codec of items and layer 3

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

func (s *schema) decode(chain []node, text string, mode Mode) (any, error) {
	if enc, ok := word(chain, "x-encoding"); ok && truthy(enc, ok) {
		v, err := strictJSON(text, true)
		if err != nil {
			return nil, err
		}
		if enc == "jcs" && mode == Writer {
			if c, err := jcs(v); err != nil || c != text {
				return nil, errBad
			}
		}
		return v, nil
	}
	codec, _ := word(chain, "x-codec")
	whole := truthy(word(chain, "x-whole"))
	list, _ := codec.([]any)
	for _, ty := range list {
		if v, err := decodeAs(ty.(string), text, mode, whole); err == nil {
			return v, nil
		}
	}
	return nil, errBad
}

func decodeAs(ty, t string, mode Mode, whole bool) (any, error) {
	w := mode == Writer
	switch ty {
	case "string", "any":
		return t, nil
	case "integer":
		if w || whole {
			if !reInt.MatchString(t) {
				return nil, errBad
			}
			i, _ := new(big.Int).SetString(t, 10)
			if w && new(big.Int).Abs(i).Cmp(intMax) > 0 {
				return nil, errBad
			}
			return num{isInt: true, i: i}, nil
		}
		if !reNum.MatchString(t) {
			return nil, errBad
		}
		r, ok := exactRat(t)
		if !ok || !r.IsInt() {
			return nil, errBad
		}
		return num{isInt: true, i: new(big.Int).Set(r.Num())}, nil
	case "number":
		re := reNum
		if w {
			re = reDec
		}
		if !re.MatchString(t) {
			return nil, errBad
		}
		x, err := strconv.ParseFloat(t, 64)
		if (err != nil && !errors.Is(err, strconv.ErrRange)) || math.IsInf(x, 0) {
			return nil, errBad
		}
		if w && plainDecimal(x) != t {
			return nil, errBad
		}
		if reInt.MatchString(t) {
			bi, _ := new(big.Float).SetFloat64(x).Int(nil) // int(float(t)) — as the reference
			return num{isInt: true, i: bi}, nil
		}
		return num{f: x}, nil
	case "boolean":
		if t != "true" && t != "false" {
			return nil, errBad
		}
		return t == "true", nil
	case "time":
		if !reTime[mode].MatchString(t) {
			return nil, errBad
		}
		x, _ := strconv.ParseFloat(t, 64)
		return num{f: x}, nil
	case "array":
		var v []any
		switch {
		case t == "":
			v = []any{}
		case strings.HasPrefix(t, "["):
			j, err := strictJSON(t, false)
			if err != nil {
				return nil, err
			}
			l, ok := j.([]any)
			if !ok {
				return nil, errBad
			}
			v = l
		default:
			for _, p := range strings.Split(t, ",") {
				v = append(v, p)
			}
		}
		if w {
			if lt, ok := listText(v); !ok || lt != t {
				return nil, errBad
			}
		}
		return v, nil
	}
	return nil, errBad
}

// exactRat — the decimal notation as an exact rational (Python Decimal).
func exactRat(t string) (*big.Rat, bool) {
	mant, exp := t, "0"
	if i := strings.IndexAny(t, "eE"); i >= 0 {
		mant, exp = t[:i], t[i+1:]
	}
	r, ok := new(big.Rat).SetString(mant)
	if !ok {
		return nil, false
	}
	e, err := strconv.Atoi(strings.TrimPrefix(exp, "+"))
	if err != nil || e > 100000 || e < -100000 {
		return nil, false
	}
	p := new(big.Rat).SetInt(new(big.Int).Exp(big.NewInt(10), big.NewInt(int64(abs(e))), nil))
	if e >= 0 {
		r.Mul(r, p)
	} else {
		r.Quo(r, p)
	}
	return r, true
}

func abs(x int) int {
	if x < 0 {
		return -x
	}
	return x
}

// plainDecimal — format(Decimal(repr(float(x))), "f") without trailing zeros (stack.plain_decimal).
func plainDecimal(x float64) string {
	r := strconv.FormatFloat(x, 'g', -1, 64) // the shortest repr digits
	rat, ok := exactRat(r)
	if !ok {
		return ""
	}
	s := rat.FloatString(400)
	if strings.Contains(s, ".") {
		s = strings.TrimRight(strings.TrimRight(s, "0"), ".")
	}
	if s == "-0" || s == "" {
		return "0"
	}
	return s
}

func listText(items []any) (string, bool) {
	if len(items) == 0 {
		return "", true
	}
	strs := make([]string, len(items))
	plain := true
	for i, e := range items {
		s, ok := e.(string)
		if !ok || s == "" || strings.Contains(s, ",") {
			plain = false
		}
		strs[i] = s
	}
	if first, ok := items[0].(string); ok && strings.HasPrefix(first, "[") {
		plain = false
	}
	if plain {
		return strings.Join(strs, ","), true
	}
	b, err := pyDumps(items)
	return b, err == nil
}

// pyDumps — json.dumps(items, ensure_ascii=False, separators=(",", ":")) of a list of decoded values.
func pyDumps(v any) (string, error) {
	switch x := v.(type) {
	case nil:
		return "null", nil
	case bool:
		if x {
			return "true", nil
		}
		return "false", nil
	case string:
		return jcsString(x), nil
	case num:
		if x.lex != "" {
			return x.lex, nil
		}
		return jcsNumber(x)
	case []any:
		parts := make([]string, len(x))
		for i, e := range x {
			s, err := pyDumps(e)
			if err != nil {
				return "", err
			}
			parts[i] = s
		}
		return "[" + strings.Join(parts, ",") + "]", nil
	case obj:
		return "", errBad
	}
	return "", errBad
}

func isTime(v any, mode Mode) bool {
	switch x := v.(type) {
	case bool:
		return false
	case num:
		if x.lex != "" {
			if !reTime[mode].MatchString(x.lex) {
				return false
			}
			f, _ := strconv.ParseFloat(x.lex, 64)
			return !math.IsInf(f, 0)
		}
		f := x.float()
		if math.IsInf(f, 0) || math.IsNaN(f) || f < 0 {
			return false
		}
		return mode == Reader || math.Round(f*1000)/1000 == f
	case string:
		return reTime[mode].MatchString(x)
	}
	return false
}

func exactInteger(n num) bool {
	if n.lex == "" {
		return n.isInteger()
	}
	r, ok := exactRat(n.lex)
	return ok && r.IsInt()
}

type place struct {
	path  []any
	chain []node
}

// walk — visit(chain, value, path) gives the new value of the place; then the children of the new value (stack.walk).
func (s *schema) walk(n node, v any, path []any, visit func([]node, any, []any) any) any {
	chain := s.resolve(n)
	if vn := s.variant(chain, v); vn != nil {
		chain = append(chain, s.resolve(vn)...)
	}
	v = visit(chain, v, path)
	switch x := v.(type) {
	case obj:
		if truthy(word(chain, "x-opaque")) {
			return v
		}
		keys := sortedKeys(x)
		for _, k := range keys {
			if c := s.child(chain, x, k); c != nil {
				x[k] = s.walk(c, x[k], extend(path, k), visit)
			}
		}
	case []any:
		for i := range x {
			if c := s.child(chain, x, i); c != nil {
				x[i] = s.walk(c, x[i], extend(path, i), visit)
			}
		}
	}
	return v
}

func sortedKeys(o obj) []string {
	keys := make([]string, 0, len(o))
	for k := range o {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	return keys
}

func (s *schema) limits(chain []node, v any, path []any, fails *[][]any, owner []node) {
	if mb, ok := word(chain, "x-max-bytes"); ok {
		if str, isS := v.(string); isS {
			lim, _ := schemaNum(mb)
			if lim.i != nil && big.NewInt(int64(len(str))).Cmp(lim.i) > 0 {
				*fails = append(*fails, path)
			}
		}
	}
	if mn, ok := word(chain, "x-max-names"); ok {
		if o, isO := v.(obj); isO {
			props := map[string]bool{}
			for _, n := range append(append([]node{}, chain...), owner...) {
				if p, ok := n["properties"].(node); ok {
					for k := range p {
						props[k] = true
					}
				}
			}
			extra := 0
			for k := range o {
				if !props[k] {
					extra++
				}
			}
			lim, _ := schemaNum(mn)
			if lim.i != nil && big.NewInt(int64(extra)).Cmp(lim.i) > 0 {
				*fails = append(*fails, path)
			}
		}
	}
}

func (s *schema) writerPlaces(n node, v any, path []any, out map[string]place) {
	chain := s.resolve(n)
	if vn := s.variant(chain, v); vn != nil {
		chain = append(chain, s.resolve(vn)...)
	}
	for _, c := range chain {
		_, a := c["x-max-bytes"]
		_, b := c["x-max-names"]
		if a || b {
			out[pointer(path)] = place{path, chain}
			break
		}
	}
	switch x := v.(type) {
	case obj:
		for _, k := range sortedKeys(x) {
			if c := s.child(chain, x, k); c != nil {
				s.writerPlaces(c, x[k], extend(path, k), out)
			}
		}
	case []any:
		for i, e := range x {
			if c := s.child(chain, x, i); c != nil {
				s.writerPlaces(c, e, extend(path, i), out)
			}
		}
	}
}

func finite(v any, path []any, fails *[][]any) any {
	switch x := v.(type) {
	case num:
		if !x.finite() {
			*fails = append(*fails, path)
			return nil
		}
	case obj:
		for _, k := range sortedKeys(x) {
			x[k] = finite(x[k], extend(path, k), fails)
		}
	case []any:
		for i := range x {
			x[i] = finite(x[i], extend(path, i), fails)
		}
	}
	return v
}

func at(v any, path []any) (any, bool) {
	for _, s := range path {
		switch x := v.(type) {
		case obj:
			k, ok := s.(string)
			if !ok {
				return nil, false
			}
			e, has := x[k]
			if !has {
				return nil, false
			}
			v = e
		case []any:
			i, ok := s.(int)
			if !ok || i >= len(x) {
				return nil, false
			}
			v = x[i]
		default:
			return nil, false
		}
	}
	return v, true
}

func (s *schema) layer3(v any, mode Mode, decoded map[string]bool, fails *[][]any) any {
	wmap := map[string]place{}
	if mode == Writer && s.writer != nil {
		s.writerPlaces(s.writer, v, nil, wmap)
	}
	mains := map[string][]node{}
	visit := func(chain []node, x any, path []any) any {
		if enc, ok := word(chain, "x-encoding"); ok && truthy(enc, ok) {
			if str, isS := x.(string); isS && !decoded[pointer(path)] {
				d, err := strictJSON(str, true)
				if err == nil && enc == "jcs" && mode == Writer {
					if c, e2 := jcs(d); e2 != nil || c != str {
						err = errBad
					}
				}
				if err != nil {
					*fails = append(*fails, path)
					return nil
				}
				x = d
			}
		}
		if n, ok := x.(num); ok && !n.finite() {
			*fails = append(*fails, path)
			return nil
		}
		if truthy(word(chain, "x-time")) && !isTime(x, mode) {
			*fails = append(*fails, path)
		}
		if truthy(word(chain, "x-integer")) {
			if n, ok := x.(num); ok && !n.isInt && n.isInteger() {
				if mode == Writer || truthy(word(chain, "x-whole")) || !exactInteger(n) {
					*fails = append(*fails, path)
				}
			}
		}
		s.limits(chain, x, path, fails, nil)
		mains[pointer(path)] = chain
		return x
	}
	v = s.walk(s.doc, v, nil, visit)
	v = finite(v, nil, fails)
	for k, p := range wmap {
		x, ok := at(v, p.path)
		if !ok {
			continue
		}
		s.limits(p.chain, x, p.path, fails, mains[k])
	}
	return v
}

// judgeRow — stack.Family.judge for kind row: items → decoded value, layer 3, JSON Schema (and $defs.writer for the
// writer), the refusal places.
func (s *schema) judgeRow(items Items, mode Mode) Result {
	if items == nil {
		return Result{"refused", []string{""}}
	}
	var fails [][]any
	decoded := map[string]bool{}
	root := s.resolve(s.doc)
	value := obj{}
	for k, it := range items {
		value[k] = it.Text
	}
	for _, k := range sortedKeys(value) {
		it := items[k]
		c := s.child(root, value, k)
		if c == nil {
			continue
		}
		if it.NotString {
			fails = append(fails, []any{k})
			delete(value, k)
			continue
		}
		d, err := s.decode(s.resolve(c), it.Text, mode)
		if err != nil {
			fails = append(fails, []any{k})
			delete(value, k)
			continue
		}
		value[k] = d
		decoded[pointer([]any{k})] = true
	}
	for k, it := range items {
		if it.NotString {
			if _, kept := value[k]; kept {
				value[k] = notString(it.Text)
			}
		}
	}
	v := s.layer3(value, mode, decoded, &fails)
	recs := s.records(s.doc, v, nil, false)
	if mode == Writer && s.writer != nil {
		recs = append(recs, s.records(s.writer, v, nil, false)...)
	}
	paths := canonical(append(fails, norm(recs)...))
	if len(paths) == 0 {
		return Result{"ok", []string{}}
	}
	return Result{"refused", paths}
}

// judgeText — stack.Family.judge for kind object (a JSON text) and file (a UTF-8 text).
func (s *schema) judgeText(kind string, text []byte, mode Mode) Result {
	var v any
	switch kind {
	case "object":
		if !utf8.Valid(text) {
			return Result{"refused", []string{""}}
		}
		x, err := strictJSON(string(text), false)
		if err != nil {
			return Result{"refused", []string{""}}
		}
		v = x
	case "file":
		if !utf8.Valid(text) {
			return Result{"refused", []string{""}}
		}
		v = string(text)
	default:
		return Result{"refused", []string{""}}
	}
	var fails [][]any
	v = s.layer3(v, mode, map[string]bool{}, &fails)
	recs := s.records(s.doc, v, nil, false)
	if mode == Writer && s.writer != nil {
		recs = append(recs, s.records(s.writer, v, nil, false)...)
	}
	paths := canonical(append(fails, norm(recs)...))
	if len(paths) == 0 {
		return Result{"ok", []string{}}
	}
	return Result{"refused", paths}
}

// notString — a value of items that is not a JSON string (a text of items only): its JSON value, as the reference
// keeps the parsed non-string value at a place without a schema child.
func notString(text string) any {
	v, err := strictJSON(text, false)
	if err != nil {
		return text
	}
	return v
}
