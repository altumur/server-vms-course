// Shared runtime of declarative policies: local state and ordered intentions only.
package workerpolicy

import (
	"encoding/json"
	"fmt"
	"sync"
)

// Intent never performs IO. Args retain the action declaration order.
type Intent struct {
	Action string
	Args   []any
}

func (i Intent) MarshalJSON() ([]byte, error) { return json.Marshal([2]any{i.Action, i.Args}) }

type Observation struct {
	State string         `json:"state"`
	Vars  map[string]any `json:"vars"`
	IO    []Intent       `json:"io"`
}
type pendingTimer struct {
	timer   int
	serial  uint64
	due     float64
	period  float64
	context map[string]any
}
type timerOrigin struct{ origin, duration float64 }

// Run has no clock, scheduler, IO callbacks or global mutable state. Times and facts
// are supplied by the caller. An evaluation/invariant error ends this run.
type Run struct {
	mu                     sync.Mutex
	p                      *Program
	state                  string
	input, vars, constants map[string]any
	now, start             float64
	io                     []Intent
	pending                []pendingTimer
	origins                map[int]timerOrigin
	serial                 uint64
	err                    error
}

func (p *Program) New(raw []byte, at float64) (*Run, error) {
	if !finite(at) || at < 0 {
		return nil, fmt.Errorf("input clock must be finite and nonnegative")
	}
	v, e := DecodeJSON(raw)
	if e != nil {
		return nil, e
	}
	supplied, ok := v.(map[string]any)
	if !ok {
		return nil, fmt.Errorf("input: expected object")
	}
	r := &Run{p: p, state: p.d.Initial, now: at, start: at, vars: map[string]any{}, constants: copyValue(p.d.Const).(map[string]any), io: []Intent{}, origins: map[int]timerOrigin{}}
	if overrides, has := supplied["const"]; has {
		m, ok := overrides.(map[string]any)
		if !ok {
			return nil, fmt.Errorf("const overrides: expected object")
		}
		for k, v := range m {
			if _, ok := r.constants[k]; !ok {
				return nil, fmt.Errorf("const override %s is undeclared", k)
			}
			r.constants[k] = v
		}
		delete(supplied, "const")
	}
	r.input, e = p.record(supplied, p.d.Input)
	if e != nil {
		return nil, fmt.Errorf("input: %w", e)
	}
	for _, v := range p.d.Vars {
		r.vars[v.Name], e = p.typed(v.Init, v.Type)
		if e != nil {
			return nil, e
		}
	}
	if e = r.syncTimers(); e != nil {
		return nil, e
	}
	if e = r.invariants("input"); e != nil {
		return nil, e
	}
	return r, nil
}

func (r *Run) eval(expr string, params map[string]any) (any, error) {
	data := map[string]any{}
	for _, n := range r.p.names {
		data[n] = nil
	}
	for k, v := range r.constants {
		data[k] = v
	}
	for k, v := range r.vars {
		data[k] = v
	}
	data["input"] = r.input
	data["vars"] = r.vars
	data["const"] = r.constants
	data["now"] = r.now
	data["s0"] = r.start
	data["state"] = r.state
	for k, v := range params {
		data[k] = v
	}
	native, e := celInput(data)
	if e != nil {
		return nil, e
	}
	pr, ok := r.p.expressions[expr]
	if !ok {
		return nil, fmt.Errorf("uncompiled CEL %q", expr)
	}
	v, _, e := pr.Eval(native)
	if e != nil {
		return nil, fmt.Errorf("CEL %q: %w", expr, e)
	}
	return plain(v)
}

func (r *Run) invariants(label string) error {
	for _, i := range r.p.d.Invariants {
		v, e := r.eval(i.Expr, nil)
		if e != nil {
			return e
		}
		if v != true {
			return fmt.Errorf("invariant %s broken after %s", i.Name, label)
		}
	}
	return nil
}

