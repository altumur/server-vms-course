package example

import (
	"os"

	"kitmodule/internal/coreadapter"
	"kitmodule/internal/launch"
)

// runDaemon — what cmd/configstore/main.go does (os.Exit of it): flags → refusal 2 → FORMAT → Open → sockets → HTTP.
func runDaemon() int {
	return launch.Main(os.Args[1:], os.Getenv, launch.App{
		Mark: launch.Mark{Format: "configstore", Version: 1, Impl: "configstore"}, // your on-disk format
		Open: coreadapter.Open,                                                    // your core (open.go)
	})
}

// runEmpty — the empty core explicitly (the frame takes it itself while coreadapter.Open is the kit's stub).
func runEmpty() int {
	return launch.Main(os.Args[1:], os.Getenv, launch.App{
		Mark: launch.Mark{Format: "configstore", Version: 1, Impl: "configstore"},
		Open: func(coreadapter.Config) (coreadapter.Core, error) { return launch.Empty{}, nil },
	})
}
