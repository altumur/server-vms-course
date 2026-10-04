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
#   An address in a row (a value with `://`) has its login and its credential parameters hidden too (`hide_in_url`),
#   inside a list or an object as well.
# - `is_credential_param(name)`, `credential_params(url)`, `hide_in_url(value)` — a credential carried in an
#   address's parameters (the eleventh review, blocker 4): refused where a url field is written
#   (`SubsystemSpec.refuse`), hidden wherever a stored one is said. Pairs in the path and in chains too (the twelfth
#   review, blocker 8).
# - `address_refusal(value)` — why an address may not be stored, in words that never repeat it (a spec's url field — a
#   camera's source —, a volume's url, the domain's kept edits, a camera's own console), an address inside a parameter
#   too (the thirteenth review, blocker 6); `NOT_AN_ADDRESS` — the words for one `urlsplit` cannot read;
#   `refusal_within(value)` — the same asked of every string inside a list or an object.
# - `hide_in_reply(value)` — `hide_in_url` over every string of a reply: the idempotency copy's floor.
# ================================================================================================
from __future__ import annotations

import functools
import re
import unicodedata
from urllib.parse import unquote_plus

SECRET_MASK = "***"


# The rule, in one line. `cred_secret` is a secret; `cred_username` is not, and neither is `secret_note` —
# the suffix is the rule and there is no second one.
def is_secret_field(name: str) -> bool:
    return name.endswith("_secret")


# Copies of `rows` with every secret field masked. Empty stays empty. An address keeps its host and path and loses
# what is a credential in it (`hide_in_url`): a row stored before the refusal below shows no password either. A value
# that is a list or an object is masked the same way all the way down (the thirteenth review, minor): `{"source":
# ["rtsp://admin:…@…"]}` was applied on a camera by a kept edit and published as typed.
def mask_secrets(rows: list[dict]) -> list[dict]:
    return [_masked(r) for r in rows]


def _masked(v, depth: int = 0):
    if depth > 64:                                       # a JSON reader stops far sooner; a structure built in code may not
        return SECRET_MASK
    if isinstance(v, dict):
        return {hide_in_url(k): (SECRET_MASK if is_secret_field(str(k)) and x else _masked(x, depth + 1))
                for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_masked(x, depth + 1) for x in v]
    return hide_in_url(v)


# A PASSWORD IN AN ADDRESS'S PARAMETERS IS A PASSWORD (the eleventh review, blocker 4; a run). The rule "no login in a url
# field" looked at the userinfo and at an `@`; `http://10.0.0.5/videostream.cgi?usr=admin&pwd=…` — how many cameras
# take their login — was 201, and `GET /cameras` handed the password to whoever may view the camera, while
# `cred_secret` beside it read `***`. The product's cross-check found the same with every kind of key it tried, in the
# domain's snapshot and raw in the log.
#
# THE RULE IS A NAMED LIST, NOT "NO QUERY". A query is how many cameras are told WHAT to send (`?channel=1&subtype=0`,
# `/Streaming/Channels/101?transportmode=unicast`), and refusing every query would refuse those cameras for a
# parameter that carries no secret. So a parameter is a credential by its NAME, read as WORDS: split at `_`, `-`, `.`
# and where the case turns (`AWSAccessKeyId` is aws access key id), case aside. It is one when
#
#   its words joined are one of the names     (`pass_word`, `PassWord`, `user_id`, `api_key`, `Access-Key`, `pwd`)
#   its last word is one of them — a last     (`access_token`, `x-auth`, `X-Amz-Signature`, `X-Amz-Credential`,
#   `id` aside                                 `aws_secret_access_key`, `AWSAccessKeyId`, `session_id`)
#   a word is a password's, or begins with    (`pwd_md5`, `secret_access_key`, `pswd`)
#   one (`_PASSWORD`, `_GLUED_HEAD`)
#   its last word ends with a password's or   (`userpwd`, `my_authtoken`, `clientsecret`)
#   a token's name (`_GLUED_TAIL`)
#
# BY WORD, NOT BY SUBSTRING (the thirteenth review, minor; the product found the same, wider). Stems were matched
# anywhere in the name, and `?token_bucket=10`, `/passage=north_channel=1`, `?authmode=digest`, `?bypass=1`,
# `?compass=1` were refused as credentials — 8 of the review's 38 ordinary addresses, with no way round for the
# operator. A word that only BEGINS a name (`token` of `token_bucket`, `auth` of `authmode`) names what the parameter
# is about, not what it holds; `pass` glued at the end is `bypass` and `compass` far more often than a password.
#
# `%`-escapes are undone until nothing changes, so `p%77d` and `%2570wd` are `pwd` (the twelfth review: once was not
# enough). A name outside the list is a parameter like any other: the list is what the refusal names, and a camera
# that hides its password under another name is one to add to it. `p`, `code`, `pin` are not on it: too many cameras
# mean something else by them (a profile, a codec), and a list that refuses those refuses cameras, not passwords.
_CRED_NAMES = frozenset({"user", "usr", "username", "userid", "login", "loginuse", "loginpas", "loginpass", "account",
                         "key", "keyid", "apikey", "authkey", "accesskey", "secretkey", "sig", "signature", "sid",
                         "session", "sessionid", "pw", "psd", "pass", "password", "passwd", "pwd", "psw", "userpass",
                         "passcode", "passphrase", "secret", "token", "auth", "authorization", "cred", "creds",
                         "credential", "credentials"})
