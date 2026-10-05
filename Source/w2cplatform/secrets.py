"""A secret is written by the operator and read by the process that needs it.
Everything between those two points renders it as `***`."""
# ================================================================================================
# NOTES — what every part of this file does and why (kept beside the code, not in a separate document)
# ================================================================================================
# # secrets.py — the `*_secret` rule: what a console may never hand back
#
# **Role in the module.** Whatever a worker opens may need a login and a password, so a unit's row has to carry them.
# Nothing else in the system does: placement is decided from labels and headroom, the console renders rows, the
# resource works on files. So a secret has exactly two honest points of contact — the operator writes it, and the one
# worker that uses it reads it — and every path between them is a leak waiting to be found.
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
# clear when it has none, with a warning said once. Anyone who may READ `<sub>/<rows>/*` reads every row, sealed or
# not: on one box whoever reads the files under `PLATFORM_DIR`; on a cluster the roles the rights file lets read it
# (`configstore-rights.json`, generated from the specs — the console, the subsystem's controller and workers, the
# roles of the subsystems that refer to it). Sealing is what keeps those readers from the secret; who opens it is
# whoever holds the key ring (`sealing.py`).
#
# ## An address: what the platform reads in it, and what a spec tells it (the boundary's step 4)
# The platform reads an address as RFC 3986 says one is written, and nothing more: a login before an `@` (anywhere
# after the `://`, or escaped in the host), a port that is no number, `name=value` pairs in the query and in a path
# segment (`;`, `&`), an address escaped whole into a path segment. Which NAMES of a pair carry a credential, which
# other spellings of a login the things a subsystem opens accept, and which pair holds another address, are the
# subsystem's: its url field says them (`secret_in`, `SecretRules`), and the platform keeps none of its own. A url
# field is refused by its own rules (`SubsystemSpec.refuse`); everything else — a page, a reply, a log line, a door
# that is no spec's field — by the rules of every spec this process loaded (`catalog.secret_rules`).
#
# ## Module-level names
# - `SECRET_MASK` — `"***"`. What a masked value reads as.
# - `is_secret_field(name)` — the whole rule: `name.endswith("_secret")`.
# - `SecretRules`, `NO_RULES` — a field's `secret_in`, read; `|` puts two together.
# - `mask_secrets(rows)` — copies of the rows with every secret masked. An EMPTY secret stays empty, so a
#   page can tell "not set" from "set" — a mask over an empty string would make every unit look
#   configured. Copies, never in place: the caller usually holds the row it is about to hand to a worker.
#   An address in a row (a value with `://`) has its login and its credential parameters hidden too (`hide_in_url`),
#   inside a list or an object as well.
# - `is_credential_param(name, rules)`, `credential_params(url, rules)`, `hide_in_url(value, rules)` — a credential
#   carried in an address: refused where a url field is written (`SubsystemSpec.refuse`), hidden wherever a stored one
#   is said. `is_login_param(name, rules)` — a pair that carries a login: refused, never hidden (a login identifies, it
#   does not authenticate). `said_name(name)` — a parameter's name as a refusal may say it (one that hides a pair,
#   `pass%3D…`, by that pair's name). `hide_logins(s)` — whatever stands before an `@`, as `…`.
# - `address_refusal(value, rules)` — why an address may not be stored, in words that never repeat it, an address
#   inside one too; `address_fault(value, rules)` — the same and what it carries (`login`, `secret`), which a refusal
#   names the field of; `NOT_AN_ADDRESS` — the words for one `urlsplit` cannot read; `refusal_within(value)` — the
#   same asked of every string inside a list or an object.
# - `hide_in_reply(value)` — `hide_in_url` over every string of a reply: the idempotency copy's floor.
# ================================================================================================
from __future__ import annotations

import functools
import re
import unicodedata
from dataclasses import dataclass
from urllib.parse import unquote_plus

SECRET_MASK = "***"


# The rule, in one line. `cred_secret` is a secret; `cred_username` is not, and neither is `secret_note` —
# the suffix is the rule and there is no second one.
def is_secret_field(name: str) -> bool:
    return name.endswith("_secret")


