"""A secret is written by the operator and read by the process that needs it.
Everything between those two points renders it as `***`."""
# ================================================================================================
# NOTES — what every part of this file does and why (kept beside the code, not in a separate document)
# ================================================================================================
# # secrets.py — the `*_secret` rule: what a console may never hand back
#
# **Role in the module.** A device needs a login and a password, so a unit's row has to carry them. Nothing
# else in the system does: placement is decided from labels and headroom, the console renders rows, the
# resource works on files. So a secret has exactly two honest points of contact — the operator writes it,
# and the one worker that opens the device reads it — and every path between them is a leak waiting to be
# found.
#
# The rule is a SUFFIX, not a registry: a field whose name ends `_secret` is a secret. One line in a YAML
# and every subsystem has it, which is the same move `type: int` is. A registry would be a second place to
# keep in step with the specs, and the specs would win.
#
# What the rule buys, in three places that are easy to miss:
# - `GET /<rows>` — the obvious one.
# - the reply to a create, and the reply to an update. Less obvious, and worse: the create's reply is what
#   `IdempotencyKeys` stores to answer a retry, so an unmasked reply puts a SECOND copy of the secret in
#   the config store, under a key nobody would think to look at. That is not a hypothetical — it is what
#   the first version of this did, and `test_credentials.py` scans the whole store because of it.
# - `snapshot:` — the fields that leave the cluster for М12. `SubsystemSpec.from_dict` refuses a spec that
#   names a secret there, and leaves secrets out when the snapshot defaults to "every field". A refusal at
#   load time rather than care at review time.
#
# What it does NOT buy, said plainly: this module is about what LEAVES — the page, the snapshot, the logs. The
# row in the store holds the secret sealed when the console has a key (`sealing.py`, `SECRETS_KEY`) and in the
# clear when it has none, with a warning said once; the store's ACL is about writers — anyone who may READ
# `<sub>/<rows>/*` reads every row, sealed or not. On one box that is the
# file under `PLATFORM_DIR`; on a cluster it is raft, encrypted at rest, with a policy per job. Narrowing
# the readers is a change to the Variables contract, not to this file, and it has not been made.
#
# ## Module-level names
# - `SECRET_MASK` — `"***"`. What a masked value reads as.
# - `is_secret_field(name)` — the whole rule: `name.endswith("_secret")`.
# - `mask_secrets(rows)` — copies of the rows with every secret masked. An EMPTY secret stays empty, so a
#   page can tell "not set" from "set" — a mask over an empty string would make every camera look
#   configured. Copies, never in place: the caller usually holds the row it is about to hand to a worker.
#   An address in a row (a value with `://`) has its login and its credential parameters hidden too (`hide_in_url`).
# - `is_credential_param(name)`, `credential_params(url)`, `hide_in_url(value)` — a credential carried in an
#   address's parameters (the eleventh review, blocker 4): refused where a url field is written
#   (`SubsystemSpec.refuse`), hidden wherever a stored one is said. Pairs in the path and in chains too (the twelfth
#   review, blocker 8).
# - `address_refusal(value)` — why an address may not be stored, in words that never repeat it (a volume's url, the
#   domain's kept edits, a camera's own console); `NOT_AN_ADDRESS` — the words for one `urlsplit` cannot read.
# - `hide_in_reply(value)` — `hide_in_url` over every string of a reply: the idempotency copy's floor.
# ================================================================================================
from __future__ import annotations

import re
from urllib.parse import unquote_plus

SECRET_MASK = "***"


# The rule, in one line. `cred_secret` is a secret; `cred_username` is not, and neither is `secret_note` —
# the suffix is the rule and there is no second one.
def is_secret_field(name: str) -> bool:
    return name.endswith("_secret")


