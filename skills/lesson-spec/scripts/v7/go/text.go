// Слой 1 В7 на Go (ADR-0092 п. 2): готовый парсер YAML 1.2 (go.yaml.in/yaml/v3 v3.0.5, узлы) и тонкая проверка —
// те же правила, что v7/textv7.py (байты, TAB только в комментарии, один документ по байтам, корень — блочное
// отображение с колонки 1, якорь, псевдоним, `<<`, тег, повтор ключа, ключ-коллекция, глубина > 64, Н1.1:95 и :46,
// `{k:}`, скаляры по scalars.tsv по стилю узла).
package main

import (
	"bufio"
	"fmt"
	"math"
	"os"
	"regexp"
	"strconv"
	"strings"
	"unicode/utf8"

	"go.yaml.in/yaml/v3"
)

const maxDepth = 64

type textRefused struct {
	Rule string `json:"rule"`
	Line int    `json:"line"`
	Msg  string `json:"msg"`
	Path []any  `json:"path"`
}

func (e *textRefused) Error() string { return fmt.Sprintf("%s line %d: %s", e.Rule, e.Line, e.Msg) }

type scalarRow struct {
	kind string
	re   *regexp.Regexp
}

var (
	scalarRows []scalarRow
	intMax     int64
	floatMax   float64
)

// loadScalars — таблица скаляров P/02.1 (`02.1-installer.scalars.tsv`): первая совпавшая строка сверху.
func loadScalars(path string) error {
	f, err := os.Open(path)
	if err != nil {
		return err
	}
	defer f.Close()
	scalarRows = nil
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		line := sc.Text()
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		cols := strings.Split(line, "\t")
		if len(cols) != 3 || cols[0] == "kind" {
			continue
		}
		if cols[0] == "limit" {
			k, v, _ := strings.Cut(cols[1], "=")
			if k == "int_max" {
				intMax, _ = strconv.ParseInt(v, 10, 64)
			} else {
				floatMax, _ = strconv.ParseFloat(v, 64)
			}
			continue
		}
		re, err := regexp.Compile(`^(?s:` + cols[1] + `)$`)
		if err != nil {
			return err
		}
		scalarRows = append(scalarRows, scalarRow{cols[0], re})
	}
	return sc.Err()
}

func kindOf(s string) string {
	for _, r := range scalarRows {
		if r.re.MatchString(s) {
			return r.kind
		}
	}
	return "string"
}

func badRune(r rune) bool {
	return (r < 0x20 && r != '\t' && r != '\n' && r != '\r') || (r >= 0x7f && r <= 0x9f) || r == 0xfffe ||
		r == 0xffff || r == 0x2028 || r == 0x2029 || (r >= 0xd800 && r <= 0xdfff)
}

func firstBad(s string) (rune, int) {
	for i, r := range s {
		if badRune(r) {
			return r, i
		}
	}
	return 0, -1
}

const escapes = "0abt\tnvfre \"/\\N_LPxuU"

// scanLine — лексика строки для тонкой проверки (как v7/textv7.py scan_line): колонка `#`, начинающего комментарий
// (в начале строки или после пробела/TAB, вне кавычек), или -1; ошибка — `#` вплотную после закрывающей кавычки или
// `]`/`}` (SU5Z), экранирование вне YAML 1.2.2 в двойных кавычках (HRE5).
func scanLine(line string) (int, string, map[int]bool) {
	rs := []rune(line)
	q := ""
	prev, esc := ' ', false
	tabs := map[int]bool{} // байтовые колонки TAB экранирования `\<TAB>` в двойных кавычках (YAML 1.2.2, Н1.1)
	for i, c := range rs {
		var nxt rune
		if i+1 < len(rs) {
			nxt = rs[i+1]
		}
		switch {
		case q == "\"":
			if esc {
				if !strings.ContainsRune(escapes, c) {
					return -1, "escape \\" + string(c) + " outside YAML 1.2.2", tabs
				}
				if c == '\t' {
					tabs[len(string(rs[:i]))] = true
				}
				esc = false
			} else if c == '\\' {
				esc = true
			} else if c == '"' {
				q = ""
				if nxt == '#' {
					return -1, "comment without a space after a quoted scalar", tabs
				}
			}
		case q == "'":
			if c == '\'' {
				if nxt == '\'' {
					q = "''"
				} else {
					q = ""
					if nxt == '#' {
						return -1, "comment without a space after a quoted scalar", tabs
					}
				}
			}
		case q == "''":
			q = "'"
		case (c == '"' || c == '\'') && strings.ContainsRune(" \t[{,:-?", prev):
			q = string(c)
		case (c == ']' || c == '}') && nxt == '#':
			return -1, "comment without a space after a flow collection", tabs
		case c == '#' && (prev == ' ' || prev == '\t'):
			return len(string(rs[:i])), "", tabs
		}
		prev = c
	}
	return -1, "", tabs
}

