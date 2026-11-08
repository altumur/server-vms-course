// Handwritten environment of gen_box.py: persistence and transport remain the host's.
// The kit closes this file; its provenance is handwritten, not generated.
package box

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
)

// CopyState is a consistent image of the host's row store. It deliberately has no
// replay-id memory or admission time: neither belongs in the portable copy.
// Index is the version high-water mark, including every row and every whole batch.
// Import is durable host metadata, never a portable copy row.
type CopyState struct {
	Index  uint64
	Rows   []Row
	Import *ImportProgress
}

// ImportProgress identifies the exact immutable input and the new floor already
// published by this attempt. The host persists this record with that first floor.
// Phase is Transfer or Done. Save the complete Floor, including its version and
// generation_at: resuming an attempt must not allocate another floor or version.
type ImportProgress struct {
	InputSHA256 string
	IndexBase   uint64
	Floor       Row
	Phase       string
}

// CopyStorage connects the copy procedure to your actual store. WithCopyLock
// excludes ordinary writes, batches and another copy procedure for the entire
// callback; it must return the callback's error. Snapshot also excludes half-batches.
// For a live backup the host honors Source's transport contract, including
// admin-only HTTP copy when declared. This port does not implement or qualify it. For a box
// import/restore open the stopped target store exclusively, not through a socket.
type CopyStorage interface {
	WithCopyLock(func(CopyTxn) error) error
}

// CopyTxn is the store port inside WithCopyLock. A successful method returns only
// after the same durability barriers as ordinary row writes. An error can have an
// unknown outcome: Snapshot after reopening must expose the actual durable state.
// BeginImport atomically persists progress, its Floor as the first row write and
// the new index high-water mark. Source replay/admission memory is never an input;
// the host still records its own floor operation's admission/replay metadata.
// WriteImport keeps
// the supplied row's version exactly; it never allocates an ordinary-write version.
// FinishImport only marks Done, after the controller has checked the actual rows.
// Keep ordinary reads/writes unavailable until Done, including after process restart.
type CopyTxn interface {
	Snapshot() (CopyState, error)
	BeginImport(ImportProgress) error
	WriteImport(Row) error
	FinishImport() error
}

// BackupCopy takes one consistent snapshot and writes an atomic portable copy.
// The target path is checked before the store is asked for any snapshot or write.
func BackupCopy(store CopyStorage, file, dir string) error {
	if store == nil {
		return errors.New("backup: no copy storage connected")
	}
	if dir == "" {
		return errors.New("backup: the live store's data directory is not connected")
	}
	if err := BackupTarget(file, dir); err != nil {
		return err
	}
	called := 0
	var operationErr error
	var data []byte
	lockErr := store.WithCopyLock(func(tx CopyTxn) (result error) {
		called++
		defer func() { operationErr = result }()
		state, err := tx.Snapshot()
		if err != nil {
			return fmt.Errorf("backup snapshot: %w", err)
		}
		if state.Import != nil && state.Import.Phase != "Done" {
			return errors.New("backup: an unfinished import is not a complete store")
		}
		// Encode while the rows are protected: the result owns its bytes and no
		// longer aliases the host's mutable slice or item maps after unlocking.
		data, err = EncodeCopy(state.Index, state.Rows)
		if err != nil {
			return err
		}
		return nil
	})
	if operationErr != nil {
		return operationErr
	}
	if lockErr != nil {
		return lockErr
	}
	if called != 1 {
		return fmt.Errorf("backup: copy storage executed snapshot %d times, want once", called)
	}
	// External file output must not hold the lock excluding ordinary mutations.
	return WriteCopyFile(file, data)
}

// WriteCopyFile uses a new file of mode 0600 in the destination directory, syncs
// it, renames it, then syncs the directory. A pre-rename failure keeps an existing
// target intact; a post-rename error is returned as an unknown durable outcome.
func WriteCopyFile(file string, data []byte) (result error) {
	dir := filepath.Dir(file)
	f, err := os.CreateTemp(dir, ".configstore-copy-*")
	if err != nil {
		return err
	}
	tmp := f.Name()
	defer func() {
		_ = f.Close()
		_ = os.Remove(tmp)
	}()
	if err = f.Chmod(0600); err != nil {
		return err
	}
	if _, err = f.Write(data); err != nil {
		return err
	}
	if err = f.Sync(); err != nil {
		return err
	}
	if err = f.Close(); err != nil {
		return err
	}
	if err = os.Rename(tmp, file); err != nil {
		return err
	}
	d, err := os.Open(dir)
	if err != nil {
		return err
	}
	defer d.Close()
	return d.Sync()
}
