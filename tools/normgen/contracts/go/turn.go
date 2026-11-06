package contracts

import (
	"crypto/rand"
	"encoding/hex"
	"math/big"
)

// Writer turn contract (common/contracts/turn.md): get and hold the turn — the actions of one side over its turn row,
// event by event. Kind "placement" (a subsystem turn {holder, manifest_rev}, a new mark of each attempt) or "signer"
// (the turn of the domain process and of the member agent {holder}, holder — the instance), or "operations"
// (the console's {holder}, a fresh mark for each capture attempt, without a manifest revision).

// TurnTerm, TurnRenew — seconds.
const (
	TurnTerm  = 45
	TurnRenew = 10
)

// TurnAction — one action: Word (held, not_held, busy, refused, manifest_behind, wait, stop, reread, done), or Write
// with Cas ("" — no row), or Guard (the guard version of the turn).
type TurnAction struct {
	Word  string
	Write map[string]string
	Cas   string
	Guard string
}

// TurnRead — a read of the turn row: Row nil — no row; Unreadable — not by its form; Version; Seen — seconds this
// version has been unchanged on my monotonic clock.
type TurnRead struct {
	Row        map[string]string
	Unreadable bool
	Version    string
	Seen       float64
}

// Turn — the side: Kind, Me (manifest_rev at placement, the instance at signer; unused at operations).
type Turn struct {
	Kind    string
	Me      string
	mark    string // the mark of the current attempt (placement/operations)
	version string // the version of my confirmed turn
	pending string // the write in flight: take, renew, barrier, confirm, release
	reread  bool   // the next read is a reread after an unknown outcome of my turn write
	held    bool
}

// Mark — the mark of the current attempt (placement/operations) or the instance (signer).
func (t *Turn) Mark() string {
	if t.Kind == "signer" {
		return t.Me
	}
	return t.mark
}

func (t *Turn) newMark() {
	b := make([]byte, 8)
	_, _ = rand.Read(b)
	t.mark = hex.EncodeToString(b)
}

func (t *Turn) write(holder, cas, pending string) TurnAction {
	t.pending = pending
	w := map[string]string{"holder": holder}
	if t.Kind == "placement" {
		w["manifest_rev"] = t.Me
	}
	return TurnAction{Write: w, Cas: cas}
}

func revGreater(a, b string) bool {
	x, ok1 := new(big.Int).SetString(a, 10)
	y, ok2 := new(big.Int).SetString(b, 10)
	return ok1 && ok2 && x.Cmp(y) > 0
}

// Read — steps 1–3 (or the reread after an unknown outcome of my turn write).
func (t *Turn) Read(r TurnRead) TurnAction {
	if t.reread {
		t.reread = false
		if r.Row != nil && !r.Unreadable && r.Row["holder"] == t.Mark() && t.Mark() != "" {
			return t.write(t.Mark(), r.Version, "confirm")
		}
		t.held = false
		return TurnAction{Word: "not_held"}
	}
	if r.Unreadable {
		return TurnAction{Word: "refused"}
	}
	if r.Row != nil && t.Kind == "placement" && revGreater(r.Row["manifest_rev"], t.Me) {
		return TurnAction{Word: "manifest_behind"}
	}
	cas := ""
	switch {
	case r.Row == nil:
	case r.Row["holder"] == "", t.Kind == "signer" && r.Row["holder"] == t.Me, r.Seen >= TurnTerm:
		cas = r.Version
	default:
		return TurnAction{Word: "busy"}
	}
	if t.Kind == "placement" || t.Kind == "operations" {
		t.newMark()
	}
	return t.write(t.Mark(), cas, "take")
}

// Reply — the answer to my write of the turn row: "ok" with the new version, "conflict", "none".
func (t *Turn) Reply(reply, version string) TurnAction {
	p := t.pending
	t.pending = ""
	if p == "release" {
		t.held = false
		return TurnAction{Word: "done"}
	}
	switch reply {
	case "ok":
		t.version, t.held = version, true
		if p == "barrier" {
			return TurnAction{Word: "reread"}
		}
		return TurnAction{Word: "held"}
	case "none":
		if p == "barrier" {
			t.held = false
			return TurnAction{Word: "stop"}
		}
		t.reread = true
		return TurnAction{Word: "reread"}
	}
	// conflict
	if p == "take" || p == "confirm" {
		t.held = false
		return TurnAction{Word: "not_held"}
	}
	t.held = false
	return TurnAction{Word: "stop"}
}

// Renew — step 4: rewrite my own turn row with the cas of my version.
func (t *Turn) Renew() TurnAction { return t.write(t.Mark(), t.version, "renew") }

// Target — step 5: a changing write with the guard while my confirmed request is younger than TURN_TERM.
func (t *Turn) Target(age float64) TurnAction {
	if age >= TurnTerm {
		return TurnAction{Word: "wait"}
	}
	return TurnAction{Guard: t.version}
}

// TargetReply — "412": stop the attempt; "none": the barrier — at placement change the version of my turn by cas
// (confirmed — reread intent and the rows), at signer reread the turn.
func (t *Turn) TargetReply(reply string) TurnAction {
	if reply == "412" {
		t.held = false
		return TurnAction{Word: "stop"}
	}
	if t.Kind == "signer" {
		t.reread = true
		return TurnAction{Word: "reread"}
	}
	return t.write(t.Mark(), t.version, "barrier")
}

// End — step 6 (signer: SIGTERM at the active one): holder "" with the cas of my version.
func (t *Turn) End() TurnAction { return t.write("", t.version, "release") }
