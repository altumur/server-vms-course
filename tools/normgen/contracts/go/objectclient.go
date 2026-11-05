package contracts

import (
	"net/url"
	"path"
	"strings"
)

// Object client contract (common/contracts/object-client.md): the address OBJECTS and the class of a read outcome.

// ObjectAddress — the parsed OBJECTS: Kind "file" | "cluster"; Dir — the directory of the writes; at cluster —
// Resource, the explicit read door (resource=), or "" with Door — the key of the door row platform/doors/<server>
// whose url is the read door.
type ObjectAddress struct {
	Kind     string
	Dir      string
	Resource string
	Door     string
}

// ParseObjects — parse: a bare file:// — <PLATFORM_DIR>/objects; file://<absolute path>; cluster://[<name>][?resource=
// <url>] (resource exactly one, non-empty after percent-decoding; without it — the door row of its own server);
// another scheme, a non-absolute path, an empty or repeated resource — ErrRefuse (a start refusal, code 2).
func ParseObjects(objects, platformDir, serverName string) (ObjectAddress, error) {
	own := path.Join(platformDir, "objects")
	switch {
	case objects == "file://":
		return ObjectAddress{Kind: "file", Dir: own}, nil
	case strings.HasPrefix(objects, "file://"):
		p := objects[len("file://"):]
		if !strings.HasPrefix(p, "/") {
			return ObjectAddress{}, ErrRefuse
		}
		return ObjectAddress{Kind: "file", Dir: p}, nil
	case strings.HasPrefix(objects, "cluster://"):
		addr := ObjectAddress{Kind: "cluster", Dir: own}
		_, query, hasQuery := strings.Cut(objects[len("cluster://"):], "?")
		found := false
		if hasQuery {
			for _, part := range strings.Split(query, "&") {
				name, value, _ := strings.Cut(part, "=")
				if name != "resource" {
					continue
				}
				v, err := url.PathUnescape(value)
				if found || err != nil || v == "" {
					return ObjectAddress{}, ErrRefuse
				}
				addr.Resource, found = v, true
			}
		}
		if !found {
			addr.Door = "platform/doors/" + serverName
		}
		return addr, nil
	}
	return ObjectAddress{}, ErrRefuse
}

// DoorRead — the door row as read at an access: Row (nil — no row), Unreadable — not by its form, NoReply — the
// store did not answer.
type DoorRead struct {
	Row        map[string]any
	Unreadable bool
	NoReply    bool
}

// ReadDoor — the read door by the door row: its url, or "" — the reading of the cluster objects is unknown (no row,
// it does not read, the store did not answer), not «absent» and not a start refusal.
func ReadDoor(d DoorRead) string {
	if d.NoReply || d.Unreadable || d.Row == nil {
		return ""
	}
	u, _ := d.Row["url"].(string)
	return u
}

// ObjectReply — the answer of GET /v1/objects/{key}: Status and X-Missing (nil — no header); a nil *ObjectReply — the
// door did not answer.
type ObjectReply struct {
	Status  int
	Missing *string
}

// ObjectOutcome — «Outcomes and what the client does»: "object", "absent" (404 without X-Missing), "unknown" (404 with
// X-Missing, 503, no answer) or "refused" (400, 403, 413).
func ObjectOutcome(r *ObjectReply) string {
	if r == nil {
		return "unknown"
	}
	switch r.Status {
	case 200:
		return "object"
	case 404:
		if r.Missing != nil {
			return "unknown"
		}
		return "absent"
	case 400, 403, 413:
		return "refused"
	}
	return "unknown"
}
