// Command goextract reads the Go sources of one lesson of an implementation
// and prints static facts as one JSON document: packages and imports, flags,
// environment variables, top-level constants, refusal literals and process
// exits. It parses syntax only (go/ast); it never type-checks, builds or runs
// the subject. Paths in the output are relative to the module root.
//
// Usage: goextract -root <module root> -start <lesson dir relative to root>
package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"flag"
	"fmt"
	"go/ast"
	"go/constant"
	"go/parser"
	"go/printer"
	"go/token"
	"io/fs"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"
)

// Version names the extractor in snapshot headers.
const Version = "goextract/1"

type Pkg struct {
	Path    string   `json:"path"`
	Dir     string   `json:"dir"`
	Name    string   `json:"name"`
	Files   []string `json:"files"`
	Imports []string `json:"imports"`

	files []*ast.File
	names []string
	// consts holds evaluated package-level constants by name.
	consts map[string]constant.Value
}

type Flag struct {
	Name    string `json:"name"`
	Set     string `json:"set"`
	Method  string `json:"method"`
	Type    string `json:"type"`
	Default string `json:"default"`
	Value   string `json:"value"`
	Usage   string `json:"usage"`
	Bound   bool   `json:"bound"`
	Func    string `json:"func"`
	Pkg     string `json:"pkg"`
	File    string `json:"file"`
	Line    int    `json:"line"`
}

type Env struct {
	Name string `json:"name"`
	Call string `json:"call"`
	Func string `json:"func"`
	Pkg  string `json:"pkg"`
	File string `json:"file"`
	Line int    `json:"line"`
}

type Const struct {
	Name     string `json:"name"`
	Type     string `json:"type"`
	Value    string `json:"value"`
	Expr     string `json:"expr"`
	Exported bool   `json:"exported"`
	Pkg      string `json:"pkg"`
	File     string `json:"file"`
	Line     int    `json:"line"`
}

type Refusal struct {
	Channel    string   `json:"channel"`
	Code       int      `json:"code"`
	Kind       string   `json:"kind"`
	Words      []string `json:"words"`
	WordSource string   `json:"word_source"`
	Fields     []string `json:"fields"`
	Via        string   `json:"via"`
	Resolved   string   `json:"resolved"`
	Func       string   `json:"func"`
	Pkg        string   `json:"pkg"`
	File       string   `json:"file"`
	Line       int      `json:"line"`
}

type Exit struct {
	Code int    `json:"code"`
	Call string `json:"call"`
	Func string `json:"func"`
	Pkg  string `json:"pkg"`
	File string `json:"file"`
	Line int    `json:"line"`
}

type Unresolved struct {
	What   string `json:"what"`
	Reason string `json:"reason"`
	Expr   string `json:"expr"`
	Func   string `json:"func"`
	Pkg    string `json:"pkg"`
	File   string `json:"file"`
	Line   int    `json:"line"`
}

type Out struct {
	Extractor  string        `json:"extractor"`
	Module     string        `json:"module"`
	Requires   []string      `json:"requires"`
	Start      string        `json:"start"`
	Packages   []*Pkg        `json:"packages"`
	Flags      []*Flag       `json:"flags"`
	Env        []*Env        `json:"env"`
	Consts     []*Const      `json:"consts"`
	Refusals   []*Refusal    `json:"refusals"`
	Wrappers   []*Refusal    `json:"wrappers"`
	Exits      []*Exit       `json:"exits"`
	Unresolved []*Unresolved `json:"unresolved"`
}

var (
	fset          = token.NewFileSet()
	root          string
	out           Out
	kindRE        = regexp.MustCompile(`^[a-z][a-z_]*$`)
	jsonKE        = regexp.MustCompile(`"kind"\s*:\s*"([a-z_]+)"\s*,\s*"error"\s*:\s*"([^"%]*)"`)
	placeholderRE = regexp.MustCompile(`\{[^{}]*\}`)
	jsonKey       = regexp.MustCompile(`"([a-z_]+)"\s*:`)
	verbRE        = regexp.MustCompile(`%[-+# 0]*[0-9*]*(\.[0-9*]+)?[a-zA-Z%]`)
	statusN       = map[string]int{
		"StatusBadRequest": 400, "StatusUnauthorized": 401, "StatusForbidden": 403,
		"StatusNotFound": 404, "StatusMethodNotAllowed": 405, "StatusConflict": 409,
		"StatusGone": 410, "StatusPreconditionFailed": 412, "StatusRequestEntityTooLarge": 413,
		"StatusUnprocessableEntity": 422, "StatusTooManyRequests": 429,
		"StatusInternalServerError": 500, "StatusNotImplemented": 501,
		"StatusBadGateway": 502, "StatusServiceUnavailable": 503, "StatusGatewayTimeout": 504,
	}
	timeUnits = map[string]int64{
		"Nanosecond": int64(time.Nanosecond), "Microsecond": int64(time.Microsecond),
		"Millisecond": int64(time.Millisecond), "Second": int64(time.Second),
		"Minute": int64(time.Minute), "Hour": int64(time.Hour),
	}
)

