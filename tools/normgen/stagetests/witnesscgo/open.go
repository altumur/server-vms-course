// Адаптер-свидетель судьи тестов этапов (ADR-0125 доп. (4) п. 6; договор ADR-0126 доп. (7) п. 5) над свидетелем c-go
// P/01 (корень cammeta-c-go на b3c054d8, /home/pilot/witness): Open — его ядро (store.Open, store.ParseRights) в
// cfg.DataDir; Core — apidoor.Handler[Ctx]: каждый метод пересобирает запрос к store.Door.Handle над ядром, ответ —
// apidoor.AnswerOf. Кладётся в <копия свидетеля>/01-store/internal/coreadapter/open.go вместо заглушки пакета; не часть
// пакета, из кода свидетеля в генераторы ничего не берётся. Часы свидетеля — его собственные (cfg.Now не подключён).
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
