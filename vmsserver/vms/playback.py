"""Who may read a device's own footage at its holder's playback door: the console's signature, or the door's key."""
# ================================================================================================
# # playback.py — a signed address for the device's archive (the review's fourth pass, blocker 4)
#
# The console checked `view` on the camera and wrote `archive.read`, and then handed the browser the holder's
# door as it is — `http://<holder>/playback/<cam>?from&to` — a door that asked nobody. `PLAYBACK_HOST` is opened
# beyond loopback for exactly that browser, so a viewer of camera 1 edited `1` into `2` and took camera 2's card,
# past the gate and the journal.
#
# Two ways the door could have checked the viewer, and the one taken:
#
#   the viewer's token    the gateway's way (`LiveWorker.handler`): the console passes the token on. A browser's
#                         `<video src>` sends no `Authorization`, and the cookie is the console's host's — the
#                         holder is another server. The token would have to ride in the URL: a bearer of every
#                         right the person has, in a log line on a machine the person never heard of
#   a signed address      the console checks the gate, then signs WHAT it allowed: this camera, these minutes,
#                         until a moment five minutes away, for this viewer. Edited, the signature does not
#                         match; replayed later, it has expired; and what it can open is only that piece
#
# THE KEY IS THE DOOR'S OWN, announced where its address is announced. The holder makes one when it opens the
# door and says it in its heartbeat (`playback_key`, beside the platform's fields — never in a camera's status
# entry: those are shown on the page as the read model). Whoever can read the address can read the key — the
# console, the recorder, the survey: processes with the cluster's object store. A browser reads neither. No
# deploy setting to share, nothing to rotate by hand: a restart is a new key, and a URL handed out before it
# is refused, as one five minutes old is.
#
# The processes that read the door — the recorder closing a gap, the survey watching a card — are not a viewer
# and are not signed per piece: they take a per-camera capability (`process_url`), a path segment the key
# derives for one camera, so an address that leaked opens that camera's card and no other. What stays open is
# what stays open at every door between processes until mutual TLS: whoever has the store has the key.
#
# Asked only when the cluster is gated — in a domain, its store holding a key set (`Gate.gated`): a console that
# is open hands out what anybody could ask it for, and a door that refused would protect nothing. The same rule
# as the console's and the gateway's.
# ================================================================================================
from __future__ import annotations

import hashlib
import hmac
import secrets
from urllib.parse import quote, urlsplit, urlunsplit

TTL = 300.0                   # how long an address the console signs opens the door: a click, and the player's re-asks


def new_key() -> str:
    return secrets.token_hex(32)


def _mac(key: str, *parts: str) -> str:
    return hmac.new(key.encode(), "\n".join(parts).encode(), hashlib.sha256).hexdigest()


def times(t0, t1) -> tuple[str, str]:
    """The interval as it is signed and as it is read back — the same text on both sides."""
    a, b = float(t0), float(t1)
    if not b > a:
        raise ValueError("an interval ends after it starts")
    return f"{a:.3f}", f"{b:.3f}"


# The query a console appends for one viewer: `from`, `to`, `exp`, `v` (who), `sig`.
def signed_query(key: str, cam, t0, t1, who: str, now: float, ttl: float = TTL) -> str:
    a, b = times(t0, t1)
    exp = f"{now + ttl:.0f}"
    sig = _mac(key, "viewer", str(cam), a, b, exp, who)
    return f"from={a}&to={b}&exp={exp}&v={quote(who, safe='')}&sig={sig}"


# `who` when the query is the console's for this camera and these minutes and has not expired; else `PermissionError`
# naming why. `q` is the parsed query.
def check_signed(key: str, cam, q: dict, now: float) -> str:
    try:
        a, b = times(q.get("from", ""), q.get("to", ""))
        exp = float(q["exp"])
    except (KeyError, ValueError):
        raise PermissionError("an address the console did not sign") from None
    want = _mac(key, "viewer", str(cam), a, b, str(q["exp"]), str(q.get("v", "")))
    if not hmac.compare_digest(want, str(q.get("sig", ""))) or q.get("from") != a or q.get("to") != b:
        raise PermissionError("the signature does not match this camera and these minutes")
    if now > exp:
        raise PermissionError("the address has expired: ask the console again")
    return str(q.get("v", ""))


def capability(key: str, cam) -> str:
    return _mac(key, "process", str(cam))[:32]


# A process's address for one camera: `…/playback/<cam>/<capability>`, to which it appends `?from&to` as it always
# did. `found` is `holder_of(…)`'s `(worker, heartbeat, status)`; a holder that announced no key (an older build,
# or a test's heartbeat) is asked as it was.
def process_url(found) -> str:
    url = str(found[2].get("playback_url") or "")
    key = str(found[1].extra.get("playback_key") or "")
    if not url or not key:
        return url
    u = urlsplit(url)
    return urlunsplit(u._replace(path=f"{u.path.rstrip('/')}/{capability(key, found[2].get('id'))}"))