// flagMethods: name index, default index (-1 none), usage index, value type.
var flagMethods = map[string]struct {
	name, def, usage int
	typ              string
}{
	"String": {0, 1, 2, "string"}, "Bool": {0, 1, 2, "bool"}, "Int": {0, 1, 2, "int"},
	"Int64": {0, 1, 2, "int64"}, "Uint": {0, 1, 2, "uint"}, "Uint64": {0, 1, 2, "uint64"},
	"Float64": {0, 1, 2, "float64"}, "Duration": {0, 1, 2, "duration"},
	"StringVar": {1, 2, 3, "string"}, "BoolVar": {1, 2, 3, "bool"}, "IntVar": {1, 2, 3, "int"},
	"Int64Var": {1, 2, 3, "int64"}, "UintVar": {1, 2, 3, "uint"}, "Uint64Var": {1, 2, 3, "uint64"},
	"Float64Var": {1, 2, 3, "float64"}, "DurationVar": {1, 2, 3, "duration"},
	"Var": {1, -1, 2, "value"}, "TextVar": {1, 2, 3, "text"},
	"Func": {0, -1, 1, "func"}, "BoolFunc": {0, -1, 1, "boolfunc"},
}

func main() {
	flag.StringVar(&root, "root", "", "module root")
	start := flag.String("start", "", "lesson directory relative to root")
	flag.Parse()
	if root == "" || *start == "" {
		fmt.Fprintln(os.Stderr, "goextract: -root and -start required")
		os.Exit(2)
	}
	var e error
	if root, e = filepath.Abs(root); e != nil {
		fail(e)
	}
	out.Extractor = Version
	out.Start = filepath.ToSlash(*start)
	readGoMod()
	pkgs := load(*start)
	for _, p := range pkgs {
		evalConsts(p)
	}
	for _, p := range pkgs {
		scanPackage(p)
	}
	refusals(pkgs)
	out.Packages = pkgs
	finish()
	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", " ")
	if e := enc.Encode(out); e != nil {
		fail(e)
	}
}

func fail(e error) {
	fmt.Fprintln(os.Stderr, "goextract:", e)
	os.Exit(1)
}

func readGoMod() {
	f, e := os.Open(filepath.Join(root, "go.mod"))
	if e != nil {
		fail(e)
	}
	defer f.Close()
	sc := bufio.NewScanner(f)
	inReq := false
	for sc.Scan() {
		line := strings.TrimSpace(strings.SplitN(sc.Text(), "//", 2)[0])
		switch {
		case strings.HasPrefix(line, "module "):
			out.Module = strings.Trim(strings.TrimSpace(line[len("module "):]), `"`)
		case line == "require (":
			inReq = true
		case inReq && line == ")":
			inReq = false
		case inReq && line != "":
			out.Requires = append(out.Requires, strings.Fields(line)[0])
		case strings.HasPrefix(line, "require "):
			out.Requires = append(out.Requires, strings.Fields(line)[1])
		}
	}
	if out.Module == "" {
		fail(fmt.Errorf("go.mod has no module line"))
	}
	sort.Strings(out.Requires)
}

func rel(abs string) string {
	r, e := filepath.Rel(root, abs)
	if e != nil {
		return abs
	}
	return filepath.ToSlash(r)
}

func importPathOf(dir string) string {
	r := rel(dir)
	if r == "." {
		return out.Module
	}
	return out.Module + "/" + r
}

// load parses every package under start and, transitively, every package of
// the same module that they import.
func load(start string) []*Pkg {
	byDir := map[string]*Pkg{}
	var queue []string
	base := filepath.Join(root, start)
	filepath.WalkDir(base, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return nil
		}
		if d.IsDir() {
			n := d.Name()
			if path != base && (n == "testdata" || n == "vendor" || strings.HasPrefix(n, ".") || strings.HasPrefix(n, "_")) {
				return filepath.SkipDir
			}
			queue = append(queue, path)
		}
		return nil
	})
	for len(queue) > 0 {
		dir := queue[0]
		queue = queue[1:]
		if _, seen := byDir[dir]; seen {
			continue
		}
		p := parseDir(dir)
		byDir[dir] = p
		if p == nil {
			continue
		}
		for _, imp := range p.Imports {
			if strings.HasPrefix(imp, out.Module+"/") {
				queue = append(queue, filepath.Join(root, filepath.FromSlash(strings.TrimPrefix(imp, out.Module+"/"))))
			}
		}
	}
	var pkgs []*Pkg
	for _, p := range byDir {
		if p != nil {
			pkgs = append(pkgs, p)
		}
	}
	sort.Slice(pkgs, func(i, j int) bool { return pkgs[i].Path < pkgs[j].Path })
	return pkgs
}

func parseDir(dir string) *Pkg {
	entries, e := os.ReadDir(dir)
	if e != nil {
		return nil
	}
	p := &Pkg{Path: importPathOf(dir), Dir: rel(dir), consts: map[string]constant.Value{}}
	imports := map[string]bool{}
	for _, en := range entries {
		n := en.Name()
		if en.IsDir() || !strings.HasSuffix(n, ".go") || strings.HasSuffix(n, "_test.go") {
			continue
		}
		path := filepath.Join(dir, n)
		f, e := parser.ParseFile(fset, path, nil, parser.SkipObjectResolution)
		if e != nil {
			out.Unresolved = append(out.Unresolved, &Unresolved{What: "file", Reason: "parse error", File: rel(path)})
			continue
		}
		if p.Name == "" {
			p.Name = f.Name.Name
		}
		p.files = append(p.files, f)
		p.names = append(p.names, rel(path))
		p.Files = append(p.Files, rel(path))
		for _, im := range f.Imports {
			v, _ := strconv.Unquote(im.Path.Value)
			imports[v] = true
		}
	}
	if len(p.files) == 0 {
		return nil
	}
	for k := range imports {
		p.Imports = append(p.Imports, k)
	}
	sort.Strings(p.Imports)
	sort.Strings(p.Files)
	return p
}

