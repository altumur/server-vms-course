// Package frame — the HTTP frame of the store daemon: YOURS (ADR-0125 addendum (1) item 2 — the HTTP frame and the
// limits of P/01.1 N2.1 are the hand part of the implementation). The kit puts this file once and never overwrites it.
//
// TEMPORARY FRAME ON net/http -- REPLACE IT. net/http is softer than N2.1: it accepts obs-fold, `#` in the target, a
// lone LF in a header, a request line or headers over HEADER_BYTES; it answers 414/431/505 and its own pages; it does
// not send the early refusal with Connection: close and the drain before the body. The stage tests (in process) pass
// over it; the raw HTTP acceptance (stage http) needs the strict parse of N2.1 -- your own reader of the connection
// (bufio over net.Conn), not net/http. The daemon (launch) needs only New, Serve and Shutdown with these signatures.
//
// @NORMS@
package frame

import (
	"context"
	"errors"
	"io"
	"net"
	"net/http"
	"strings"
	"time"

	"normgen/p01-1/coreadapter"
)

// Server — the frame of one socket: every request goes to coreadapter.Handle (the body limit 413 → apidoor.Route →
// Dispatch → Encode over your Core) with the identity of the socket.
type Server struct {
	srv *http.Server
}

// New — the frame of the socket sock ("admin" or the role): the identity of every request on it.
func New(c coreadapter.Core, cfg coreadapter.Config, sock string) *Server {
	return &Server{srv: &http.Server{Handler: handler(c, cfg, sock), ReadHeaderTimeout: 10 * time.Second,
		MaxHeaderBytes: 1 << 16}}
}

// Serve — serves l until Shutdown; then nil.
func (s *Server) Serve(l net.Listener) error {
	if err := s.srv.Serve(l); err != nil && !errors.Is(err, http.ErrServerClosed) {
		return err
	}
	return nil
}

// Shutdown — stops accepting, waits for the requests in flight until ctx is done.
func (s *Server) Shutdown(ctx context.Context) error {
	return s.srv.Shutdown(ctx)
}

func handler(c coreadapter.Core, cfg coreadapter.Config, sock string) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var body []byte
		if r.Body != nil && r.Body != http.NoBody {
			b, err := io.ReadAll(io.LimitReader(r.Body, cfg.BodyLimit+1))
			if err != nil {
				http.Error(w, `{"kind":"badrequest","error":"the body is not read"}`, http.StatusBadRequest)
				return
			}
			body = b
		}
		header := make(map[string]string, len(r.Header))
		for k, v := range r.Header {
			header[k] = strings.Join(v, ", ")
		}
		code, hdr, out := coreadapter.Handle(c, cfg, coreadapter.Call{Sock: sock}, r.Method, r.RequestURI, header, body)
		for k, v := range hdr {
			w.Header().Set(k, v)
		}
		w.WriteHeader(code)
		_, _ = w.Write(out)
	})
}
