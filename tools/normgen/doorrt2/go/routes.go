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
	"sort"
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
// P/06 also retains its owners' badkey=400 after selecting the path and method.
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
	if p06CatalogueBinding {
		return p06Route(method, path, cat, p06Bindings())
	}
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
	var tableOps []p06Operation
	for _, o := range domainTableBindings() {
		shape := template{path: o.path}
		possible := len(o.segments) == len(segs)
		for i, s := range o.segments {
			shape.segs = append(shape.segs, segment{lit: s.literal, param: s.parameter})
			if possible && s.parameter == "" && segs[i] != s.literal {
				possible = false
			}
		}
		for _, h := range hits {
			if len(h.t.segs) == len(shape.segs) && moreConcrete(h.t, shape) > 0 {
				possible = false // A source literal already wins without consulting a table catalogue.
			}
		}
		if possible {
			tableOps = append(tableOps, o)
		}
	}
	if len(tableOps) != 0 {
		candidates, err := domainTableCandidates(tableOps, path, cat)
		if err != nil {
			return Match{}, err
		}
		for _, c := range candidates {
			t := template{path: c.operation.path}
			for _, s := range c.segments {
				// Retain catalogue rank rather than turning a bound name into a source literal.
				t.segs = append(t.segs, segment{lit: s.literal, param: s.parameter})
				if s.rank == 1 {
					t.segs[len(t.segs)-1].param = "table"
				}
			}
			hits = append(hits, hit{t, c.values, c.sub})
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

// The S08 carrier is shared; only the generated P/06 declaration activates it.
// Other lessons never request this private capability or inspect these records.
type p06BindingSpec struct {
	operations []p06Operation
	references []string
	documents  map[string]string
}
type p06Server struct {
	mounted bool
	subs    []string
}
type p06Segment struct{ literal, parameter string }
type p06Operation struct {
	op                                  Op
	path, component, source, base       string
	servers                             []p06Server
	segments                            []p06Segment
	checks                              map[string]paramCheck
	itemParameters, operationParameters []Param
	security                            string
}
type p06Choice struct {
	parameter, value, owner string
	metadata                any // Borrowed accepted metadata; never changed or interpreted as permissions.
}
type p06BoundSegment struct {
	literal, parameter string
	rank               int // Source literal=2, catalogue substitution=1, free=0.
	raw                bool
}
type p06Candidate struct {
	operation                           p06Operation
	key, sub                            string
	prefixed, file, prefix, tail        bool
	segments                            []p06BoundSegment
	bound, values                       map[string]string
	itemParameters, operationParameters []Param
	metadata                            any
}
type p06Target struct {
	path    string
	parts   []string
	offsets []int
}

// These owner PathItems enumerate only the accepted domain.edit_tables projection.
// The existing private startup-snapshot capability adds no loader or public Catalog method.
func domainTableCandidates(operations []p06Operation, path string, cat Catalog) ([]p06Candidate, *RouteError) {
	provider, ok := cat.(interface {
		CatalogSnapshot() (root string, views []map[string]any)
	})
	if !ok {
		return nil, p06ContextError("CatalogSnapshot is required for domain table doors")
	}
	root, views := provider.CatalogSnapshot()
	if root == "" {
		return nil, p06ContextError("selected root is not loaded")
	}
	target, ok := p06Split(path)
	if !ok {
		return nil, &RouteError{Code: 404, Reason: "the path is not a request path"}
	}
	seen, result := map[string]bool{}, []p06Candidate{}
	for _, view := range views {
		sub, ok := view["name"].(string)
		if !ok || sub == "" || seen[sub] {
			return nil, p06ContextError("missing/duplicate manifest name")
		}
		seen[sub] = true
		value, exists := view["domain"]
		if !exists {
			continue
		}
		domain, ok := p06Map(value)
		if !ok {
			return nil, p06ContextError("domain is not a canonical view object")
		}
		value, exists = domain["edit_tables"]
		if !exists {
			continue
		}
		tables, ok := p06Map(value)
		if !ok {
			return nil, p06ContextError("domain.edit_tables is not a canonical view object")
		}
		for _, table := range p06Keys(tables) {
			if table == "" {
				return nil, p06ContextError("domain.edit_tables has an empty name")
			}
			for _, o := range operations {
				c := p06Bind(o, p06Server{}, sub, p06Choice{"table", table, "domain.edit_tables", tables[table]})
				if !c.match(target) {
					continue
				}
				valid := true
				for name, raw := range c.values {
					value, decoded := raw, true
					if _, bound := c.bound[name]; !bound {
						value, decoded = unescape(raw)
					}
					check, checked := o.checks[name]
					valid = valid && decoded && value != "" && (!checked || check.ok(value))
					c.values[name] = value
				}
				if valid {
					result = append(result, c)
				}
			}
		}
	}
	if !seen[root] {
		return nil, p06ContextError("selected root is not loaded")
	}
	return result, nil
}

func p06ContextError(reason string) *RouteError {
	return &RouteError{Code: 0, Reason: "P06 catalogue context: " + reason}
}

func p06Map(value any) (map[string]any, bool) {
	m, ok := value.(map[string]any)
	return m, ok && m != nil
}

func p06List(value any) ([]any, bool) {
	if a, ok := value.([]any); ok {
		return a, true
	}
	if a, ok := value.([]string); ok {
		r := make([]any, len(a))
		for i := range a {
			r[i] = a[i]
		}
		return r, true
	}
	return nil, false
}

func p06Keys(m map[string]any) []string {
	names := make([]string, 0, len(m))
	for name := range m {
		names = append(names, name)
	}
	sort.Strings(names) // Local ordering does not select a winning route.
	return names
}

func p06Owner(o p06Operation) string {
	switch o.component {
	case "UnitsCollection", "UnitItem":
		return "unit"
	case "TableCollection", "TableItem":
		return "table"
	case "PassRoot":
		return "pass"
	case "ConsoleFile":
		return "file"
	}
	// These existing source identities are not classified by a parameter's name.
	switch o.path {
	case "/{rows}/{id}/{blob_field}":
		return "unit"
	case "/where/{table}/{place}", "/{sub}/where/{table}/{place}", "/domain/at/{cluster}/{sub}/where/{table}/{place}":
		return "table"
	case "/domain/at/{cluster}/{sub}/{rows}":
		return "domain-family"
	case "/domain/at/{cluster}/{sub}/{rows}/{id}":
		return "domain-item"
	case "/domain/at/{cluster}/{sub}/{rows}/{id}/{tail}":
		return "domain-tail"
	}
	return ""
}

// Enumerate names only from this one already accepted manifest view. No loader,
// defaults, fixture catalogue, file IO or admission procedure is run here.
func p06Choices(o p06Operation, view map[string]any) ([]p06Choice, *RouteError) {
	owner := p06Owner(o)
	if owner == "" {
		return []p06Choice{{}}, nil
	}
	choices := []p06Choice{}
	if owner == "unit" || owner == "domain-family" || owner == "domain-item" {
		if value, exists := view["unit"]; exists {
			unit, ok := p06Map(value)
			if !ok {
				return nil, p06ContextError("unit is not a view object")
			}
			if value, exists := unit["rows"]; exists {
				name, ok := value.(string)
				if !ok || name == "" {
					return nil, p06ContextError("unit.rows is not a name")
				}
				choices = append(choices, p06Choice{"rows", name, "unit.rows", unit})
			}
		}
	}
	if owner == "table" || owner == "domain-family" || owner == "domain-item" {
		if value, exists := view["tables"]; exists {
			tables, ok := p06Map(value)
			if !ok {
				return nil, p06ContextError("tables is not a canonical view object")
			}
			for _, name := range p06Keys(tables) {
				table, ok := p06Map(tables[name])
				if !ok {
					return nil, p06ContextError("table is not a canonical view object")
				}
				if service, exists := table["service"]; exists {
					b, ok := service.(bool)
					if !ok {
						return nil, p06ContextError("table.service is not boolean")
					}
					if b && owner != "table" {
						continue
					}
				}
				parameter := "table"
				if owner != "table" {
					parameter = "rows"
				}
				choices = append(choices, p06Choice{parameter, name, "tables", table})
			}
		}
	}
	if owner == "file" {
		if value, exists := view["console"]; exists {
			console, ok := p06Map(value)
			if !ok {
				return nil, p06ContextError("console is not a view object")
			}
			if value, exists := console["files"]; exists {
				files, ok := p06List(value)
				if !ok {
					return nil, p06ContextError("console.files is not a list")
				}
				for _, value := range files {
					name, ok := value.(string)
					if !ok || name == "" {
						return nil, p06ContextError("file is not a complete name")
					}
					choices = append(choices, p06Choice{"file", name, "console.files", console})
				}
			}
		}
	}
	if owner == "pass" || owner == "domain-item" || owner == "domain-tail" {
		if value, exists := view["door"]; exists {
			door, ok := p06Map(value)
			if !ok {
				return nil, p06ContextError("door is not a view object")
			}
			if owner == "pass" {
				if value, exists := door["pass"]; exists {
					kind, metadata := "door.pass.first", value
					if object, ok := p06Map(value); ok {
						value = object["routes"]
						kind = "door.pass.second"
					}
					passes, ok := p06List(value)
					if !ok {
						return nil, p06ContextError("door.pass routes is not a list")
					}
					for _, value := range passes {
						name, ok := value.(string)
						if !ok || name == "" {
							return nil, p06ContextError("pass is not a prefix")
						}
						choices = append(choices, p06Choice{"pass", name, kind, metadata})
					}
				}
			} else if value, exists := door["routes"]; exists {
				routes, ok := p06List(value)
				if !ok {
					return nil, p06ContextError("door.routes is not a list")
				}
				for _, value := range routes {
					name, simple := value.(string)
					if !simple {
						route, ok := p06Map(value)
						if !ok {
							return nil, p06ContextError("door route is not a name/object")
						}
						name, ok = route["name"].(string)
						if !ok {
							return nil, p06ContextError("door route has no name")
						}
						if _, role := route["role"]; role {
							continue
						}
					}
					if name == "" {
						return nil, p06ContextError("door route is empty")
					}
					choices = append(choices, p06Choice{"rows", name, "door.routes", value})
				}
			}
		}
	}
	return choices, nil
}

func p06Effective(parameters []Param, bound map[string]string) []Param {
	result := make([]Param, 0, len(parameters))
	for _, p := range parameters {
		if _, exists := bound[p.Name]; p.In == "path" && exists {
			continue
		}
		result = append(result, p)
	}
	return result
}

func p06Bind(o p06Operation, server p06Server, sub string, choice p06Choice) p06Candidate {
	c := p06Candidate{operation: o, prefixed: server.mounted, file: o.component == "ConsoleFile",
		prefix: o.component == "PassRoot", tail: p06Owner(o) == "domain-tail", bound: map[string]string{}, metadata: choice.metadata}
	if server.mounted {
		c.segments = append(c.segments, p06BoundSegment{literal: sub, rank: 1})
		c.bound["sub"], c.sub = sub, sub
	}
	for _, s := range o.segments {
		if s.parameter == "sub" {
			c.bound["sub"], c.sub = sub, sub
			c.segments = append(c.segments, p06BoundSegment{literal: sub, rank: 1})
		} else if choice.parameter != "" && s.parameter == choice.parameter {
			c.bound[s.parameter] = choice.value
			for _, part := range strings.Split(choice.value, "/") {
				c.segments = append(c.segments, p06BoundSegment{literal: part, rank: 1, raw: c.file})
			}
		} else if s.parameter == "tail" && c.tail {
			// This existing branch captures the whole raw remainder, not one segment.
		} else if s.parameter != "" {
			c.segments = append(c.segments, p06BoundSegment{parameter: s.parameter})
		} else {
			c.segments = append(c.segments, p06BoundSegment{literal: s.literal, rank: 2})
		}
	}
	c.itemParameters = p06Effective(o.itemParameters, c.bound)
	c.operationParameters = p06Effective(o.operationParameters, c.bound)
	// Source identity keeps independent branches apart, including both domain-at forms.
	c.key = o.path + "\x00" + sub + "\x00" + choice.owner + "\x00" + choice.value
	if server.mounted {
		c.key += "\x00mounted"
	}
	return c
}

func p06Split(target string) (p06Target, bool) {
	path, _, _ := strings.Cut(target, "?")
	if !strings.HasPrefix(path, "/") {
		return p06Target{}, false
	}
	t := p06Target{path: path}
	if path != "/" {
		t.parts = strings.Split(path[1:], "/")
		offset := 1
		for _, p := range t.parts {
			t.offsets = append(t.offsets, offset)
			offset += len(p) + 1
		}
	}
	return t, true
}

func (c *p06Candidate) match(t p06Target) bool {
	n := len(c.segments)
	if c.tail {
		if len(t.parts) <= n || t.path[t.offsets[n]:] == "" {
			return false
		}
	} else if (!c.prefix && len(t.parts) != n) || (c.prefix && len(t.parts) < n) {
		return false
	}
	c.values = make(map[string]string, len(c.bound)+len(c.segments))
	for k, v := range c.bound {
		c.values[k] = v
	}
	for i, s := range c.segments {
		raw := t.parts[i]
		if s.parameter != "" {
			if raw == "" {
				return false
			}
			c.values[s.parameter] = raw
			continue // Decode/check free parameters only after path and method selection.
		}
		value := raw
		if !s.raw {
			var ok bool
			value, ok = unescape(raw)
			if !ok {
				return false
			}
		}
		if value != s.literal {
			return false
		}
	}
	if c.tail {
		c.values["tail"] = t.path[t.offsets[n]:] // Slice original bytes; never join decoded parameters.
	}
	return true
}

func p06MoreConcrete(a, b p06Candidate) int {
	if a.file != b.file {
		if a.file {
			return 1
		}
		return -1
	}
	n := len(a.segments)
	if len(b.segments) > n {
		n = len(b.segments)
	}
	for i := 0; i < n; i++ {
		// Beyond a pass prefix is its opaque free remainder. A longer declared
		// catalogue prefix still compares as catalogue, never as source literal.
		ra, rb := 0, 0
		if i < len(a.segments) {
			ra = a.segments[i].rank
		}
		if i < len(b.segments) {
			rb = b.segments[i].rank
		}
		if ra > rb {
			return 1
		}
		if ra < rb {
			return -1
		}
	}
	return 0
}

func p06Route(method, path string, cat Catalog, spec *p06BindingSpec) (Match, *RouteError) {
	if spec == nil || len(spec.operations) != 146 {
		return Match{}, p06ContextError("missing active operation spec")
	}
	provider, ok := cat.(interface {
		CatalogSnapshot() (root string, views []map[string]any)
	})
	if !ok {
		return Match{}, p06ContextError("CatalogSnapshot is required")
	}
	root, views := provider.CatalogSnapshot() // Exactly one borrowed startup snapshot per Route.
	catalogue := map[string]any{}
	for _, view := range views {
		name, ok := view["name"].(string)
		if !ok || name == "" || catalogue[name] != nil {
			return Match{}, p06ContextError("missing/duplicate manifest name")
		}
		// The required routing projection of a canonical view is a context
		// precondition, not another manifest loader/admission procedure.
		unit, unitOK := p06Map(view["unit"])
		_, tablesOK := p06Map(view["tables"])
		door, doorOK := p06Map(view["door"])
		rows, rowsOK := unit["rows"].(string)
		_, routesOK := door["routes"]
		_, passOK := door["pass"]
		if !unitOK || !tablesOK || !doorOK || !rowsOK || rows == "" || !routesOK || !passOK {
			return Match{}, p06ContextError("incomplete routing view")
		}
		catalogue[name] = view
	}
	if root == "" || catalogue[root] == nil {
		return Match{}, p06ContextError("selected root is not loaded")
	}
	target, ok := p06Split(path)
	if !ok {
		return Match{}, &RouteError{Code: 404, Reason: "the path is not a request path"}
	}
	var hits []p06Candidate
	for _, operation := range spec.operations {
		explicit := false
		for _, s := range operation.segments {
			explicit = explicit || s.parameter == "sub"
		}
		for _, server := range operation.servers {
			subs := []string{root}
			if server.mounted || explicit {
				subs = p06Keys(catalogue)
			}
			for _, sub := range subs {
				if server.mounted && server.subs != nil {
					allowed := false
					for _, name := range server.subs {
						allowed = allowed || name == sub
					}
					if !allowed {
						continue
					}
				}
				view, _ := p06Map(catalogue[sub])
				choices, err := p06Choices(operation, view)
				if err != nil {
					return Match{}, err
				}
				for _, choice := range choices {
					candidate := p06Bind(operation, server, sub, choice)
					if candidate.match(target) {
						hits = append(hits, candidate)
					}
				}
			}
		}
	}
	if len(hits) == 0 {
		return Match{}, &RouteError{Code: 404, Reason: "no route"}
	}
	best := []p06Candidate{hits[0]}
	for _, h := range hits[1:] {
		switch p06MoreConcrete(h, best[0]) {
		case 1:
			best = []p06Candidate{h}
		case 0:
			best = append(best, h)
		}
	}
	for _, h := range best[1:] {
		if h.key != best[0].key {
			return Match{}, &RouteError{Code: 0, Reason: "ambiguous: " + best[0].operation.path + " " + h.operation.path}
		}
	}
	method = strings.ToUpper(method)
	allow, unanimous := []string{}, true
	var selected *p06Candidate
	for i := range best {
		h := &best[i]
		info := Ops[h.operation.op]
		present := false
		for _, old := range allow {
			present = present || old == info.Method
		}
		if !present {
			allow = append(allow, info.Method)
		}
		has405 := false
		for _, response := range info.Responses {
			has405 = has405 || response.Code == "405"
		}
		unanimous = unanimous && has405
		if info.Method == method {
			selected = h
		}
	}
	if selected == nil {
		code := 404
		if unanimous || best[0].file {
			code = 405
		}
		return Match{}, &RouteError{Code: code, Allow: allow, Reason: "method " + method + " is not of " + best[0].operation.path}
	}
	for name, raw := range selected.values {
		if _, bound := selected.bound[name]; bound || (name == "tail" && selected.tail) {
			continue
		}
		value, ok := unescape(raw)
		check, hasCheck := selected.operation.checks[name]
		if !ok || (hasCheck && !check.ok(value)) {
			code := 404
			if (name == "id" && (selected.operation.component == "UnitItem" || selected.operation.path == "/{rows}/{id}/{blob_field}")) ||
				(name == "name" && selected.operation.component == "TableItem") {
				code = 400 // Existing badkey of these owners, after selecting their route.
			}
			return Match{}, &RouteError{Code: code, Reason: "badkey " + name}
		}
		selected.values[name] = value
	}
	return Match{Op: selected.operation.op, Params: selected.values, Sub: selected.sub, Prefixed: selected.prefixed}, nil
}
