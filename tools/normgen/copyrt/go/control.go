// Handwritten environment of gen_box.py; closed in a kit, origin handwritten.
package box

import (
	"errors"
	"fmt"
	"os"
	"time"
)

// CopyControl implements admin.CopyOps without choosing your storage format or
// private admin transport. Open connects the actual live store for backup, or an
// exclusive stopped target for import/restore; close releases it. Construct a
// control per command, using that command's -dir, -max-value and wall clock.
type CopyControl struct {
	Open    func(command string) (store CopyStorage, close func(), err error)
	Dir     string
	Ceiling int64
	Now     func() time.Time
}

func (c CopyControl) open(command string) (CopyStorage, func(), error) {
	if c.Open == nil {
		return nil, nil, errors.New("copy: no store opener connected")
	}
	s, close, err := c.Open(command)
	if err != nil {
		return nil, nil, err
	}
	if close == nil {
		close = func() {}
	}
	if s == nil {
		close()
		return nil, nil, errors.New("copy: store opener returned nil")
	}
	return s, close, nil
}

func (c CopyControl) Backup(file string) error {
	if c.Dir == "" {
		return errors.New("backup: the live store's data directory is not connected")
	}
	if err := BackupTarget(file, c.Dir); err != nil {
		return err
	}
	s, close, err := c.open("backup")
	if err != nil {
		return err
	}
	defer close()
	if err = BackupCopy(s, file, c.Dir); err != nil {
		return fmt.Errorf("copy backup %s: %w", file, err)
	}
	return nil
}

func (c CopyControl) Import(file string, base uint64, force bool) error {
	return c.transfer("import", file, base, force)
}

func (c CopyControl) Restore(file string, force bool) error {
	return c.transfer("restore", file, 0, force)
}

func (c CopyControl) transfer(command, file string, base uint64, force bool) error {
	// Read once: this immutable byte slice identifies the attempt, even if the
	// source path is replaced after the check. No reopening between rows.
	data, err := os.ReadFile(file)
	if err != nil {
		return fmt.Errorf("copy Check input %s: %w", file, err)
	}
	index, rows, copyError := DecodeCopy(data, c.Ceiling)
	if copyError != nil {
		return fmt.Errorf("copy Check input %s: %w", file, copyError)
	}
	if command == "restore" {
		base = index
	}
	if c.Now == nil {
		return fmt.Errorf("copy Check input %s: no wall clock connected", file)
	}
	opts := CopyOptions{IndexBase: base, Force: force, Now: c.Now()}
	// Reject bad input and clock before even opening a target. ImportCopy repeats
	// these checks under its own public API; the host opener can itself refuse.
	if _, err = copyNowText(opts.Now); err != nil {
		return fmt.Errorf("copy input %s: %w", file, err)
	}
	if base < index {
		return fmt.Errorf("copy input %s: %w", file, copyRefuse("Check", "index-base is below the copy index"))
	}
	if err = checkCopyUpperAndClock(rows, opts); err != nil {
		return fmt.Errorf("copy input %s: %w", file, err)
	}
	s, close, err := c.open(command)
	if err != nil {
		return fmt.Errorf("copy Isolation input %s: %w", file, err)
	}
	defer close()
	if err = ImportCopy(s, data, c.Ceiling, opts); err != nil {
		return fmt.Errorf("copy input %s: %w", file, err)
	}
	return nil
}