// fileCtx carries per-file import names.
type fileCtx struct {
	pkg   *Pkg
	file  string
	names map[string]string // local name -> import path
}

func newFileCtx(p *Pkg, f *ast.File, name string) *fileCtx {
	c := &fileCtx{pkg: p, file: name, names: map[string]string{}}
	for _, im := range f.Imports {
		path, _ := strconv.Unquote(im.Path.Value)
		local := path[strings.LastIndex(path, "/")+1:]
		if im.Name != nil {
			local = im.Name.Name
		}
		c.names[local] = path
	}
	return c
}

// pkgSel reports the import path and selector when e is <importname>.<Sel>.
func (c *fileCtx) pkgSel(e ast.Expr) (string, string, bool) {
	s, ok := e.(*ast.SelectorExpr)
	if !ok {
		return "", "", false
	}
	x, ok := s.X.(*ast.Ident)
	if !ok {
		return "", "", false
	}
	path, ok := c.names[x.Name]
	if !ok {
		return "", "", false
	}
	return path, s.Sel.Name, true
}

func (c *fileCtx) line(n ast.Node) int { return fset.Position(n.Pos()).Line }

func text(n ast.Node) string {
	var b bytes.Buffer
	printer.Fprint(&b, fset, n)
	return b.String()
}

func funcName(d *ast.FuncDecl) string {
	if d.Recv == nil || len(d.Recv.List) == 0 {
		return d.Name.Name
	}
	t := d.Recv.List[0].Type
	if s, ok := t.(*ast.StarExpr); ok {
		t = s.X
	}
	if ix, ok := t.(*ast.IndexExpr); ok {
		t = ix.X
	}
	if id, ok := t.(*ast.Ident); ok {
		return id.Name + "." + d.Name.Name
	}
	return d.Name.Name
}

// eval evaluates a constant expression: literals, package constants, iota,
// arithmetic, conversions to basic types, time units.
func (c *fileCtx) eval(e ast.Expr, iota int) (constant.Value, string, bool) {
	switch x := e.(type) {
	case *ast.BasicLit:
		v := constant.MakeFromLiteral(x.Value, x.Kind, 0)
		return v, "", v.Kind() != constant.Unknown
	case *ast.Ident:
		switch x.Name {
		case "true":
			return constant.MakeBool(true), "", true
		case "false":
			return constant.MakeBool(false), "", true
		case "iota":
			if iota >= 0 {
				return constant.MakeInt64(int64(iota)), "", true
			}
		}
		if v, ok := c.pkg.consts[x.Name]; ok {
			return v, "", true
		}
	case *ast.ParenExpr:
		return c.eval(x.X, iota)
	case *ast.UnaryExpr:
		v, t, ok := c.eval(x.X, iota)
		if !ok {
			return nil, "", false
		}
		return constant.UnaryOp(x.Op, v, 0), t, true
	case *ast.BinaryExpr:
		a, ta, ok1 := c.eval(x.X, iota)
		b, tb, ok2 := c.eval(x.Y, iota)
		if !ok1 || !ok2 {
			return nil, "", false
		}
		t := ta
		if t == "" {
			t = tb
		}
		switch x.Op {
		case token.SHL, token.SHR:
			s, ok := constant.Uint64Val(constant.ToInt(b))
			if !ok {
				return nil, "", false
			}
			return constant.Shift(a, x.Op, uint(s)), ta, true
		case token.EQL, token.NEQ, token.LSS, token.LEQ, token.GTR, token.GEQ:
			return constant.MakeBool(constant.Compare(a, x.Op, b)), "bool", true
		case token.QUO:
			if a.Kind() == constant.Int && b.Kind() == constant.Int {
				return constant.BinaryOp(a, token.QUO_ASSIGN, b), t, true
			}
		}
		return constant.BinaryOp(a, x.Op, b), t, true
	case *ast.SelectorExpr:
		if path, sel, ok := c.pkgSel(x); ok && path == "time" {
			if n, ok := timeUnits[sel]; ok {
				return constant.MakeInt64(n), "time.Duration", true
			}
		}
	case *ast.CallExpr:
		if len(x.Args) == 1 {
			name := ""
			if id, ok := x.Fun.(*ast.Ident); ok {
				name = id.Name
			} else if path, sel, ok := c.pkgSel(x.Fun); ok && path == "time" && sel == "Duration" {
				name = "time.Duration"
			}
			switch name {
			case "int", "int8", "int16", "int32", "int64", "uint", "uint8", "uint16", "uint32", "uint64",
				"uintptr", "float32", "float64", "string", "byte", "rune", "time.Duration":
				v, _, ok := c.eval(x.Args[0], iota)
				return v, name, ok
			}
		}
	}
	return nil, "", false
}

func show(v constant.Value, typ string) string {
	switch v.Kind() {
	case constant.String:
		return constant.StringVal(v)
	case constant.Bool:
		return strconv.FormatBool(constant.BoolVal(v))
	case constant.Int:
		if typ == "time.Duration" || typ == "duration" {
			if n, ok := constant.Int64Val(v); ok {
				return time.Duration(n).String()
			}
		}
		return v.ExactString()
	case constant.Float:
		f, _ := constant.Float64Val(v)
		return strconv.FormatFloat(f, 'g', -1, 64)
	}
	return v.ExactString()
}

