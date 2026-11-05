// Handwritten environment of gen_box.py; closed in a kit, origin handwritten.
package box

import (
	"crypto/sha256"
	"fmt"
	"math"
	"reflect"
	"strconv"
	"strings"
)

// ImportCopy implements the box transfer over the durable store port. All input
// checks finish before BeginImport. Only the input bytes and the explicit base
// identify an attempt; force removes the clock refusal alone.
func ImportCopy(store CopyStorage, data []byte, ceiling int64, opts CopyOptions) error {
	index, rows, copyError := DecodeCopy(data, ceiling)
	if copyError != nil {
		return copyError
	}
	var err error
	if err = checkCopyPreflight(index, rows, opts); err != nil {
		return err
	}
	if store == nil {
		return copyRefuse("Isolation", "no copy storage connected")
	}
	digest := fmt.Sprintf("%x", sha256.Sum256(data))
	called := 0
	var operationErr error
	lockErr := store.WithCopyLock(func(tx CopyTxn) (result error) {
		called++
		defer func() { operationErr = result }()
		state, err := tx.Snapshot()
		if err != nil {
			return fmt.Errorf("import snapshot: %w", err)
		}
		if err = checkCopyUpperAndClock(state.Rows, opts); err != nil {
			return err
		}
		for _, row := range state.Rows {
			if row.Index > state.Index {
				return copyRefuse("Check", "unreliable store index: %s", row.Key)
			}
		}
		var progress ImportProgress
		if state.Import != nil {
			if state.Import.Phase == "Done" {
				return copyRefuse("Done", "import_repeated: a former import already finished")
			}
			if state.Import.Phase != "Transfer" || state.Import.InputSHA256 != digest || state.Import.IndexBase != opts.IndexBase {
				return copyRefuse("Isolation", "unfinished import: repeat the same input and index-base")
			}
			progress = *state.Import
			progress.Floor = cloneCopyRow(progress.Floor)
			if err = checkSavedFloor(state, progress); err != nil {
				return err
			}
		} else {
			for _, row := range state.Rows {
				if !strings.HasPrefix(row.Key, "platform/configstore-doors/") {
					return copyRefuse("Isolation", "target is not fresh: %s", row.Key)
				}
			}
			_, floor, ok := Floor(Upper(rows, state.Rows), opts.Now)
			if !ok {
				return copyRefuse("Check", "generation overflow")
			}
			base := opts.IndexBase
			if state.Index > base {
				base = state.Index
			}
			if base == math.MaxUint64 {
				return copyRefuse("Check", "version overflow")
			}
			at, _ := copyNowText(opts.Now)
			progress = ImportProgress{InputSHA256: digest, IndexBase: opts.IndexBase, Phase: "Transfer",
				Floor: Row{Key: FloorKey, Index: base + 1, Items: map[string]string{
					"floor": strconv.FormatUint(floor, 10), "generation_at": at}}}
			// One durable boundary publishes this exact F1 and the continuation
			// identity. An unknown reply is resolved by Snapshot on the next call.
			if err = tx.BeginImport(progress); err != nil {
				return fmt.Errorf("copy New floor: %w", err)
			}
			state, err = tx.Snapshot()
			if err != nil {
				return err
			}
			if err = checkSavedFloor(state, progress); err != nil {
				return err
			}
		}
		if state.Import.Phase != "Transfer" {
			return copyRefuse("New floor", "the store did not durably mark Transfer")
		}
		present, err := copyRowsByKey(state.Rows)
		if err != nil {
			return err
		}
		for _, row := range rows {
			if row.Key == FloorKey {
				continue // input floor is only upper/generation_at input, never a transfer row
			}
			if got, exists := present[row.Key]; exists && sameCopyRow(got, row) {
				continue // durable progress, also after a lost WriteImport reply
			}
			if err = tx.WriteImport(cloneCopyRow(row)); err != nil {
				return fmt.Errorf("copy Transfer %s: %w", row.Key, err)
			}
		}
		state, err = tx.Snapshot()
		if err != nil {
			return err
		}
		if err = checkCopyComplete(state, progress, rows); err != nil {
			return err
		}
		if err = tx.FinishImport(); err != nil {
			return fmt.Errorf("copy Done: %w", err)
		}
		state, err = tx.Snapshot()
		if err != nil {
			return err
		}
		if state.Import == nil || state.Import.Phase != "Done" {
			return copyRefuse("Done", "the store did not durably mark completion")
		}
		return checkCopyComplete(state, progress, rows)
	})
	if operationErr != nil {
		return operationErr
	}
	if lockErr != nil {
		return lockErr
	}
	if called != 1 {
		return copyRefuse("Isolation", "copy storage executed transfer %d times, want once", called)
	}
	return nil
}

func cloneCopyRow(row Row) Row {
	if row.Items != nil {
		items := make(map[string]string, len(row.Items))
		for k, v := range row.Items {
			items[k] = v
		}
		row.Items = items
	}
	return row
}

func sameCopyRow(left, right Row) bool {
	return left.Key == right.Key && left.Index == right.Index && left.Unreadable == right.Unreadable && reflect.DeepEqual(left.Items, right.Items)
}

func copyRowsByKey(rows []Row) (map[string]Row, error) {
	out := make(map[string]Row, len(rows))
	for _, row := range rows {
		if _, exists := out[row.Key]; exists {
			return nil, copyRefuse("Transfer", "duplicate saved key: %s", row.Key)
		}
		out[row.Key] = row
	}
	return out, nil
}

func checkSavedFloor(state CopyState, p ImportProgress) error {
	if state.Import == nil || state.Import.InputSHA256 != p.InputSHA256 || state.Import.IndexBase != p.IndexBase ||
		!sameCopyRow(state.Import.Floor, p.Floor) || p.Floor.Index <= p.IndexBase || state.Index < p.Floor.Index || state.Index < p.IndexBase {
		return copyRefuse("Transfer", "durable progress/index differs from the first new floor")
	}
	if p.Floor.Key != FloorKey || p.Floor.Unreadable || !decimalItem(p.Floor.Items, "floor") {
		return copyRefuse("Transfer", "invalid saved first floor")
	}
	rows, err := copyRowsByKey(state.Rows)
	if err != nil {
		return err
	}
	if got, exists := rows[FloorKey]; !exists || !sameCopyRow(got, p.Floor) {
		return copyRefuse("Transfer", "the first new floor row was lost or replaced")
	}
	return nil
}

func checkCopyComplete(state CopyState, p ImportProgress, input []Row) error {
	if err := checkSavedFloor(state, p); err != nil {
		return err
	}
	rows, err := copyRowsByKey(state.Rows)
	if err != nil {
		return err
	}
	for _, want := range input {
		if want.Key == FloorKey {
			continue
		}
		if got, exists := rows[want.Key]; !exists || !sameCopyRow(got, want) {
			return copyRefuse("Done", "incomplete transfer: %s or its copy version", want.Key)
		}
	}
	expected, err := copyRowsByKey(input)
	if err != nil {
		return err
	}
	for key := range rows {
		if _, exists := expected[key]; !exists && key != FloorKey && !strings.HasPrefix(key, "platform/configstore-doors/") {
			return copyRefuse("Done", "unexpected saved row: %s", key)
		}
	}
	return nil
}