# HOW AN ADDRESS CARRIES A LOGIN, AS A SPEC SAYS IT (`fields.<url field>.secret_in`; the boundary's step 4, the form
# the architect approved for the course and the product alike). The forms a credential takes in the addresses of what
# a subsystem opens are the subsystem's knowledge — the names what it opens gives a password parameter, a login chained
# into a path — and were a list in this file. Three kinds, each a list entry of its own:
#
#   {param: [names], login: [names]}     a pair `name=value` whose NAME is one of `param` carries a credential, one of
#                                        `login` a login. Read as WORDS (split at `_`, `-`, `.` and where the case
#                                        turns, `%`-escapes undone, a full-width letter its letter): `pwd` — the words
#                                        joined, or the last word (an `id` aside), is it; `=auth` — the words joined and
#                                        nothing else (as the last word of a longer name it names a mode:
#                                        `enable_auth`); `pwd*` — a word begins with it; `*pwd` — the last word ends
#                                        with it. Both are refused; a credential's value is hidden, a login's is not
#   {regex: '…(?P<login>…)…(?P<secret>…)…(?P<name>…)…', in: path|query|authority|fragment, schemes: [...], decoded: bool}
#                                        a spelling of a login that is no pair, read in that part of the address — of
#                                        the schemes listed, any when there is no list: what `secret` matches is
#                                        refused and hidden where it stands, what `login` matches refused, and `name`
#                                        is what a refusal calls it. `decoded` (true unless said): matched on the part
#                                        with its `%`-escapes undone, hidden in the address as written
#   {nested: [names]}                    the value of a pair of these names is read as an address once unescaped (a
#                                        `<scheme>:` before its own `scheme://` aside: `ffmpeg:https://…`), by the
#                                        same rules, three levels deep (`_NESTED`)
#
# BY WORD, NOT BY SUBSTRING (the thirteenth review, minor): a word that only BEGINS a name (`token` of `token_bucket`,
# `auth` of `authmode`) names what the parameter is about, not what it holds — which is why a name is matched whole,
# or as its last word, unless the spec says `x*` or `*x`.
_ENTRY = re.compile(r"(\*?|=)[a-z0-9]+\*?")
PARTS = ("path", "query", "authority", "fragment")
_SCHEME = re.compile(r"[a-z][a-z0-9+.\-]*")
_KINDS = ("{param: […], login: […]}, {regex: …, in: path|query|authority|fragment, schemes?, decoded?}, "
          "{nested: […]}")


@dataclass(frozen=True)
class Names:
    """Pair names as a spec writes them — `name`, `=name`, `name*`, `*name` — read."""
    names: frozenset = frozenset()       # `pwd`: the words joined, or the last word, is one of these
    whole: frozenset = frozenset()       # `=auth`: the words joined is one of these
    begins: tuple = ()                   # `pwd*`: a word begins with one of these
    ends: tuple = ()                     # `*pwd`: the last word ends with one of these

    def __or__(self, other: "Names") -> "Names":
        return Names(self.names | other.names, self.whole | other.whole, tuple(dict.fromkeys(self.begins + other.begins)),
                     tuple(dict.fromkeys(self.ends + other.ends)))

    def says(self, words: list[str]) -> bool:
        if not words:
            return False
        bare = "".join(words)
        tail = words[:-1] if len(words) > 1 and words[-1] == "id" else words
        return (bare in self.names or bare in self.whole or tail[-1] in self.names or tail[-1].endswith(self.ends)
                or any(w.startswith(self.begins) for w in words))

    @classmethod
    def parse(cls, got, key: str, where: str) -> "Names":
        if not isinstance(got, list) or not got:
            raise ValueError(f"{where}: `{key}` is a list of names, not {got!r}")
        names, whole, begins, ends = set(), set(), [], []
        for n in got:
            n = str(n).lower()
            if not _ENTRY.fullmatch(n) or (n.startswith(("*", "=")) and n.endswith("*")):
                raise ValueError(f"{where}: {n!r} in `{key}` is a name, `=name`, `name*` or `*name` — letters and digits")
            if n.startswith("="):
                whole.add(n[1:])
            elif n.endswith("*"):
                begins.append(n[:-1])
            elif n.startswith("*"):
                ends.append(n[1:])
            else:
                names.add(n)
        return cls(frozenset(names), frozenset(whole), tuple(begins), tuple(ends))


