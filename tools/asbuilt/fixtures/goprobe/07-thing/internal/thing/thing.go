// Package thing holds the synthetic door with known refusals.
package thing

import (
	"fmt"

	"probe/08-other/peer"
	"probe/common/wire"
)

const kindRefused = "refused"

type Fault struct {
	Code int
	Body map[string]any
}

func fault(code int, kind string) *Fault {
	return &Fault{code, map[string]any{"kind": kind, "error": kind}}
}

func forbidden(role, key string) *Fault {
	f := fault(403, "forbidden")
	f.Body["error"] = fmt.Sprintf("%s may not read %s", role, key)
	return f
}

// Handle answers one synthetic request.
func Handle(method, role, key string, size int) (*Fault, []byte) {
	if method != "GET" {
		code := 404
		if method == "POST" {
			code = 405
		}
		return fault(code, "badrequest"), nil
	}
	if key == "" {
		return fault(400, "badkey"), nil
	}
	if role != "admin" {
		return forbidden(role, key), nil
	}
	if size > 10 {
		f := fault(413, "toolarge")
		f.Body["limit"] = 10
		f.Body["size"] = size
		return f, nil
	}
	if key == "same" {
		return fault(409, kindRefused), nil
	}
	if peer.Down() {
		return nil, wire.Basic(503, "unavailable", 0)
	}
	return nil, wire.Basic(413, "toolarge", 10)
}

// Dynamic builds a refusal whose code and kind are not constants.
func Dynamic(code int, kind string) *Fault {
	return fault(code, kind)
}
