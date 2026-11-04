// Заглушка демона на пакете flags (ADR-0125 № 3, доп. (1) п. 1): судья tools/normgen/flag_judge.py гоняет на ней те же
// пробы запуска, что и на собранном демоне реализации, и в режиме --stub сверяет ещё и разобранные значения.
// Отказ — строка в stderr, {"refusal": флаг} в stdout, код flags.RefuseCode; иначе — поля Flags одним JSON, код 0.
package main

import (
	"encoding/json"
	"fmt"
	"os"
	"reflect"
	"time"

	"normgen/p01-1/flags"
)

func main() {
	fl, ref := flags.ParseArgs(os.Args[1:], os.Getenv)
	if ref != nil {
		fmt.Fprintln(os.Stderr, "start refusal:", ref.Error())
		_ = json.NewEncoder(os.Stdout).Encode(map[string]any{"refusal": ref.Flag})
		os.Exit(ref.Code)
	}
	fields := map[string]any{}
	v := reflect.ValueOf(*fl)
	for k := 0; k < v.NumField(); k++ {
		name, x := v.Type().Field(k).Name, v.Field(k).Interface()
		switch x := x.(type) {
		case time.Duration:
			fields[name] = int64(x)
		case []flags.Member:
			out := []any{}
			for _, m := range x {
				out = append(out, append([]string{m.ID}, m.Addrs...))
			}
			fields[name] = out
		case map[string]bool:
			given := []string{}
			for f := range x {
				given = append(given, f)
			}
			fields[name] = given
		case []string:
			if x == nil {
				x = []string{}
			}
			fields[name] = x
		default:
			fields[name] = x
		}
	}
	_ = json.NewEncoder(os.Stdout).Encode(map[string]any{"fields": fields})
}
