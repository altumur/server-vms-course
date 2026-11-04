package example

import (
	"fmt"
	"os"

	"kitmodule/internal/flags"
)

// parseDaemon — the command line of P/01.3 Н1.3 «Daemon flags»: a refusal is exit 2 with the flag named.
func parseDaemon(args []string) (*flags.Flags, int) {
	f, r := flags.ParseArgs(args, os.Getenv) // os.Args[1:]
	if r != nil {
		fmt.Fprintln(os.Stderr, "configstore:", r.Error())
		return nil, r.Code // 2
	}
	if f.Cmd != "daemon" {
		return f, 0 // admin_ops: status, join, … — yours
	}
	fmt.Printf("dir %s sockets %s rights %q body %d row %d\n", f.Dir, f.Sockets, f.Rights, f.MaxBody, f.MaxValue)
	return f, 0
}
