// Адаптер-свидетель судьи тестов этапов (ADR-0125 доп. (4) п. 6; договор ADR-0126 доп. (7) п. 5) над кодом 16-й
// попытки MiniMax (p01-1-go-ct102-16-green): Open — её ядро и дверь в процессе; Core — apidoor.Handler[Ctx]: каждый
// метод пересобирает запрос HTTP к её door.Handle, ответ — apidoor.AnswerOf. Кладётся в
// <посев>/01-store/internal/coreadapter/open.go вместо заглушки; не часть пакета.
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

// Ctx — контекст свидетеля: личность вызова и заголовки.
type Ctx = *Request

func (w *witness) Context(call Call, header map[string]string) Ctx { return &Request{Call: call, Header: header} }

// answer — запрос к двери свидетеля, ответ — в apidoor.AnswerOf (схема OpenAPI операции).
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

// QueryRefused — свидетель сырого query уже не видит: 400 badrequest (шаги формы query сверяются отдельно).
func (w *witness) QueryRefused(c Ctx, op apidoor.Op, e *apidoor.QueryError) apidoor.Answer {
	a, _ := apidoor.Refuse(op, 400, "badrequest", "query: "+e.Param, nil)
	return a
}
