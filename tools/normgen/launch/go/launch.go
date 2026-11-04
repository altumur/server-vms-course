// Package launch — the daemon frame of the store (kit part launch; ADR-0083 addendum (95) item 3, ADR-0125): the
// command line by forms/daemon-flags.tsv (package flags), the FORMAT mark (P/01.3 Н1.3 format), the flat sockets
// (Н1.3 sockets), on every socket your HTTP frame (App.Frame: internal/frame — yours, ADR-0125 addendum (1) item 2) over
// your Core (the same Open as the stage tests), SIGTERM — a clean stop. Yours: coreadapter.Open (the core),
// internal/frame (the HTTP frame and the limits of Н2.1) and cmd/configstore/main.go (the mark, the hooks).
package launch

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"os"
	"os/signal"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"

	"normgen/p01-1/apidoor"
	"normgen/p01-1/coreadapter"
	"normgen/p01-1/flags"
)

// RefuseCode — the exit code of a start refusal (P/01.3 Н4).
const RefuseCode = 2

// Mark — the FORMAT mark of the data directory (P/01.3 Н1.3 format): format and version — your on-disk format,
// impl — the name of your implementation, only for the log.
type Mark struct {
	Format  string `json:"format"`
	Version int64  `json:"version"`
	Impl    string `json:"impl"`
}

// App — what main gives Main.
type App struct {
	Mark Mark
	// Open — a fresh core (coreadapter.Open): DataDir = -dir, Rights = the bytes of -rights (nil without it),
	// BodyLimit = -max-body, RowCeiling = -max-value, Now = time.Now.
	Open func(coreadapter.Config) (coreadapter.Core, error)
	// Frame — the HTTP frame of one socket (yours: internal/frame, frame.New): sock is "admin" or the role — the
	// identity of every request on it (Call.Sock); the frame calls coreadapter.Handle(c, cfg, Call{Sock: sock}, …).
	Frame func(c coreadapter.Core, cfg coreadapter.Config, sock string) Frame
	// Raft — the build has raft; false (a box): -group-size 3|5, -join, -door — code 2 «this build has no raft»
	// (P/01.3 Н1.3 box).
	Raft bool
	// Start — optional: called once the sockets listen (an -api door, the group…); stop is called on SIGTERM.
	Start func(f *flags.Flags, c coreadapter.Core) (stop func(), err error)
	// Admin — the subcommands of admin_ops (status, join, …); nil — «not implemented», exit 1.
	Admin func(f *flags.Flags) int
	// Log — the daemon log; nil — os.Stderr.
	Log io.Writer
}

// Frame — the HTTP frame of one socket: Serve serves l until Shutdown (then it returns nil; any other return is a
// failure of the socket, the daemon stops with exit 1); Shutdown stops accepting and waits for the requests in flight
// until ctx is done.
type Frame interface {
	Serve(l net.Listener) error
	Shutdown(ctx context.Context) error
}

// Refusal — a start refusal: exit code 2, Reason goes to the log.
type Refusal struct{ Reason string }

func (r *Refusal) Error() string { return r.Reason }

func refusef(format string, a ...any) *Refusal { return &Refusal{Reason: fmt.Sprintf(format, a...)} }

// Main — the whole daemon: parse, refuse (2), mark, open, listen, serve until SIGTERM (0). os.Exit(Main(…)).
func Main(args []string, getenv func(string) string, app App) int {
	log := app.Log
	if log == nil {
		log = os.Stderr
	}
	f, r := flags.ParseArgs(args, getenv)
	if r != nil {
		fmt.Fprintf(log, "configstore: %s\n", r.Error())
		return RefuseCode
	}
	if f.Cmd != "daemon" {
		if app.Admin == nil {
			fmt.Fprintf(log, "configstore: %s: not implemented\n", f.Cmd)
			return 1
		}
		return app.Admin(f)
	}
	d, err := Start(f, getenv, app)
	if err != nil {
		fmt.Fprintf(log, "configstore: %s\n", err)
		var ref *Refusal
		if errors.As(err, &ref) {
			return RefuseCode
		}
		return 1
	}
	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGTERM, syscall.SIGINT)
	select {
	case <-sig:
	case err = <-d.Failed:
		fmt.Fprintf(log, "configstore: %s\n", err)
	}
	d.Stop()
	if err != nil {
		return 1
	}
	return 0
}

