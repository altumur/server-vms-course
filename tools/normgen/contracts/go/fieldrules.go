package contracts

import (
	"fmt"
	"regexp"
	"strconv"
	"strings"
)

// The rules of url fields (the address contract «The field rule and the common vocabulary», «Schemes»): the
// declarations credentials, secret_in, schemes of a field type: url (P/02.1 N1.2a). ReadFieldRules reads them from the
// subset of YAML that the field declarations use (fields.yaml of the vectors secret-in): block mappings and sequences,
// flow mappings and sequences, plain, single- and double-quoted scalars, comments. A loader with its own YAML parser
// builds URLRule directly.

// SchemeRule — the declaration of one scheme: host "authority" (default) | "path"; FragmentNone — `#` is an ordinary
// character; None — the exact authority nodes that mean «no host».
type SchemeRule struct {
	Host         string
	FragmentNone bool
	None         []string
}

// ParamRule — {param, login}: the name patterns (A5); the names of Login are a login, the others a secret.
type ParamRule struct {
	Param []string
	Login []string
}

// RegexRule — a spelling of the manifest (A13): RE2 with the groups login, secret, name; In — the parts (path, query,
// authority, fragment); Schemes — empty is any; Decoded — the part is decoded to a fixed point (default true).
type RegexRule struct {
	Re      *regexp.Regexp
	In      []string
	Schemes []string
	Decoded bool
}

// URLRule — the rule of one field type: url (or the united rule of a catalogue).
type URLRule struct {
	Field   string
	Login   string
	Secret  string
	Schemes map[string]SchemeRule
	Params  []ParamRule
	Regexes []RegexRule
	Nested  []string
}

// Union — the united rule: the param, login, regex and nested of all rules (A8 «The rule»).
func Union(rules ...URLRule) URLRule {
	out := URLRule{}
	for _, r := range rules {
		out.Params = append(out.Params, r.Params...)
		out.Regexes = append(out.Regexes, r.Regexes...)
		out.Nested = append(out.Nested, r.Nested...)
	}
	return out
}

// ReadFieldRules — the url field rules of a declarations file: a mapping field name → declaration (type: url).
// The order is the order of the file.
func ReadFieldRules(data []byte) ([]URLRule, error) {
	v, err := parseYAMLSubset(string(data))
	if err != nil {
		return nil, err
	}
	top, ok := v.(yamlMap)
	if !ok {
		return nil, fmt.Errorf("fields: the root is not a mapping")
	}
	var out []URLRule
	for _, k := range top.keys {
		decl, ok := top.vals[k].(yamlMap)
		if !ok || decl.str("type") != "url" {
			continue
		}
		r := URLRule{Field: k, Schemes: map[string]SchemeRule{}}
		if c, ok := decl.vals["credentials"].(yamlMap); ok {
			r.Login, r.Secret = c.str("login"), c.str("secret")
		}
		if s, ok := decl.vals["schemes"].(yamlMap); ok {
			for _, name := range s.keys {
				d, _ := s.vals[name].(yamlMap)
				sr := SchemeRule{Host: "authority"}
				if h := d.str("host"); h != "" {
					sr.Host = h
				}
				sr.FragmentNone = d.str("fragment") == "none"
				sr.None = strList(d.vals["none"])
				r.Schemes[strings.ToLower(name)] = sr
			}
		}
		items, _ := decl.vals["secret_in"].([]any)
		for _, it := range items {
			m, ok := it.(yamlMap)
			if !ok {
				return nil, fmt.Errorf("fields %s: a secret_in element is not a mapping", k)
			}
			switch {
			case m.has("param"):
				r.Params = append(r.Params, ParamRule{Param: strList(m.vals["param"]), Login: strList(m.vals["login"])})
			case m.has("regex"):
				re, err := regexp.Compile(m.str("regex"))
				if err != nil {
					return nil, fmt.Errorf("fields %s: regex: %v", k, err)
				}
				in := strList(m.vals["in"])
				rr := RegexRule{Re: re, In: in, Schemes: strList(m.vals["schemes"]), Decoded: m.str("decoded") != "false"}
				r.Regexes = append(r.Regexes, rr)
			case m.has("nested"):
				r.Nested = append(r.Nested, strList(m.vals["nested"])...)
			}
		}
		out = append(out, r)
	}
	return out, nil
}

// The YAML subset.

type yamlMap struct {
	keys []string
	vals map[string]any
}

func (m yamlMap) has(k string) bool { _, ok := m.vals[k]; return ok }

