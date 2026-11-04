// Package coreadapter: Open and Ctx — yours (ADR-0126 addendum (7) item 5). The kit puts this stub once and never
// overwrites it.
package coreadapter

// Ctx — the context type of your Handler: what Context(call, header) gives each request. Request is ready to use;
// replace the alias with your own type if you need more.
type Ctx = *Request

// Open — a fresh core for cfg: your store in cfg.DataDir with the clock cfg.Now and the rights cfg.Rights. Return a
// value that implements Core: Context, Close and apidoor.Handler[Ctx] (Get, List, Write, QueryRefused over your core
// of Н3; embed NotInStage for Rights, Status, Join, Leave, Metrics until your stage needs them).
func Open(cfg Config) (Core, error) {
	return nil, ErrNotImplemented
}
