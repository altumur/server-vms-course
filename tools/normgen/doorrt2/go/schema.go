// Ручная среда тел двери урока (ADR-0125 № 2, P/06 часть 3б): проверка значения JSON по схеме из сборки bodies.go.
//
// Подмножество JSON Schema 2020-12 — ровно слова схем OpenAPI урока: $ref (#/$defs/<имя>), type, enum, const, allOf,
// anyOf, oneOf, not, if/then/else, properties, patternProperties, additionalProperties, unevaluatedProperties,
// propertyNames, required, dependentRequired, minProperties, maxProperties, items, minItems, maxItems, uniqueItems,
// minLength, maxLength, pattern, minimum, maximum, exclusiveMinimum, exclusiveMaximum; аннотации (description,
// format, default, readOnly, contentMediaType, title, examples) не судятся. Числа — по значению (big.Rat), integer —
// математически целое (1.0 — integer, как в 2020-12); длина строки — в символах Unicode.
package apidoor

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
	"unicode/utf8"
)

// Violation — первое нарушение схемы: путь значения (JSON Pointer) и правило.
type Violation struct {
	At   string
	Rule string
}

func (v *Violation) Error() string { return "schema: " + v.Rule + " at " + strconv.Quote(v.At) }

var (
	defsOnce sync.Once
	defs     map[string]any
	rxCache  sync.Map
)

func schemaDefs() map[string]any {
	defsOnce.Do(func() {
		dec := json.NewDecoder(strings.NewReader(bundle))
		dec.UseNumber()
		var root map[string]any
		if err := dec.Decode(&root); err != nil {
			panic("apidoor: the schema bundle is not JSON: " + err.Error())
		}
		defs, _ = root["$defs"].(map[string]any)
	})
	return defs
}

func rx(p string) *regexp.Regexp {
	if r, ok := rxCache.Load(p); ok {
		return r.(*regexp.Regexp)
	}
	r := regexp.MustCompile(p)
	rxCache.Store(p, r)
	return r
}

// Validate — значение v по схеме сборки name; nil — значение схемы.
func Validate(name string, v any) *Violation {
	s, ok := schemaDefs()[name]
	if !ok {
		return &Violation{At: "", Rule: "no schema " + name}
	}
	var errs []Violation
	validate(s, v, "", &errs)
	if len(errs) > 0 {
		return &errs[0]
	}
	return nil
}

// StrictJSON — одно значение JSON без повторов имён и без хвоста; числа — json.Number.
func StrictJSON(b []byte) (any, error) {
	dec := json.NewDecoder(bytes.NewReader(b))
	dec.UseNumber()
	v, err := strictValue(dec, 0)
	if err != nil {
		return nil, err
	}
	if _, err := dec.Token(); err == nil {
		return nil, errors.New("more than one JSON value")
	}
	return v, nil
}

func strictValue(dec *json.Decoder, depth int) (any, error) {
	if depth > 512 {
		return nil, errors.New("too deep")
	}
	t, err := dec.Token()
	if err != nil {
		return nil, err
	}
	switch x := t.(type) {
	case json.Delim:
		switch x {
		case '{':
			m := map[string]any{}
			for dec.More() {
				kt, err := dec.Token()
				if err != nil {
					return nil, err
				}
				k := kt.(string)
				if _, dup := m[k]; dup {
					return nil, fmt.Errorf("repeated name %q", k)
				}
				v, err := strictValue(dec, depth+1)
				if err != nil {
					return nil, err
				}
				m[k] = v
			}
			_, err := dec.Token()
			return m, err
		case '[':
			a := []any{}
			for dec.More() {
				v, err := strictValue(dec, depth+1)
				if err != nil {
					return nil, err
				}
				a = append(a, v)
			}
			_, err := dec.Token()
			return a, err
		}
	}
	return t, nil
}

func num(v any) (*big.Rat, bool) {
	switch x := v.(type) {
	case json.Number:
		r, ok := new(big.Rat).SetString(string(x))
		return r, ok
	case float64:
		r := new(big.Rat)
		if r.SetFloat64(x) == nil {
			return nil, false
		}
		return r, true
	case int:
		return new(big.Rat).SetInt64(int64(x)), true
	case int64:
		return new(big.Rat).SetInt64(x), true
	}
	return nil, false
}

func typeOf(v any) string {
	switch v.(type) {
	case nil:
		return "null"
	case bool:
		return "boolean"
	case string:
		return "string"
	case []any:
		return "array"
	case map[string]any:
		return "object"
	}
	if _, ok := num(v); ok {
		return "number"
	}
	return "?"
}