// Daemon — a started daemon: Stop closes the sockets, waits for the requests, closes the core.
type Daemon struct {
	Core      coreadapter.Core
	Listeners map[string]net.Listener // "admin" and the roles → the listener
	Failed    chan error              // a socket stopped serving
	servers   []Frame
	created   []string
	stop      func()
	once      sync.Once
}

// Start — everything of Main except the wait: refusals (Refusal — code 2), the mark, Open, the sockets, HTTP.
func Start(f *flags.Flags, getenv func(string) string, app App) (*Daemon, error) {
	if !app.Raft && (f.GroupSize == 3 || f.GroupSize == 5 || f.Given["-join"] || f.Given["-door"]) {
		return nil, refusef("this build has no raft")
	}
	var rights []byte
	roles := []string{}
	if f.Rights != "" {
		b, err := os.ReadFile(f.Rights)
		if err != nil {
			return nil, refusef("rights file %s: %v", f.Rights, err)
		}
		if roles, err = Roles(b); err != nil {
			return nil, refusef("rights file %s: %v", f.Rights, err)
		}
		rights = b
	}
	if err := CheckFormat(f.Dir, app.Mark); err != nil {
		return nil, err
	}
	ls, created, err := Listen(f.Sockets, roles, getenv)
	if err != nil {
		return nil, err
	}
	cfg := coreadapter.Config{BodyLimit: f.MaxBody, RowCeiling: f.MaxValue, Rights: rights, Now: time.Now, DataDir: f.Dir}
	if app.Open == nil {
		closeAll(ls, created)
		return nil, errors.New("launch: App.Open is nil")
	}
	if app.Frame == nil {
		closeAll(ls, created)
		return nil, errors.New("launch: App.Frame is nil (cmd/configstore/main.go: Frame — your internal/frame)")
	}
	c, err := app.Open(cfg)
	if errors.Is(err, coreadapter.ErrNotImplemented) { // no core yet: the empty store of the frame
		log := app.Log
		if log == nil {
			log = os.Stderr
		}
		fmt.Fprintln(log, "configstore: coreadapter.Open is not implemented: the empty core of the kit (every key absent)")
		c, err = Empty{}, nil
	}
	if err != nil {
		closeAll(ls, created)
		return nil, fmt.Errorf("open the core: %w", err)
	}
	d := &Daemon{Core: c, Listeners: ls, Failed: make(chan error, len(ls)), created: created}
	for name, l := range ls {
		srv := app.Frame(c, cfg, name)
		d.servers = append(d.servers, srv)
		go func(name string, l net.Listener) {
			if err := srv.Serve(l); err != nil {
				d.Failed <- fmt.Errorf("socket %s: %w", name, err)
			}
		}(name, l)
	}
	if app.Start != nil {
		stop, err := app.Start(f, c)
		if err != nil {
			d.Stop()
			return nil, err
		}
		d.stop = stop
	}
	return d, nil
}

// Stop — a clean stop (idempotent).
func (d *Daemon) Stop() {
	d.once.Do(func() {
		if d.stop != nil {
			d.stop()
		}
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		for _, s := range d.servers {
			_ = s.Shutdown(ctx)
		}
		d.Core.Close()
		for _, p := range d.created {
			_ = os.Remove(p)
		}
	})
}

// Roles — the role names of a rights file (P/01.2 Н1.2): the keys of "roles". Only what the sockets need; the form of
// the file is your core's (Open gets the bytes).
func Roles(file []byte) ([]string, error) {
	var doc struct {
		Roles map[string]json.RawMessage `json:"roles"`
	}
	dec := json.NewDecoder(bytes.NewReader(file))
	if err := dec.Decode(&doc); err != nil {
		return nil, fmt.Errorf("not a JSON object with roles: %v", err)
	}
	if doc.Roles == nil {
		return nil, errors.New("no roles")
	}
	out := make([]string, 0, len(doc.Roles))
	for name := range doc.Roles {
		if name == "" || name == "admin" || strings.ContainsAny(name, "/\x00") || name == "." || name == ".." {
			return nil, fmt.Errorf("role %q cannot name a socket", name)
		}
		out = append(out, name)
	}
	sort.Strings(out)
	return out, nil
}

