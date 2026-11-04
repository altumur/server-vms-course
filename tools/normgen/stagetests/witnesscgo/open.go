// Адаптер-свидетель судьи тестов этапов (ADR-0125 доп. (4) п. 6) над свидетелем c-go P/01 (корень cammeta-c-go на
// b3c054d8, /home/pilot/witness): Open поднимает его ядро (store.Open, store.ParseRights) в свежем каталоге, Handle
// повторяет предел тела его рамки (common/httpwire.Server: /v1/write — предел стенда, прочее — 1 MiB; 413 toolarge
// {limit} до маршрута) и зовёт store.Door.Handle над ядром. Кладётся в <копия свидетеля>/01-store/internal/coreadapter/
// open.go вместо заглушки пакета; не часть пакета, из кода свидетеля в генераторы ничего не берётся.
package coreadapter

import (
	"fmt"
	"os"
	"strings"

	"cammeta-c-go/01-store/internal/store"
	"cammeta-c-go/common/httpwire"
)

type witness struct {
	eng *store.Engine
	dir string
	cfg Config
}

func Open(cfg Config) (Core, error) {
	r, err := store.ParseRights(cfg.Rights)
	if err != nil {
		return nil, err
	}
	dir, err := os.MkdirTemp("", "cgo-stage-")
	if err != nil {
		return nil, err
	}
	eng, err := store.Open(dir+"/configstore", int(cfg.RowCeiling), r)
	if err != nil {
		return nil, err
	}
	return &witness{eng: eng, dir: dir, cfg: cfg}, nil
}

func (w *witness) Handle(call Call, method, target string, header map[string]string, body []byte) (int, map[string]string, []byte) {
	limit := int64(1 << 20)
	if path, _, _ := strings.Cut(target, "?"); path == "/v1/write" {
		limit = w.cfg.BodyLimit
	}
	if int64(len(body)) > limit {
		return 413, map[string]string{"Content-Type": "application/json"},
			[]byte(fmt.Sprintf(`{"kind":"toolarge","error":"body limit","limit":%d}`, limit))
	}
	h := map[string][]string{}
	for k, v := range header {
		h[strings.ToLower(k)] = append(h[strings.ToLower(k)], v)
	}
	role := call.Sock
	q := &httpwire.Request{Method: method, Target: target, Version: "HTTP/1.1", Headers: h, Body: body,
		Length: int64(len(body))}
	resp := store.Door{Engine: w.eng, Role: role}.Handle(q)
	out := map[string]string{"Content-Type": resp.ContentType}
	for k, v := range resp.Headers {
		out[k] = v
	}
	return resp.Code, out, resp.Body
}

func (w *witness) Close() error {
	w.eng.Close()
	return os.RemoveAll(w.dir)
}