func (m yamlMap) str(k string) string {
	s, _ := m.vals[k].(string)
	return s
}

func strList(v any) []string {
	switch x := v.(type) {
	case string:
		return []string{x}
	case []any:
		var out []string
		for _, e := range x {
			if s, ok := e.(string); ok {
				out = append(out, s)
			}
		}
		return out
	}
	return nil
}

type yamlLine struct {
	indent int
	text   string
}

type yamlParser struct {
	lines []yamlLine
	at    int
}

func parseYAMLSubset(src string) (any, error) {
	p := &yamlParser{}
	for _, raw := range strings.Split(src, "\n") {
		t := stripComment(raw)
		if strings.TrimSpace(t) == "" {
			continue
		}
		ind := len(t) - len(strings.TrimLeft(t, " "))
		p.lines = append(p.lines, yamlLine{ind, strings.TrimRight(t[ind:], " \t\r")})
	}
	if len(p.lines) == 0 {
		return yamlMap{vals: map[string]any{}}, nil
	}
	v, err := p.block(p.lines[0].indent)
	if err == nil && p.at != len(p.lines) {
		err = fmt.Errorf("yaml: line %q out of the structure", p.lines[p.at].text)
	}
	return v, err
}

// stripComment drops « #…» outside quotes.
func stripComment(s string) string {
	var q byte
	for i := 0; i < len(s); i++ {
		c := s[i]
		switch {
		case q != 0:
			if c == '\\' && q == '"' {
				i++
			} else if c == q {
				if q == '\'' && i+1 < len(s) && s[i+1] == '\'' {
					i++
				} else {
					q = 0
				}
			}
		case c == '\'' || c == '"':
			if i == 0 || strings.ContainsRune(" [{,:-", rune(s[i-1])) {
				q = c
			}
		case c == '#' && (i == 0 || s[i-1] == ' ' || s[i-1] == '\t'):
			return s[:i]
		}
	}
	return s
}

func (p *yamlParser) block(indent int) (any, error) {
	if strings.HasPrefix(p.lines[p.at].text, "- ") || p.lines[p.at].text == "-" {
		return p.sequence(indent)
	}
	return p.mapping(indent)
}

func (p *yamlParser) sequence(indent int) (any, error) {
	var out []any
	for p.at < len(p.lines) && p.lines[p.at].indent == indent && strings.HasPrefix(p.lines[p.at].text+" ", "- ") {
		rest := strings.TrimSpace(strings.TrimPrefix(p.lines[p.at].text, "-"))
		if rest == "" {
			p.at++
			v, err := p.block(p.lines[p.at].indent)
			if err != nil {
				return nil, err
			}
			out = append(out, v)
			continue
		}
		// «- key: value» opens a mapping at the column of key
		if k, _, ok := splitKey(rest); ok && k != "" && !strings.HasPrefix(rest, "{") && !strings.HasPrefix(rest, "[") {
			col := indent + (len(p.lines[p.at].text) - len(rest))
			p.lines[p.at] = yamlLine{col, rest}
			v, err := p.mapping(col)
			if err != nil {
				return nil, err
			}
			out = append(out, v)
			continue
		}
		v, err := blockValue(rest)
		if err != nil {
			return nil, err
		}
		out = append(out, v)
		p.at++
	}
	return out, nil
}

func (p *yamlParser) mapping(indent int) (any, error) {
	m := yamlMap{vals: map[string]any{}}
	for p.at < len(p.lines) && p.lines[p.at].indent == indent {
		line := p.lines[p.at].text
		k, rest, ok := splitKey(line)
		if !ok {
			return nil, fmt.Errorf("yaml: not a key line %q", line)
		}
		if _, dup := m.vals[k]; dup {
			return nil, fmt.Errorf("yaml: a repeated key %q", k)
		}
		p.at++
		var v any
		var err error
		if rest == "" {
			if p.at < len(p.lines) && (p.lines[p.at].indent > indent ||
				(p.lines[p.at].indent == indent && strings.HasPrefix(p.lines[p.at].text, "- "))) {
				v, err = p.block(p.lines[p.at].indent)
			}
		} else {
			v, err = blockValue(rest)
		}
		if err != nil {
			return nil, err
		}
		m.keys = append(m.keys, k)
		m.vals[k] = v
	}
	return m, nil
}