_PASSWORD = ("password", "passwd", "pwd", "psw", "secret")
_GLUED_HEAD = ("password", "passwd", "pwd", "psw")
_GLUED_TAIL = ("password", "passwd", "pwd", "secret", "token")
_WORDS = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+")
# …and a path segment that IS a password's name gives the next segment as its value (`/user/admin/password/X/snap.jpg`).
# Only a password's, spelt out: a segment named `auth` or `session` is how many paths are spelt (`/cgi-bin/auth/…`),
# and so are `pass` and `pw` (`/live/pass/stream`, `/pw/1` — refused as passwords until the thirteenth review).
_PATH_NAMES = frozenset({"password", "passwd", "pwd", "psw"})


def _unquoted(s: str) -> str:
    if "%" not in s and "+" not in s:                    # nothing to undo: most segments of most addresses
        return s
    for _ in range(4):                                   # `%2570` is `%70` is `p`; four rounds is more than any device
        u = unquote_plus(s)
        if u == s:
            break
        s = u
    return s


def is_credential_param(name: str) -> bool:
    # NFKC: a full-width `ｐｗｄ` is `pwd` to whoever reads it (a probe of the thirteenth review)
    words = [w.lower() for w in _WORDS.findall(unicodedata.normalize("NFKC", _unquoted(str(name))).strip())]
    if not words:
        return False
    bare = "".join(words)
    tail = words[:-1] if len(words) > 1 and words[-1] == "id" else words
    return (bare in _CRED_NAMES or tail[-1] in _CRED_NAMES or tail[-1].endswith(_GLUED_TAIL)
            or any(w in _PASSWORD or w.startswith(_GLUED_HEAD) for w in words))


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


# Kept for the last few addresses: one is read by the rule, the hiding and the nested walk in turn, each wanting its
# pairs, and each pass over a long address is a pass over all of it.
@functools.lru_cache(maxsize=32)
def _pairs(s: str) -> tuple[tuple[str, int, int], ...]:
    """`(name, start, end)` of every `name=value` of an address, the value's span in `s`."""
    out: list = []
    at = s.find("://")
    if at < 0:
        return ()
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
    return tuple(out)


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


