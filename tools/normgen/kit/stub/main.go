// stubstore is the P/01 store daemon stub for the external door judge (ADR-0125 addendum (1), item 1): kit B (door from
// OpenAPI, writecheck from write-checks.tsv) behind a simple net/http frame and an in-memory store without N3 semantics.
// It is not a lesson implementation: no cas, guard, id memory, admission time, durability or group. The judge measures
// core-independent P/01.1 acceptance steps: response shapes, parse refusal codes, routes and methods. Handwritten;
// tools/normgen/kit/build_stub.py rewrites the internal package imports.
//
// Run: stubstore -dir <directory> -admin <admin.sock path> -rights <rights file> -max-body <bytes> -max-value <bytes>
// Role sockets (<role>.sock for each role in the rights file) are next to admin.sock.
package main

import (
	"bytes"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"sync"
	"syscall"

	"kitmodule/internal/apidoor"
	"kitmodule/internal/jsonstrict"
	"kitmodule/internal/writecheck"
)

// Lesson limits (P/01.1 N1): BATCH_WRITES and BATCH_GUARDS are 64; ROW_CEILING is the -max-value flag.
const batchLimit = 64

type rights struct {
	Roles map[string]struct {
		Read   []string `json:"read"`
		Write  []string `json:"write"`
		Delete []string `json:"delete"`
	} `json:"roles"`
}

type row struct {
	items map[string]string
	index string
}

type store struct {
	mu       sync.Mutex
	rows     map[string]row
	next     uint64
	maxBody  int64
	maxValue int64
	rights   rights
	raw      any // Rights file as a JSON value (for /v1/rights).
}

// call is the handwritten handler's call context: the socket role.
type call struct {
	sock string
}

// match is the stub rights pattern: "prefix*" or an exact key (full P/01.2 N1.3 semantics are outside the stub).
func match(patterns []string, key string) bool {
	for _, p := range patterns {
		if strings.HasSuffix(p, "*") && strings.HasPrefix(key, strings.TrimSuffix(p, "*")) || p == key {
			return true
		}
	}
	return false
}

func (s *store) allowed(sock, op, key string) bool {
	if sock == "admin" {
		return true
	}
	r, ok := s.rights.Roles[sock]
	if !ok {
		return false
	}
	switch op {
	case "read":
		return match(r.Read, key)
	case "write":
		return match(r.Write, key)
	case "delete":
		return match(r.Delete, key)
	}
	return false
}

func (s *store) version() string {
	s.next++
	return strconv.FormatUint(s.next, 10)
}

func copyHead(op apidoor.Op) bool {
	bodyless := false
	// BEGIN CopyHead
	bodyless = op == apidoor.OpCopyHead
	// END CopyHead
	return bodyless
}

func refuse(op apidoor.Op, code int, kind, msg string, fields map[string]any) apidoor.Answer {
	if copyHead(op) {
		return apidoor.Answer{Code: code}
	}
	a, err := apidoor.Refuse(op, code, kind, msg, fields)
	if err != nil {
		log.Printf("stubstore: refuse %v %d %s: %v", op, code, kind, err)
		a, _ = apidoor.Refuse(op, 503, "unavailable", "stub: "+kind, nil)
	}
	return a
}

// apidoor.Handler methods form the handwritten part of the stub.

