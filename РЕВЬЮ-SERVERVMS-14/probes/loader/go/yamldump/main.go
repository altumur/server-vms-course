// yamldump: prints each file as the PRODUCT's YAML parser (w2cplatform.ParseYAML) reads it, as one JSON line
// `<file>\t<json>` (or `<file>\tERROR\t<why>`) — the Go half of probe_yaml_alike.py, which compares it with PyYAML's
// reading (the course's). Run: GOWORK=<this dir>/../go.work go run . <files...>
package main

import (
	"encoding/json"
	"fmt"
	"math"
	"os"

	p "vmsworker.local/vmsworker/w2cplatform"
)

func clean(v any) any { // NaN/Inf are no JSON: written as strings, as the Python half writes them
	switch x := v.(type) {
	case map[string]any:
		for k, e := range x {
			x[k] = clean(e)
		}
	case []any:
		for i, e := range x {
			x[i] = clean(e)
		}
	case float64:
		if math.IsNaN(x) || math.IsInf(x, 0) {
			return fmt.Sprintf("<float %v>", x)
		}
	}
	return v
}

func main() {
	for _, f := range os.Args[1:] {
		src, err := os.ReadFile(f)
		if err != nil {
			fmt.Printf("%s\tERROR\t%v\n", f, err)
			continue
		}
		v, err := p.ParseYAML(string(src))
		if err != nil {
			fmt.Printf("%s\tERROR\t%v\n", f, err)
			continue
		}
		b, err := json.Marshal(clean(v))
		if err != nil {
			fmt.Printf("%s\tERROR\tjson: %v\n", f, err)
			continue
		}
		fmt.Printf("%s\t%s\n", f, b)
	}
}