# WHERE AN ADDRESS NAMES ITS HOST: the authority — and, for a scheme that names its host in the path, the path's first
# segment too (`driverpack://acme/<host>/ch/1`; a file's name is a name). The thirteenth review, major 8: the port of
# `driverpack://acme/admin:Hunter2/ch/1` was read by nobody here, so the page said it and `source_refusal` quoted it.
_HOST_IN_PATH = frozenset({"driverpack"})


def _hosts(s: str) -> list[tuple[int, int]]:
    at = s.find("://")
    lo = at + 3
    end = lambda i: min([j for j in (s.find(c, i) for c in "/?#") if j >= 0] or [len(s)])
    hi = end(lo)
    out = [(lo, hi)]
    if s[:at].strip().lower() in _HOST_IN_PATH and s[lo:hi].strip().lower() != "file" and s[hi:hi + 1] == "/":
        out.append((hi + 1, end(hi + 1)))
    return out


# The span of a host's port when it is no port: not digits — or digits followed, past the host, by an `@`
# (`s3://KEY:12/34…@host`: the `/` cut a secret that begins with digits, and its head stood where a port does).
def _port_span(s: str, lo: int, hi: int) -> tuple[int, int] | None:
    host = s[lo:hi]
    colon = host.rfind(":")
    if colon < 0 or (host.startswith("[") and colon < host.find("]")):
        return None
    port = host[colon + 1:]
    return (lo + colon + 1, hi) if port and (not port.isdigit() or "@" in s[hi:]) else None


# AN ADDRESS INSIDE AN ADDRESS (the thirteenth review, blocker 6; a run). A relay is told what to fetch in a parameter —
# go2rtc's `?src=` —, and `http://proxy/relay?src=rtsp%3A%2F%2Fadmin%3AHunter2%40cam%2Fs` was 201: the rule read the
# outer address, where the inner one's `@`, `:` and `?` stand escaped, and the password was in the row, the page, the
# snapshot and the device's key. So a parameter's value, or a path segment, that is an address once unescaped is an
# address like any other: refused for what the outer one would be refused for, and hidden whole where a stored one is
# said. Read to `_NESTED` levels deep — and an address nested deeper is refused for that alone: what is not read is not
# known to be clean. `(name, start, end, inner)`: the value's span in `s`, and the address it holds.
_NESTED = 3


def _nested(s: str) -> list[tuple[str, int, int, str]]:
    out = []
    at = s.find("://")
    q = s.find("?", at + 3)
    for a, b in _split(s, at + 3, len(s) if q < 0 else q, "/"):
        if "%" in s[a:b] and "://" in _unquoted(s[a:b]):
            out.append(("a path segment", a, b, _unquoted(s[a:b])))
    for name, a, b in _pairs(s):
        inner = _unquoted(s[a:b])
        if "://" in inner:
            out.append((name, a, b, inner))
    return out


def hide_in_url(value, _depth: int = 0):
    if not isinstance(value, str) or "://" not in value:
        return value
    s = USERINFO.sub("…@", value)
    spans = [(a, b) for name, a, b in _pairs(s) if b > a and is_credential_param(name)]
    for lo, hi in _hosts(s):
        port = _port_span(s, lo, hi)
        if port is not None:
            spans.append(port)
        if "@" not in s[lo:hi] and "@" in _unquoted(s[lo:hi]):   # an escaped `@`: a login before it, maybe a password
            spans.append((lo, hi))                                  # (a plain one is `…@` already: USERINFO)
    spans += [(a, b) for _, a, b, inner in _nested(s) if address_refusal(inner, _depth + 1)]
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
# keeps (`SubsystemSpec.refuse`: a camera's source since the thirteenth review, which had its own copy of the rule),
# and the doors that are not a spec's: a volume's url (`vms/volumes.refuse`), the domain's edit it keeps and relays
# (М12 `domain/api.py`), a camera's own console (М12 `Device._update`). An address is a string with `://` in it, and it
# may not carry:
# - a login — a userinfo, or an `@` anywhere after the `://` (`s3://KEY:SEC/RET@host`: a secret with a `/` in it put the
#   `@` in the path, past a check that looked before the first `/`; the twelfth review, blocker 10), or an escaped one
#   in a host (`_hosts`). A file's name is a name, `@` and all;
# - a host or port that cannot be read — `KEY:SECRET` with no `@` at all, a password whose `/`, `?` or `#` cut the
#   host short, a host in the path whose port is no number (`driverpack://acme/admin:Hunter2/ch/1`);
# - a credential pair (`credential_params`);
# - an address inside it that may not be stored (`_nested`).
# The words name the parameter, never a value: `urlsplit`'s own ("Port could not be cast to integer value as
# 'Hunter2'") quote the password, and they went into the reply, the journal and the idempotency copy (major 16).
NOT_AN_ADDRESS = ("its host or port cannot be read — a password with an unescaped '/', '?' or '#' in it reads that way; "
                  "the login goes in its own field")


