// Package coreadapter: the empty core of the launch judge (tools/normgen/launch_judge.py; ADR-0083 addendum (95)
// item 3) — put in place of open.go of the kit. Get — always an absent row; the rest — 503 «not in this stage».
// Not an implementation of the lesson: the judge measures the frame (flags, FORMAT, sockets, HTTP), not the core.
package coreadapter

import "kitmodule/internal/apidoor"

type Ctx = *Request

type empty struct{ NotInStage }

func Open(cfg Config) (Core, error) { return empty{}, nil }

func (empty) Context(call Call, header map[string]string) Ctx { return &Request{Call: call, Header: header} }
func (empty) Close()                                           {}

func (empty) Get(Ctx, apidoor.GetQuery) apidoor.Answer {
	a, err := apidoor.AnswerOf(apidoor.OpGet, 200, map[string]any{"items": nil, "index": ""})
	if err != nil {
		panic(err)
	}
	return a
}

func (empty) List(Ctx, apidoor.ListQuery) apidoor.Answer { return notInStage(apidoor.OpList) }
func (empty) Write(Ctx, []byte) apidoor.Answer           { return notInStage(apidoor.OpWrite) }
func (empty) QueryRefused(_ Ctx, op apidoor.Op, _ *apidoor.QueryError) apidoor.Answer {
	a, err := apidoor.Refuse(op, 400, "badrequest", "query out of form", nil)
	if err != nil {
		return notInStage(op)
	}
	return a
}
