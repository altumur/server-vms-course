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
# clear when it has none, with a warning said once; the store's ACL is about writers — anyone who may READ
# `<sub>/<rows>/*` reads every row, sealed or not. On one box that is the
# file under `PLATFORM_DIR`; on a cluster it is raft, encrypted at rest, with a policy per job. Narrowing
# the readers is a change to the Variables contract, not to this file, and it has not been made.
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
#   is said.
# - `address_refusal(value, rules)` — why an address may not be stored, in words that never repeat it, an address
#   inside one too; `NOT_AN_ADDRESS` — the words for one `urlsplit` cannot read; `refusal_within(value)` — the same
#   asked of every string inside a list or an object.
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


# HOW AN ADDRESS CARRIES A LOGIN, AS A SPEC SAYS IT (`fields.<url field>.secret_in`; the boundary's step 4, the kinds
# agreed with the product). The forms a credential takes in the addresses of what a subsystem opens are the
# subsystem's knowledge — the names what it opens gives a password parameter, a login chained into a path — and were a
# list in this file. Three kinds, each a list entry of its own:
#
#   {param: [names]}                     a pair `name=value` whose NAME is one of these carries a credential, read as
#                                        WORDS (split at `_`, `-`, `.` and where the case turns, `%`-escapes undone, a
#                                        full-width letter its letter): `pwd` — the words joined, or the last word (an
#                                        `id` aside), is it; `pwd*` — a word begins with it; `*pwd` — the last word ends
#                                        with it
#   {regex: '…(?P<login>…)…(?P<secret>…)…', in: path|query}
#                                        a spelling of a login that is no pair: what the groups match is the login and
#                                        the password, refused and hidden where they stand
#   {nested: name | [names]}             the value of a pair of this name is read as an address once unescaped, by the
#                                        same rules, three levels deep (`_NESTED`)
#
# BY WORD, NOT BY SUBSTRING (the thirteenth review, minor): a word that only BEGINS a name (`token` of `token_bucket`,
# `auth` of `authmode`) names what the parameter is about, not what it holds — which is why a name is matched whole,
# or as its last word, unless the spec says `x*` or `*x`.
_ENTRY = re.compile(r"\*?[a-z0-9]+\*?")