def address_refusal(value, _depth: int = 0) -> str | None:
    from urllib.parse import urlsplit
    s = str(value)
    if "://" not in s:
        return None
    if _depth > _NESTED:
        return f"it nests addresses more than {_NESTED} deep, and what is not read is not known to carry no login"
    try:
        u = urlsplit(s)
        u.port
    except ValueError:                                   # a port that is no number among them: `urlsplit` reads it
        return f"it is not an address: {NOT_AN_ADDRESS}"
    a_file = u.scheme.lower() == "file" or u.netloc.lower() == "file"
    hosts = _hosts(s)
    if not a_file and any(_port_span(s, lo, hi) for lo, hi in hosts[1:]):
        return f"it is not an address: {NOT_AN_ADDRESS}"
    if u.username or u.password or (not a_file and ("@" in s.split("://", 1)[1]
                                                    or any("@" in _unquoted(s[lo:hi]) for lo, hi in hosts))):
        return "it carries a login (what stands before an '@')"
    creds = credential_params(s)
    if creds:
        return f"it carries a credential in its parameters ({', '.join(dict.fromkeys(creds))})"
    for name, _, _, inner in ([] if a_file else _nested(s)):
        why = address_refusal(inner, _depth + 1)
        if why:
            return f"it holds an address in {name if name == 'a path segment' else repr(name)} that may not be stored: {why}"
    return None


# …and one inside a list or an object (the thirteenth review, minor): the domain's door and a camera's own console
# asked only a value that is a string, and `{"source": ["rtsp://admin:…@…"]}` was 202, kept, and applied on the camera.
# `(where, why)` for the first address that may not be stored — `where` its place, `source[0]`, `extra.url` —, None
# when there is none. Past `depth` the structure itself is refused: what is not read is not known to be clean.
def refusal_within(value, where: str = "", depth: int = 0):
    if depth > 64:
        return where, "it is nested too deep to be read"
    if isinstance(value, dict):
        for k in value:                                  # a key is said in `where`: one that is an address is asked first
            why = address_refusal(k) if isinstance(k, str) else None
            if why:
                return where or "a key", why
        items = ((f"{where}.{k}" if where else str(k), v) for k, v in value.items())
    elif isinstance(value, (list, tuple)):
        items = ((f"{where}[{i}]", v) for i, v in enumerate(value))
    else:
        why = address_refusal(value) if isinstance(value, str) else None
        return (where, why) if why else None
    for at, v in items:
        found = refusal_within(v, at, depth + 1)
        if found:
            return found
    return None


# A reply as a copy of it may keep it — the idempotency copy (`IdempotencyKeys.store`): every string in it said as a page
# says an address (`hide_in_url`; a string without `://` stays as it was). Masking twice is masking once.
def hide_in_reply(value):
    if isinstance(value, dict):
        return {k: hide_in_reply(v) for k, v in value.items()}
    if isinstance(value, list):
        return [hide_in_reply(v) for v in value]
    return hide_in_url(value)