@dataclass(frozen=True)
class Pattern:
    """A `{regex: …}` of `secret_in`, read: where it reads, in which schemes, on the text decoded or as written."""
    rx: re.Pattern
    part: str
    schemes: frozenset = frozenset()     # empty: every scheme
    decoded: bool = True


@dataclass(frozen=True)
class SecretRules:
    secret: Names = Names()              # `param:` — a credential: refused, its value hidden
    login: Names = Names()               # `login:` — a login: refused, shown
    patterns: tuple = ()                 # `(Pattern, …)`
    nested: frozenset = frozenset()      # pair names whose value is an address

    def __or__(self, other: "SecretRules") -> "SecretRules":
        return SecretRules(self.secret | other.secret, self.login | other.login,
                           tuple(dict.fromkeys(self.patterns + other.patterns)), self.nested | other.nested)

    # `secret_in` as a spec writes it, read and checked: anything else is refused at load, in words.
    @classmethod
    def parse(cls, secret_in, where: str) -> "SecretRules":
        if not isinstance(secret_in, list):
            raise ValueError(f"{where}: `secret_in` is a list of {_KINDS}, not {secret_in!r}")
        secret, login, patterns, nested = Names(), Names(), [], set()
        for entry in secret_in:
            keys = set(entry) if isinstance(entry, dict) else set()
            if not keys:
                raise ValueError(f"{where}: an entry of `secret_in` is one of {_KINDS}, not {entry!r}")
            if keys & {"param", "login"}:
                if keys - {"param", "login"}:
                    raise ValueError(f"{where}: an entry of `secret_in` is one of {_KINDS}, not {entry!r}")
                if "param" in entry:
                    secret = secret | Names.parse(entry["param"], "param", where)
                if "login" in entry:
                    login = login | Names.parse(entry["login"], "login", where)
            elif "regex" in keys:
                patterns.append(_pattern(entry, keys, where))
            elif "nested" in keys:
                got = entry["nested"]
                if keys != {"nested"} or not isinstance(got, list) or not got or \
                        not all(isinstance(n, str) and n for n in got):
                    raise ValueError(f"{where}: `nested` names the pairs holding an address, a list — not {entry!r}")
                nested |= {n.lower() for n in got}
            else:
                raise ValueError(f"{where}: an entry of `secret_in` is param, regex or nested, not {entry!r}")
        return cls(secret, login, tuple(patterns), frozenset(nested))


def _pattern(entry: dict, keys: set, where: str) -> Pattern:
    if keys - {"regex", "in", "schemes", "decoded"}:
        raise ValueError(f"{where}: an entry of `secret_in` is one of {_KINDS}, not {entry!r}")
    if entry.get("in") not in PARTS:
        raise ValueError(f"{where}: a `regex` says where it reads: `in:` {', '.join(PARTS)}, not {entry.get('in')!r}")
    schemes = entry.get("schemes", [])
    if not isinstance(schemes, list) or not all(isinstance(x, str) and _SCHEME.fullmatch(x) for x in schemes):
        raise ValueError(f"{where}: a `regex`'s `schemes` is a list of schemes (`https`, `ftp`), not {schemes!r}")
    if not isinstance(entry.get("decoded", True), bool):
        raise ValueError(f"{where}: a `regex`'s `decoded` is true or false, not {entry['decoded']!r}")
    try:
        rx = re.compile(str(entry["regex"]))
    except re.error as e:
        raise ValueError(f"{where}: `regex` {entry['regex']!r} is no regular expression: {e}") from None
    if not {"login", "secret"} & set(rx.groupindex) or set(rx.groupindex) - {"login", "secret", "name"}:
        raise ValueError(f"{where}: `regex` {entry['regex']!r} names what it finds — a group `(?P<login>…)` or "
                         f"`(?P<secret>…)`, and maybe `(?P<name>…)`, no other")
    return Pattern(rx, entry["in"], frozenset(schemes), entry.get("decoded", True))


NO_RULES = SecretRules()


def _rules(rules: SecretRules | None) -> SecretRules:
    if rules is not None:
        return rules
    from .catalog import secret_rules
    return secret_rules()


# Copies of `rows` with every secret field masked. Empty stays empty. An address keeps its host and path and loses
# what is a credential in it (`hide_in_url`): a row stored before the refusal below shows no password either. A value
# that is a list or an object is masked the same way all the way down (the thirteenth review, minor): a list holding
# an address with a login was applied by a kept edit and published as typed.
def mask_secrets(rows: list[dict]) -> list[dict]:
    rules = _rules(None)
    return [_masked(r, rules) for r in rows]


