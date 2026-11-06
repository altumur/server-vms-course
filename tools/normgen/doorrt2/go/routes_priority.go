// Handwritten x-route-priority router (ADR-0125 generator 2; P/05-R057's four rules), using routes.go.
// Copy only for lessons whose OpenAPI declares x-route-priority.
//
// Do not decode the entire path before matching: compare literal segment bytes, keep trailing slashes
// and do not split on %2F. segment captures one raw segment; final-only remainder captures the whole
// raw suffix, including empty tails and a//b. From shape matches, retain the request method, then choose
// minimum x-route-priority. Shape without method gives bodyless405; no match gives bodyless404.
// Decode parameters afterward, each segment independently under percent-segment; decoded '/' is invalid.
// Validate their schemas; failure uses the method's x-path-error without falling back to another
// route.
package apidoor

import (
	"strings"
	"unicode/utf8"
)

// Match contains the selected operation and decoded path parameters.
type Match struct {
	Op     Op
	Params map[string]string
}

// RouteError has Code404/405 (empty Response means no body), or Op/Param's x-path-error status and
// component response schema name, again empty for no body.
type RouteError struct {
	Code     int
	Response string
	Op       Op
	Param    string
	Reason   string
}

func (e *RouteError) Error() string { return e.Reason }

type prioSegment struct {
	lit       string
	param     string
	remainder bool
}

type prioTemplate struct {
	path     string
	segs     []prioSegment
	priority int
}

// pathError maps a parameter/method to status and response schema, empty for no body.
type pathError struct {
	status   int
	response string
}

func (t prioTemplate) shape(raw []string) (map[string]string, bool) {
	params := map[string]string{}
	for i, s := range t.segs {
		if s.remainder {
			if i >= len(raw) { // Remainder starts after its slash: /v1/objects does not match /v1/objects/{key}.
				return nil, false
			}
			params[s.param] = strings.Join(raw[i:], "/")
			return params, true
		}
		if i >= len(raw) {
			return nil, false
		}
		if s.param == "" {
			if raw[i] != s.lit {
				return nil, false
			}
			continue
		}
		params[s.param] = raw[i]
	}
	return params, len(raw) == len(t.segs)
}

// decodeSegment decodes one percent-segment; malformed %XX or decoded '/' errors.
func decodeSegment(s string) (string, bool) {
	d, ok := unescapeSegment(s)
	if !ok || strings.Contains(d, "/") {
		return "", false
	}
	return d, true
}

func unescapeSegment(s string) (string, bool) {
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
		h, ok1 := hexDigit(s[i+1])
		l, ok2 := hexDigit(s[i+2])
		if !ok1 || !ok2 {
			return "", false
		}
		b.WriteByte(h<<4 | l)
		i += 2
	}
	return b.String(), true
}

func hexDigit(c byte) (byte, bool) {
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

// Route matches the request method and raw path without query under lesson x-route-priority rules.
func Route(method, rawPath string) (Match, *RouteError) {
	if !strings.HasPrefix(rawPath, "/") {
		return Match{}, &RouteError{Code: 404, Reason: "not a request path"}
	}
	raw := strings.Split(rawPath[1:], "/")
	if rawPath == "/" {
		raw = []string{}
	}
	m := strings.ToUpper(method)
	shaped := false
	var best *prioTemplate
	var bestParams map[string]string
	for i := range prioTemplates {
		t := &prioTemplates[i]
		params, ok := t.shape(raw)
		if !ok {
			continue
		}
		shaped = true
		if _, has := byPathMethod[t.path+" "+m]; !has {
			continue
		}
		if best == nil || t.priority < best.priority {
			best, bestParams = t, params
		}
	}
	if best == nil {
		if shaped {
			return Match{}, &RouteError{Code: 405, Reason: "method " + m + " is not of the matched paths"}
		}
		return Match{}, &RouteError{Code: 404, Reason: "no route"}
	}
	op := byPathMethod[best.path+" "+m]
	out := map[string]string{}
	for _, s := range best.segs {
		if s.param == "" {
			continue
		}
		v := bestParams[s.param]
		dec, ok := v, true
		if pathDecode[best.path][s.param] {
			if s.remainder {
				parts := strings.Split(v, "/")
				for k, p := range parts {
					if parts[k], ok = decodeSegment(p); !ok {
						break
					}
				}
				dec = strings.Join(parts, "/")
			} else {
				dec, ok = decodeSegment(v)
			}
		}
		if ok && v == "" {
			ok = false // An empty capture is an operation parameter error.
		}
		if ok && !utf8.ValidString(dec) {
			ok = false // Parameter values must be UTF-8 strings (s32:%FF).
		}
		if ok {
			if name := pathSchemas[best.path][s.param]; name != "" && Validate(name, dec) != nil {
				ok = false
			}
		}
		if !ok {
			pe, has := pathErrors[best.path][s.param][m]
			if !has {
				pe = pathError{status: 404}
			}
			return Match{}, &RouteError{Code: pe.status, Response: pe.response, Op: op, Param: s.param,
				Reason: "parameter " + s.param + " of " + best.path}
		}
		out[s.param] = dec
	}
	return Match{Op: op, Params: out}, nil
}

// Admitted checks certificate roles against door-roles.tsv in mtls mode: '*' allows any kit role;
// <sub>worker requires a loaded isSub name. An operation absent from the table is not admitted.
func Admitted(op Op, role string, isSub func(string) bool) bool {
	for _, r := range opRoles[op] {
		switch {
		case r == "*":
			return role != ""
		case r == "<sub>worker":
			if strings.HasSuffix(role, "worker") && isSub != nil && isSub(strings.TrimSuffix(role, "worker")) {
				return true
			}
		case r == role:
			return true
		}
	}
	return false
}
