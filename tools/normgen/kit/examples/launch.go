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

// runWithoutCore — before your core exists: every method answers 503 «not implemented».
func runWithoutCore() int {
	return launch.Main(os.Args[1:], os.Getenv, launch.App{
		Mark: launch.Mark{Format: "configstore", Version: 1, Impl: "configstore"},
		Open: func(coreadapter.Config) (coreadapter.Core, error) { return launch.NotImplemented{}, nil },
	})
}