def _masked(v, rules: SecretRules, depth: int = 0):
    if depth > 64:                                       # a JSON reader stops far sooner; a structure built in code may not
        return SECRET_MASK
    if isinstance(v, dict):
        return {hide_in_url(k, rules): (SECRET_MASK if is_secret_field(str(k)) and x else _masked(x, rules, depth + 1))
                for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_masked(x, rules, depth + 1) for x in v]
    return hide_in_url(v, rules)


_WORDS = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+")


def _unquoted(s: str) -> str:
    if "%" not in s and "+" not in s:                    # nothing to undo: most segments of most addresses
        return s
    for _ in range(4):                                   # `%2570` is `%70` is `p`; four rounds is more than any address needs
        u = unquote_plus(s)
        if u == s:
            break
        s = u
    return s


def _name_words(name: str) -> list[str]:
    # NFKC: a full-width `ｐｗｄ` is `pwd` to whoever reads it (a probe of the thirteenth review)
    return [w.lower() for w in _WORDS.findall(unicodedata.normalize("NFKC", _unquoted(str(name))).strip())]


# A NAME THAT HIDES A PAIR (the product's r28-secrets2): `?pass%3Dhunter2=1` is, unescaped, `pass=hunter2` — a pair inside
# the name — and the name read as one word was nobody's. A name whose unescaping holds a `=`, `&` or `;` is read as the
# pairs it holds, each by its own name; and said by that name alone (`said_name`), never by what follows it.
_HIDDEN_PAIR = re.compile(r"[=&;]")


def is_credential_param(name: str, rules: SecretRules | None = None) -> bool:
    return _says(name, _rules(rules).secret)


# …and a login's (`login:`): refused, as a credential is, and said as written — a login identifies, and the page that
# shows the address shows whose it is.
def is_login_param(name: str, rules: SecretRules | None = None) -> bool:
    rules = _rules(rules)
    return not _says(name, rules.secret) and _says(name, rules.login)


def _says(name: str, names: Names) -> bool:
    text = _unquoted(str(name))
    if _HIDDEN_PAIR.search(text):
        return any(names.says(_name_words(part.split("=", 1)[0])) for part in re.split(r"[&;]", text))
    return names.says(_name_words(text))


def said_name(name: str) -> str:
    """A parameter's name as a refusal may say it: as written — or, for one that hides a pair, the name of that pair."""
    text = _unquoted(str(name))
    return _HIDDEN_PAIR.split(text, 1)[0] if _HIDDEN_PAIR.search(text) else str(name)


# PAIRS ARE PAIRS WHEREVER THEY STAND (the twelfth review, blocker 8). A pair is `name=value` after the `://`:
#
#   in the query                 parts split at `&` and `;` — a value runs to the next of those, `#` and all (a
#                                stored `pwd=ab#cd` was hidden only up to the `#`; the twelfth review, minor)
#   in a path segment            parts split at `&`, `;` and `#` (`/user=admin&password=…&channel=1`, `/cgi;pwd=…`)
#
# A pair's value runs to the end of its part: `name=a_b=c` is one pair, its value `a_b=c`. A spelling that chains
# several in one part is a subsystem's (`secret_in: {regex: …}`).
# Positions, not copies: `hide_in_url` masks the value where it stands. One scan of the string, whatever its length.
def _split(s: str, lo: int, hi: int, seps: str):
    i = lo
    for j in range(lo, hi + 1):
        if j == hi or s[j] in seps:
            yield i, j
            i = j + 1


def _pair(s: str, lo: int, hi: int, out: list) -> None:
    eq = s.find("=", lo, hi)
    if eq >= 0:
        out.append((s[lo:eq], eq + 1, hi))


def _parts(s: str) -> dict[str, tuple[int, int]]:
    """`{part: (start, end)}` of an address, as RFC 3986 cuts one: its authority after the `://`, its path from the first
    `/`, its query after the `?`, its fragment after the `#`."""
    lo, n = s.find("://") + 3, len(s)
    h = s.find("#", lo)
    h = n if h < 0 else h
    q = s.find("?", lo, h)
    q = h if q < 0 else q
    slash = s.find("/", lo, q)
    a_end = q if slash < 0 else slash
    return {"authority": (lo, a_end), "path": (a_end, q), "query": (min(q + 1, h), h), "fragment": (min(h + 1, n), n)}


