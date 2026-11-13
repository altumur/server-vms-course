// Persistent doorprobe for test_gen_door.py:read JSON commands from stdin and immediately emit replies.
// The test writes go.mod with replace pointing at generated output. Handwritten handlers follow P/01
// OpenAPI operations.
//
// Commands:table lists operations/responses; route(method, target) calls Route;
// {"cmd": "check", "schema", "json"} — CheckSchema; {"cmd": "answer", "op", "code", "json", "via_op"?, "via_code"?,
// optional retry passes through AnswerOf/Encode; refuse(op, code, kind, msg, fields) calls Refuse/Encode;
// dispatch(op, query) returns the handler's parsed query;
// decode(schema, json) calls the request body's Decode<Schema>.
package main

import (
	"bufio"
	"bytes"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"os"

	"normgen/p01-1/apidoor"
)

type request struct {
	Cmd              string
	Method           string
	Target           string
	Schema           string
	JSON             string
	Op               string
	Code             int
	ViaOp            string `json:"via_op"`
	ViaCode          int    `json:"via_code"`
	Retry            bool
	RetryAfter       *int64 `json:"retry_after"`
	Allow            bool
	ContentLength    *string `json:"content_length"`
	TransferEncoding *string `json:"transfer_encoding"`
	NoBody           bool    `json:"no_body"`
	Kind             string
	Msg              string
	Fields           json.RawMessage
	Query            string
}

func retryAfter(req request) *int64 {
	if req.RetryAfter != nil {
		return req.RetryAfter
	}
	if req.Retry {
		seconds := int64(1)
		return &seconds
	}
	return nil
}

func decode(text string) (any, error) {
	d := json.NewDecoder(bytes.NewReader([]byte(text)))
	d.UseNumber()
	var v any
	err := d.Decode(&v)
	return v, err
}

func opByName(name string) apidoor.Op {
	for _, o := range apidoor.Operations {
		if o.Op.String() == name {
			return o.Op
		}
	}
	return 0
}

func response(r *apidoor.Response) any {
	if r == nil {
		return nil
	}
	return map[string]any{"code": r.Code, "header": r.Header, "body": base64.StdEncoding.EncodeToString(r.Body)}
}

func violation(e *apidoor.Violation) any {
	if e == nil {
		return nil
	}
	return map[string]any{"at": e.At, "rule": e.Rule}
}

// record captures the probe handler's operation method, parsed query and query refusal.
type record struct {
	method string
	query  map[string]any
	qerr   *apidoor.QueryError
}

type probe struct{}

// b64 encodes query string/*string values by OpenAPI requiredness; nil means absent.
func b64(v any) any {
	switch x := v.(type) {
	case string:
		return base64.StdEncoding.EncodeToString([]byte(x))
	case *string:
		if x != nil {
			return base64.StdEncoding.EncodeToString([]byte(*x))
		}
	}
	return nil
}

func (probe) Get(c *record, q apidoor.GetQuery) apidoor.Answer {
	c.method, c.query = "Get", map[string]any{"key": b64(q.Key)}
	return apidoor.Answer{}
}
func (probe) List(c *record, q apidoor.ListQuery) apidoor.Answer {
	c.method, c.query = "List", map[string]any{"prefix": b64(q.Prefix)}
	return apidoor.Answer{}
}
func (probe) Write(c *record, body []byte) apidoor.Answer {
	c.method = "Write"
	return apidoor.Answer{}
}
func (probe) Rights(c *record) apidoor.Answer            { c.method = "Rights"; return apidoor.Answer{} }
func (probe) Status(c *record) apidoor.Answer            { c.method = "Status"; return apidoor.Answer{} }
func (probe) Join(c *record, body []byte) apidoor.Answer { c.method = "Join"; return apidoor.Answer{} }
func (probe) Leave(c *record, body []byte) apidoor.Answer {
	c.method = "Leave"
	return apidoor.Answer{}
}
func (probe) CopyGet(c *record) apidoor.Answer  { c.method = "CopyGet"; return apidoor.Answer{} }
func (probe) CopyHead(c *record) apidoor.Answer { c.method = "CopyHead"; return apidoor.Answer{} }
func (probe) Metrics(c *record) apidoor.Answer  { c.method = "Metrics"; return apidoor.Answer{} }
func (probe) QueryRefused(c *record, op apidoor.Op, e *apidoor.QueryError) apidoor.Answer {
	c.method, c.qerr = "QueryRefused", e
	return apidoor.Answer{}
}

