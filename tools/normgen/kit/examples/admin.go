package example

import (
	"fmt"
	"path/filepath"

	"kitmodule/internal/admin"
	"kitmodule/internal/flags"
)

// backupShape — the shape of a subcommand body in internal/admin/backup.go: the positional words from f.Args, the
// flags as fields of f, the output to env, the exit code (0 — done; ≠ 0 — a refusal with its reason on Stderr).
func backupShape(f *flags.Flags, env admin.Env) int {
	if len(f.Args) != 1 {
		fmt.Fprintln(env.Stderr, "configstore backup: want backup <file>")
		return 1
	}
	sock := filepath.Join(f.Sockets, "admin.sock") // talk HTTP to the live daemon here
	_ = sock
	return admin.NotInStage("backup", env) // until the stage needs it
}