# A part with its `%`-escapes undone, and where each of its characters stands in the part as written: what a spec's
# regex reads (`decoded`), and how what it found is hidden where it was written. Escapes of a character of ASCII only —
# what a login and a password are cut by (`:`, `@`, `/`, `=`) is ASCII — four rounds, as `_unquoted`.
_ESCAPE = re.compile(r"%[0-7][0-9A-Fa-f]")


def _decoded(text: str) -> tuple[str, list[int]]:
    pos = list(range(len(text) + 1))
    for _ in range(4):
        if not _ESCAPE.search(text):
            break
        out, at, i = [], [], 0
        while i < len(text):
            if _ESCAPE.match(text, i):
                out.append(chr(int(text[i + 1:i + 3], 16)))
                at.append(pos[i])
                i += 3
            else:
                out.append(text[i])
                at.append(pos[i])
                i += 1
        at.append(pos[len(text)])
        text, pos = "".join(out), at
    return text, pos


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
    for a, b in _split(s, lo, q, "/"):
        for c, d in _split(s, a, b, "&;#"):
            _pair(s, c, d, out)
    if q < len(s):
        for c, d in _split(s, q + 1, len(s), "&;"):
            _pair(s, c, d, out)
    return tuple(out)


# What a spec's `regex` finds: `(kind, start, end, name)` of every login and password it matches, in the part it reads
# of an address of a scheme it reads, the span in `s` as written; `name` is what its group `name` matched, or "".
@functools.lru_cache(maxsize=32)
def _found(s: str, rules: SecretRules) -> tuple[tuple[str, int, int, str], ...]:
    if not rules.patterns or "://" not in s:
        return ()
    scheme, parts = s[:s.find("://")].lower(), _parts(s)
    out = []
    for p in rules.patterns:
        lo, hi = parts[p.part]
        if lo >= hi or (p.schemes and scheme not in p.schemes):
            continue
        text, pos = _decoded(s[lo:hi]) if p.decoded else (s[lo:hi], None)
        for m in p.rx.finditer(text):                   # the part alone: `^` and `$` are its ends
            name = (m.group("name") or "") if "name" in p.rx.groupindex else ""
            for g in ("login", "secret"):
                if g in p.rx.groupindex and m.group(g):
                    a, b = m.span(g)
                    out.append((g, lo + (pos[a] if pos else a), lo + (pos[b] if pos else b), name))
    return tuple(out)


def credential_params(url: str, rules: SecretRules | None = None) -> list[str]:
    """The names of the parameters of `url` that carry a credential, as written (`said_name`)."""
    rules = _rules(rules)
    s = str(url)
    return [said_name(name) for name, a, b in _pairs(s) if is_credential_param(name, rules) or _hides(s[a:b], rules)]


# A VALUE THAT HIDES A PAIR: `?user=admin%26pwd%3D…` is, unescaped, a login and then `pwd=…` — a credential's pair inside
# a value, which nobody read while the login's value was hidden whole and everybody reads now that a login is shown.
# Such a value is a credential's, whatever its pair is named. (A value that is an address is read as one, `_nested`.)
def _hides(value: str, rules: SecretRules) -> bool:
    if "%" not in value:                                 # a `&` or `;` written plainly ends the pair: no value holds it
        return False
    text = _unquoted(value)
    return bool(re.search(r"[&;]", text)) and "://" not in text and any(
        "=" in part and _says(part.split("=", 1)[0], rules.secret) for part in re.split(r"[&;]", text))


def login_params(url: str, rules: SecretRules | None = None) -> list[str]:
    """The names of the parameters of `url` that carry a login, as written (`said_name`)."""
    rules = _rules(rules)
    s = str(url)
    return [said_name(name) for name, a, b in _pairs(s) if is_login_param(name, rules) and not _hides(s[a:b], rules)]


