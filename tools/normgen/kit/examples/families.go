package example

import (
	"log"

	"kitmodule/internal/families"
)

// readFloor — the floor row as the issuer reads it: the value, or the outcome of an unreadable row at the reader.
func readFloor(items map[string]string) (int64, bool) {
	row, r := families.ReadEpochFloor(items, families.Reader)
	if !r.OK() {
		// which rows of epoch_floor.outcomes.tsv act ("/floor", ""): what they do is the norm's prose — yours
		log.Printf("epoch_floor unreadable at %v: outcomes %v", r.Paths, families.EpochFloor.OutcomesFor(r.Paths, "<s>worker"))
		return 0, false
	}
	return row.Floor, true
}

// doorRow — the own door row in the writer's notation; a refused Result is not to be written.
func doorRow(id string, now float64) (string, map[string]string, bool) {
	items, r := families.ConfigstoreDoorsRow{SeenAt: now}.Items()
	return families.ConfigstoreDoorsKey(id), items, r.OK()
}

// visibleDoor — a stored door row counts only when its key and items are readable.
func visibleDoor(key string, items map[string]string) bool {
	return families.ConfigstoreDoors.Judge(key, families.ItemsOf(items), families.Reader).OK()
}
