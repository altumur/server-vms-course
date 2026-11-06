// Handwritten lesson door router (ADR-0125 generator 2, P/06 part 3a), using routes.go operation tables.
//
// Split paths into segments: '/' has none, a trailing slash adds an empty last segment; decode each %XX.
// A template matches when literals, parameter schemas and implementation Catalog classes all match.
// Catalog classes are sub, rows, table, pass. Keep the most concrete matches: compare the first differing
// segment rank, literal first (OpenAPI concrete-before-template), then Catalog-confirmed class, then free
// parameter. Missing method yields405 only if every path operation declares405, otherwise404.
package apidoor

import (
	"regexp"
	"strings"
	"unicode/utf8"
)

// Catalog is YOURS: loaded names. Empty sub denotes the short path without /{sub}.
type Catalog interface {
	Sub(name string) bool
	Rows(sub, name string) bool
	Table(sub, name string) bool
	Pass(sub, name string) bool
}

// Match contains the selected operation, decoded path parameters and prefix/parameter sub, or empty.
type Match struct {
	Op       Op
	Params   map[string]string
	Sub      string
	Prefixed bool
}

// RouteError has Code404/405 and Allow methods, or Code0 for equal-concreteness ambiguity:
// multiple Catalog-confirmed templates indicate an implementation catalog error, not a client response.
type RouteError struct {
	Code   int
	Allow  []string
	Reason string
}

func (e *RouteError) Error() string { return e.Reason }

type segment struct {
	lit   string
	param string // Parameter name; empty denotes a literal.
}

type template struct {
	path     string
	segs     []segment
	prefixed bool
}

type paramCheck struct {
	minLen, maxLen int // Character lengths; maxLen=-1 means unbounded.
	rx             *regexp.Regexp
	enum           []string
	notEnum        []string         // not {enum}: forbidden values.
	notRx          []*regexp.Regexp // not {pattern}: forbidden patterns.
}

func (c paramCheck) ok(v string) bool {
	if !utf8.ValidString(v) && (c.rx != nil || c.minLen > 0 || c.maxLen >= 0) {
		return false
	}
	n := utf8.RuneCountInString(v)
	if n < c.minLen || (c.maxLen >= 0 && n > c.maxLen) {
		return false
	}
	if c.rx != nil && !c.rx.MatchString(v) {
		return false
	}
	for _, e := range c.notEnum {
		if e == v {
			return false
		}
	}
	for _, r := range c.notRx {
		if r.MatchString(v) {
			return false
		}
	}
	if c.enum != nil {
		for _, e := range c.enum {
			if e == v {
				return true
			}
		}
		return false
	}
	return true
}

func splitPath(p string) ([]string, bool) {
	if !strings.HasPrefix(p, "/") {
		return nil, false
	}
	if p == "/" {
		return []string{}, true
	}
	raw := strings.Split(p[1:], "/")
	out := make([]string, len(raw))
	for i, s := range raw {
		d, ok := unescape(s)
		if !ok {
			return nil, false
		}
		out[i] = d
	}
	return out, true
}

func unescape(s string) (string, bool) {
	if !strings.Contains(s, "%") {
		return s, true
	}
	var b strings.Builder
	for i := 0; i < len(s); i++ {
		if s[i] != '%' {
			b.WriteByte(s[i])
			continue
		}
		if i+2 >= len(s) {
			return "", false
		}
		h, ok1 := hexval(s[i+1])
		l, ok2 := hexval(s[i+2])
		if !ok1 || !ok2 {
			return "", false
		}
		b.WriteByte(h<<4 | l)
		i += 2
	}
	return b.String(), true
}

func hexval(c byte) (byte, bool) {
	switch {
	case c >= '0' && c <= '9':
		return c - '0', true
	case c >= 'a' && c <= 'f':
		return c - 'a' + 10, true
	case c >= 'A' && c <= 'F':
		return c - 'A' + 10, true
	}
	return 0, false
}

func (t template) match(segs []string, cat Catalog) (map[string]string, string, bool) {
	if len(segs) != len(t.segs) {
		return nil, "", false
	}
	params := map[string]string{}
	for i, s := range t.segs {
		if s.param == "" {
			if segs[i] != s.lit {
				return nil, "", false
			}
			continue
		}
		v := segs[i]
		if v == "" || !paramChecks[t.path][s.param].ok(v) {
			return nil, "", false
		}
		params[s.param] = v
	}
	sub := params["sub"]
	for name, v := range params {
		switch name {
		case "sub":
			if cat == nil || !cat.Sub(v) {
				return nil, "", false
			}
		case "rows":
			if cat == nil || !cat.Rows(sub, v) {
				return nil, "", false
			}
		case "table":
			if cat == nil || !cat.Table(sub, v) {
				return nil, "", false
			}
		case "pass":
			if cat == nil || !cat.Pass(sub, v) {
				return nil, "", false
			}
		}
	}
	return params, sub, true
}

// Segment rank: literal2, Catalog class(sub, rows, table, pass)1, free parameter0.
func rank(s segment) int {
	switch {
	case s.param == "":
		return 2
	case s.param == "sub" || s.param == "rows" || s.param == "table" || s.param == "pass":
		return 1
	}
	return 0
}

// moreConcrete means a wins at the first segment with differing ranks.
func moreConcrete(a, b template) int {
	for i := range a.segs {
		ra, rb := rank(a.segs[i]), rank(b.segs[i])
		if ra > rb {
			return 1
		}
		if ra < rb {
			return -1
		}
	}
	return 0
}

// Route selects the method/path operation using lesson OpenAPI tables and the implementation Catalog.
func Route(method, path string, cat Catalog) (Match, *RouteError) {
	segs, ok := splitPath(path)
	if !ok {
		return Match{}, &RouteError{Code: 404, Reason: "the path is not a request path"}
	}
	type hit struct {
		t      template
		params map[string]string
		sub    string
	}
	var hits []hit
	for _, t := range templates {
		if params, sub, ok := t.match(segs, cat); ok {
			hits = append(hits, hit{t, params, sub})
		}
	}
	if len(hits) == 0 {
		return Match{}, &RouteError{Code: 404, Reason: "no route"}
	}
	best := []hit{hits[0]}
	for _, h := range hits[1:] {
		switch moreConcrete(h.t, best[0].t) {
		case 1:
			best = []hit{h}
		case 0:
			best = append(best, h)
		}
	}
	paths := map[string]bool{}
	for _, h := range best {
		paths[h.t.path] = true
	}
	if len(paths) > 1 {
		names := []string{}
		for _, h := range best {
			names = append(names, h.t.path)
		}
		return Match{}, &RouteError{Code: 0, Reason: "ambiguous: " + strings.Join(names, " ")}
	}
	h := best[0]
	for _, b := range best {
		if !b.t.prefixed {
			h = b // Short/prefixed variants cannot match simultaneously; prefer short defensively.
		}
	}
	m := strings.ToUpper(method)
	if op, ok := byPathMethod[h.t.path+" "+m]; ok {
		return Match{Op: op, Params: h.params, Sub: h.sub, Prefixed: h.t.prefixed}, nil
	}
	allow := methodsOf[h.t.path]
	if all405[h.t.path] {
		return Match{}, &RouteError{Code: 405, Allow: allow, Reason: "method " + m + " is not of " + h.t.path}
	}
	return Match{}, &RouteError{Code: 404, Allow: allow, Reason: "method " + m + " is not of " + h.t.path}
}
