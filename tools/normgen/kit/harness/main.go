// Обвязка tools/normgen/kit/test_kit.py: один долгоживущий процесс в собранном пакете (cmd/kitprobe рядом с internal);
// читает входы построчно со stdin, на каждую строку сразу пишет строку ответа. Путь "kitmodule/internal/" заменяет тест.
//
// Вход строки: {"sock": s, "body": base64 сырых байт тела, "lim": {имя: int}, "allow": [[сокет, операция, префикс]]}.
// Выход строки: {"refusal": отказ writecheck | null, "value": тело с метками | null, "lone": [указатели] | null};
// метки чисел {"$int": "8"}, {"$double": "1.5"}, отображение {"$map": {...}} — чтобы int и double не смешались.
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