@dataclass(frozen=True)
class SecretRules:
    names: frozenset = frozenset()       # `pwd`: the words joined, or the last word, is one of these
    begins: tuple = ()                   # `pwd*`: a word begins with one of these
    ends: tuple = ()                     # `*pwd`: the last word ends with one of these
    patterns: tuple = ()                 # `((compiled, "path" | "query"), …)`
    nested: frozenset = frozenset()      # pair names whose value is an address

    def __or__(self, other: "SecretRules") -> "SecretRules":
        return SecretRules(self.names | other.names, tuple(dict.fromkeys(self.begins + other.begins)),
                           tuple(dict.fromkeys(self.ends + other.ends)),
                           tuple(dict.fromkeys(self.patterns + other.patterns)), self.nested | other.nested)

    # `secret_in` as a spec writes it, read and checked: anything else is refused at load, in words.
    @classmethod
    def parse(cls, secret_in, where: str) -> "SecretRules":
        if not isinstance(secret_in, list):
            raise ValueError(f"{where}: `secret_in` is a list of {{param: […]}}, {{regex: …, in: path|query}}, "
                             f"{{nested: …}}, not {secret_in!r}")
        names, begins, ends, patterns, nested = set(), [], [], [], set()
        for entry in secret_in:
            if not isinstance(entry, dict) or not entry or len(set(entry) - {"in"}) != 1:
                raise ValueError(f"{where}: an entry of `secret_in` is one of {{param: […]}}, {{regex: …, in: "
                                 f"path|query}}, {{nested: …}}, not {entry!r}")
            if "param" in entry:
                if set(entry) != {"param"} or not isinstance(entry["param"], list) or not entry["param"]:
                    raise ValueError(f"{where}: `param` is a list of names, not {entry!r}")
                for n in entry["param"]:
                    n = str(n).lower()
                    if not _ENTRY.fullmatch(n) or (n.startswith("*") and n.endswith("*")):
                        raise ValueError(f"{where}: {n!r} in `param` is a name, `name*` or `*name` — letters and digits")
                    if n.endswith("*"):
                        begins.append(n[:-1])
                    elif n.startswith("*"):
                        ends.append(n[1:])
                    else:
                        names.add(n)
            elif "regex" in entry:
                if entry.get("in") not in ("path", "query"):
                    raise ValueError(f"{where}: a `regex` says where it reads: `in: path` or `in: query`, not "
                                     f"{entry.get('in')!r}")
                try:
                    rx = re.compile(str(entry["regex"]))
                except re.error as e:
                    raise ValueError(f"{where}: `regex` {entry['regex']!r} is no regular expression: {e}") from None
                if not {"login", "secret"} & set(rx.groupindex):
                    raise ValueError(f"{where}: `regex` {entry['regex']!r} names what it finds — a group "
                                     f"`(?P<login>…)` or `(?P<secret>…)`")
                patterns.append((rx, entry["in"]))
            elif "nested" in entry:
                got = entry["nested"]
                got = [got] if isinstance(got, str) else got
                if set(entry) != {"nested"} or not isinstance(got, list) or not got or \
                        not all(isinstance(n, str) and n for n in got):
                    raise ValueError(f"{where}: `nested` names the pair (or pairs) holding an address, not {entry!r}")
                nested |= {n.lower() for n in got}
            else:
                raise ValueError(f"{where}: an entry of `secret_in` is param, regex or nested, not {entry!r}")
        return cls(frozenset(names), tuple(begins), tuple(ends), tuple(patterns), frozenset(nested))


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


def is_credential_param(name: str, rules: SecretRules | None = None) -> bool:
    rules = _rules(rules)
    words = _name_words(name)
    if not words:
        return False
    bare = "".join(words)
    tail = words[:-1] if len(words) > 1 and words[-1] == "id" else words
    return (bare in rules.names or tail[-1] in rules.names or tail[-1].endswith(rules.ends)
            or any(w.startswith(rules.begins) for w in words))


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


def _bounds(s: str) -> tuple[int, int, int]:
    """`(start of the path, the `?` or the end, the end)` of an address."""
    at = s.find("://")
    lo = at + 3
    q = s.find("?", lo)
    q = len(s) if q < 0 else q
    slash = s.find("/", lo, q)
    return (q if slash < 0 else slash), q, len(s)


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


# What a spec's `regex` finds: `(kind, start, end)` of every login and password it matches, in the part it reads.
@functools.lru_cache(maxsize=32)
def _found(s: str, rules: SecretRules) -> tuple[tuple[str, int, int], ...]:
    if not rules.patterns or "://" not in s:
        return ()
    path, q, end = _bounds(s)
    out = []
    for rx, part in rules.patterns:
        lo, hi = (path, q) if part == "path" else (q + 1, end)
        if lo >= hi:
            continue
        for m in rx.finditer(s[lo:hi]):                 # the part alone: `^` and `$` are its ends
            for g in ("login", "secret"):
                if g in rx.groupindex and m.group(g):
                    out.append((g, lo + m.start(g), lo + m.end(g)))
    return tuple(out)


def credential_params(url: str, rules: SecretRules | None = None) -> list[str]:
    """The names of the parameters of `url` that carry a credential, as written."""
    rules = _rules(rules)
    return [name for name, _, _ in _pairs(str(url)) if is_credential_param(name, rules)]