func (r *Run) action(call Call, params map[string]any) error {
	a := r.p.d.Actions[call.Action]
	args := map[string]any{}
	ordered := []any{}
	for i, expr := range call.Args {
		v, e := r.eval(expr, params)
		if e != nil {
			return e
		}
		v, e = r.p.typed(v, a.Args[i].Type)
		if e != nil {
			return fmt.Errorf("action %s arg %s: %w", call.Action, a.Args[i].Name, e)
		}
		args[a.Args[i].Name] = v
		ordered = append(ordered, v)
	}
	// All assignments read the same pre-action variables. Later actions see the result.
	next := map[string]any{}
	for _, s := range a.Set {
		v, e := r.eval(s.Expr, args)
		if e != nil {
			return e
		}
		v, e = r.p.typed(v, r.p.varTypes[s.Name])
		if e != nil {
			return fmt.Errorf("action %s set %s: %w", call.Action, s.Name, e)
		}
		next[s.Name] = v
	}
	for k, v := range next {
		r.vars[k] = v
	}
	if a.IO != "" {
		r.io = append(r.io, Intent{call.Action, copyValue(ordered).([]any)})
		for i, t := range r.p.d.Timers {
			if t.AfterIO == call.Action {
				r.serial++
				if e := r.arm(i, r.serial, r.now, args); e != nil {
					return e
				}
			}
		}
	}
	return nil
}

func member(list []string, s string) bool {
	for _, x := range list {
		if x == s {
			return true
		}
	}
	return false
}

func (r *Run) deliver(kind string, raw map[string]any) error {
	params, e := r.p.record(raw, r.p.d.Events[kind])
	if e != nil {
		return fmt.Errorf("event %s: %w", kind, e)
	}
	if r.p.terminal[r.state] {
		return nil
	}
	for _, t := range r.p.d.Transitions {
		if t.Event != kind || !member(t.From, r.state) {
			continue
		}
		v, e := r.eval(t.If, params)
		if e != nil {
			return e
		}
		guard, ok := v.(bool)
		if !ok {
			return fmt.Errorf("transition %s guard is not bool", t.ID)
		}
		if !guard {
			continue
		}
		for _, c := range t.Do {
			if e := r.action(c, params); e != nil {
				return fmt.Errorf("transition %s: %w", t.ID, e)
			}
		}
		if t.To != nil {
			r.state = *t.To
			break
		}
		if t.Stop {
			break
		}
	}
	if e := r.syncTimers(); e != nil {
		return e
	}
	return r.invariants(kind)
}

func (r *Run) duration(i int, params map[string]any) (float64, error) {
	t := r.p.d.Timers[i]
	v, e := r.eval(t.Duration, params)
	if e != nil {
		return 0, e
	}
	f, ok := numeric(v)
	if !ok || !finite(f) || f < 0 || t.Every && f == 0 {
		return 0, fmt.Errorf("timer %s: positive every or nonnegative after required", t.Name)
	}
	return f, nil
}

func (r *Run) arm(i int, serial uint64, origin float64, params map[string]any) error {
	if !finite(origin) || origin < 0 {
		return fmt.Errorf("timer %s: nonnegative finite origin", r.p.d.Timers[i].Name)
	}
	d, e := r.duration(i, params)
	if e != nil {
		return e
	}
	due := origin
	period := 0.0
	if r.p.d.Timers[i].Every {
		period = d
	} else {
		due += d
	}
	if !finite(due) {
		return fmt.Errorf("timer due overflow")
	}
	if due < r.now {
		due = r.now
	}
	// A non-IO timer has one pending instance. after_io retains each occurrence.
	if serial == 0 {
		kept := r.pending[:0]
		for _, t := range r.pending {
			if t.timer != i || t.serial != 0 {
				kept = append(kept, t)
			}
		}
		r.pending = kept
	}
	ctx := map[string]any{}
	if params != nil {
		ctx = copyValue(params).(map[string]any)
	}
	r.pending = append(r.pending, pendingTimer{i, serial, due, period, ctx})
	return nil
}