# Copies of `rows` with every secret field masked. Empty stays empty. An address keeps its host and path and loses
# what is a credential in it (`hide_in_url`): a row stored before the refusal below shows no password either.
def mask_secrets(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        out.append({k: (SECRET_MASK if is_secret_field(k) and v else hide_in_url(v)) for k, v in r.items()})
    return out


# A PASSWORD IN AN ADDRESS'S PARAMETERS IS A PASSWORD (the eleventh review, blocker 4; a run). The rule "no login in a url
# field" looked at the userinfo and at an `@`; `http://10.0.0.5/videostream.cgi?usr=admin&pwd=…` — how many cameras
# take their login — was 201, and `GET /cameras` handed the password to whoever may view the camera, while
# `cred_secret` beside it read `***`. The product's cross-check found the same with every kind of key it tried, in the
# domain's snapshot and raw in the log.
#
# THE RULE IS A NAMED LIST, NOT "NO QUERY". A query is how many cameras are told WHAT to send (`?channel=1&subtype=0`,
# `/Streaming/Channels/101?transportmode=unicast`), and refusing every query would refuse those cameras for a
# parameter that carries no secret. So a parameter is a credential by its NAME, case and `-`/`_` aside:
#
#   a stem anywhere      pass, pwd, psw, secret, token, auth, cred,  (`password`, `pwd`, `access_token`, `x-auth`,
#                        signature, accesskey                         `X-Amz-Signature`, `AWSAccessKeyId`)
#   one of the names     user, usr, username, userid, login, loginuse, loginpas, account, key, apikey, sig, signature,
#                        sid, session, pw, psd                        (`_` aside too: `user_id` is `userid`)
#   a suffix             `_key`                                       (`api_key`, `access_key`)
#
# `%`-escapes are undone until nothing changes, so `p%77d` and `%2570wd` are `pwd` (the twelfth review: once was not
# enough). A name outside the list is a parameter like any other: the list is what the refusal names, and a camera
# that hides its password under another name is one to add to it. `p`, `code`, `pin` are not on it: too many cameras
# mean something else by them (a profile, a codec), and a list that refuses those refuses cameras, not passwords.
_CRED_STEMS = ("pass", "pwd", "psw", "secret", "token", "auth", "cred", "signature", "accesskey")
_CRED_NAMES = frozenset({"user", "usr", "username", "userid", "login", "loginuse", "loginpas", "account", "key",
                         "apikey", "sig", "signature", "sid", "session", "pw", "psd"})
# …and a path segment that IS a password's name gives the next segment as its value (`/user/admin/password/X/snap.jpg`).
# Only a password's: a segment named `auth` or `session` is how many paths are spelt (`/cgi-bin/auth/snapshot.jpg`).
_PATH_NAMES = frozenset({"password", "passwd", "pass", "pwd", "psw", "pw", "psd"})


def _unquoted(s: str) -> str:
    for _ in range(4):                                   # `%2570` is `%70` is `p`; four rounds is more than any device
        u = unquote_plus(s)
        if u == s:
            break
        s = u
    return s


def is_credential_param(name: str) -> bool:
    n = _unquoted(str(name)).strip().lower().replace("-", "_")
    bare = n.replace("_", "")
    return n in _CRED_NAMES or bare in _CRED_NAMES or n.endswith("_key") or any(s in bare for s in _CRED_STEMS)


# PAIRS IN THE PATH ARE PAIRS (the twelfth review, blocker 8; a run). Pairs were read in the query and after a `;` in a
# path segment, and `rtsp://10.0.0.9:554/user=admin_password=…_channel=1_stream=0.sdp` — how XMeye/Xiongmai recorders
# and many cheap cameras take their login — was 201, and the password stood in `GET /cameras`, the domain's snapshot,
# the device's key (`device_of`: the heartbeat, `/devices`, `vms/requests/*`). Now a pair is `name=value` wherever it
# stands after the `://`:
#
#   in the query                 parts split at `&` and `;` — a value runs to the next of those, `#` and all (a
#                                stored `pwd=ab#cd` was hidden only up to the `#`; the twelfth review, minor)
#   in a path segment            parts split at `&`, `;` and `#` (`/user=admin&password=…&channel=1`, `/cgi;pwd=…`)
#   in a chain                   a part with more than one `=` is `name=value_name=value…`: a value ends at the LAST `_`
#                                (or `#`) before the next `=`, so `Hun_ter2_channel=1` is `Hun_ter2` and `channel`. An
#                                `=` with no `_` before it is the value's own (`token=abc==`)
#   a name segment               `/password/<value>/` (`_PATH_NAMES`)
#
# Positions, not copies: `hide_in_url` masks the value where it stands. One scan of the string, whatever its length.
def _chain(s: str, lo: int, hi: int, out: list) -> None:
    eq = s.find("=", lo, hi)
    if eq < 0:
        return
    name, start, sep = s[lo:eq], eq + 1, -1
    for i in range(eq + 1, hi):
        c = s[i]
        if c in "_#":
            sep = i
        elif c == "=" and sep >= 0:
            out.append((name, start, sep))
            name, start, sep = s[sep + 1:i], i + 1, -1
    out.append((name, start, hi))


def _split(s: str, lo: int, hi: int, seps: str):
    i = lo
    for j in range(lo, hi + 1):
        if j == hi or s[j] in seps:
            yield i, j
            i = j + 1


def _pairs(s: str) -> list[tuple[str, int, int]]:
    """`(name, start, end)` of every `name=value` of an address, the value's span in `s`."""
    out: list = []
    at = s.find("://")
    if at < 0:
        return out
    lo = at + 3
    q = s.find("?", lo)
    q = len(s) if q < 0 else q
    segs = list(_split(s, lo, q, "/"))
    for k, (a, b) in enumerate(segs):
        for c, d in _split(s, a, b, "&;#"):
            _chain(s, c, d, out)
        if k + 1 < len(segs) and _unquoted(s[a:b]).strip().lower() in _PATH_NAMES:
            out.append((s[a:b], *segs[k + 1]))
    if q < len(s):
        for c, d in _split(s, q + 1, len(s), "&;"):
            _chain(s, c, d, out)
    return out


def credential_params(url: str) -> list[str]:
    """The names of the parameters of `url` that carry a credential, as written."""
    return [name for name, _, _ in _pairs(str(url)) if is_credential_param(name)]


# …and a stored one is never said (a row kept from before the refusal; one another build wrote): whatever stands before
# an `@` — a userinfo, or one in a path that names its host there —, a port that is no number (`admin:Hunter2%40h`: a
# password before an escaped `@`, or an unescaped `/`, `?`, `#` in it — the twelfth review, major 16), and the value of
# every credential pair (`_pairs`). Only a string with `://` in it is an address; anything else comes back as it was.
#
# A run up to an `@`, tried only where a run can begin — the start, or after a `/` or an `@` (the eleventh review's
# sweep): unanchored, `[^/@]*@` was tried from every position of a run with no `@` in it, and a source of 100 000
# characters held a console's thread for minutes. The same matches; one scan of the string.
USERINFO = re.compile(r"(?<![^/@])[^/@]*@")


# The span of the authority's port when it is no port: not digits — or digits followed, past the authority, by an `@`
# (`s3://KEY:12/34…@host`: the `/` cut a secret that begins with digits, and its head stood where a port does).
def _port_span(s: str) -> tuple[int, int] | None:
    at = s.find("://")
    lo = at + 3
    hi = min([i for i in (s.find(c, lo) for c in "/?#") if i >= 0] or [len(s)])
    host = s[lo:hi]
    colon = host.rfind(":")
    if colon < 0 or (host.startswith("[") and colon < host.find("]")):
        return None
    port = host[colon + 1:]
    return (lo + colon + 1, hi) if port and (not port.isdigit() or "@" in s[hi:]) else None


def hide_in_url(value):
    if not isinstance(value, str) or "://" not in value:
        return value
    s = USERINFO.sub("…@", value)
    spans = [(a, b) for name, a, b in _pairs(s) if b > a and is_credential_param(name)]
    port = _port_span(s)
    if port is not None:
        spans.append(port)
    out, i = [], 0
    for a, b in sorted(spans):
        if a < i:                                        # inside a span already masked
            a = i
        if b <= a:
            continue
        out += [s[i:a], SECRET_MASK]
        i = b
    return "".join(out) + s[i:]


# WHY AN ADDRESS MAY NOT BE STORED, IN WORDS THAT NEVER REPEAT IT — None when it may. The rule a url field of a spec
# keeps (`SubsystemSpec.refuse`), for the doors that are not a spec's: a volume's url (`vms/volumes.refuse`), the
# domain's edit it keeps and relays (М12 `domain/api.py`), a camera's own console (М12 `Device._update`). An address
# is a string with `://` in it, and it may not carry:
# - a login — a userinfo, or an `@` anywhere after the `://` (`s3://KEY:SEC/RET@host`: a secret with a `/` in it put the
#   `@` in the path, past a check that looked before the first `/`; the twelfth review, blocker 10). A file's name is a
#   name, `@` and all;
# - a host or port `urlsplit` cannot read — `KEY:SECRET` with no `@` at all, or a password whose `/`, `?` or `#` cut
#   the host short;
# - a credential pair (`credential_params`).
# The words name the parameter, never a value: `urlsplit`'s own ("Port could not be cast to integer value as
# 'Hunter2'") quote the password, and they went into the reply, the journal and the idempotency copy (major 16).
NOT_AN_ADDRESS = ("its host or port cannot be read — a password with an unescaped '/', '?' or '#' in it reads that way; "
                  "the login goes in its own field")


def address_refusal(value) -> str | None:
    from urllib.parse import urlsplit
    s = str(value)
    if "://" not in s:
        return None
    try:
        u = urlsplit(s)
        u.port
    except ValueError:                                   # a port that is no number among them: `urlsplit` reads it
        return f"it is not an address: {NOT_AN_ADDRESS}"
    a_file = u.scheme.lower() == "file" or u.netloc.lower() == "file"
    if u.username or u.password or ("@" in s.split("://", 1)[1] and not a_file):
        return "it carries a login (what stands before an '@')"
    creds = credential_params(s)
    if creds:
        return f"it carries a credential in its parameters ({', '.join(dict.fromkeys(creds))})"
    return None


# A reply as a copy of it may keep it — the idempotency copy (`IdempotencyKeys.store`): every string in it said as a page
# says an address (`hide_in_url`; a string without `://` stays as it was). Masking twice is masking once.
def hide_in_reply(value):
    if isinstance(value, dict):
        return {k: hide_in_reply(v) for k, v in value.items()}
    if isinstance(value, list):
        return [hide_in_reply(v) for v in value]
    return hide_in_url(value)
