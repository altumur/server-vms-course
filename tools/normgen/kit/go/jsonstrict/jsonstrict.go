// Package jsonstrict parses POST /v1/write JSON per P/01.1 N2.1 (ADR-0083 addendum 86, item 2).
// Handwritten once;test_kit.py checks write-checks probes and lesson JCS vectors.
//
// RFC 8259:reject duplicate names in any object;count object/array depth from root1;reject BOM, NaN,
// Infinity and invalid UTF-8. Replace lone surrogate escapes with U+FFFD and record their JSON Pointers.
// Every parse refusal is400badrequest. Values follow the checks runtime model.
// nil, bool, int64, float64, string, []any, map[string]any.
package jsonstrict

import (
	"bytes"
	"fmt"
	"sort"
	"strconv"
	"strings"
	"unicode/utf8"
)

// Depth is P/01.1 N2.1 JSON_DEPTH:128 nested objects/arrays including root;129 refuses.
const Depth = 128

// Error.Reason is journal-only;do not quote supplied input back to callers (P/01.1 N4).
const (
	ReasonBOM       = "bom"             // Body starts with EF BB BF.
	ReasonUTF8      = "utf8"            // Body bytes are not UTF-8 (RFC 8259 section8.1).
	ReasonNonFinite = "nan_or_infinity" // NaN, Infinity and -Infinity are not JSON.
	ReasonSyntax    = "syntax"          // Other RFC 8259 grammar violation, empty body or trailing data.
	ReasonDuplicate = "duplicate_name"  // Duplicate field name within one object (RFC 8259 section4).
	ReasonDepth     = "depth"           // Depth exceeds the limit.
)

// Error is a400badrequest parse refusal with reason and byte offset (P/01.1 N2.1).
type Error struct {
	Code   int
	Kind   string
	Reason string
	Offset int
}

func (e *Error) Error() string {
	return fmt.Sprintf("jsonstrict: %s at byte %d", e.Reason, e.Offset)
}

var bom = []byte{0xEF, 0xBB, 0xBF}

// Decode returns checks-compatible Body values:int64 for lexical integers in range, otherwise float64.
// Binary64 overflow yields infinity, rejected by field checks rather than parsing because extra-field
// numbers are ignored under N2.1. Replace lone surrogates with U+FFFD. lone records each affected value's
// RFC 6901 pointer, or containing-object pointer for a field name, sorted and deduplicated;nil if none.
// Pointer names reflect surrogate replacement;depth limits nesting (normally Depth).
// On refusal, value and lone are nil, err is nonnil.
func Decode(body []byte, depth int) (value any, lone []string, err *Error) {
	if bytes.HasPrefix(body, bom) {
		return nil, nil, fail(0, ReasonBOM)
	}
	if at := invalidUTF8(body); at >= 0 {
		return nil, nil, fail(at, ReasonUTF8)
	}
	p := &parser{b: body, limit: depth}
	p.ws()
	v, e := p.value(0)
	if e != nil {
		return nil, nil, e
	}
	p.ws()
	if p.i != len(p.b) {
		return nil, nil, fail(p.i, ReasonSyntax)
	}
	if len(p.lone) > 1 {
		sort.Strings(p.lone)
		out := p.lone[:1]
		for _, s := range p.lone[1:] {
			if s != out[len(out)-1] {
				out = append(out, s)
			}
		}
		p.lone = out
	}
	return v, p.lone, nil
}

func fail(at int, reason string) *Error {
	return &Error{Code: 400, Kind: "badrequest", Reason: reason, Offset: at}
}

// invalidUTF8 returns the first invalid byte offset or-1. Go UTF-8 validation rejects surrogate encodings,
// overlong sequences and code points above U+10FFFF.
func invalidUTF8(b []byte) int {
	if utf8.Valid(b) {
		return -1
	}
	for i := 0; i < len(b); {
		if b[i] < utf8.RuneSelf {
			i++
			continue
		}
		r, n := utf8.DecodeRune(b[i:])
		if r == utf8.RuneError && n == 1 {
			return i
		}
		i += n
	}
	return len(b)
}

// seg is a root-relative path segment:surrogate-replaced name or array index.
type seg struct {
	name  string
	index int
	isIdx bool
}

type parser struct {
	b     []byte
	i     int
	limit int
	path  []seg
	lone  []string
	buf   []byte
}

func (p *parser) ws() {
	for p.i < len(p.b) {
		switch p.b[p.i] {
		case ' ', '\t', '\n', '\r':
			p.i++
		default:
			return
		}
	}
}

