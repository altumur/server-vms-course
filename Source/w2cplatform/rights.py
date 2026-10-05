"""Who may touch a key: ONE evaluator for every store of the platform.

A store answers "may this role (or writer) do this to this key" in two places, and they must answer alike:

    configstore     the daemon's rights file (`storemachine.Rights`), by the socket a process came through — a
                    cluster, and a box whose store is `configstore://`
    in-process      the ACL a handle carries (`FileVariables`, `MemVariables`, `ConfigstoreVariables` as a
                    writer, the tests' fake) — a box with `file://` or `memory://`, where no daemon stands between
                    a process and the rows, and the ACL is the only rule there is

A rule that holds in one and not the other holds nowhere: a deny the rights file has and a box's ACL ignores does
nothing on a single box (the product's r23-domain note: the domain's agent may not write the signer's key — on a
box with `file://` it could, until the two shared this).

A pattern is a key, or a prefix with one trailing `*`; with a leading `!` it DENIES what it names. Denials are asked
first, wherever they stand in the list: `["domain/*", "!domain/signer*"]` is every row of the domain but the signer's.
"""
# ================================================================================================
# NOTES — what every part of this file does and why (kept beside the code, not in a separate document)
# ================================================================================================
# # rights.py — the one evaluator of store rights
#
# - `hit(pattern, key)` — one pattern (no `!`) against one key: equal, or a prefix when the pattern ends in `*`.
# - `valid(pattern)` — what a rights file or an ACL may hold: a non-empty string, `*` only last, `!` only first.
# - `allowed(patterns, key)` — the question: any denial that hits says no; else any grant that hits says yes; else no.
# - `refusal(writer, acl, key, action)` — the in-process form: None when the handle may, else the words of a
#   `Forbidden`. No writer, or no ACL at all, is an unrestricted handle (a test's, the operator's own tool).
# - `DOMAIN_ROLES` — who may DELETE `domain/*` (the product's names): the domain's processes on its holder's store,
#   and its agent in a member's. Nobody else, `admin` included; a store that cannot name its writer refuses it for
#   everybody. One set for the rights file and the in-process ACL (it was a role set there and a writer string here).
# ================================================================================================
from __future__ import annotations

DOMAIN_ROLES = frozenset({"domain", "domainagent"})


def hit(pattern: str, key: str) -> bool:
    return key == pattern or (pattern.endswith("*") and key.startswith(pattern[:-1]))


def valid(p) -> bool:
    if not isinstance(p, str):
        return False
    body = p[1:] if p.startswith("!") else p
    return bool(body) and "!" not in body and "*" not in body[:-1]


def allowed(patterns, key: str) -> bool:
    pats = list(patterns or ())
    if any(hit(p[1:], key) for p in pats if p.startswith("!")):
        return False                          # a denial wins over every grant, wherever it stands in the list
    return any(hit(p, key) for p in pats if not p.startswith("!"))


def refusal(writer: str | None, acl: dict | None, key: str, action: str = "write") -> str | None:
    """Why the in-process handle `writer` may not `action` `key` under `acl` ({writer: [patterns]}); None if it may."""
    if writer is None or not acl:
        return None
    return None if allowed(acl.get(writer, []), key) else f"{writer} may not {action} {key}"