// slashEscapes — `\/` в двойных кавычках → `/` (YAML 1.2.2 и Н1.1 допускают `\/`, go.yaml.in/yaml/v3 v3.0.5 — нет:
// yaml-test-suite 3UYS, дефект D13); кавычки — по той же лексике, что scanLine.
func slashEscapes(line string) string {
	if !strings.Contains(line, `\/`) {
		return line
	}
	rs := []rune(line)
	var b strings.Builder
	q := ""
	prev, esc := ' ', false
	for _, c := range rs {
		switch {
		case q == "\"":
			if esc {
				esc = false
				if c == '/' {
					b.WriteRune('/')
					prev = c
					continue
				}
				b.WriteRune('\\')
			} else if c == '\\' {
				esc = true
				prev = c
				continue
			} else if c == '"' {
				q = ""
			}
		case q == "'":
			if c == '\'' {
				q = ""
			}
		case (c == '"' || c == '\'') && strings.ContainsRune(" \t[{,:-?", prev):
			q = string(c)
		}
		b.WriteRune(c)
		prev = c
	}
	return b.String()
}

// blockLeadingOK — блочный скаляр с заголовком на строке at (с 0): начальные пустые строки тела не глубже первой
// строки содержимого (S98Z).
func blockLeadingOK(lines []string, at int) bool {
	indent := func(s string) int { return len(s) - len(strings.TrimLeft(s, " ")) }
	base := indent(lines[at])
	lead := -1
	for _, ln := range lines[at+1:] {
		if strings.TrimSpace(ln) == "" {
			if len(ln) > lead {
				lead = len(ln)
			}
			continue
		}
		ind := indent(ln)
		if ind <= base {
			return lead < 0 || lead <= base
		}
		return lead < 0 || lead <= ind
	}
	return true
}

var (
	reDocEnd   = regexp.MustCompile(`^\.\.\.(\s|$)`)
	reDocStart = regexp.MustCompile(`^---(\s|$)`)
	reDocShift = regexp.MustCompile(`^\s+---(\s|$)`)
	reIndent   = regexp.MustCompile(`^[|>][-+]?[0-9]|^[|>][0-9]`)
	reHeader   = regexp.MustCompile(`^[|>][-+]?(\s|$)`)
)