# …and a stored one is never said (a row kept from before the refusal; one another build wrote): whatever stands before
# an `@` — a userinfo, or one in a path —, a port that is no number (`admin:Hunter2%40h`: a password before an escaped
# `@`, or an unescaped `/`, `?`, `#` in it — the twelfth review, major 16), the value of every credential pair
# (`_pairs`), and what a spec's `regex` finds. Only a string with `://` in it is an address; anything else comes back
# as it was.
#
# A run up to an `@`, tried only where a run can begin — the start, or after a `/` or an `@` (the eleventh review's
# sweep): unanchored, `[^/@]*@` was tried from every position of a run with no `@` in it, and a value of 100 000
# characters held a console's thread for minutes. The same matches; one scan of the string.
#
# …AND NOT ACROSS A QUERY'S PAIRS (the product's r28-secrets2): `x://10.0.0.5:554/s?x=y@b` was said
# `x://10.0.0.5:***/…@b` — the run from the path's segment took `s?x=y`, and the `@` made the port a secret. A run
# begins after a `/`, an `@`, a `&`, a `;` or an `=` and ends at the next of them: `?x=…@b`. It may cross a `?` (a
# secret with a `/` and a `?` in it, `KEY:12/3?4@host`). Only at an address's authority — right after its `://` — does
# it run across all of them, as a userinfo with `=` or `&` in its password does (`_AUTHORITY_LOGIN`).
USERINFO = re.compile(r"(?<![^/@&;=])[^/@&;=]*@")
_AUTHORITY_LOGIN = re.compile(r"(?<=://)[^/@]*@")


def hide_logins(s: str) -> str:
    """Whatever stands before an `@` in `s`, as `…`."""
    return USERINFO.sub("…@", _AUTHORITY_LOGIN.sub("…@", s))


# WHERE AN ADDRESS NAMES ITS HOST: its authority. A host a subsystem's addresses carry somewhere else — in the path —
# is that subsystem's spelling (`secret_in: {regex: …, in: path}`).
def _host(s: str) -> tuple[int, int]:
    lo = s.find("://") + 3
    return lo, min([j for j in (s.find(c, lo) for c in "/?#") if j >= 0] or [len(s)])


# The span of a host's port when it is no port: not digits — or digits followed, past the host, by an `@`
# (`s3://KEY:12/34…@host`: the `/` cut a secret that begins with digits, and its head stood where a port does).
def _port_span(s: str, lo: int, hi: int) -> tuple[int, int] | None:
    host = s[lo:hi]
    colon = host.rfind(":")
    if colon < 0 or (host.startswith("[") and colon < host.find("]")):
        return None
    port = host[colon + 1:]
    return (lo + colon + 1, hi) if port and (not port.isdigit() or _login_after(s, hi)) else None


# …an `@` of THIS address's: before any pair and any address inside it (the product's r28-secrets2). A relay's
# `http://h:1984/api/s?src=x://admin:…@h2` was said `h:***`: the `@` of the address in its `src` made the relay's own
# port a secret.
def _login_after(s: str, i: int) -> bool:
    at = s.find("@", i)
    return at >= 0 and not any(0 <= s.find(mark, i, at) for mark in ("=", "&", ";", "://"))


# AN ADDRESS INSIDE AN ADDRESS (the thirteenth review, blocker 6). A relay is told what to fetch in a parameter, and an
# address escaped into it had its `@`, `:` and `?` out of the outer address's sight: the password was in the row, the
# page and the snapshot. So the value of a pair the spec names (`secret_in: {nested: …}`), and a path segment that is
# an address once unescaped, are an address like any other: refused for what the outer one would be refused for, and
# hidden whole where a stored one is said. Read to `_NESTED` levels deep — and an address nested deeper is refused for
# that alone: what is not read is not known to be clean. `(name, start, end, inner)`: the value's span in `s`, and the
# address it holds.
_NESTED = 3


