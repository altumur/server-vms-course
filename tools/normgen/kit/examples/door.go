package example

import "kitmodule/internal/apidoor"

// serveOne — one request through the door when you serve HTTP yourself (part launch does this for you:
// coreadapter.Handle): route, dispatch to your Handler, encode; send Response as is.
func serveOne[C any](h apidoor.Handler[C], c C, method, target string, body []byte) *apidoor.Response {
	op, query, refusal := apidoor.Route(method, target)
	if refusal != nil {
		return refusal // 404 / 405 ready to send
	}
	resp, err := apidoor.Encode(op, apidoor.Dispatch(h, c, op, query, body))
	if err != nil {
		return &apidoor.Response{Code: 500} // an answer out of the OpenAPI: a bug of yours
	}
	return resp
}

// absent — GET /v1/get of a key that is not stored: 200 {"items":null,"index":""} (Row2).
func absent() apidoor.Answer {
	a, _ := apidoor.AnswerOf(apidoor.OpGet, 200, map[string]any{"items": nil, "index": ""})
	return a
}