func kindName(v constant.Value) string {
	switch v.Kind() {
	case constant.String:
		return "untyped string"
	case constant.Bool:
		return "untyped bool"
	case constant.Int:
		return "untyped int"
	case constant.Float:
		return "untyped float"
	}
	return "untyped"
}

func evalConsts(p *Pkg) {
	for i, f := range p.files {
		c := newFileCtx(p, f, p.names[i])
		for _, d := range f.Decls {
			g, ok := d.(*ast.GenDecl)
			if !ok || g.Tok != token.CONST {
				continue
			}
			var lastValues []ast.Expr
			var lastType ast.Expr
			for idx, s := range g.Specs {
				vs := s.(*ast.ValueSpec)
				values, typ := vs.Values, vs.Type
				if len(values) == 0 {
					values, typ = lastValues, lastType
				} else {
					lastValues, lastType = values, typ
				}
				for j, n := range vs.Names {
					if n.Name == "_" {
						continue
					}
					cst := &Const{Name: n.Name, Exported: n.IsExported(), Pkg: p.Path, File: c.file, Line: c.line(n)}
					if j < len(values) {
						cst.Expr = text(values[j])
						if v, t, ok := c.eval(values[j], idx); ok {
							p.consts[n.Name] = v
							cst.Type = t
							if typ != nil {
								cst.Type = text(typ)
							}
							if cst.Type == "" {
								cst.Type = kindName(v)
							}
							cst.Value = show(v, cst.Type)
						} else {
							if typ != nil {
								cst.Type = text(typ)
							}
							out.Unresolved = append(out.Unresolved, &Unresolved{What: "const", Reason: "value not evaluated", Expr: cst.Expr, Pkg: p.Path, File: c.file, Line: cst.Line})
						}
					}
					out.Consts = append(out.Consts, cst)
				}
			}
		}
	}
}

// inspect walks n and gives f each node with its ancestors.
func inspect(n ast.Node, f func(x ast.Node, stack []ast.Node)) {
	var stack []ast.Node
	ast.Inspect(n, func(x ast.Node) bool {
		if x == nil {
			stack = stack[:len(stack)-1]
			return true
		}
		f(x, stack)
		stack = append(stack, x)
		return true
	})
}

func strLit(e ast.Expr) (string, bool) {
	b, ok := e.(*ast.BasicLit)
	if !ok || b.Kind != token.STRING {
		return "", false
	}
	s, e2 := strconv.Unquote(b.Value)
	return s, e2 == nil
}

// stringOf resolves a string literal or a string constant of the package.
func (c *fileCtx) stringOf(e ast.Expr) (string, bool) {
	if s, ok := strLit(e); ok {
		return s, true
	}
	if v, _, ok := c.eval(e, -1); ok && v.Kind() == constant.String {
		return constant.StringVal(v), true
	}
	return "", false
}

// scanPackage collects flags, environment reads and exits.
func scanPackage(p *Pkg) {
	for i, f := range p.files {
		c := newFileCtx(p, f, p.names[i])
		sets := map[string]string{}
		// Package-level flag sets.
		for _, d := range f.Decls {
			if g, ok := d.(*ast.GenDecl); ok && g.Tok == token.VAR {
				for _, s := range g.Specs {
					vs := s.(*ast.ValueSpec)
					for j, n := range vs.Names {
						if j < len(vs.Values) {
							c.flagSet(vs.Values[j], n.Name, sets)
						}
					}
				}
			}
		}
		for _, d := range f.Decls {
			fn := ""
			local := map[string]string{}
			for k, v := range sets {
				local[k] = v
			}
			if fd, ok := d.(*ast.FuncDecl); ok {
				fn = funcName(fd)
			}
			inspect(d, func(x ast.Node, stack []ast.Node) {
				switch n := x.(type) {
				case *ast.AssignStmt:
					for j, l := range n.Lhs {
						if id, ok := l.(*ast.Ident); ok && j < len(n.Rhs) {
							c.flagSet(n.Rhs[j], id.Name, local)
						}
					}
				case *ast.CallExpr:
					c.flagCall(n, stack, local, fn)
					c.envCall(n, fn)
					c.exitCall(n, fn)
				}
			})
		}
	}
}

func (c *fileCtx) flagSet(e ast.Expr, name string, sets map[string]string) {
	call, ok := e.(*ast.CallExpr)
	if !ok {
		return
	}
	if path, sel, ok := c.pkgSel(call.Fun); ok && path == "flag" && sel == "NewFlagSet" && len(call.Args) > 0 {
		if s, ok := c.stringOf(call.Args[0]); ok {
			sets[name] = s
		} else {
			sets[name] = "<" + text(call.Args[0]) + ">"
		}
	}
}

