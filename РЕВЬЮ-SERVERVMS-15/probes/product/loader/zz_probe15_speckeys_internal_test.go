package w2cplatform

// Probe 15/A: dump every path of the product's closed key tree (speckeys.go) in the course's notation
// (`*` for names, list items under the list's own path, `…` free), to diff against speckeys.py KEYS.

import (
	"fmt"
	"os"
	"sort"
	"testing"
)

func TestProbe15DumpSpecKeys(t *testing.T) {
	out := os.Getenv("PROBE15_KEYS_OUT")
	if out == "" {
		t.Skip("PROBE15_KEYS_OUT unset")
	}
	var paths []string
	var walk func(at string, n *keyNode)
	walk = func(at string, n *keyNode) {
		if n == nil {
			return
		}
		if n.free {
			paths = append(paths, at+" (free)")
			return
		}
		if n.keys != nil {
			for k, c := range n.keys {
				p := k
				if at != "" {
					p = at + "." + k
				}
				paths = append(paths, p)
				walk(p, c)
			}
		}
		if n.named != nil {
			p := at + ".*"
			paths = append(paths, p)
			walk(p, n.named)
		}
		if n.item != nil {
			walk(at, n.item)
		}
	}
	walk("", specKeys)
	sort.Strings(paths)
	f, _ := os.Create(out)
	defer f.Close()
	for _, p := range paths {
		fmt.Fprintln(f, p)
	}
}