// splitKey — «key: rest» with a plain or quoted key.
func splitKey(line string) (string, string, bool) {
	if line == "" {
		return "", "", false
	}
	if line[0] == '\'' || line[0] == '"' {
		s, n, err := quoted(line)
		if err != nil || !strings.HasPrefix(line[n:], ":") {
			return "", "", false
		}
		return s, strings.TrimSpace(line[n+1:]), true
	}
	for i := 0; i < len(line); i++ {
		if line[i] == ':' && (i+1 == len(line) || line[i+1] == ' ') {
			return strings.TrimSpace(line[:i]), strings.TrimSpace(line[i+1:]), true
		}
		if line[i] == '{' || line[i] == '[' {
			return "", "", false
		}
	}
	return "", "", false
}

func quoted(s string) (string, int, error) {
	q := s[0]
	var b strings.Builder
	for i := 1; i < len(s); i++ {
		c := s[i]
		if q == '\'' {
			if c == '\'' {
				if i+1 < len(s) && s[i+1] == '\'' {
					b.WriteByte('\'')
					i++
					continue
				}
				return b.String(), i + 1, nil
			}
			b.WriteByte(c)
			continue
		}
		if c == '"' {
			v, err := strconv.Unquote(s[:i+1])
			return v, i + 1, err
		}
		if c == '\\' {
			i++
		}
	}
	return "", 0, fmt.Errorf("yaml: an unclosed quote")
}

// blockValue — the value after «key:» or «-» on its line: a flow collection, a quoted scalar or a plain scalar to
// the end of the line (in the block context «,», «[», «]» are ordinary characters).
func blockValue(s string) (any, error) {
	switch s[0] {
	case '[', '{':
		return flowValue(s)
	case '\'', '"':
		v, n, err := quoted(s)
		if err == nil && strings.TrimSpace(s[n:]) != "" {
			err = fmt.Errorf("yaml: extra text after a quoted scalar")
		}
		return v, err
	}
	return s, nil
}

func flowValue(s string) (any, error) {
	v, n, err := flowParse(s, 0)
	if err != nil {
		return nil, err
	}
	if strings.TrimSpace(s[n:]) != "" {
		return nil, fmt.Errorf("yaml: extra text %q", s[n:])
	}
	return v, nil
}

func skipSpace(s string, i int) int {
	for i < len(s) && s[i] == ' ' {
		i++
	}
	return i
}

func flowParse(s string, i int) (any, int, error) {
	i = skipSpace(s, i)
	if i >= len(s) {
		return "", i, nil
	}
	switch s[i] {
	case '[':
		var out []any
		i = skipSpace(s, i+1)
		if i < len(s) && s[i] == ']' {
			return []any{}, i + 1, nil
		}
		for {
			v, n, err := flowParse(s, i)
			if err != nil {
				return nil, 0, err
			}
			out = append(out, v)
			i = skipSpace(s, n)
			if i < len(s) && s[i] == ',' {
				i++
				continue
			}
			if i < len(s) && s[i] == ']' {
				return out, i + 1, nil
			}
			return nil, 0, fmt.Errorf("yaml: a flow sequence is not closed")
		}
	case '{':
		m := yamlMap{vals: map[string]any{}}
		i = skipSpace(s, i+1)
		if i < len(s) && s[i] == '}' {
			return m, i + 1, nil
		}
		for {
			kv, n, err := flowScalar(s, i, true)
			if err != nil {
				return nil, 0, err
			}
			i = skipSpace(s, n)
			if i >= len(s) || s[i] != ':' {
				return nil, 0, fmt.Errorf("yaml: a flow key without «:»")
			}
			v, n2, err := flowParse(s, i+1)
			if err != nil {
				return nil, 0, err
			}
			m.keys = append(m.keys, kv)
			m.vals[kv] = v
			i = skipSpace(s, n2)
			if i < len(s) && s[i] == ',' {
				i = skipSpace(s, i+1)
				continue
			}
			if i < len(s) && s[i] == '}' {
				return m, i + 1, nil
			}
			return nil, 0, fmt.Errorf("yaml: a flow mapping is not closed")
		}
	}
	v, n, err := flowScalar(s, i, false)
	return v, n, err
}

func flowScalar(s string, i int, key bool) (string, int, error) {
	i = skipSpace(s, i)
	if i < len(s) && (s[i] == '\'' || s[i] == '"') {
		v, n, err := quoted(s[i:])
		return v, i + n, err
	}
	j := i
	for j < len(s) {
		c := s[j]
		if c == ',' || c == ']' || c == '}' {
			break
		}
		if c == ':' && (key || j+1 == len(s) || s[j+1] == ' ' || s[j+1] == ',') {
			break
		}
		j++
	}
	return strings.TrimSpace(s[i:j]), j, nil
}