func (c *fileCtx) flagCall(call *ast.CallExpr, stack []ast.Node, sets map[string]string, fn string) {
	sel, ok := call.Fun.(*ast.SelectorExpr)
	if !ok {
		return
	}
	m, ok := flagMethods[sel.Sel.Name]
	if !ok {
		return
	}
	set := ""
	if path, _, ok := c.pkgSel(sel); ok {
		if path != "flag" {
			return
		}
		set = "<commandline>"
	} else if id, ok := sel.X.(*ast.Ident); ok {
		if set, ok = sets[id.Name]; !ok {
			return
		}
	} else {
		return
	}
	fl := &Flag{Set: set, Method: sel.Sel.Name, Type: m.typ, Func: fn, Pkg: c.pkg.Path, File: c.file, Line: c.line(call), Bound: true}
	if m.name >= len(call.Args) {
		return
	}
	if s, ok := c.stringOf(call.Args[m.name]); ok {
		fl.Name = s
	} else {
		out.Unresolved = append(out.Unresolved, &Unresolved{What: "flag", Reason: "name not a constant", Expr: text(call), Func: fn, Pkg: c.pkg.Path, File: c.file, Line: fl.Line})
		return
	}
	if m.def >= 0 && m.def < len(call.Args) {
		fl.Default = text(call.Args[m.def])
		if v, t, ok := c.eval(call.Args[m.def], -1); ok {
			if t == "" {
				t = m.typ
			}
			fl.Value = show(v, t)
		}
	}
	if m.usage < len(call.Args) {
		if s, ok := c.stringOf(call.Args[m.usage]); ok {
			fl.Usage = s
		}
	}
	if len(stack) > 0 {
		if _, ok := stack[len(stack)-1].(*ast.ExprStmt); ok && !strings.HasSuffix(fl.Method, "Var") && fl.Method != "Var" && fl.Method != "Func" && fl.Method != "BoolFunc" {
			fl.Bound = false
		}
	}
	out.Flags = append(out.Flags, fl)
}

func (c *fileCtx) envCall(call *ast.CallExpr, fn string) {
	path, sel, ok := c.pkgSel(call.Fun)
	if !ok || len(call.Args) == 0 {
		return
	}
	name := path + "." + sel
	switch name {
	case "os.Getenv", "os.LookupEnv", "syscall.Getenv", "os.Setenv", "os.Unsetenv":
	default:
		return
	}
	if s, ok := c.stringOf(call.Args[0]); ok {
		out.Env = append(out.Env, &Env{Name: s, Call: name, Func: fn, Pkg: c.pkg.Path, File: c.file, Line: c.line(call)})
		return
	}
	out.Unresolved = append(out.Unresolved, &Unresolved{What: "env", Reason: "name not a constant", Expr: text(call), Func: fn, Pkg: c.pkg.Path, File: c.file, Line: c.line(call)})
}

func (c *fileCtx) exitCall(call *ast.CallExpr, fn string) {
	path, sel, ok := c.pkgSel(call.Fun)
	if !ok {
		return
	}
	switch {
	case path == "os" && sel == "Exit" && len(call.Args) == 1:
		if v, _, ok := c.eval(call.Args[0], -1); ok && v.Kind() == constant.Int {
			n, _ := constant.Int64Val(v)
			out.Exits = append(out.Exits, &Exit{Code: int(n), Call: "os.Exit", Func: fn, Pkg: c.pkg.Path, File: c.file, Line: c.line(call)})
		} else {
			out.Unresolved = append(out.Unresolved, &Unresolved{What: "exit", Reason: "code not a constant", Expr: text(call), Func: fn, Pkg: c.pkg.Path, File: c.file, Line: c.line(call)})
		}
	case path == "log" && (sel == "Fatal" || sel == "Fatalf" || sel == "Fatalln"):
		out.Exits = append(out.Exits, &Exit{Code: 1, Call: "log." + sel, Func: fn, Pkg: c.pkg.Path, File: c.file, Line: c.line(call)})
	}
}

// ---- refusals ----

type ctorInfo struct {
	key         string
	short       string
	kindParam   string
	defaultWord bool                // error word defaults to the kind
	kindWords   map[string]string   // kind -> word fixed inside the constructor
	kindFields  map[string][]string // kind -> body fields fixed inside the constructor
}

type wrapperInfo struct {
	code   int
	kind   string
	params []string
	words  []string
	fields []string
	src    string
	ws     string
}

type funcRef struct {
	c  *fileCtx
	fd *ast.FuncDecl
}

// calleeKey names the called function: <import path>.<name> for package
// functions, ".<name>" for methods (receiver type unknown without types).
func (c *fileCtx) calleeKey(call *ast.CallExpr) string {
	switch f := call.Fun.(type) {
	case *ast.Ident:
		return c.pkg.Path + "." + f.Name
	case *ast.SelectorExpr:
		if path, sel, ok := c.pkgSel(f); ok {
			return path + "." + sel
		}
		return "." + f.Sel.Name
	}
	return ""
}

func shortKey(k string) string {
	return k[strings.LastIndex(k, "/")+1:]
}

func (c *fileCtx) intOf(e ast.Expr) (int, bool) {
	if path, sel, ok := c.pkgSel(e); ok && path == "net/http" {
		n, ok := statusN[sel]
		return n, ok
	}
	if v, _, ok := c.eval(e, -1); ok && v.Kind() == constant.Int {
		n, ok := constant.Int64Val(v)
		return int(n), ok
	}
	return 0, false
}

func isRefusalShape(c *fileCtx, call *ast.CallExpr) bool {
	if len(call.Args) < 2 {
		return false
	}
	code, ok := c.intOf(call.Args[0])
	if !ok || code < 400 || code > 599 {
		return false
	}
	k, ok := c.stringOf(call.Args[1])
	return ok && kindRE.MatchString(k)
}