func (r *Run) syncTimers() error {
	if r.p.terminal[r.state] {
		r.pending = nil
		return nil
	}
	for i, t := range r.p.d.Timers {
		if t.AfterIO != "" {
			continue
		}
		v, e := r.eval(t.Origin, nil)
		if e != nil {
			return e
		}
		origin, ok := numeric(v)
		if !ok || !finite(origin) || origin < 0 {
			return fmt.Errorf("timer %s: nonnegative finite origin", t.Name)
		}
		d, e := r.duration(i, nil)
		if e != nil {
			return e
		}
		signature := timerOrigin{origin, d}
		if old, ok := r.origins[i]; !ok || old != signature {
			r.origins[i] = signature
			if e := r.arm(i, 0, origin, nil); e != nil {
				return e
			}
		}
	}
	return nil
}

func (r *Run) due(at float64) error {
	for count := 0; ; count++ {
		best := -1
		for i, t := range r.pending {
			if t.due > at {
				continue
			}
			if best < 0 {
				best = i
				continue
			}
			b := r.pending[best]
			if t.due < b.due || t.due == b.due && (t.timer < b.timer || t.timer == b.timer && t.serial < b.serial) {
				best = i
			}
		}
		if best < 0 {
			return nil
		}
		if count >= 10000 {
			return fmt.Errorf("timer delivery limit (zero-time cycle)")
		}
		p := r.pending[best]
		r.pending = append(r.pending[:best], r.pending[best+1:]...)
		r.now = p.due
		if p.period > 0 {
			next := p
			next.due += next.period
			if !finite(next.due) || next.due <= p.due {
				return fmt.Errorf("timer period overflow")
			}
			r.pending = append(r.pending, next)
		}
		t := r.p.d.Timers[p.timer]
		payload := map[string]any{}
		for _, f := range t.Payload {
			v, e := r.eval(f.Expr, p.context)
			if e != nil {
				return e
			}
			payload[f.Name] = v
		}
		if e := r.deliver(t.Event, payload); e != nil {
			return e
		}
	}
}

// Step delivers due timers first, then the external event, then zero-delay timers.
// A malformed step does not advance the run. An evaluation error makes it unusable.
func (r *Run) Step(at float64, event string, raw []byte) (Observation, error) {
	r.mu.Lock()
	defer r.mu.Unlock()
	if r.err != nil {
		return r.snapshot(), r.err
	}
	if !finite(at) || at < r.now {
		return r.snapshot(), fmt.Errorf("time must be finite and nondecreasing")
	}
	var payload map[string]any
	if event == "advance" {
		if len(raw) != 0 {
			return r.snapshot(), fmt.Errorf("advance has no payload")
		}
	} else {
		fields, ok := r.p.d.Events[event]
		if !ok {
			return r.snapshot(), fmt.Errorf("undeclared event %s", event)
		}
		for _, t := range r.p.d.Timers {
			if t.Event == event {
				return r.snapshot(), fmt.Errorf("timer event %s cannot be raised externally", event)
			}
		}
		v, e := DecodeJSON(raw)
		if e != nil {
			return r.snapshot(), e
		}
		payload, e = r.p.record(v, fields)
		if e != nil {
			return r.snapshot(), fmt.Errorf("event %s: %w", event, e)
		}
	}
	r.io = []Intent{}
	if e := r.due(at); e != nil {
		r.err = e
		return r.snapshot(), e
	}
	r.now = at
	if event != "advance" {
		if e := r.deliver(event, payload); e != nil {
			r.err = e
			return r.snapshot(), e
		}
		if e := r.due(at); e != nil {
			r.err = e
			return r.snapshot(), e
		}
	}
	return r.snapshot(), nil
}

func (r *Run) snapshot() Observation {
	intents := make([]Intent, len(r.io))
	for i, v := range r.io {
		intents[i] = Intent{v.Action, copyValue(v.Args).([]any)}
	}
	return Observation{r.state, copyValue(r.vars).(map[string]any), intents}
}

func (r *Run) Snapshot() Observation { r.mu.Lock(); defer r.mu.Unlock(); return r.snapshot() }