// CheckFormat — the FORMAT mark (P/01.3 Н1.3 format): an empty or absent directory — FORMAT is written first (tmp +
// rename); otherwise FORMAT must be in form with your format and version; else Refusal (code 2) naming the directory
// and the mark found; nothing is written or removed then.
func CheckFormat(dir string, m Mark) error {
	if dir == "" {
		return refusef("no -dir")
	}
	entries, err := os.ReadDir(dir)
	if errors.Is(err, os.ErrNotExist) {
		if err := os.MkdirAll(dir, 0o700); err != nil {
			return fmt.Errorf("data directory %s: %w", dir, err)
		}
		entries, err = nil, nil
	}
	if err != nil {
		return refusef("data directory %s: %v", dir, err)
	}
	path := filepath.Join(dir, "FORMAT")
	if len(entries) == 0 {
		return writeMark(dir, m)
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		return refusef("data directory %s is not empty and has no FORMAT mark", dir)
	}
	got, err := readMark(raw)
	if err != nil {
		return refusef("data directory %s: FORMAT out of form (%v): %q", dir, err, clip(raw))
	}
	if got.Format != m.Format || got.Version != m.Version {
		return refusef("data directory %s: foreign FORMAT mark %q version %d (impl %q); this build reads %q version %d",
			dir, got.Format, got.Version, got.Impl, m.Format, m.Version)
	}
	return nil
}

func readMark(raw []byte) (Mark, error) {
	var fields map[string]json.RawMessage
	if err := json.Unmarshal(raw, &fields); err != nil {
		return Mark{}, err
	}
	var m Mark
	if len(fields) != 3 || json.Unmarshal(fields["format"], &m.Format) != nil ||
		json.Unmarshal(fields["impl"], &m.Impl) != nil || fields["version"] == nil {
		return Mark{}, errors.New("want {format, version, impl}")
	}
	v := string(fields["version"])
	n, err := strconv.ParseInt(v, 10, 64)
	if err != nil {
		return Mark{}, errors.New("version is not an integer")
	}
	m.Version = n
	return m, nil
}

func writeMark(dir string, m Mark) error {
	b, err := json.Marshal(m)
	if err != nil {
		return err
	}
	tmp := filepath.Join(dir, "FORMAT.tmp")
	fh, err := os.OpenFile(tmp, os.O_WRONLY|os.O_CREATE|os.O_TRUNC, 0o600)
	if err != nil {
		return fmt.Errorf("write FORMAT: %w", err)
	}
	if _, err = fh.Write(append(b, '\n')); err == nil {
		err = fh.Sync()
	}
	if cerr := fh.Close(); err == nil {
		err = cerr
	}
	if err == nil {
		err = os.Rename(tmp, filepath.Join(dir, "FORMAT"))
	}
	if err != nil {
		_ = os.Remove(tmp)
		return fmt.Errorf("write FORMAT: %w", err)
	}
	if d, err := os.Open(dir); err == nil {
		_ = d.Sync()
		_ = d.Close()
	}
	return nil
}

