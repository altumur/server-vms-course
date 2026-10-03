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
#   (`SubsystemSpec.refuse`), hidden wherever a stored one is said.
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
#   a stem anywhere      pass, pwd, psw, secret, token, auth, cred   (`password`, `pwd`, `access_token`, `x-auth`)
#   one of the names     user, usr, username, userid, login, loginuse, loginpas, account, key, apikey, sig, signature,
#                        sid, session
#   a suffix             `_key`                                       (`api_key`, `access_key`)
#
# Read in the query and in a path segment's `;name=value` (a matrix parameter, which some RTSP servers read the login
# from); `%`-escapes undone first, so `p%77d` is `pwd`. A name outside the list is a parameter like any other: the list
# is what the refusal names, and a camera that hides its password under another name is one to add to it.
_CRED_STEMS = ("pass", "pwd", "psw", "secret", "token", "auth", "cred")
_CRED_NAMES = frozenset({"user", "usr", "username", "userid", "login", "loginuse", "loginpas", "account", "key",
                         "apikey", "sig", "signature", "sid", "session"})


def is_credential_param(name: str) -> bool:
    n = unquote_plus(str(name)).strip().lower().replace("-", "_")
    return n in _CRED_NAMES or n.endswith("_key") or any(s in n for s in _CRED_STEMS)


def _params(url: str) -> list[tuple[str, str]]:
    s = str(url).split("#", 1)[0]
    head, _, query = s.partition("?")
    parts = re.split(r"[&;]", query) if query else []
    parts += [p for seg in head.split("://", 1)[-1].split("/") for p in seg.split(";")[1:]]
    return [(name, v) for name, eq, v in (p.partition("=") for p in parts) if eq]


def credential_params(url: str) -> list[str]:
    """The names of the parameters of `url` that carry a credential, as written."""
    return [name for name, _ in _params(url) if is_credential_param(name)]


# …and a stored one is never said (a row kept from before the refusal; one another build wrote): whatever stands before
# an `@` — a userinfo, or one in a path that names its host there — and the value of every credential parameter. Only a
# string with `://` in it is an address; anything else comes back as it was.
_PARAM = re.compile(r"([?&;])([^=&;#?/]*)=([^&;#]*)")
# A run up to an `@`, tried only where a run can begin — the start, or after a `/` or an `@` (the eleventh review's
# sweep): unanchored, `[^/@]*@` was tried from every position of a run with no `@` in it, and a source of 100 000
# characters held a console's thread for minutes. The same matches; one scan of the string.
USERINFO = re.compile(r"(?<![^/@])[^/@]*@")


def hide_in_url(value):
    if not isinstance(value, str) or "://" not in value:
        return value
    s = USERINFO.sub("…@", value)
    return _PARAM.sub(lambda m: f"{m[1]}{m[2]}={SECRET_MASK}" if m[3] and is_credential_param(m[2]) else m[0], s)