# …and one whose `//` stands unescaped (`/proxy/x%3A//admin%3A…%40h2/s`, a probe beside the product's r28-secrets2):
# each segment alone is no address, the escaped `:` and the literal `//` together are. The rest of the path from that
# segment is the address. Each segment is unescaped once: one scan, whatever the path's length.
def _nested(s: str, rules: SecretRules) -> list[tuple[str, int, int, str]]:
    out = []
    at = s.find("://")
    q = s.find("?", at + 3)
    end = len(s) if q < 0 else q
    segs = [(a, b, _unquoted(s[a:b]) if "%" in s[a:b] else s[a:b]) for a, b in _split(s, at + 3, end, "/")]
    for a, b, u in segs:
        if "%" in s[a:b] and "://" in u:
            out.append(("a path segment", a, b, u))
        elif "%" in s[a:b] and b < end and "://" in u[-3:] + _unquoted(s[b:min(end, b + 9)]):
            out.append(("a path segment", a, end, _unquoted(s[a:end])))
            break
    if rules.nested:
        for name, a, b in _pairs(s):
            inner = _WRAPPED.sub("", _unquoted(s[a:b]))
            if "://" in inner and "".join(_name_words(name)) in rules.nested:
                out.append((name, a, b, inner))
    return out


# …and one a relay is told to fetch through something it runs (`ffmpeg:https://…`): the `<scheme>:` before the address's
# own `scheme://` is the relay's word, and the address is what follows it.
_WRAPPED = re.compile(r"^(?:[A-Za-z][A-Za-z0-9+.\-]*:(?!//))+(?=[A-Za-z][A-Za-z0-9+.\-]*://)")


def hide_in_url(value, rules: SecretRules | None = None, _depth: int = 0):
    if not isinstance(value, str):
        return value
    if "://" not in value:
        return SECRET_MASK if _escaped_whole(value) and address_refusal(value, rules, _depth) else value
    rules = _rules(rules)
    s = hide_logins(value)
    # a pair's value — and, for a name that hides a pair (`pass%3D…=1`), the name with it
    spans = [(a - 1 - len(name) if _HIDDEN_PAIR.search(_unquoted(name)) else a, b) for name, a, b in _pairs(s)
             if b > a and (is_credential_param(name, rules) or _hides(s[a:b], rules))]
    spans += [(a, b) for kind, a, b, _ in _found(s, rules) if kind == "secret"]    # a login is said as written
    lo, hi = _host(s)
    port = _port_span(s, lo, hi)
    if port is not None:
        spans.append(port)
    if "@" not in s[lo:hi] and "@" in _unquoted(s[lo:hi]):   # an escaped `@`: a login before it, maybe a password
        spans.append((lo, hi))                                  # (a plain one is `…@` already: USERINFO)
    spans += [(a, b) for _, a, b, inner in _nested(s, rules) if address_refusal(inner, rules, _depth + 1)]
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
# keeps (`SubsystemSpec.refuse`, by the field's own `secret_in`), and the doors that are not a spec's field (a
# subsystem's table of its own, the domain's edit it keeps and relays: by the rules of every loaded spec). An address
# is a string with `://` in it, and it may not carry:
# - a login — a userinfo, or an `@` anywhere after the `://` (`s3://KEY:SEC/RET@host`: a secret with a `/` in it put the
#   `@` in the path, past a check that looked before the first `/`; the twelfth review, blocker 10), or an escaped one
#   in its host. A file's name is a name, `@` and all;
# - a host or port that cannot be read — `KEY:SECRET` with no `@` at all, a password whose `/`, `?` or `#` cut the
#   host short;
# - a credential pair (`credential_params`), or a login or password a spec's `regex` finds;
# - an address inside it that may not be stored (`_nested`).
# The words name the parameter, never a value: `urlsplit`'s own ("Port could not be cast to integer value as
# 'Hunter2'") quote the password, and they went into the reply, the journal and the idempotency copy (major 16).
NOT_AN_ADDRESS = ("its host or port cannot be read — a password with an unescaped '/', '?' or '#' in it reads that way; "
                  "the login goes in its own field")


# AN ADDRESS ESCAPED WHOLE (the product's r28-secrets2, the domain's door): `["x%3A%2F%2Fadmin%3A…%40h2"]` has no
# `://` to see, and was no address — taken, kept, handed on to whoever unescapes it. A value that is an
# address once unescaped is that address: refused for what it would be refused for, and said masked whole.
def _escaped_whole(s: str) -> bool:
    return "%" in s and "://" in _unquoted(s)


def address_refusal(value, rules: SecretRules | None = None, _depth: int = 0) -> str | None:
    got = address_fault(value, rules, _depth)
    return got[0] if got else None