// Listen — the flat sockets (P/01.3 Н1.3 sockets): "admin" and every role. Inherited ones (LISTEN_PID, LISTEN_FDS,
// LISTEN_FDNAMES) are taken by name — a name that is neither admin nor a role is Refusal (code 2); the rest are
// created in dir: admin.sock 0600, <role>.sock 0660. → listeners and the paths created (Stop removes them).
func Listen(dir string, roles []string, getenv func(string) string) (map[string]net.Listener, []string, error) {
	want := map[string]bool{"admin": true}
	for _, r := range roles {
		want[r] = true
	}
	ls := map[string]net.Listener{}
	var created []string
	if getenv("LISTEN_PID") == strconv.Itoa(os.Getpid()) {
		n, _ := strconv.Atoi(getenv("LISTEN_FDS"))
		names := strings.Split(getenv("LISTEN_FDNAMES"), ":")
		for i := 0; i < n; i++ {
			name := ""
			if i < len(names) {
				name = names[i]
			}
			if !want[name] || ls[name] != nil {
				closeAll(ls, nil)
				return nil, nil, refusef("inherited socket with a foreign name %q", name)
			}
			l, err := net.FileListener(os.NewFile(uintptr(3+i), name))
			if err != nil {
				closeAll(ls, nil)
				return nil, nil, fmt.Errorf("inherited socket %s: %w", name, err)
			}
			ls[name] = l
		}
		for _, k := range []string{"LISTEN_PID", "LISTEN_FDS", "LISTEN_FDNAMES"} {
			_ = os.Unsetenv(k)
		}
	}
	names := make([]string, 0, len(want))
	for name := range want {
		names = append(names, name)
	}
	sort.Strings(names)
	for _, name := range names {
		if ls[name] != nil {
			continue
		}
		if err := os.MkdirAll(dir, 0o755); err != nil {
			closeAll(ls, created)
			return nil, nil, fmt.Errorf("sockets %s: %w", dir, err)
		}
		path := filepath.Join(dir, name+".sock")
		if st, err := os.Lstat(path); err == nil && st.Mode()&os.ModeSocket != 0 {
			_ = os.Remove(path) // a stale socket of a former run
		}
		l, err := net.Listen("unix", path)
		if err != nil {
			closeAll(ls, created)
			return nil, nil, fmt.Errorf("socket %s: %w", path, err)
		}
		l.(*net.UnixListener).SetUnlinkOnClose(false)
		mode := os.FileMode(0o660)
		if name == "admin" {
			mode = 0o600
		}
		if err := os.Chmod(path, mode); err != nil {
			l.Close()
			closeAll(ls, created)
			return nil, nil, fmt.Errorf("socket %s: %w", path, err)
		}
		ls[name] = l
		created = append(created, path)
	}
	return ls, created, nil
}

func closeAll(ls map[string]net.Listener, created []string) {
	for _, l := range ls {
		_ = l.Close()
	}
	for _, p := range created {
		_ = os.Remove(p)
	}
}

func clip(b []byte) string {
	if len(b) > 200 {
		b = b[:200]
	}
	return string(b)
}

// Empty — the empty core of the frame: an empty store (GET /v1/get — every key absent, 200 {"items":null,"index":""});
// the rest — 503 «not implemented». Start uses it while coreadapter.Open returns coreadapter.ErrNotImplemented.
type Empty struct{ NotImplemented }

func (Empty) Get(coreadapter.Ctx, apidoor.GetQuery) apidoor.Answer {
	a, err := apidoor.AnswerOf(apidoor.OpGet, 200, map[string]any{"items": nil, "index": ""})
	if err != nil {
		return notImplemented(apidoor.OpGet)
	}
	return a
}

// NotImplemented — a Core whose every method answers 503 «not implemented»: a start for Open before your core
// exists (`return launch.NotImplemented{}, nil`). Replace it method by method with your core.
type NotImplemented struct{ coreadapter.NotInStage }

func notImplemented(op apidoor.Op) apidoor.Answer {
	a, err := apidoor.Refuse(op, 503, "unavailable", "not implemented", nil)
	if err != nil {
		return apidoor.Answer{Code: 503}
	}
	return a
}

func (NotImplemented) Context(call coreadapter.Call, header map[string]string) coreadapter.Ctx {
	return &coreadapter.Request{Call: call, Header: header}
}
func (NotImplemented) Close() {}
func (NotImplemented) Get(coreadapter.Ctx, apidoor.GetQuery) apidoor.Answer {
	return notImplemented(apidoor.OpGet)
}
func (NotImplemented) List(coreadapter.Ctx, apidoor.ListQuery) apidoor.Answer {
	return notImplemented(apidoor.OpList)
}
func (NotImplemented) Write(coreadapter.Ctx, []byte) apidoor.Answer {
	return notImplemented(apidoor.OpWrite)
}
func (NotImplemented) QueryRefused(_ coreadapter.Ctx, op apidoor.Op, _ *apidoor.QueryError) apidoor.Answer {
	return notImplemented(op)
}