func checkBytes(data []byte) (string, []string, *textRefused) {
	lineAt := func(i int) int { return strings.Count(string(data[:i]), "\n") + 1 }
	if !utf8.Valid(data) {
		i := 0
		for i < len(data) {
			r, n := utf8.DecodeRune(data[i:])
			if r == utf8.RuneError && n <= 1 {
				break
			}
			i += n
		}
		return "", nil, &textRefused{"bytes", lineAt(i), "not UTF-8", nil}
	}
	text := string(data)
	if strings.HasPrefix(text, "\ufeff") {
		return "", nil, &textRefused{"bytes", 1, "BOM", nil}
	}
	if r, i := firstBad(text); i >= 0 {
		return "", nil, &textRefused{"bytes", lineAt(i), fmt.Sprintf("character U+%04X", r), nil}
	}
	for i := strings.IndexByte(text, '\r'); i >= 0; {
		if i+1 >= len(text) || text[i+1] != '\n' {
			return "", nil, &textRefused{"bytes", lineAt(i), "lone CR", nil}
		}
		j := strings.IndexByte(text[i+1:], '\r')
		if j < 0 {
			break
		}
		i += 1 + j
	}
	text = strings.ReplaceAll(text, "\r\n", "\n")
	if text != "" && !strings.HasSuffix(text, "\n") {
		text += "\n" // обход D16: последняя строка без LF — с LF (значение по YAML 1.2.2)
	}
	lines := strings.Split(text, "\n")
	content := false
	for n, ln := range lines {
		no := n + 1
		c, lerr, escTabs := scanLine(ln)
		if lerr != "" {
			return "", nil, &textRefused{"lexis", no, lerr, nil}
		}
		for t := 0; t < len(ln); t++ {
			if ln[t] == '\t' && !escTabs[t] && (c < 0 || t < c) {
				return "", nil, &textRefused{"tab", no, "TAB outside a comment (ADR-0092 п. 4)", nil}
			}
		}
		if reDocEnd.MatchString(ln) {
			return "", nil, &textRefused{"document", no, "`...` (Н1.1:46)", nil}
		}
		if strings.HasPrefix(ln, "%") {
			return "", nil, &textRefused{"document", no, "directive `%` (Н1.1:46)", nil}
		}
		if reDocStart.MatchString(ln) {
			if content {
				return "", nil, &textRefused{"document", no, "second document or `---` after content", nil}
			}
			content = true // содержимое на строке `---` отказывают парсер или правило root
			continue
		}
		if reDocShift.MatchString(ln) {
			return "", nil, &textRefused{"document", no, "`---` not at column 1", nil}
		}
		if s := strings.TrimSpace(ln); s != "" && !strings.HasPrefix(s, "#") {
			content = true
		}
	}
	for i, ln := range lines {
		lines[i] = slashEscapes(ln)
	}
	return strings.Join(lines, "\n"), lines, nil
}

type textOut struct {
	tree    strings.Builder
	numbers [][2]any
	empties [][]any
	lines   []string
}

func (o *textOut) refuse(rule string, n *yaml.Node, msg string, path []any) *textRefused {
	return &textRefused{rule, n.Line, msg, append([]any{}, path...)}
}

const quoted = yaml.DoubleQuotedStyle | yaml.SingleQuotedStyle

func (o *textOut) common(n *yaml.Node, path []any) *textRefused {
	if n.Kind == yaml.AliasNode {
		return o.refuse("alias", n, "alias `*`", path)
	}
	if n.Anchor != "" {
		return o.refuse("anchor", n, "anchor `&`", path)
	}
	if n.Style&yaml.TaggedStyle != 0 {
		return o.refuse("tag", n, "tag `!…`", path)
	}
	return nil
}

// spanOneLine — от знака открытия (строка, колонка с 1) до парного закрытия — на одной строке (Н1.1:95).
func (o *textOut) spanOneLine(n *yaml.Node) bool {
	ln := o.lines[n.Line-1]
	runes := []rune(ln)
	i := n.Column - 1
	if i < 0 || i >= len(runes) {
		return true
	}
	open := runes[i]
	if !strings.ContainsRune("[{\"'", open) {
		return true // пара `k: v` в потоковом списке — отображение без скобок, одной строкой по YAML
	}
	depth := 0
	prev := ' '

	var q rune
	esc := false
	for ; i < len(runes); i++ {
		c := runes[i]
		switch {
		case q == '"':
			if esc {
				esc = false
			} else if c == '\\' {
				esc = true
			} else if c == '"' {
				q = 0
				if open == '"' {
					return true
				}
			}
		case q == '\'':
			if c == '\'' {
				if i+1 < len(runes) && runes[i+1] == '\'' {
					i++
					continue
				}
				q = 0
				if open == '\'' {
					return true
				}
			}
		case (c == '"' || c == '\'') && (i == n.Column-1 || strings.ContainsRune(" \t[{,:", prev)):
			q = c
		case c == '[' || c == '{':
			depth++
		case c == ']' || c == '}':
			depth--
			if depth == 0 {
				return true
			}
		}
		prev = c
	}
	return false
}

