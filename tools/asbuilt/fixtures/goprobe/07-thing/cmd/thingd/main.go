// Command thingd is a synthetic daemon for the as-built extractor tests.
package main

import (
	"errors"
	"flag"
	"fmt"
	"os"
	"time"

	"probe/07-thing/internal/thing"
	"probe/common/wire"
)

const MaxItems = 1 << 10

const Timeout = 2 * time.Second

const modeEnv = "THING_MODE"

func main() {
	if err := run(os.Args[1:]); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
}

func run(args []string) error {
	fs := flag.NewFlagSet("thingd", flag.ContinueOnError)
	dir := fs.String("dir", "", "data directory")
	root := fs.String("root", "/var/lib/thing", "state root")
	limit := fs.Int("limit", 64, "item limit")
	wait := fs.Duration("wait", 3*time.Second, "wait for peers")
	verbose := fs.Bool("verbose", false, "verbose log")
	fs.Bool("legacy", false, "accepted and ignored")
	if err := fs.Parse(args); err != nil {
		return err
	}
	if *dir == "" {
		return errors.New("-dir required")
	}
	if *limit > MaxItems {
		return fmt.Errorf("-limit above %d", MaxItems)
	}
	token := os.Getenv("THING_TOKEN")
	_, ok := os.LookupEnv(modeEnv)
	_, _ = thing.Handle("GET", "admin", "k", 1)
	_ = wire.Check("")
	_, _, _, _, _ = root, wait, verbose, token, ok
	return nil
}