// pointer escapes the current JSON Pointer path:~->~0, /->~1.
func (p *parser) pointer() string {
	var sb strings.Builder
	for _, s := range p.path {
		sb.WriteByte('/')
		if s.isIdx {
			sb.WriteString(strconv.Itoa(s.index))
			continue
		}
		sb.WriteString(strings.ReplaceAll(strings.ReplaceAll(s.name, "~", "~0"), "/", "~1"))
	}
	return sb.String()
}

// value reads at p.i;level counts enclosing objects/arrays.
func (p *parser) value(level int) (any, *Error) {
	if p.i >= len(p.b) {
		return nil, fail(p.i, ReasonSyntax)
	}
	switch c := p.b[p.i]; {
	case c == '{':
		return p.object(level + 1)
	case c == '[':
		return p.array(level + 1)
	case c == '"':
		raw, lone, e := p.str()
		if e != nil {
			return nil, e
		}
		if lone {
			p.lone = append(p.lone, p.pointer())
			return clean(raw), nil
		}
		return raw, nil
	case c == 't':
		return true, p.literal("true")
	case c == 'f':
		return false, p.literal("false")
	case c == 'n':
		return nil, p.literal("null")
	case c == '-' || c >= '0' && c <= '9':
		return p.number()
	case c == 'N' || c == 'I':
		return nil, fail(p.i, ReasonNonFinite)
	}
	return nil, fail(p.i, ReasonSyntax)
}

func (p *parser) literal(word string) *Error {
	if !bytes.HasPrefix(p.b[p.i:], []byte(word)) {
		return fail(p.i, ReasonSyntax)
	}
	p.i += len(word)
	return nil
}

func (p *parser) object(level int) (any, *Error) {
	if level > p.limit {
		return nil, fail(p.i, ReasonDepth)
	}
	p.i++
	out := map[string]any{}
	p.ws()
	if p.i < len(p.b) && p.b[p.i] == '}' {
		p.i++
		return out, nil
	}
	// Detect duplicates before surrogate replacement:distinct surrogate escapes are distinct RFC 8259 names.
	seen := map[string]struct{}{}
	for {
		if p.i >= len(p.b) || p.b[p.i] != '"' {
			return nil, fail(p.i, ReasonSyntax)
		}
		at := p.i
		raw, lone, e := p.str()
		if e != nil {
			return nil, e
		}
		if _, dup := seen[raw]; dup {
			return nil, fail(at, ReasonDuplicate)
		}
		seen[raw] = struct{}{}
		name := raw
		if lone {
			p.lone = append(p.lone, p.pointer())
			name = clean(raw)
		}
		p.ws()
		if p.i >= len(p.b) || p.b[p.i] != ':' {
			return nil, fail(p.i, ReasonSyntax)
		}
		p.i++
		p.ws()
		p.path = append(p.path, seg{name: name})
		v, e := p.value(level)
		p.path = p.path[:len(p.path)-1]
		if e != nil {
			return nil, e
		}
		// Different lone-surrogate names may collide after replacement;retain the last like check_tables.decode.
		// Such names are always in lone, so table rows reading that object already refuse it.
		out[name] = v
		p.ws()
		if p.i < len(p.b) && p.b[p.i] == ',' {
			p.i++
			p.ws()
			continue
		}
		if p.i < len(p.b) && p.b[p.i] == '}' {
			p.i++
			return out, nil
		}
		return nil, fail(p.i, ReasonSyntax)
	}
}

func (p *parser) array(level int) (any, *Error) {
	if level > p.limit {
		return nil, fail(p.i, ReasonDepth)
	}
	p.i++
	out := []any{}
	p.ws()
	if p.i < len(p.b) && p.b[p.i] == ']' {
		p.i++
		return out, nil
	}
	for k := 0; ; k++ {
		p.path = append(p.path, seg{index: k, isIdx: true})
		v, e := p.value(level)
		p.path = p.path[:len(p.path)-1]
		if e != nil {
			return nil, e
		}
		out = append(out, v)
		p.ws()
		if p.i < len(p.b) && p.b[p.i] == ',' {
			p.i++
			p.ws()
			continue
		}
		if p.i < len(p.b) && p.b[p.i] == ']' {
			p.i++
			return out, nil
		}
		return nil, fail(p.i, ReasonSyntax)
	}
}