func (o *textOut) node(n *yaml.Node, path []any, depth int) *textRefused {
	if e := o.common(n, path); e != nil {
		return e
	}
	switch n.Kind {
	case yaml.MappingNode, yaml.SequenceNode:
		if depth > maxDepth {
			return o.refuse("depth", n, "nesting deeper than 64", path)
		}
		if n.Style&yaml.FlowStyle != 0 && !o.spanOneLine(n) {
			return o.refuse("rare", n, "flow collection on several lines (Н1.1:95)", path)
		}
		if n.Kind == yaml.SequenceNode {
			o.tree.WriteByte('[')
			for i, c := range n.Content {
				if i > 0 {
					o.tree.WriteByte(',')
				}
				if e := o.node(c, with(path, i), depth+1); e != nil {
					return e
				}
			}
			o.tree.WriteByte(']')
			return nil
		}
		return o.mapping(n, path, depth)
	case yaml.ScalarNode:
		return o.scalar(n, path)
	}
	return o.refuse("parser", n, "unexpected node", path)
}

func (o *textOut) mapping(n *yaml.Node, path []any, depth int) *textRefused {
	seen := map[string]bool{}
	o.tree.WriteByte('{')
	flow := n.Style&yaml.FlowStyle != 0
	for i := 0; i+1 < len(n.Content); i += 2 {
		k, v := n.Content[i], n.Content[i+1]
		if e := o.common(k, path); e != nil {
			return e
		}
		if k.Kind != yaml.ScalarNode {
			return o.refuse("key", k, "a key is a collection", path)
		}
		before := strings.TrimRight(string([]rune(o.lines[k.Line-1])[:k.Column-1]), " \t")
		if before == "?" || (strings.HasSuffix(before, "?") && strings.ContainsRune(" \t-[{,", []rune(before)[len([]rune(before))-2])) {
			return o.refuse("rare", k, "complex key `? …` (Н1.1:95)", path)
		}
		if k.Style&(quoted|yaml.LiteralStyle|yaml.FoldedStyle) == 0 {
			if k.Value == "<<" {
				return o.refuse("merge", k, "merge key `<<`", path)
			}
			if kd := kindOf(k.Value); kd != "string" {
				return o.refuse("key", k, "a plain key read as "+kd, with(path, k.Value))
			}
		} else if e := o.scalarStyle(k, path); e != nil {
			return e
		}
		if r, i := firstBad(k.Value); i >= 0 {
			return o.refuse("bytes", k, fmt.Sprintf("character U+%04X in a value", r), path)
		}
		if seen[k.Value] {
			return o.refuse("duplicate", k, fmt.Sprintf("key %q said twice", k.Value), with(path, k.Value))
		}
		seen[k.Value] = true
		if flow && v.Kind == yaml.ScalarNode && v.Style&(quoted|yaml.LiteralStyle|yaml.FoldedStyle) == 0 &&
			v.Value == "" && v.Line == k.Line {
			return o.refuse("flow", v, "`{k:}` — key without a value in a flow mapping (ADR-0092 п. 4)",
				with(path, k.Value))
		}
		if i > 0 {
			o.tree.WriteByte(',')
		}
		o.tree.WriteString(jsonString(k.Value))
		o.tree.WriteByte(':')
		if e := o.node(v, with(path, k.Value), depth+1); e != nil {
			return e
		}
	}
	o.tree.WriteByte('}')
	return nil
}

func (o *textOut) scalarStyle(n *yaml.Node, path []any) *textRefused {
	if n.Style&quoted != 0 && !o.spanOneLine(n) {
		return o.refuse("rare", n, "quoted string on several lines (Н1.1:95)", path)
	}
	if n.Style&(yaml.LiteralStyle|yaml.FoldedStyle) != 0 {
		if strings.ContainsRune(n.Value, '\t') {
			return o.refuse("tab", n, "TAB in a block scalar (ADR-0092 п. 4)", path)
		}
		head := string([]rune(o.lines[n.Line-1])[n.Column-1:])
		if reIndent.MatchString(head) {
			return o.refuse("rare", n, "explicit indentation indicator (Н1.1:95)", path)
		}
		if !reHeader.MatchString(head) {
			return o.refuse("lexis", n, "block scalar header without a space before a comment (X4QW)", path)
		}
		if !blockLeadingOK(o.lines, n.Line-1) {
			return o.refuse("lexis", n, "leading empty line deeper than the first content line (S98Z)", path)
		}
	}
	return nil
}