// render turns a word expression into text; non-constant parts become {expr}.
func (c *fileCtx) render(e ast.Expr, subst map[string]string) string {
	switch x := e.(type) {
	case *ast.BasicLit:
		if s, ok := strLit(x); ok {
			return s
		}
		return x.Value
	case *ast.Ident:
		if v, ok := subst[x.Name]; ok {
			return v
		}
		if s, ok := c.stringOf(x); ok {
			return s
		}
		return "{" + x.Name + "}"
	case *ast.BinaryExpr:
		if x.Op == token.ADD && !numericLit(x.X) && !numericLit(x.Y) {
			return c.render(x.X, subst) + c.render(x.Y, subst)
		}
	case *ast.ParenExpr:
		return c.render(x.X, subst)
	case *ast.CallExpr:
		if path, sel, ok := c.pkgSel(x.Fun); ok && path == "fmt" && (sel == "Sprintf" || sel == "Errorf") && len(x.Args) > 0 {
			if f, ok := c.stringOf(x.Args[0]); ok {
				args := x.Args[1:]
				i := 0
				return verbRE.ReplaceAllStringFunc(f, func(v string) string {
					if v == "%%" {
						return "%"
					}
					if i >= len(args) {
						return v
					}
					a := args[i]
					i++
					if s, ok := c.stringOf(a); ok {
						return s
					}
					return c.render(a, subst)
				})
			}
		}
	}
	return "{" + text(e) + "}"
}

func numericLit(e ast.Expr) bool {
	b, ok := e.(*ast.BasicLit)
	return ok && b.Kind != token.STRING
}

func hasLiteralText(s string) bool {
	return strings.TrimSpace(placeholderRE.ReplaceAllString(s, "")) != ""
}

func refusals(pkgs []*Pkg) {
	var funcs []funcRef
	decls := map[string]funcRef{}
	for _, p := range pkgs {
		for i, f := range p.files {
			c := newFileCtx(p, f, p.names[i])
			for _, d := range f.Decls {
				if fd, ok := d.(*ast.FuncDecl); ok && fd.Body != nil {
					funcs = append(funcs, funcRef{c, fd})
					if fd.Recv == nil {
						decls[p.Path+"."+fd.Name.Name] = funcRef{c, fd}
					}
				}
			}
		}
	}
	// Phase A: constructors are functions called with (literal 4xx/5xx, literal kind).
	ctors := map[string]*ctorInfo{}
	for _, fr := range funcs {
		ast.Inspect(fr.fd.Body, func(x ast.Node) bool {
			if call, ok := x.(*ast.CallExpr); ok && isRefusalShape(fr.c, call) {
				k := fr.c.calleeKey(call)
				if k != "" && ctors[k] == nil {
					ctors[k] = &ctorInfo{key: k, short: shortKey(k), kindWords: map[string]string{}, kindFields: map[string][]string{}}
				}
			}
			return true
		})
	}
	for k, ci := range ctors {
		fr, ok := decls[k]
		if !ok {
			continue
		}
		var params []string
		for _, f := range fr.fd.Type.Params.List {
			for _, n := range f.Names {
				params = append(params, n.Name)
			}
		}
		if len(params) > 1 {
			ci.kindParam = params[1]
		}
		ast.Inspect(fr.fd.Body, func(x ast.Node) bool {
			switch n := x.(type) {
			case *ast.CompositeLit:
				var kindV, errV ast.Expr
				for _, el := range n.Elts {
					kv, ok := el.(*ast.KeyValueExpr)
					if !ok {
						continue
					}
					if s, ok := strLit(kv.Key); ok {
						if s == "kind" {
							kindV = kv.Value
						} else if s == "error" {
							errV = kv.Value
						}
					}
				}
				if errV != nil {
					if id, ok := errV.(*ast.Ident); ok && id.Name == ci.kindParam {
						ci.defaultWord = true
					}
					ks, ok1 := strLit(kindV)
					es, ok2 := strLit(errV)
					if ok1 && ok2 {
						ci.kindWords[ks] = es
					}
				}
			case *ast.CallExpr:
				if path, sel, ok := fr.c.pkgSel(n.Fun); ok && path == "fmt" && sel == "Sprintf" && len(n.Args) > 0 {
					if f, ok := strLit(n.Args[0]); ok {
						if at := strings.Index(f, `"error":%q`); at >= 0 {
							idx := len(verbRE.FindAllString(f[:at], -1))
							if idx+1 < len(n.Args) {
								if id, ok := n.Args[idx+1].(*ast.Ident); ok && id.Name == ci.kindParam {
									ci.defaultWord = true
								}
							}
						}
					}
				}
			case *ast.BasicLit:
				if s, ok := strLit(n); ok {
					for _, m := range jsonKE.FindAllStringSubmatch(s, -1) {
						ci.kindWords[m[1]] = m[2]
						var fs []string
						for _, k := range jsonKey.FindAllStringSubmatch(s, -1) {
							if k[1] != "kind" && k[1] != "error" {
								fs = append(fs, k[1])
							}
						}
						sort.Strings(fs)
						ci.kindFields[m[1]] = fs
					}
				}
			}
			return true
		})
	}
	// Wrappers: straight-line functions `f := ctor(lit, lit); f.X[k] = …; return f`.
	wrappers := map[string]*wrapperInfo{}
	for _, fr := range funcs {
		if fr.fd.Recv != nil {
			continue
		}
		if w := wrapperOf(fr, ctors); w != nil {
			wrappers[fr.c.pkg.Path+"."+fr.fd.Name.Name] = w
		}
	}
	// Phase B: sites.
	for _, fr := range funcs {
		fn := funcName(fr.fd)
		_, isWrapper := wrappers[fr.c.pkg.Path+"."+fr.fd.Name.Name]
		if fr.fd.Recv != nil {
			isWrapper = false
		}
		inspect(fr.fd.Body, func(x ast.Node, stack []ast.Node) {
			call, ok := x.(*ast.CallExpr)
			if !ok {
				return
			}
			c := fr.c
			key := c.calleeKey(call)
			if ci, ok := ctors[key]; ok {
				site(c, fr.fd, fn, call, stack, ci, isWrapper)
				return
			}
			if w, ok := wrappers[key]; ok && !isWrapper {
				r := &Refusal{Channel: "http", Code: w.code, Kind: w.kind, Via: shortKey(key), Fields: w.fields, WordSource: w.ws, Resolved: "wrapper", Func: fn, Pkg: c.pkg.Path, File: c.file, Line: c.line(call)}
				subst := map[string]string{}
				for i, pn := range w.params {
					if i < len(call.Args) {
						if s, ok := c.stringOf(call.Args[i]); ok {
							subst[pn] = s
						} else {
							subst[pn] = c.render(call.Args[i], nil)
						}
					}
				}
				for _, wd := range w.words {
					for pn, v := range subst {
						wd = strings.ReplaceAll(wd, "{"+pn+"}", v)
					}
					r.Words = append(r.Words, wd)
				}
				out.Refusals = append(out.Refusals, r)
				return
			}
			path, sel, ok := c.pkgSel(call.Fun)
			if !ok {
				if s, ok := call.Fun.(*ast.SelectorExpr); ok && s.Sel.Name == "WriteHeader" && len(call.Args) == 1 {
					if n, ok := c.intOf(call.Args[0]); ok && n >= 400 {
						out.Refusals = append(out.Refusals, &Refusal{Channel: "http", Code: n, Via: "WriteHeader", Resolved: "literal", Func: fn, Pkg: c.pkg.Path, File: c.file, Line: c.line(call)})
					}
				}
				return
			}
			switch path + "." + sel {
			case "errors.New", "fmt.Errorf":
				if len(call.Args) == 0 {
					return
				}
				w := c.render(call, nil)
				if path == "errors" {
					w = c.render(call.Args[0], nil)
				}
				if !hasLiteralText(w) {
					out.Unresolved = append(out.Unresolved, &Unresolved{What: "error", Reason: "word not a constant", Expr: text(call), Func: fn, Pkg: c.pkg.Path, File: c.file, Line: c.line(call)})
					return
				}
				out.Refusals = append(out.Refusals, &Refusal{Channel: "error", Words: []string{w}, WordSource: "literal", Via: path + "." + sel, Resolved: "literal", Func: fn, Pkg: c.pkg.Path, File: c.file, Line: c.line(call)})
			case "net/http.Error":
				if len(call.Args) == 3 {
					r := &Refusal{Channel: "http", Via: "http.Error", Resolved: "literal", Func: fn, Pkg: c.pkg.Path, File: c.file, Line: c.line(call)}
					if n, ok := c.intOf(call.Args[2]); ok {
						r.Code = n
					} else {
						r.Resolved = "code-unresolved"
					}
					r.Words = []string{c.render(call.Args[1], nil)}
					r.WordSource = "literal"
					out.Refusals = append(out.Refusals, r)
				}
			}
		})
	}
}