# …and a stored one is never said (a row kept from before the refusal; one another build wrote): whatever stands before
# an `@` — a userinfo, or one in a path —, a port that is no number (`admin:Hunter2%40h`: a password before an escaped
# `@`, or an unescaped `/`, `?`, `#` in it — the twelfth review, major 16), the value of every credential pair
# (`_pairs`), and what a spec's `regex` finds. Only a string with `://` in it is an address; anything else comes back
# as it was.
#
# A run up to an `@`, tried only where a run can begin — the start, or after a `/` or an `@` (the eleventh review's
# sweep): unanchored, `[^/@]*@` was tried from every position of a run with no `@` in it, and a value of 100 000
# characters held a console's thread for minutes. The same matches; one scan of the string.
USERINFO = re.compile(r"(?<![^/@])[^/@]*@")


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
    return (lo + colon + 1, hi) if port and (not port.isdigit() or "@" in s[hi:]) else None


# AN ADDRESS INSIDE AN ADDRESS (the thirteenth review, blocker 6). A relay is told what to fetch in a parameter, and an
# address escaped into it had its `@`, `:` and `?` out of the outer address's sight: the password was in the row, the
# page and the snapshot. So the value of a pair the spec names (`secret_in: {nested: …}`), and a path segment that is
# an address once unescaped, are an address like any other: refused for what the outer one would be refused for, and
# hidden whole where a stored one is said. Read to `_NESTED` levels deep — and an address nested deeper is refused for
# that alone: what is not read is not known to be clean. `(name, start, end, inner)`: the value's span in `s`, and the
# address it holds.
_NESTED = 3


def _nested(s: str, rules: SecretRules) -> list[tuple[str, int, int, str]]:
    out = []
    at = s.find("://")
    q = s.find("?", at + 3)
    for a, b in _split(s, at + 3, len(s) if q < 0 else q, "/"):
        if "%" in s[a:b] and "://" in _unquoted(s[a:b]):
            out.append(("a path segment", a, b, _unquoted(s[a:b])))
    if rules.nested:
        for name, a, b in _pairs(s):
            inner = _unquoted(s[a:b])
            if "://" in inner and "".join(_name_words(name)) in rules.nested:
                out.append((name, a, b, inner))
    return out


def hide_in_url(value, rules: SecretRules | None = None, _depth: int = 0):
    if not isinstance(value, str) or "://" not in value:
        return value
    rules = _rules(rules)
    s = USERINFO.sub("…@", value)
    spans = [(a, b) for name, a, b in _pairs(s) if b > a and is_credential_param(name, rules)]
    spans += [(a, b) for _, a, b in _found(s, rules)]
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


def address_refusal(value, rules: SecretRules | None = None, _depth: int = 0) -> str | None:
    from urllib.parse import urlsplit
    s = str(value)
    if "://" not in s:
        return None
    rules = _rules(rules)
    if _depth > _NESTED:
        return f"it nests addresses more than {_NESTED} deep, and what is not read is not known to carry no login"
    try:
        u = urlsplit(s)
        u.port
    except ValueError:                                   # a port that is no number among them: `urlsplit` reads it
        return f"it is not an address: {NOT_AN_ADDRESS}"
    a_file = u.scheme.lower() == "file" or u.netloc.lower() == "file"
    lo, hi = _host(s)
    if u.username or u.password or (not a_file and ("@" in s.split("://", 1)[1] or "@" in _unquoted(s[lo:hi]))):
        return "it carries a login (what stands before an '@')"
    creds = credential_params(s, rules)
    if creds:
        return f"it carries a credential in its parameters ({', '.join(dict.fromkeys(creds))})"
    found = [] if a_file else _found(s, rules)
    if found:
        path = _bounds(s)[1]
        where = sorted({"its query" if a > path else "its path" for _, a, _ in found})
        kinds = sorted({k for k, _, _ in found}, key=("login", "secret").index)
        return f"it carries {' and '.join('a login' if k == 'login' else 'a password' for k in kinds)} in {' and '.join(where)}"
    for name, _, _, inner in ([] if a_file else _nested(s, rules)):
        why = address_refusal(inner, rules, _depth + 1)
        if why:
            return f"it holds an address in {name if name == 'a path segment' else repr(name)} that may not be stored: {why}"
    return None


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
