"""The domain's roles in a cluster's rights file (`storemachine.Rights`, `w2cplatform/rights.py`), from the specs.

    domain        the signer on the HOLDER's store — the one process with the domain's keys, and the holder's whole pass:
                  every row of the domain and the people (`identity/*`); reads the cluster's units too, for its own copy
    domainconsole the domain's console on the holder's store (ADR-0032): no key — `domain/signer*` neither read nor
                  written, no people — and the records a person decides there with no key: admitting a member, the
                  topology, the grants, an edit kept again; it reads the rest of the domain, and the units
    domainagent   the agent, in EVERY cluster's store (the holder's included): the rows it carries home and its own key,
                  and nothing a holder alone writes — the signer's keys, the people, the list of members, the per-member
                  rows the holder keeps for the others, a subsystem's books for the others and its kept rows — DENIED by
                  name, so a grant on `domain/*` cannot reach them (the product's r23-domain note: careful with what the
                  agent writes on a member — its own copies of `domain/keys`, `root`, `grants`, `pending`, `backup`, the
                  books carried home, its `member-key`; deny only what it writes nowhere). It reads what it writes, and
                  never the signer's row
    <sub>domain   a subsystem's worker on the domain, on the holder (`domain.books` of its spec): its own prefix
                  `domain/<sub>/*`; reads what its books are made of — the key set, the topology, the members, the
                  shared settings' pointer, the units of every subsystem and the platform's rows — and, when its spec
                  keeps a family of subjects (`domain.names`), the people and the grants, which the platform asks on
                  each of its writes

There is no `member` role any more: a member reads NOTHING of the holder's store; what it carries comes through the
domain's door (`carry.py`).
"""
from __future__ import annotations

from . import declared

# The domain's keys (`domain/signer`, the token key and the issuing key): the signer's alone.
SIGNER_KEYS = "!domain/signer*"
# What the domain's console writes (ADR-0032): the list of members, the topology, the grants of every cluster and the
# domain's own, the edits kept for members that are off — none sealed, none signed.
CONSOLE_WRITES = ("domain/members", "domain/topology", "domain/grants/*", "domain/pending/*")


# THE TOKENS SOCKET HAS A GROUP OF ITS OWN (ADR-0031). The signer's socket for a subsystem's books (`tokendoor.py`) was
# the worker's store role's group, `<deployment>-<sub>domain` — and a role group has whoever opens that store socket for
# members, configstore among them: who could ask the domain's key for a token hung on the purity of another file. Its
# own group, by the platform's rule — written by hand nowhere — with ONE member, the subsystem's domain worker.
def tokens_group(sub: str, deployment: str) -> str:
    """The group of the signer's tokens socket for `sub`'s domain worker: `<deployment>-<sub>domaintokens`."""
    return f"{deployment}-{sub}domaintokens"


def agent_denials(specs=None) -> list[str]:
    """What only the holder writes, by name: the agent may hold `domain/*` and none of these."""
    out = [SIGNER_KEYS, "!domain/members", "!domain/placement*", "!domain/licence", "!domain/stranded",
           "!domain/grants/*", "!domain/pending/*", "!domain/backup/*", "!domain/break_glass/*", "!domain/ldevid/*"]
    for s in _on_domain(specs):
        out += [f"!{s.domain_prefix}{b}/*" for b in s.domain.books]       # the books the holder keeps for each member
        # what a subsystem keeps for the domain: a row, or every row of a family (`kept: [x/]`)
        out += [f"!{s.domain_prefix}{k}{'*' if k.endswith('/') else ''}" for k in s.domain.kept]
        if s.domain.books or s.domain.kept:
            out += [f"!{s.domain_prefix}worker", f"!{s.domain_prefix}heartbeat"]   # its worker's slot on the holder
    return out


def _on_domain(specs) -> list:
    return declared.specs() if specs is None else [s for s in specs if s.domain is not None]


def roles(group=lambda r: f"w2c-{r}", schema: str = "platform/schema", specs=None) -> dict[str, dict]:
    """`{role: {group, read, write, delete}}` for the domain's roles, to stand beside the cluster's in its rights file.
    `specs`: the specs the file is generated for (default: the ones this process loaded)."""
    def role(name: str, write: list[str], read: list[str], delete: list[str] | None = None) -> dict:
        write = list(dict.fromkeys(write))
        return {"group": group(name), "read": list(dict.fromkeys(read)), "write": write,
                "delete": list(dict.fromkeys(write if delete is None else delete))}
    on = _on_domain(specs)
    units = list(dict.fromkeys([f"{s.name}/*" for s in (specs if specs is not None else declared.specs())]))
    agent = ["domain/*", *agent_denials(specs)]
    out = {
        "domain": role("domain", ["domain/*", "identity/*"], [schema, "domain/*", "identity/*", "platform/*", *units]),
        # The domain's console: the keys are not its to read, and the people's rows are opened where the ring is — the
        # signer's; what it writes is plain and a person's (`console.Console`).
        "domainconsole": role("domainconsole", list(CONSOLE_WRITES),
                              [schema, "domain/*", SIGNER_KEYS, "platform/*", *units]),
        # It reads what it carries, on a member, and on the holder what the holder's own agent reads through `answer` —
        # the holder's rows for every member included; never the signer's.
        "domainagent": role("domainagent", agent, [schema, "domain/*", SIGNER_KEYS]),
    }
    for s in on:
        if not (s.domain.books or s.domain.kept):
            continue
        # …and, with a family of subjects (`domain.names`), the people and the grants the platform asks on its writes
        apart = [x for r in s.domain.names.values() for x in (f"{declared.PEOPLE[r['exclusive_with']]}*",
                                                               f"{declared.GRANTS_PREFIX}*")]
        out[f"{s.name}domain"] = role(f"{s.name}domain", [f"{s.domain_prefix}*"],
                                      [schema, f"{s.domain_prefix}*", "domain/keys", "domain/topology", "domain/members",
                                       "domain/shared", "platform/*", *units, *apart])
    return out
