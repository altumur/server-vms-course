// Обвязка проверки tools/normgen/test_gen_checks.py: один долгоживущий процесс; читает входы JSON построчно со stdin,
// гоняет сгенерированный пакет checks и на каждую строку сразу пишет строку с цепочкой и отказом.
// go.mod обвязки пишет тест (replace на каталог сгенерированного модуля).
//
// Вход строки: {"sock": s, "body": JSON тела, "lone": [указатели], "lim": {имя: int}, "allow": [[сокет, операция, префикс]]}.
// Выход строки: {"chain": [[n, исход]], "check": отказ | null, "chain_hit": отказ | null}; значения fault — с метками
// {"$int": "8"}, {"$double": "1.5"}, {"$map": {...}}, чтобы int и double не смешались в JSON.
package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"fmt"
	"os"
	"strconv"
	"strings"

	"normgen/p01-1/checks"
)

type request struct {
	Sock  string
	Body  json.RawMessage
	Lone  []string
	Lim   map[string]int64
	Allow [][3]string
}

// decodeBody — JSON тела в значения пакета: число без . и e в пределах int64 — int64, иначе float64 (1e400 — +Inf).
func decodeBody(raw json.RawMessage) (any, error) {
	d := json.NewDecoder(bytes.NewReader(raw))
	d.UseNumber()
	var v any
	if err := d.Decode(&v); err != nil {
		return nil, err
	}
	return convert(v), nil
}

func convert(v any) any {
	switch x := v.(type) {
	case json.Number:
		s := string(x)
		if !strings.ContainsAny(s, ".eE") {
			if i, err := strconv.ParseInt(s, 10, 64); err == nil {
				return i
			}
		}
		f, _ := strconv.ParseFloat(s, 64)
		return f
	case []any:
		for k := range x {
			x[k] = convert(x[k])
		}
		return x
	case map[string]any:
		for k := range x {
			x[k] = convert(x[k])
		}
		return x
	}
	return v
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

func refusal(r *checks.Refusal) any {
	if r == nil {
		return nil
	}
	var fault any
	if r.Fault != nil {
		fault = tag(r.Fault)
	}
	return map[string]any{"n": r.N, "check": r.Check, "code": r.Code, "kind": r.Kind, "fault": fault,
		"fault_error": r.FaultErr != ""}
}

func main() {
	in := bufio.NewScanner(os.Stdin)
	in.Buffer(make([]byte, 1<<20), 1<<26)
	out := bufio.NewWriter(os.Stdout)
	defer out.Flush()
	enc := json.NewEncoder(out)
	enc.SetEscapeHTML(false)
	for in.Scan() {
		var req request
		if err := json.Unmarshal(in.Bytes(), &req); err != nil {
			fmt.Fprintln(os.Stderr, "harness: bad request:", err)
			os.Exit(2)
		}
		body, err := decodeBody(req.Body)
		if err != nil {
			fmt.Fprintln(os.Stderr, "harness: bad body:", err)
			os.Exit(2)
		}
		allow := req.Allow
		input := checks.Input{Body: body, Sock: req.Sock, Lone: req.Lone, Lim: req.Lim, Fns: checks.Fns{
			Allowed: func(sock, op, key string) bool {
				for _, a := range allow {
					if a[0] == sock && (a[1] == "*" || a[1] == op) && strings.HasPrefix(key, a[2]) {
						return true
					}
				}
				return false
			}}}
		hit := checks.Check(input)
		// Chain — на свежем разборе: Check не должен менять вход, но сверка не полагается на это.
		body2, _ := decodeBody(req.Body)
		input.Body = body2
		steps, chainHit := checks.Chain(input)
		chain := make([][2]any, len(steps))
		for k, s := range steps {
			chain[k] = [2]any{s.N, s.Status}
		}
		if err := enc.Encode(map[string]any{"chain": chain, "check": refusal(hit), "chain_hit": refusal(chainHit)}); err != nil {
			fmt.Fprintln(os.Stderr, "harness:", err)
			os.Exit(2)
		}
		// Процесс долгоживущий: ответ на строку уходит сразу, тест читает его до следующего входа.
		if err := out.Flush(); err != nil {
			fmt.Fprintln(os.Stderr, "harness:", err)
			os.Exit(2)
		}
	}
	if err := in.Err(); err != nil {
		fmt.Fprintln(os.Stderr, "harness:", err)
		os.Exit(2)
	}
}