# …and what it carries, `{"login"}`, `{"secret"}` or both — a refusal names the field the spec gives each
# (`credentials`): a password goes in the secret's, a login with no password in the login's. What cannot be read — a
# host whose port is no number, an address nested deeper than is read — is said to carry a password: the field that
# keeps one sealed is where whatever hides there belongs.
_SECRET, _LOGIN, _BOTH = frozenset({"secret"}), frozenset({"login"}), frozenset({"login", "secret"})


def address_fault(value, rules: SecretRules | None = None, _depth: int = 0) -> tuple[str, frozenset] | None:
    from urllib.parse import urlsplit
    s = str(value)
    rules = _rules(rules)
    if "://" not in s:
        if not _escaped_whole(s):
            return None
        got = address_fault(_unquoted(s), rules, _depth + 1)
        return (f"it is an address escaped whole that may not be stored: {got[0]}", got[1]) if got else None
    if _depth > _NESTED:
        return f"it nests addresses more than {_NESTED} deep, and what is not read is not known to carry no login", _SECRET
    try:
        u = urlsplit(s)
        u.port
    except ValueError:                                   # a port that is no number among them: `urlsplit` reads it
        return f"it is not an address: {NOT_AN_ADDRESS}", _SECRET
    a_file = u.scheme.lower() == "file" or u.netloc.lower() == "file"
    lo, hi = _host(s)
    if u.username or u.password or (not a_file and ("@" in s.split("://", 1)[1] or "@" in _unquoted(s[lo:hi]))):
        # …and a password elsewhere in it — where a port goes, by the spec's regex — is a password to the refusal too
        # (`acme/admin@10.0.0.5:…/ch/1`: a login, and the password where its host's port stands)
        found = () if a_file else _found(s, rules)
        both = _password_before_at(s, u) or any(k == "secret" for k, _, _, _ in found)
        return "it carries a login (what stands before an '@')", (_BOTH if both else _LOGIN)
    # …what its pairs and the spec's regexes find, said together: a login in a pair and a password the chain beside it
    # spells (`/user=admin_password=…`) is a password to the refusal, whichever was read first.
    creds, logins = credential_params(s, rules), login_params(s, rules)
    said = ([f"a credential in its parameters ({', '.join(dict.fromkeys(creds))})"] if creds else []) + \
           ([f"a login in its parameters ({', '.join(dict.fromkeys(logins))})"] if logins else [])
    kinds = ({"secret"} if creds else set()) | ({"login"} if logins else set())
    found = [] if a_file else _found(s, rules)
    if found:
        parts = _parts(s)
        where = sorted({next(f"its {'host' if p == 'authority' else p}" for p, (a0, b0) in parts.items() if a0 <= a <= b0)
                        for _, a, _, _ in found})
        what = sorted({k for k, _, _, _ in found}, key=("login", "secret").index)
        names = [n for _, _, _, n in found if n]
        named = f" ({', '.join(dict.fromkeys(names))})" if names else ""
        said.append(f"{' and '.join('a login' if k == 'login' else 'a password' for k in what)} in "
                    f"{' and '.join(where)}{named}")
        kinds |= set(what)
    if said:
        return f"it carries {' and '.join(said)}", frozenset(kinds)
    for name, _, _, inner in ([] if a_file else _nested(s, rules)):
        got = address_fault(inner, rules, _depth + 1)
        if got:
            return (f"it holds an address in {name if name == 'a path segment' else repr(name)} that may not be "
                    f"stored: {got[0]}", got[1])
    return None


# A password before the `@`: the userinfo's, or a `:` in what stands between the address's last `://` and its `@`
# (`s3://https://KEY:SEC/RET@host` — the bucket's address inside the volume's).
def _password_before_at(s: str, u) -> bool:
    if u.password is not None:
        return True
    at = s.find("@", s.find("://") + 3)
    if at < 0:
        lo, hi = _host(s)
        head = _unquoted(s[lo:hi])
        return ":" in head[:head.rfind("@")] if "@" in head else False
    return ":" in _unquoted(s[s.rfind("://", 0, at) + 3:at])


# …and one inside a list or an object (the thirteenth review, minor): the domain's door asked only a value that is a
# string, and a list holding an address with a login was 202, kept, and applied. `(where, why)` for the first address
# that may not be stored — `where` its place, `source[0]`, `extra.url` —, None when there is none. Past `depth` the
# structure itself is refused: what is not read is not known to be clean.
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