var reMantissaNonzero = regexp.MustCompile(`[1-9]`)

func (o *textOut) scalar(n *yaml.Node, path []any) *textRefused {
	if r, i := firstBad(n.Value); i >= 0 {
		return o.refuse("bytes", n, fmt.Sprintf("character U+%04X in a value", r), path)
	}
	if n.Style&(quoted|yaml.LiteralStyle|yaml.FoldedStyle) != 0 {
		if e := o.scalarStyle(n, path); e != nil {
			return e
		}
		o.tree.WriteString(jsonString(n.Value))
		return nil
	}
	s := n.Value
	p := append([]any{}, path...)
	if s == "" {
		o.empties = append(o.empties, p)
		o.tree.WriteString("null")
		return nil
	}
	switch kindOf(s) {
	case "null":
		o.tree.WriteString("null")
	case "true":
		o.tree.WriteString("true")
	case "false":
		o.tree.WriteString("false")
	case "int":
		digits := strings.TrimLeft(strings.TrimLeft(s, "+-"), "0")
		v, err := strconv.ParseInt(strings.TrimPrefix(s, "+"), 10, 64)
		if len(digits) > 16 || err != nil || v > intMax || v < -intMax {
			o.numbers = append(o.numbers, [2]any{p, s})
			o.tree.WriteString("null")
			return nil
		}
		o.tree.WriteString(strconv.FormatInt(v, 10))
	case "float":
		x, _ := strconv.ParseFloat(s, 64)
		mant := strings.SplitN(strings.ToLower(s), "e", 2)[0]
		if math.IsInf(x, 0) || math.IsNaN(x) || math.Abs(x) > floatMax || (x == 0 && reMantissaNonzero.MatchString(mant)) {
			o.numbers = append(o.numbers, [2]any{p, s})
			o.tree.WriteString("null")
			return nil
		}
		f := strconv.FormatFloat(x, 'g', -1, 64)
		if !strings.ContainsAny(f, ".eE") {
			f += ".0"
		}
		o.tree.WriteString(f)
	case "nonfinite":
		o.numbers = append(o.numbers, [2]any{p, s})
		o.tree.WriteString("null")
	default:
		o.tree.WriteString(jsonString(s))
	}
	return nil
}

func with(path []any, x any) []any {
	return append(append(make([]any, 0, len(path)+1), path...), x)
}

func jsonString(s string) string {
	var b strings.Builder
	b.WriteByte('"')
	for _, r := range s {
		switch {
		case r == '"' || r == '\\':
			b.WriteByte('\\')
			b.WriteRune(r)
		case r < 0x20:
			fmt.Fprintf(&b, "\\u%04x", r)
		default:
			b.WriteRune(r)
		}
	}
	b.WriteByte('"')
	return b.String()
}

// loadText — байты манифеста → (дерево JSON в порядке автора, numbers, empties) или отказ text.
func loadText(data []byte) (string, [][2]any, [][]any, *textRefused) {
	text, lines, e := checkBytes(data)
	if e != nil {
		return "", nil, nil, e
	}
	var doc yaml.Node
	if err := yaml.Unmarshal([]byte(text), &doc); err != nil {
		return "", nil, nil, &textRefused{"parser", 0, err.Error(), nil}
	}
	if doc.Kind != yaml.DocumentNode || len(doc.Content) == 0 {
		return "", nil, nil, &textRefused{"root", 1, "empty file", nil}
	}
	root := doc.Content[0]
	if root.Kind != yaml.MappingNode || root.Style&yaml.FlowStyle != 0 || root.Column != 1 {
		return "", nil, nil, &textRefused{"root", root.Line, "the root is a block mapping from column 1", nil}
	}
	o := &textOut{lines: lines}
	if e := o.node(root, []any{}, 1); e != nil {
		return "", nil, nil, e
	}
	return o.tree.String(), o.numbers, o.empties, nil
}
