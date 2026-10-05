"""Who may read a device's own footage at its holder's playback door: a process of the cluster, by the door's key."""
# ================================================================================================
# # playback.py — a per-camera capability for the device's archive (the review's fourth pass, blocker 4)
#
# The console checked `view` on the camera and wrote `archive.read`, and then handed the browser the holder's
# door as it is — `http://<holder>/playback/<cam>?from&to` — a door that asked nobody. A viewer of camera 1 edited
# `1` into `2` and took camera 2's card, past the gate and the journal.
#
# A page reads a camera's own footage at a RECORDING's door now — its recorder's, handed out with the recording's
# place, with a door token (ADR 0015: the bytes bypass the console; `vms/footage.py`, `device_piece`). The holder's
# door has no door for a page. What reads it is a process of the cluster — the recorder closing a gap or passing a
# page's piece on, the survey watching a card — by a per-camera capability (`process_url`), a path segment the
# door's key derives for one camera, so an address that leaked opens that camera's card and no other.
#
# THE KEY IS THE DOOR'S OWN, announced where its address is announced. The holder makes one when it opens the
# door and says it in its heartbeat (`playback_key`, beside the platform's fields — never in a camera's status
# entry: those are shown on the page as the read model). Whoever can read the address can read the key — the
# recorder, the survey: processes with the cluster's object store. A browser reads neither. No deploy setting to
# share, nothing to rotate by hand: a restart is a new key. What stays open is what stays open at every door between
# processes until mutual TLS: whoever has the store has the key.
#
# WHAT THIS DOOR DOES NOT ASK, AND UNTIL WHEN (the review's sixth pass asked for a signature on the two other routes
# of the holder's door; the owner's decision: authentication between processes waits for the mutual-TLS step). The
# footage — `/playback/<cam>` — is asked for as above. `/devices` and `/recordings/<cam>` are asked for nothing:
# whoever reaches the door on the network reads which devices this holder has open, their channels and how many of
# each device's playback sessions are in use, and the spans every camera's card holds — where the footage is, never
# the footage. What the door has since that pass without asking anybody: a bound on connections and on one
# address's share of them, a deadline on a request's headers, and a stream written in pieces to a client that
# takes them (`vms/worker.py`, `playback_handler`; `w2cplatform/console.py`).
#
# Asked only when the cluster is gated — in a domain, its store holding a key set (`Gate.gated`): a cluster that is
# open hands out what anybody could ask it for, and a door that refused would protect nothing. The same rule as the
# console's and the gateway's.
# ================================================================================================
from __future__ import annotations

import hashlib
import hmac
import secrets
from urllib.parse import urlsplit, urlunsplit


def new_key() -> str:
    return secrets.token_hex(32)


def _mac(key: str, *parts: str) -> str:
    return hmac.new(key.encode(), "\n".join(parts).encode(), hashlib.sha256).hexdigest()


def capability(key: str, cam) -> str:
    return _mac(key, "process", str(cam))[:32]


# A process's address for one camera: `…/playback/<cam>/<capability>`, to which it appends `?from&to` as it always
# did. `found` is `holder_of(…)`'s `(worker, heartbeat, status)`; a holder that announced no key (a test's
# heartbeat) is asked as it was.
def process_url(found) -> str:
    url = str(found[2].get("playback_url") or "")
    key = str(found[1].extra.get("playback_key") or "")
    if not url or not key:
        return url
    u = urlsplit(url)
    return urlunsplit(u._replace(path=f"{u.path.rstrip('/')}/{capability(key, found[2].get('id'))}"))
