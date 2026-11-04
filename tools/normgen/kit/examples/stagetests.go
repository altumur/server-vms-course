package example

import (
	"sync"

	"kitmodule/internal/apidoor"
	"kitmodule/internal/coreadapter"
)

// store — the shape of your core in open.go (package coreadapter there; here a sketch of the same methods):
// Open returns it; NotInStage answers Rights, Status, Join, Leave, Metrics until your stage needs them.
type store struct {
	coreadapter.NotInStage
	mu   sync.Mutex
	cfg  coreadapter.Config
	rows map[string]map[string]any
}

func openStore(cfg coreadapter.Config) (coreadapter.Core, error) { // coreadapter.Open in open.go
	return &store{cfg: cfg, rows: map[string]map[string]any{}}, nil
}

func (s *store) Context(call coreadapter.Call, h map[string]string) coreadapter.Ctx {
	return &coreadapter.Request{Call: call, Header: h} // Call.Sock: "admin" or the role
}
func (s *store) Close() {}
func (s *store) Get(c coreadapter.Ctx, q apidoor.GetQuery) apidoor.Answer {
	s.mu.Lock()
	defer s.mu.Unlock()
	a, _ := apidoor.AnswerOf(apidoor.OpGet, 200, map[string]any{"items": nil, "index": ""}) // absent: q.Key unknown
	return a
}
func (s *store) List(coreadapter.Ctx, apidoor.ListQuery) apidoor.Answer { return apidoor.Answer{Code: 503} }
func (s *store) Write(coreadapter.Ctx, []byte) apidoor.Answer          { return apidoor.Answer{Code: 503} }
func (s *store) QueryRefused(_ coreadapter.Ctx, op apidoor.Op, e *apidoor.QueryError) apidoor.Answer {
	a, _ := apidoor.Refuse(op, 400, "badrequest", "query: "+e.Param, nil)
	return a
}