func isType(v any, t string) bool {
	got := typeOf(v)
	if t == "integer" {
		r, ok := num(v)
		return ok && r.IsInt()
	}
	return got == t
}

func equalJSONValue(a, b any) bool {
	ra, oka := num(a)
	rb, okb := num(b)
	if oka || okb {
		return oka && okb && ra.Cmp(rb) == 0
	}
	switch x := a.(type) {
	case map[string]any:
		y, ok := b.(map[string]any)
		if !ok || len(x) != len(y) {
			return false
		}
		for k, v := range x {
			w, ok := y[k]
			if !ok || !equalJSONValue(v, w) {
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
			if !equalJSONValue(x[i], y[i]) {
				return false
			}
		}
		return true
	}
	return a == b
}

func childPath(at, k string) string {
	return at + "/" + strings.ReplaceAll(strings.ReplaceAll(k, "~", "~0"), "/", "~1")
}

func bound(n any) *big.Rat {
	r, _ := num(n)
	return r
}

// validate — правила узла s над v; → множество свойств объекта v, оценённых этим узлом (для unevaluatedProperties).
func validate(s any, v any, at string, errs *[]Violation) map[string]bool {
	evaluated := map[string]bool{}
	switch b := s.(type) {
	case bool:
		if !b {
			*errs = append(*errs, Violation{at, "false"})
		}
		return evaluated
	case map[string]any:
		n := b
		fail := func(rule string) { *errs = append(*errs, Violation{at, rule}) }
		sub := func(node any) (bool, map[string]bool) {
			var e []Violation
			ev := validate(node, v, at, &e)
			return len(e) == 0, ev
		}
		merge := func(m map[string]bool) {
			for k := range m {
				evaluated[k] = true
			}
		}
		if ref, ok := n["$ref"].(string); ok {
			name := strings.TrimPrefix(ref, "#/$defs/")
			target, ok := schemaDefs()[name]
			if !ok {
				fail("$ref " + ref)
			} else {
				merge(validate(target, v, at, errs))
			}
		}
		if t, ok := n["type"]; ok {
			match := false
			switch tt := t.(type) {
			case string:
				match = isType(v, tt)
			case []any:
				for _, x := range tt {
					if s, _ := x.(string); isType(v, s) {
						match = true
					}
				}
			}
			if !match {
				fail("type")
			}
		}
		if e, ok := n["enum"].([]any); ok {
			found := false
			for _, x := range e {
				if equalJSONValue(x, v) {
					found = true
				}
			}
			if !found {
				fail("enum")
			}
		}
		if c, ok := n["const"]; ok && !equalJSONValue(c, v) {
			fail("const")
		}
		if all, ok := n["allOf"].([]any); ok {
			for _, x := range all {
				merge(validate(x, v, at, errs))
			}
		}
		if any_, ok := n["anyOf"].([]any); ok {
			hit := false
			for _, x := range any_ {
				if good, ev := sub(x); good {
					hit = true
					merge(ev)
				}
			}
			if !hit {
				fail("anyOf")
			}
		}
		if one, ok := n["oneOf"].([]any); ok {
			hits := 0
			var keep map[string]bool
			for _, x := range one {
				if good, ev := sub(x); good {
					hits++
					keep = ev
				}
			}
			if hits != 1 {
				fail("oneOf")
			} else {
				merge(keep)
			}
		}
		if not, ok := n["not"]; ok {
			if good, _ := sub(not); good {
				fail("not")
			}
		}
		if cond, ok := n["if"]; ok {
			if good, ev := sub(cond); good {
				merge(ev)
				if th, ok := n["then"]; ok {
					merge(validate(th, v, at, errs))
				}
			} else if el, ok := n["else"]; ok {
				merge(validate(el, v, at, errs))
			}
		}
		switch x := v.(type) {
		case string:
			l := utf8.RuneCountInString(x)
			if m := bound(n["minLength"]); m != nil && big.NewRat(int64(l), 1).Cmp(m) < 0 {
				fail("minLength")
			}
			if m := bound(n["maxLength"]); m != nil && big.NewRat(int64(l), 1).Cmp(m) > 0 {
				fail("maxLength")
			}
			if p, ok := n["pattern"].(string); ok && !rx(p).MatchString(x) {
				fail("pattern")
			}
		case []any:
			if m := bound(n["minItems"]); m != nil && big.NewRat(int64(len(x)), 1).Cmp(m) < 0 {
				fail("minItems")
			}
			if m := bound(n["maxItems"]); m != nil && big.NewRat(int64(len(x)), 1).Cmp(m) > 0 {
				fail("maxItems")
			}
			if u, _ := n["uniqueItems"].(bool); u {
				for i := range x {
					for j := i + 1; j < len(x); j++ {
						if equalJSONValue(x[i], x[j]) {
							fail("uniqueItems")
							i, j = len(x), len(x)
						}
					}
				}
			}
			if it, ok := n["items"]; ok {
				for i, e := range x {
					validate(it, e, at+"/"+strconv.Itoa(i), errs)
				}
			}
		case map[string]any:
			keys := make([]string, 0, len(x))
			for k := range x {
				keys = append(keys, k)
			}
			sort.Strings(keys)
			if m := bound(n["minProperties"]); m != nil && big.NewRat(int64(len(x)), 1).Cmp(m) < 0 {
				fail("minProperties")
			}
			if m := bound(n["maxProperties"]); m != nil && big.NewRat(int64(len(x)), 1).Cmp(m) > 0 {
				fail("maxProperties")
			}
			if req, ok := n["required"].([]any); ok {
				for _, r := range req {
					if _, has := x[r.(string)]; !has {
						fail("required " + r.(string))
					}
				}
			}
			if dr, ok := n["dependentRequired"].(map[string]any); ok {
				for k, list := range dr {
					if _, has := x[k]; !has {
						continue
					}
					for _, r := range list.([]any) {
						if _, has := x[r.(string)]; !has {
							fail("dependentRequired " + k + " → " + r.(string))
						}
					}
				}
			}
			if pn, ok := n["propertyNames"]; ok {
				for _, k := range keys {
					validate(pn, k, childPath(at, k), errs)
				}
			}
			props, _ := n["properties"].(map[string]any)
			pats, _ := n["patternProperties"].(map[string]any)
			local := map[string]bool{}
			for _, k := range keys {
				if ps, ok := props[k]; ok {
					validate(ps, x[k], childPath(at, k), errs)
					local[k] = true
				}
				for p, ps := range pats {
					if rx(p).MatchString(k) {
						validate(ps, x[k], childPath(at, k), errs)
						local[k] = true
					}
				}
			}
			if ap, ok := n["additionalProperties"]; ok {
				for _, k := range keys {
					if !local[k] {
						validate(ap, x[k], childPath(at, k), errs)
					}
					evaluated[k] = true
				}
			}
			merge(local)
			if up, ok := n["unevaluatedProperties"]; ok {
				for _, k := range keys {
					if !evaluated[k] {
						validate(up, x[k], childPath(at, k), errs)
						evaluated[k] = true
					}
				}
			}
		}
		if r, ok := num(v); ok {
			if m := bound(n["minimum"]); m != nil && r.Cmp(m) < 0 {
				fail("minimum")
			}
			if m := bound(n["maximum"]); m != nil && r.Cmp(m) > 0 {
				fail("maximum")
			}
			if m := bound(n["exclusiveMinimum"]); m != nil && r.Cmp(m) <= 0 {
				fail("exclusiveMinimum")
			}
			if m := bound(n["exclusiveMaximum"]); m != nil && r.Cmp(m) >= 0 {
				fail("exclusiveMaximum")
			}
		}
	}
	return evaluated
}

// mediaType — тип без параметров, в нижнем регистре.
func mediaType(m string) string {
	if i := strings.IndexByte(m, ';'); i >= 0 {
		m = m[:i]
	}
	return strings.ToLower(strings.TrimSpace(m))
}

func isJSONMedia(m string) bool {
	return m == "application/json" || strings.HasSuffix(m, "+json")
}

// DecodeRequest — тело запроса операции op с типом media (Content-Type): объявленный тип, разбор (JSON — строго: одно
// значение, без повторов имён) и проверка по схеме тела. Не-JSON тело — строка байт, по схеме, если она есть.
func DecodeRequest(op Op, media string, body []byte) (any, *Violation) {
	declared := requestSchemas[op]
	if len(declared) == 0 {
		if len(body) == 0 {
			return nil, nil
		}
		return nil, &Violation{At: "", Rule: "the operation takes no body"}
	}
	m := mediaType(media)
	name, ok := declared[m]
	if !ok {
		return nil, &Violation{At: "", Rule: "media type " + strconv.Quote(m) + " is not declared"}
	}
	var v any = string(body)
	if isJSONMedia(m) {
		x, err := StrictJSON(body)
		if err != nil {
			return nil, &Violation{At: "", Rule: "not JSON: " + err.Error()}
		}
		v = x
	}
	if name == "" {
		return v, nil
	}
	return v, Validate(name, v)
}

func responseSchema(op Op, code int, media string) (string, string, *Violation) {
	byCode, ok := responseSchemas[op]
	if !ok {
		return "", "", &Violation{Rule: "no operation"}
	}
	medias, ok := byCode[strconv.Itoa(code)]
	if !ok {
		medias, ok = byCode["default"]
	}
	if !ok {
		return "", "", &Violation{Rule: "code " + strconv.Itoa(code) + " is not declared"}
	}
	m := mediaType(media)
	if m == "" && len(medias) == 1 {
		for k := range medias {
			m = k
		}
	}
	if len(medias) == 0 {
		return "", "", nil
	}
	name, ok := medias[m]
	if !ok {
		return "", "", &Violation{Rule: "media type " + strconv.Quote(m) + " is not declared for " + strconv.Itoa(code)}
	}
	return m, name, nil
}

// CheckResponse — ответ code с телом v объявлен у op (код или default, тип) и v — значение его схемы.
func CheckResponse(op Op, code int, media string, v any) *Violation {
	m, name, viol := responseSchema(op, code, media)
	if viol != nil {
		return viol
	}
	if m == "" {
		if v != nil {
			return &Violation{Rule: "the response has no body"}
		}
		return nil
	}
	if line, ok := ndjsonLines[op][strconv.Itoa(code)]; ok && m == "application/x-ndjson" {
		return checkNDJSON(line, v)
	}
	if !isJSONMedia(m) {
		switch v.(type) {
		case string, []byte:
		default:
			return &Violation{Rule: "a " + m + " body is a string or bytes"}
		}
	}
	if name == "" {
		return nil
	}
	if b, ok := v.([]byte); ok {
		v = string(b)
	}
	if isJSONMedia(m) {
		b, err := json.Marshal(v)
		if err != nil {
			return &Violation{Rule: "not JSON-able: " + err.Error()}
		}
		x, err := StrictJSON(b)
		if err != nil {
			return &Violation{Rule: "not JSON: " + err.Error()}
		}
		v = x
	}
	return Validate(name, v)
}

// EncodeResponse — CheckResponse и байты тела: JSON без экранирования HTML; не-JSON — байты строки.
func EncodeResponse(op Op, code int, media string, v any) ([]byte, *Violation) {
	if viol := CheckResponse(op, code, media, v); viol != nil {
		return nil, viol
	}
	m, _, _ := responseSchema(op, code, media)
	if m == "" {
		return nil, nil
	}
	if _, ok := ndjsonLines[op][strconv.Itoa(code)]; ok && m == "application/x-ndjson" {
		var buf bytes.Buffer
		for _, l := range v.([]any) {
			enc := json.NewEncoder(&buf)
			enc.SetEscapeHTML(false)
			if err := enc.Encode(l); err != nil {
				return nil, &Violation{Rule: err.Error()}
			}
		}
		return buf.Bytes(), nil
	}
	if !isJSONMedia(m) {
		if b, ok := v.([]byte); ok {
			return b, nil
		}
		return []byte(v.(string)), nil
	}
	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	enc.SetEscapeHTML(false)
	if err := enc.Encode(v); err != nil {
		return nil, &Violation{Rule: err.Error()}
	}
	return bytes.TrimSuffix(buf.Bytes(), []byte("\n")), nil
}

type paramSpec struct {
	name, in string
	required bool
	schema   string // имя схемы в сборке ("" — без схемы)
	def      string // умолчание — текст JSON ("" — нет)
	lexeme   *queryLexeme
}

// queryLexeme — x-query-lexeme параметра query (P/05-R022, R031): шаблон текста, затем удаление strip, затем разбор.
type queryLexeme struct {
	pattern string
	parse   string // number | integer | uint64
	strip   string // "" | "_" (только number)
}

var maxUint64 = new(big.Int).SetUint64(^uint64(0))

// lexemeValue — текст по x-query-lexeme: шаблон → strip → number (конечное binary64; исчезновение порядка — 0,
// переполнение — отказ) | integer (точное целое) | uint64 (0…2^64−1, исходный текст); ok false — отказ параметра.
func lexemeValue(l *queryLexeme, raw string) (any, bool) {
	if !rx(l.pattern).MatchString(raw) {
		return nil, false
	}
	text := raw
	if l.strip != "" {
		text = strings.ReplaceAll(text, l.strip, "")
	}
	switch l.parse {
	case "number":
		f, err := strconv.ParseFloat(text, 64)
		if math.IsInf(f, 0) || math.IsNaN(f) || (err != nil && !errors.Is(err, strconv.ErrRange)) {
			return nil, false
		}
		return json.Number(strconv.FormatFloat(f, 'g', -1, 64)), true
	case "integer":
		n, ok := new(big.Int).SetString(text, 10)
		if !ok {
			return nil, false
		}
		return json.Number(n.String()), true
	case "uint64":
		n, ok := new(big.Int).SetString(text, 10)
		if !ok || n.Sign() < 0 || n.Cmp(maxUint64) > 0 {
			return nil, false
		}
		return raw, true
	}
	return nil, false
}

// CheckParams — параметры query и header операции op по их схемам: обязательность, повтор (нарушение), умолчание
// схемы (JSON), приведение текста к типу схемы (number/integer — десятичная запись JSON, boolean — true|false, иначе
// строка). → значения по имени параметра; Violation.At — имя параметра.
func CheckParams(op Op, query map[string][]string, header map[string][]string) (map[string]any, *Violation) {
	out := map[string]any{}
	for _, p := range paramSchemas[op] {
		var vals []string
		if p.in == "query" {
			vals = query[p.name]
		} else {
			for k, v := range header {
				if strings.EqualFold(k, p.name) {
					vals = append(vals, v...)
				}
			}
		}
		v, present, viol := checkParam(p, vals)
		if viol != nil {
			return nil, viol
		}
		if present {
			out[p.name] = v
		}
	}
	return out, nil
}

// CheckParam — один параметр query или header операции op по значениям vals (в порядке запроса): значение (с
// умолчанием схемы, если параметра нет), есть ли оно, нарушение.
func CheckParam(op Op, in, name string, vals []string) (any, bool, *Violation) {
	for _, p := range paramSchemas[op] {
		if p.in == in && strings.EqualFold(p.name, name) {
			return checkParam(p, vals)
		}
	}
	return nil, false, &Violation{At: name, Rule: "not a parameter of the operation"}
}

func checkParam(p paramSpec, vals []string) (any, bool, *Violation) {
	if len(vals) == 0 {
		if p.required {
			return nil, false, &Violation{At: p.name, Rule: "required"}
		}
		if p.def != "" {
			d, _ := StrictJSON([]byte(p.def))
			return d, true, nil
		}
		return nil, false, nil
	}
	if len(vals) > 1 {
		return nil, false, &Violation{At: p.name, Rule: "repeated"}
	}
	v := coerce(p.schema, vals[0])
	if p.lexeme != nil {
		lv, ok := lexemeValue(p.lexeme, vals[0])
		if !ok {
			return nil, false, &Violation{At: p.name, Rule: "x-query-lexeme"}
		}
		v = lv
	}
	if p.schema != "" {
		if viol := Validate(p.schema, v); viol != nil {
			return nil, false, &Violation{At: p.name, Rule: viol.Rule}
		}
	}
	return v, true, nil
}

var numberText = regexp.MustCompile(`^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?$`)

func coerce(schema string, raw string) any {
	s, _ := schemaDefs()[schema].(map[string]any)
	t, _ := s["type"].(string)
	switch t {
	case "number", "integer":
		if numberText.MatchString(raw) {
			return json.Number(raw)
		}
	case "boolean":
		if raw == "true" || raw == "false" {
			return raw == "true"
		}
	}
	return raw
}

// checkNDJSON — тело application/x-ndjson: v — список значений строк, каждая по x-line-schema.
func checkNDJSON(name string, v any) *Violation {
	lines, ok := v.([]any)
	if !ok {
		return &Violation{Rule: "an x-ndjson body is a list of line values"}
	}
	for i, l := range lines {
		b, err := json.Marshal(l)
		if err != nil {
			return &Violation{At: "/" + strconv.Itoa(i), Rule: err.Error()}
		}
		x, _ := StrictJSON(b)
		if viol := Validate(name, x); viol != nil {
			viol.At = "/" + strconv.Itoa(i) + viol.At
			return viol
		}
	}
	return nil
}