func (s *store) Get(c *call, q apidoor.GetQuery) apidoor.Answer {
	if len(q.Key) > 1024 { // N1: key limit in UTF-8 bytes, outside the OpenAPI form.
		return refuse(apidoor.OpGet, 400, "badkey", "key too long", nil)
	}
	if !s.allowed(c.sock, "read", q.Key) {
		return refuse(apidoor.OpGet, 403, "forbidden", "no read right", nil)
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	r, ok := s.rows[q.Key]
	if !ok {
		return apidoor.Answer{Code: 200, Body: apidoor.Row2{}}
	}
	items := make(map[string]string, len(r.items))
	for k, v := range r.items {
		items[k] = v
	}
	return apidoor.Answer{Code: 200, Body: apidoor.Row1{Items: items, Index: r.index}}
}

func (s *store) List(c *call, q apidoor.ListQuery) apidoor.Answer {
	prefix := ""
	if q.Prefix != nil {
		prefix = *q.Prefix
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	keys := map[string]string{}
	for k, r := range s.rows {
		if strings.HasPrefix(k, prefix) {
			keys[k] = r.index
		}
	}
	return apidoor.Answer{Code: 200, Body: apidoor.Listing{Keys: keys}}
}

func strItems(v any) map[string]string {
	m, _ := v.(map[string]any)
	out := make(map[string]string, len(m))
	for k, x := range m {
		out[k], _ = x.(string)
	}
	return out
}

func (s *store) apply(op, key string, items any) {
	if op == "put" {
		s.rows[key] = row{items: strItems(items)}
	} else {
		delete(s.rows, key)
	}
}

func (s *store) Write(c *call, body []byte) apidoor.Answer {
	lim := map[string]int64{"BATCH_WRITES": batchLimit, "BATCH_GUARDS": batchLimit, "ROW_CEILING": s.maxValue}
	r, v := writecheck.Check(body, c.sock, lim, s.allowed)
	if r != nil {
		return refuse(apidoor.OpWrite, r.Code, r.Kind, "refused", r.Fault)
	}
	cmd := v.(map[string]any)
	s.mu.Lock()
	defer s.mu.Unlock()
	switch cmd["op"] {
	case "floor":
		if _, e := apidoor.DecodeFloorCmd(cmd); e != nil {
			return refuse(apidoor.OpWrite, 400, "badrequest", "floor out of form", nil)
		}
		return apidoor.Answer{Code: 200, Body: apidoor.Written{Index: s.version()}}
	case "batch":
		index := s.version()
		for _, w := range cmd["writes"].([]any) {
			m := w.(map[string]any)
			key := m["key"].(string)
			s.apply(m["op"].(string), key, m["items"])
			if x, ok := s.rows[key]; ok {
				x.index = index
				s.rows[key] = x
			}
		}
		return apidoor.Answer{Code: 200, Body: apidoor.Written{Index: index}}
	}
	key := cmd["key"].(string)
	index := s.version()
	s.apply(cmd["op"].(string), key, cmd["items"])
	if x, ok := s.rows[key]; ok {
		x.index = index
		s.rows[key] = x
	}
	return apidoor.Answer{Code: 200, Body: apidoor.Written{Index: index}}
}

func (s *store) Rights(c *call) apidoor.Answer {
	if c.sock != "admin" {
		return refuse(apidoor.OpRights, 403, "forbidden", "admin only", nil)
	}
	if s.raw == nil {
		return refuse(apidoor.OpRights, 404, "badrequest", "no rights file", nil)
	}
	a, err := apidoor.AnswerOf(apidoor.OpRights, 200, s.raw)
	if err != nil {
		return refuse(apidoor.OpRights, 503, "unavailable", "rights file out of form", nil)
	}
	return a
}

func (s *store) Status(c *call) apidoor.Answer {
	s.mu.Lock()
	defer s.mu.Unlock()
	return apidoor.Answer{Code: 200, Body: apidoor.Status{Id: "stub", State: "Leader", LeaderId: "stub", Commit: s.next,
		Applied: s.next, Voters: []string{"stub"}, Members: map[string]string{}, MaxValue: s.maxValue, MaxBody: s.maxBody}}
}

func (s *store) member(op apidoor.Op, c *call, body []byte, decode func(any) *apidoor.Violation) apidoor.Answer {
	if c.sock != "admin" {
		return refuse(op, 403, "forbidden", "admin.sock only", nil)
	}
	v, _, err := jsonstrict.Decode(body, jsonstrict.Depth)
	if err != nil {
		return refuse(op, 400, "badrequest", "not JSON", nil)
	}
	if e := decode(v); e != nil {
		return refuse(op, 400, "badrequest", "out of form", nil)
	}
	return refuse(op, 409, "refused", "stub has no group", nil)
}

func (s *store) Join(c *call, body []byte) apidoor.Answer {
	return s.member(apidoor.OpJoin, c, body, func(v any) *apidoor.Violation { _, e := apidoor.DecodeJoin(v); return e })
}

func (s *store) Leave(c *call, body []byte) apidoor.Answer {
	return s.member(apidoor.OpLeave, c, body, func(v any) *apidoor.Violation { _, e := apidoor.DecodeLeave(v); return e })
}

func (s *store) Metrics(c *call) apidoor.Answer {
	return apidoor.Answer{Code: 200, Body: apidoor.Metrics200("configstore_doors 1\n")}
}

// BEGIN CopyGet
// CopyGet never claims to produce a consistent snapshot: this stub has no store core.
func (s *store) CopyGet(c *call) apidoor.Answer {
	if c.sock != "admin" {
		return refuse(apidoor.OpCopyGet, 403, "forbidden", "admin.sock only", nil)
	}
	return refuse(apidoor.OpCopyGet, 503, "unavailable", "stub has no snapshot", nil)
}

// END CopyGet

// BEGIN CopyHead
func (s *store) CopyHead(c *call) apidoor.Answer {
	return apidoor.Answer{Code: 405, Allow: true}
}

// END CopyHead

// QueryRefused selects the refusal for an out-of-form query, specified only in prose in OpenAPI (P/01.1 N2.1):
// duplicates and missing values give badrequest; values outside the Key schema (including invalid UTF-8) give badkey.
func (s *store) QueryRefused(c *call, op apidoor.Op, e *apidoor.QueryError) apidoor.Answer {
	if e.Reason == apidoor.QueryValue && e.Schema == "Key" {
		return refuse(op, 400, "badkey", "bad key", nil)
	}
	return refuse(op, 400, "badrequest", "query out of form", nil)
}

// Frame: net/http (a stub, not the N2.1 frame). Order: route -> identity -> body limit -> operation.

type handler struct {
	s    *store
	sock string
}

func write(w http.ResponseWriter, r *apidoor.Response) {
	for _, h := range r.Header {
		w.Header().Add(h[0], h[1])
	}
	w.Header().Set("Content-Length", strconv.Itoa(len(r.Body)))
	w.WriteHeader(r.Code)
	_, _ = w.Write(r.Body)
}

func (h handler) answer(w http.ResponseWriter, op apidoor.Op, a apidoor.Answer) {
	resp, err := apidoor.Encode(op, a)
	if err != nil {
		log.Printf("stubstore: %v", err)
		resp, _ = apidoor.Encode(op, refuse(op, 503, "unavailable", "stub: undeclared answer", nil))
	}
	write(w, resp)
}

func (h handler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	op, query, refusal := apidoor.Route(r.Method, r.RequestURI)
	if refusal != nil {
		write(w, refusal)
		return
	}
	c := &call{sock: h.sock}
	if !copyHead(op) && h.sock != "admin" && r.Header.Get("X-Configstore-Role") != "" {
		h.answer(w, op, refuse(op, 403, "forbidden", "role header on a role socket", nil))
		return
	}
	var body []byte
	if r.Body != nil {
		limit := h.s.maxBody
		if r.ContentLength > limit {
			w.Header().Set("Connection", "close")
			h.answer(w, op, refuse(op, 413, "toolarge", "body too large",
				map[string]any{"limit": limit, "size": r.ContentLength}))
			return
		}
		b, err := io.ReadAll(io.LimitReader(r.Body, limit+1))
		if err != nil {
			h.answer(w, op, refuse(op, 400, "badrequest", "body", nil))
			return
		}
		if int64(len(b)) > limit {
			w.Header().Set("Connection", "close")
			h.answer(w, op, refuse(op, 413, "toolarge", "body too large", map[string]any{"limit": limit}))
			return
		}
		body = b
	}
	h.answer(w, op, apidoor.Dispatch[*call](h.s, c, op, query, body))
}

func listen(path string, s *store, sock string, servers *[]*http.Server) {
	_ = os.Remove(path)
	l, err := net.Listen("unix", path)
	if err != nil {
		fmt.Fprintf(os.Stderr, "stubstore: socket %s: %v\n", path, err)
		os.Exit(2)
	}
	srv := &http.Server{Handler: handler{s: s, sock: sock}}
	*servers = append(*servers, srv)
	go func() { _ = srv.Serve(l) }()
}

func main() {
	dir := flag.String("dir", "", "data directory")
	admin := flag.String("admin", "", "path of admin.sock (role sockets next to it)")
	rightsPath := flag.String("rights", "", "rights file")
	maxBody := flag.Int64("max-body", 1048576, "body read limit, bytes")
	maxValue := flag.Int64("max-value", 524288, "row ceiling, bytes")
	flag.Parse()
	if *dir == "" || *admin == "" || *maxBody <= 0 || *maxValue <= 0 || flag.NArg() != 0 {
		fmt.Fprintln(os.Stderr, "stubstore: -dir, -admin required; -max-body, -max-value > 0")
		os.Exit(2)
	}
	if err := os.MkdirAll(*dir, 0o755); err != nil {
		fmt.Fprintln(os.Stderr, "stubstore:", err)
		os.Exit(2)
	}
	s := &store{rows: map[string]row{}, maxBody: *maxBody, maxValue: *maxValue}
	if *rightsPath != "" {
		data, err := os.ReadFile(*rightsPath)
		if err == nil {
			err = json.Unmarshal(data, &s.rights)
		}
		if err == nil {
			d := json.NewDecoder(bytes.NewReader(data))
			d.UseNumber()
			err = d.Decode(&s.raw)
		}
		if err != nil {
			fmt.Fprintln(os.Stderr, "stubstore: rights file:", err)
			os.Exit(2)
		}
	}
	var servers []*http.Server
	listen(*admin, s, "admin", &servers)
	roles := make([]string, 0, len(s.rights.Roles))
	for role := range s.rights.Roles {
		roles = append(roles, role)
	}
	sort.Strings(roles)
	for _, role := range roles {
		listen(filepath.Join(filepath.Dir(*admin), role+".sock"), s, role, &servers)
	}
	stop := make(chan os.Signal, 1)
	signal.Notify(stop, syscall.SIGTERM, syscall.SIGINT)
	<-stop
	for _, srv := range servers {
		_ = srv.Close()
	}
	_ = os.Remove(*admin)
	for _, role := range roles {
		_ = os.Remove(filepath.Join(filepath.Dir(*admin), role+".sock"))
	}
}
