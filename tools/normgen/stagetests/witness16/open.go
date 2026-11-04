// Адаптер-свидетель судьи тестов этапов (ADR-0125 доп. (3) п. 4, доп. (4) п. 6) над кодом 16-й попытки MiniMax
// (p01-1-go-ct102-16-green): Open поднимает её ядро и дверь в процессе, Handle гонит запрос через её door.Handle
// (её рамка HTTP, не Wrap пакета) — так шаги тестов сверяются с шагами раннера на том же коде. Кладётся в
// <посев>/01-store/internal/coreadapter/open.go вместо заглушки; не часть пакета.
package coreadapter

import (
	"bufio"
	"bytes"
	"fmt"
	"net/http"
	"io"
	"strconv"

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
	srv := door.New(door.Options{Store: store.New(nil), Rights: rf, RoleHeader: "X-Configstore-Role",
		MaxBody: cfg.BodyLimit, RowCeiling: cfg.RowCeiling})
	return &witness{srv: srv}, nil
}

func (w *witness) Handle(call Call, method, target string, header map[string]string, body []byte) (int, map[string]string, []byte) {
	var req bytes.Buffer
	fmt.Fprintf(&req, "%s %s HTTP/1.1\r\nHost: x\r\nConnection: close\r\n", method, target)
	for k, v := range header {
		fmt.Fprintf(&req, "%s: %s\r\n", k, v)
	}
	if body != nil {
		req.WriteString("Content-Length: " + strconv.Itoa(len(body)) + "\r\n")
	}
	req.WriteString("\r\n")
	req.Write(body)
	var out bytes.Buffer
	w.srv.Handle(bufio.NewReader(&req), &out, call.Sock)
	resp, err := http.ReadResponse(bufio.NewReader(&out), nil)
	if err != nil {
		return 599, nil, []byte(err.Error())
	}
	b, _ := io.ReadAll(resp.Body)
	h := map[string]string{}
	for k := range resp.Header {
		h[k] = resp.Header.Get(k)
	}
	return resp.StatusCode, h, b
}

func (w *witness) Close() error { return nil }
