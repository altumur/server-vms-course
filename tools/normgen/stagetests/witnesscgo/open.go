// Stage-judge witness adapter over P/01 c-go (ADR-0125 addendum 4, item 6;ADR-0126 addendum 7, item 5).
// Source:cammeta-c-go b3c054d8, /home/pilot/witness.Open uses store.Open/ParseRights in cfg.DataDir;Core
// implements apidoor.Handler[Ctx] by reconstructing requests to store.Door.Handle and mapping responses
// through AnswerOf.Install into a witness copy's01-store/internal/coreadapter/open.go, not the kit.
// No witness implementation code enters generators.Witness clocks remain its own;cfg.Now is not wired.
package coreadapter

import (
	"bytes"
	"encoding/json"
	"fmt"
	"strings"

	"cammeta-c-go/01-store/internal/apidoor"
	"cammeta-c-go/01-store/internal/store"
	"cammeta-c-go/common/httpwire"
)

type witness struct{ eng *store.Engine }

func Open(cfg Config) (Core, error) {
	r, err := store.ParseRights(cfg.Rights)
	if err != nil {
		return nil, err
	}
	eng, err := store.Open(cfg.DataDir+"/configstore", int(cfg.RowCeiling), r)
	if err != nil {
		return nil, err
	}
	return &witness{eng: eng}, nil
}

func (w *witness) Close() { w.eng.Close() }

func (w *witness) forward(c Ctx, method, target string, body []byte) (int, []byte) {
	h := map[string][]string{}
	for k, v := range c.Header {
		h[strings.ToLower(k)] = append(h[strings.ToLower(k)], v)
	}
	q := &httpwire.Request{Method: method, Target: target, Version: "HTTP/1.1", Headers: h, Body: body,
		Length: int64(len(body))}
	resp := store.Door{Engine: w.eng, Role: c.Call.Sock}.Handle(q)
	return resp.Code, resp.Body
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
