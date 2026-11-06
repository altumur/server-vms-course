// Persistent kit/test_kit.py harness beside internal/:read stdin lines and immediately write responses.
// The test rewrites kitmodule/internal imports.
//
// Input:sock, base64 raw body, lim{name:int}, allow[[socket, action, prefix]].
// Output:writecheck refusal|null, tagged body|null, lone pointers|null;
// $int, $double and $map tags preserve numeric kinds through JSON.
package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"strconv"
	"strings"

	"kitmodule/internal/jsonstrict"
	"kitmodule/internal/writecheck"
)

type request struct {
	Sock  string
	Body  []byte // encoding/json: base64
	Lim   map[string]int64
	Allow [][3]string
}

func tag(v any) any {
	switch x := v.(type) {
	case int64:
		return map[string]any{"$int": strconv.FormatInt(x, 10)}
	case float64:
		return map[string]any{"$double": strconv.FormatFloat(x, 'g', -1, 64)}
	case []any:
		out := make([]any, len(x))
		for k := range x {
			out[k] = tag(x[k])
		}
		return out
	case map[string]any:
		out := make(map[string]any, len(x))
		for k := range x {
			out[k] = tag(x[k])
		}
		return map[string]any{"$map": out}
	}
	return v
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
			fmt.Fprintln(os.Stderr, "kitprobe: bad request:", err)
			os.Exit(2)
		}
		allow := req.Allow
		r, value := writecheck.Check(req.Body, req.Sock, req.Lim, func(sock, op, key string) bool {
			for _, a := range allow {
				if a[0] == sock && (a[1] == "*" || a[1] == op) && strings.HasPrefix(key, a[2]) {
					return true
				}
			}
			return false
		})
		var refusal any
		if r != nil {
			var fault any
			if r.Fault != nil {
				fault = tag(r.Fault)
			}
			refusal = map[string]any{"n": r.N, "check": r.Check, "code": r.Code, "kind": r.Kind, "fault": fault,
				"reason": r.Reason}
		}
		var lone any
		if r == nil || r.N > 0 {
			_, l, _ := jsonstrict.Decode(req.Body, writecheck.JSONDepth)
			if l == nil {
				l = []string{}
			}
			lone = l
		}
		if err := enc.Encode(map[string]any{"refusal": refusal, "value": tag(value), "lone": lone}); err != nil {
			fmt.Fprintln(os.Stderr, "kitprobe:", err)
			os.Exit(2)
		}
		if err := out.Flush(); err != nil {
			fmt.Fprintln(os.Stderr, "kitprobe:", err)
			os.Exit(2)
		}
	}
	if err := in.Err(); err != nil {
		fmt.Fprintln(os.Stderr, "kitprobe:", err)
		os.Exit(2)
	}
}
