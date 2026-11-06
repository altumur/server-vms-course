// Stage-judge witness adapter (ADR-0125 addendum 4, item 6;ADR-0126 addendum 7, item 5) over MiniMax attempt 16
// p01-1-go-ct102-16-green:Open returns its core/door in process;Core implements apidoor.Handler[Ctx].
// Each method reconstructs an HTTP request to door.Handle and maps the response through AnswerOf.Install
// as <seed>/01-store/internal/coreadapter/open.go instead of the scaffold;not part of the kit.
package coreadapter

import (
	"bufio"
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strconv"
	"strings"

	"p01store/01-store/internal/apidoor"
	"p01store/01-store/internal/door"
	"p01store/01-store/internal/rights"
	"p01store/01-store/internal/store"
)

type witness struct{ srv *door.Server }

func Open(cfg Config) (Core, error) {
	rf, err := rights.Parse(cfg.Rights)
	if err != nil {
		return nil, err
	}
	srv := door.New(door.Options{Store: store.New(cfg.Now), Rights: rf, RoleHeader: "X-Configstore-Role",
		MaxBody: cfg.BodyLimit, RowCeiling: cfg.RowCeiling})
	return &witness{srv: srv}, nil
}

func (w *witness) Close() {}

func (w *witness) forward(c Ctx, method, target string, body []byte) (int, []byte) {
	var req bytes.Buffer
	fmt.Fprintf(&req, "%s %s HTTP/1.1\r\nHost: x\r\nConnection: close\r\n", method, target)
	for k, v := range c.Header {
		fmt.Fprintf(&req, "%s: %s\r\n", k, v)
	}
	if body != nil {
		req.WriteString("Content-Length: " + strconv.Itoa(len(body)) + "\r\n")
	}
	req.WriteString("\r\n")
	req.Write(body)
	var out bytes.Buffer
	w.srv.Handle(bufio.NewReader(&req), &out, c.Call.Sock)
	resp, err := http.ReadResponse(bufio.NewReader(&out), nil)
	if err != nil {
		return 599, []byte(err.Error())
	}
	b, _ := io.ReadAll(resp.Body)
	return resp.StatusCode, b
}

// Ctx carries witness call identity and headers.
type Ctx = *Request

func (w *witness) Context(call Call, header map[string]string) Ctx { return &Request{Call: call, Header: header} }

// answer requests the witness door and converts its response with the operation's AnswerOf schema.
func (w *witness) answer(op apidoor.Op, c Ctx, method, target string, body []byte) apidoor.Answer {
	code, raw := w.forward(c, method, target, body)
	var v any = string(raw)
	if op != apidoor.OpMetrics || code != 200 {
		dec := json.NewDecoder(bytes.NewReader(raw))
		dec.UseNumber()
		if err := dec.Decode(&v); err != nil {
			return apidoor.Answer{Code: 599}
		}
	}
	a, err := apidoor.AnswerOf(op, code, v)
	if err != nil {
		return apidoor.Answer{Code: 598}
	}
	return a
}

func esc(s string) string {
	var b strings.Builder
	for i := 0; i < len(s); i++ {
		c := s[i]
		if c >= 'A' && c <= 'Z' || c >= 'a' && c <= 'z' || c >= '0' && c <= '9' || strings.IndexByte("-._~/", c) >= 0 {
			b.WriteByte(c)
		} else {
			fmt.Fprintf(&b, "%%%02X", c)
		}
	}
	return b.String()
}

func (w *witness) Get(c Ctx, q apidoor.GetQuery) apidoor.Answer {
	return w.answer(apidoor.OpGet, c, "GET", "/v1/get?key="+esc(q.Key), nil)
}
func (w *witness) List(c Ctx, q apidoor.ListQuery) apidoor.Answer {
	t := "/v1/list"
	if q.Prefix != nil {
		t += "?prefix=" + esc(*q.Prefix)
	}
	return w.answer(apidoor.OpList, c, "GET", t, nil)
}
func (w *witness) Write(c Ctx, body []byte) apidoor.Answer {
	return w.answer(apidoor.OpWrite, c, "POST", "/v1/write", body)
}
func (w *witness) Rights(c Ctx) apidoor.Answer { return w.answer(apidoor.OpRights, c, "GET", "/v1/rights", nil) }
func (w *witness) Status(c Ctx) apidoor.Answer { return w.answer(apidoor.OpStatus, c, "GET", "/v1/status", nil) }
func (w *witness) Join(c Ctx, b []byte) apidoor.Answer {
	return w.answer(apidoor.OpJoin, c, "POST", "/v1/join", b)
}
func (w *witness) Leave(c Ctx, b []byte) apidoor.Answer {
	return w.answer(apidoor.OpLeave, c, "POST", "/v1/leave", b)
}
func (w *witness) Metrics(c Ctx) apidoor.Answer { return w.answer(apidoor.OpMetrics, c, "GET", "/metrics", nil) }

// QueryRefused cannot inspect raw query in the witness;return400badrequest.Query-form steps are checked separately.
func (w *witness) QueryRefused(c Ctx, op apidoor.Op, e *apidoor.QueryError) apidoor.Answer {
	a, _ := apidoor.Refuse(op, 400, "badrequest", "query: "+e.Param, nil)
	return a
}