// str reads a quote at p.i. raw represents lone surrogates as three-byte WTF-8, which valid body UTF-8
// cannot contain, retaining name identity for duplicate checks;lone records their presence.
func (p *parser) str() (raw string, lone bool, err *Error) {
	p.i++
	start := p.i
	for p.i < len(p.b) {
		c := p.b[p.i]
		if c == '"' {
			s := string(p.b[start:p.i])
			p.i++
			return s, false, nil
		}
		if c == '\\' {
			break
		}
		if c < 0x20 {
			return "", false, fail(p.i, ReasonSyntax)
		}
		p.i++
	}
	buf := append(p.buf[:0], p.b[start:p.i]...)
	for {
		if p.i >= len(p.b) {
			return "", false, fail(p.i, ReasonSyntax)
		}
		c := p.b[p.i]
		switch {
		case c == '"':
			p.i++
			p.buf = buf
			return string(buf), lone, nil
		case c < 0x20:
			return "", false, fail(p.i, ReasonSyntax)
		case c != '\\':
			j := p.i + 1
			for j < len(p.b) && p.b[j] != '"' && p.b[j] != '\\' && p.b[j] >= 0x20 {
				j++
			}
			buf = append(buf, p.b[p.i:j]...)
			p.i = j
			continue
		}
		if p.i+1 >= len(p.b) {
			return "", false, fail(p.i, ReasonSyntax)
		}
		switch e := p.b[p.i+1]; e {
		case '"', '\\', '/':
			buf = append(buf, e)
		case 'b':
			buf = append(buf, '\b')
		case 'f':
			buf = append(buf, '\f')
		case 'n':
			buf = append(buf, '\n')
		case 'r':
			buf = append(buf, '\r')
		case 't':
			buf = append(buf, '\t')
		case 'u':
			u, ok := hex4(p.b, p.i+2)
			if !ok {
				return "", false, fail(p.i, ReasonSyntax)
			}
			p.i += 6
			if u >= 0xD800 && u <= 0xDBFF && p.i+1 < len(p.b) && p.b[p.i] == '\\' && p.b[p.i+1] == 'u' {
				if u2, ok := hex4(p.b, p.i+2); ok && u2 >= 0xDC00 && u2 <= 0xDFFF {
					buf = utf8.AppendRune(buf, rune(0x10000+(u-0xD800)<<10+(u2-0xDC00)))
					p.i += 6
					continue
				}
			}
			if u >= 0xD800 && u <= 0xDFFF {
				buf = append(buf, 0xE0|byte(u>>12), 0x80|byte(u>>6&0x3F), 0x80|byte(u&0x3F))
				lone = true
				continue
			}
			buf = utf8.AppendRune(buf, rune(u))
			continue
		default:
			return "", false, fail(p.i, ReasonSyntax)
		}
		p.i += 2
	}
}

func hex4(b []byte, at int) (int, bool) {
	if at+4 > len(b) {
		return 0, false
	}
	u := 0
	for _, c := range b[at : at+4] {
		switch {
		case c >= '0' && c <= '9':
			u = u<<4 | int(c-'0')
		case c >= 'a' && c <= 'f':
			u = u<<4 | int(c-'a'+10)
		case c >= 'A' && c <= 'F':
			u = u<<4 | int(c-'A'+10)
		default:
			return 0, false
		}
	}
	return u, true
}

// clean replaces every raw WTF-8 surrogate with U+FFFD.
func clean(raw string) string {
	var sb strings.Builder
	sb.Grow(len(raw))
	for i := 0; i < len(raw); i++ {
		if raw[i] == 0xED && i+2 < len(raw) && raw[i+1] >= 0xA0 && raw[i+1] <= 0xBF {
			sb.WriteString("\uFFFD")
			i += 2
			continue
		}
		sb.WriteByte(raw[i])
	}
	return sb.String()
}

func digits(b []byte, i int) int {
	for i < len(b) && b[i] >= '0' && b[i] <= '9' {
		i++
	}
	return i
}

// number follows RFC 8259 section6 decimal syntax, without a length bound.
func (p *parser) number() (any, *Error) {
	b, start, i := p.b, p.i, p.i
	if b[i] == '-' {
		i++
		if i < len(b) && b[i] == 'I' {
			return nil, fail(i, ReasonNonFinite)
		}
	}
	switch {
	case i < len(b) && b[i] == '0':
		i++
	case i < len(b) && b[i] >= '1' && b[i] <= '9':
		i = digits(b, i+1)
	default:
		return nil, fail(i, ReasonSyntax)
	}
	integer := true
	if i < len(b) && b[i] == '.' {
		integer = false
		j := digits(b, i+1)
		if j == i+1 {
			return nil, fail(j, ReasonSyntax)
		}
		i = j
	}
	if i < len(b) && (b[i] == 'e' || b[i] == 'E') {
		integer = false
		i++
		if i < len(b) && (b[i] == '+' || b[i] == '-') {
			i++
		}
		j := digits(b, i)
		if j == i {
			return nil, fail(j, ReasonSyntax)
		}
		i = j
	}
	p.i = i
	text := string(b[start:i])
	if integer && len(text) <= 20 {
		if n, err := strconv.ParseInt(text, 10, 64); err == nil {
			return n, nil
		}
	}
	// Grammar is already valid;ParseFloat errors here are only ErrRange, returning infinities or signed zero.
	f, _ := strconv.ParseFloat(text, 64)
	return f, nil
}
