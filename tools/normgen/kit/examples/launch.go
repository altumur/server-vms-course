package example

import (
	"os"

	"kitmodule/internal/coreadapter"
	"kitmodule/internal/frame"
	"kitmodule/internal/launch"
)

// newFrame — the HTTP frame of one socket: yours, internal/frame (the kit's is a TEMPORARY one on net/http).
func newFrame(c coreadapter.Core, cfg coreadapter.Config, sock string) launch.Frame {
	return frame.New(c, cfg, sock)
}

// runDaemon — what cmd/configstore/main.go does (os.Exit of it): flags → refusal 2 → FORMAT → Open → sockets → your frame.
func runDaemon() int {
	return launch.Main(os.Args[1:], os.Getenv, launch.App{
		Mark:  launch.Mark{Format: "configstore", Version: 1, Impl: "configstore"}, // your on-disk format
		Open:  coreadapter.Open,                                                    // your core (open.go)
		Frame: newFrame,                                                            // your HTTP frame (internal/frame)
	})
}

// runEmpty — the empty core explicitly (the frame takes it itself while coreadapter.Open is the kit's stub).
func runEmpty() int {
	return launch.Main(os.Args[1:], os.Getenv, launch.App{
		Mark:  launch.Mark{Format: "configstore", Version: 1, Impl: "configstore"},
		Open:  func(coreadapter.Config) (coreadapter.Core, error) { return launch.Empty{}, nil },
		Frame: newFrame,
	})
}