func wrapperOf(fr funcRef, ctors map[string]*ctorInfo) *wrapperInfo {
	body := fr.fd.Body.List
	if len(body) < 2 || fr.fd.Type.Params.NumFields() == 0 {
		return nil
	}
	c := fr.c
	first, ok := body[0].(*ast.AssignStmt)
	if !ok || len(first.Lhs) != 1 || len(first.Rhs) != 1 {
		return nil
	}
	v, ok := first.Lhs[0].(*ast.Ident)
	call, ok2 := first.Rhs[0].(*ast.CallExpr)
	if !ok || !ok2 || ctors[c.calleeKey(call)] == nil || !isRefusalShape(c, call) {
		return nil
	}
	ret, ok := body[len(body)-1].(*ast.ReturnStmt)
	if !ok || len(ret.Results) != 1 {
		return nil
	}
	if id, ok := ret.Results[0].(*ast.Ident); !ok || id.Name != v.Name {
		return nil
	}
	for _, s := range body[1 : len(body)-1] {
		if _, ok := s.(*ast.AssignStmt); !ok {
			return nil
		}
	}
	code, _ := c.intOf(call.Args[0])
	kind, _ := c.stringOf(call.Args[1])
	w := &wrapperInfo{code: code, kind: kind}
	for _, f := range fr.fd.Type.Params.List {
		for _, n := range f.Names {
			w.params = append(w.params, n.Name)
		}
	}
	subst := map[string]string{}
	for _, pn := range w.params {
		subst[pn] = "{" + pn + "}"
	}
	w.words, w.fields = bodyFields(c, fr.fd.Body, v.Name, call.End(), subst)
	if len(w.words) > 0 {
		w.ws = "assigned"
	}
	return w
}