func run(req request) any {
	switch req.Cmd {
	case "table":
		ops := []any{}
		for _, o := range apidoor.Operations {
			declared := map[string]any{}
			for code, d := range apidoor.Declared(o.Op) {
				declared[fmt.Sprint(code)] = map[string]any{"schemas": append([]string{}, d[0]...), "headers": d[1]}
			}
			ops = append(ops, map[string]any{"op": o.Op.String(), "method": o.Method, "path": o.Path, "query": o.Query,
				"body": o.Body, "body_required": o.BodyRequired, "writecheck": o.Writecheck, "declared": declared})
		}
		return map[string]any{"ops": ops}
	case "route":
		op, query, refusal := apidoor.Route(req.Method, req.Target)
		name := ""
		if op != 0 {
			name = op.String()
		}
		return map[string]any{"op": name, "query": query, "resp": response(refusal)}
	case "check":
		v, err := decode(req.JSON)
		if err != nil {
			return map[string]any{"error": err.Error()}
		}
		e, known := apidoor.CheckSchema(req.Schema, v)
		return map[string]any{"known": known, "violation": violation(e)}
	case "answer":
		via, code := req.Op, req.Code
		if req.ViaOp != "" {
			via, code = req.ViaOp, req.ViaCode
		}
		var a apidoor.Answer
		var err error
		if req.NoBody {
			a = apidoor.Answer{Code: code}
		} else {
			var v any
			v, err = decode(req.JSON)
			if err != nil {
				return map[string]any{"error": err.Error()}
			}
			a, err = apidoor.AnswerOf(opByName(via), code, v)
		}
		if err != nil {
			return map[string]any{"answer_error": err.Error()}
		}
		a.Code, a.RetryAfter = req.Code, retryAfter(req)
		a.Allow, a.ContentLength, a.TransferEncoding = req.Allow, req.ContentLength, req.TransferEncoding
		schema := ""
		if a.Body != nil {
			schema = a.Body.SchemaName()
		}
		r, err := apidoor.Encode(opByName(req.Op), a)
		if err != nil {
			return map[string]any{"encode_error": err.Error(), "schema": schema}
		}
		return map[string]any{"resp": response(r), "schema": schema}
	case "refuse":
		fields := map[string]any{}
		if len(req.Fields) > 0 {
			v, err := decode(string(req.Fields))
			if err != nil {
				return map[string]any{"error": err.Error()}
			}
			fields = v.(map[string]any)
		}
		a, err := apidoor.Refuse(opByName(req.Op), req.Code, req.Kind, req.Msg, fields)
		if err != nil {
			return map[string]any{"answer_error": err.Error()}
		}
		a.RetryAfter, a.Allow = retryAfter(req), req.Allow
		a.ContentLength, a.TransferEncoding = req.ContentLength, req.TransferEncoding
		r, err := apidoor.Encode(opByName(req.Op), a)
		if err != nil {
			return map[string]any{"encode_error": err.Error()}
		}
		return map[string]any{"resp": response(r), "schema": a.Body.SchemaName()}
	case "dispatch":
		var c record
		apidoor.Dispatch[*record](probe{}, &c, opByName(req.Op), req.Query, nil)
		var qerr any
		if c.qerr != nil {
			qerr = map[string]any{"param": c.qerr.Param, "reason": int(c.qerr.Reason), "schema": c.qerr.Schema,
				"rule": c.qerr.Rule}
		}
		return map[string]any{"method": c.method, "query": c.query, "error": qerr}
	case "decode":
		v, err := decode(req.JSON)
		if err != nil {
			return map[string]any{"error": err.Error()}
		}
		var out any
		var e *apidoor.Violation
		switch req.Schema {
		case "FloorCmd":
			out, e = apidoor.DecodeFloorCmd(v)
		case "Join":
			out, e = apidoor.DecodeJoin(v)
		case "Leave":
			out, e = apidoor.DecodeLeave(v)
		default:
			return map[string]any{"error": "no decoder " + req.Schema}
		}
		if e != nil {
			out = nil
		}
		return map[string]any{"value": out, "violation": violation(e)}
	}
	return map[string]any{"error": "unknown cmd " + req.Cmd}
}

func main() {
	in := bufio.NewScanner(os.Stdin)
	in.Buffer(make([]byte, 1<<20), 1<<26)
	out := bufio.NewWriter(os.Stdout)
	enc := json.NewEncoder(out)
	enc.SetEscapeHTML(false)
	for in.Scan() {
		var req request
		if err := json.Unmarshal(in.Bytes(), &req); err != nil {
			fmt.Fprintln(os.Stderr, "doorprobe: bad request:", err)
			os.Exit(2)
		}
		if err := enc.Encode(run(req)); err != nil {
			fmt.Fprintln(os.Stderr, "doorprobe:", err)
			os.Exit(2)
		}
		out.Flush()
	}
}