// bodyFields finds `<v>.X["k"] = expr` or `<v>["k"] = expr` after pos.
func bodyFields(c *fileCtx, body *ast.BlockStmt, v string, after token.Pos, subst map[string]string) (words, fields []string) {
	seen := map[string]bool{}
	ast.Inspect(body, func(x ast.Node) bool {
		as, ok := x.(*ast.AssignStmt)
		if !ok || as.Pos() < after || len(as.Lhs) != 1 || len(as.Rhs) != 1 {
			return true
		}
		ix, ok := as.Lhs[0].(*ast.IndexExpr)
		if !ok {
			return true
		}
		base := ix.X
		if s, ok := base.(*ast.SelectorExpr); ok {
			base = s.X
		}
		if id, ok := base.(*ast.Ident); !ok || id.Name != v {
			return true
		}
		k, ok := strLit(ix.Index)
		if !ok {
			return true
		}
		if k == "error" {
			words = append(words, c.render(as.Rhs[0], subst))
		} else if k != "kind" && !seen[k] {
			seen[k] = true
			fields = append(fields, k)
		}
		return true
	})
	sort.Strings(fields)
	return
}

func site(c *fileCtx, fd *ast.FuncDecl, fn string, call *ast.CallExpr, stack []ast.Node, ci *ctorInfo, inWrapper bool) {
	line := c.line(call)
	var codes []int
	resolved := "literal"
	if n, ok := c.intOf(call.Args[0]); ok {
		codes = []int{n}
	} else if id, ok := call.Args[0].(*ast.Ident); ok {
		codes = localInts(c, fd, id.Name)
		resolved = "local-assign"
	}
	if len(call.Args) < 2 {
		return
	}
	kind, kok := c.stringOf(call.Args[1])
	if len(codes) == 0 || !kok {
		reason := "code not resolved"
		if !kok {
			reason = "kind not a constant"
		}
		out.Unresolved = append(out.Unresolved, &Unresolved{What: "refusal", Reason: reason, Expr: text(call), Func: fn, Pkg: c.pkg.Path, File: c.file, Line: line})
		return
	}
	var words, fields []string
	ws := ""
	if len(stack) > 0 {
		if as, ok := stack[len(stack)-1].(*ast.AssignStmt); ok && len(as.Lhs) == 1 && len(as.Rhs) == 1 && as.Rhs[0] == call {
			if v, ok := as.Lhs[0].(*ast.Ident); ok {
				words, fields = bodyFields(c, fd.Body, v.Name, call.End(), nil)
				if len(words) > 0 {
					ws = "assigned"
				}
			}
		}
	}
	if len(words) == 0 {
		if w, ok := ci.kindWords[kind]; ok {
			words, ws = []string{w}, "constructor"
			if len(fields) == 0 {
				fields = ci.kindFields[kind]
			}
		} else if ci.defaultWord {
			words, ws = []string{kind}, "constructor-default"
		}
	}
	channel := "http"
	if inWrapper {
		channel = "wrapper"
	}
	for _, code := range codes {
		r := &Refusal{Channel: channel, Code: code, Kind: kind, Words: words, WordSource: ws, Fields: fields, Via: ci.short, Resolved: resolved, Func: fn, Pkg: c.pkg.Path, File: c.file, Line: line}
		if inWrapper {
			out.Wrappers = append(out.Wrappers, r)
		} else {
			out.Refusals = append(out.Refusals, r)
		}
	}
}

// localInts collects integer constants assigned to name inside fd.
func localInts(c *fileCtx, fd *ast.FuncDecl, name string) []int {
	seen := map[int]bool{}
	ast.Inspect(fd.Body, func(x ast.Node) bool {
		switch n := x.(type) {
		case *ast.AssignStmt:
			for i, l := range n.Lhs {
				if id, ok := l.(*ast.Ident); ok && id.Name == name && i < len(n.Rhs) {
					if v, ok := c.intOf(n.Rhs[i]); ok {
						seen[v] = true
					}
				}
			}
		case *ast.ValueSpec:
			for i, id := range n.Names {
				if id.Name == name && i < len(n.Values) {
					if v, ok := c.intOf(n.Values[i]); ok {
						seen[v] = true
					}
				}
			}
		}
		return true
	})
	var r []int
	for v := range seen {
		r = append(r, v)
	}
	sort.Ints(r)
	return r
}

func finish() {
	sort.Slice(out.Flags, func(i, j int) bool {
		a, b := out.Flags[i], out.Flags[j]
		if a.File != b.File {
			return a.File < b.File
		}
		return a.Line < b.Line
	})
	sort.Slice(out.Env, func(i, j int) bool {
		a, b := out.Env[i], out.Env[j]
		if a.File != b.File {
			return a.File < b.File
		}
		return a.Line < b.Line
	})
	sort.Slice(out.Consts, func(i, j int) bool {
		a, b := out.Consts[i], out.Consts[j]
		if a.File != b.File {
			return a.File < b.File
		}
		return a.Line < b.Line
	})
	for _, rs := range [][]*Refusal{out.Refusals, out.Wrappers} {
		sort.SliceStable(rs, func(i, j int) bool {
			a, b := rs[i], rs[j]
			if a.File != b.File {
				return a.File < b.File
			}
			if a.Line != b.Line {
				return a.Line < b.Line
			}
			return a.Code < b.Code
		})
	}
	sort.Slice(out.Exits, func(i, j int) bool {
		a, b := out.Exits[i], out.Exits[j]
		if a.File != b.File {
			return a.File < b.File
		}
		return a.Line < b.Line
	})
	sort.SliceStable(out.Unresolved, func(i, j int) bool {
		a, b := out.Unresolved[i], out.Unresolved[j]
		if a.File != b.File {
			return a.File < b.File
		}
		return a.Line < b.Line
	})
}
