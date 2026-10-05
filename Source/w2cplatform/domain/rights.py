"""The domain's roles in a cluster's rights file (`storemachine.Rights`, `w2cplatform/rights.py`), from the specs.

    domain        the domain's own processes on the HOLDER's store — the signer and its doors, the domain's console: every
                  row of the domain and the people (`identity/*`); reads the cluster's units too, for its own copy
    domainagent   the agent, in EVERY cluster's store (the holder's included): the rows it carries home and its own key,
                  and nothing a holder alone writes — the signer's keys, the people, the list of members, the per-member
                  rows the holder keeps for the others, a subsystem's books for the others and its kept rows — DENIED by
                  name, so a grant on `domain/*` cannot reach them (the product's r23-domain note: careful with what the
                  agent writes on a member — its own copies of `domain/keys`, `root`, `grants`, `pending`, `backup`, the
                  books carried home, its `member-key`; deny only what it writes nowhere). It reads what it writes, and
                  never the signer's row
    <sub>domain   a subsystem's worker on the domain, on the holder (`domain.books` of its spec): its own prefix
                  `domain/<sub>/*`; reads what its books are made of — the key set, the topology, the members, the
                  shared settings' pointer, the units of every subsystem and the platform's rows

There is no `member` role any more: a member reads NOTHING of the holder's store; what it carries comes through the
domain's door (`carry.py`).
"""
from __future__ import annotations

from . import declared


def agent_denials(specs=None) -> list[str]:
    """What only the holder writes, by name: the agent may hold `domain/*` and none of these."""
    out = ["!domain/signer*", "!domain/members", "!domain/placement*", "!domain/licence", "!domain/stranded",
           "!domain/grants/*", "!domain/pending/*", "!domain/backup/*", "!domain/break_glass/*", "!domain/ldevid/*"]
    for s in _on_domain(specs):
        out += [f"!{s.domain_prefix}{b}/*" for b in s.domain.books]       # the books the holder keeps for each member
        out += [f"!{s.domain_prefix}{k}" for k in s.domain.kept]          # what a subsystem keeps for the domain
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
        # It reads what it carries, on a member, and on the holder what the holder's own agent reads through `answer` —
        # the holder's rows for every member included; never the signer's.
        "domainagent": role("domainagent", agent, [schema, "domain/*", "!domain/signer*"]),
    }
    for s in on:
        if not (s.domain.books or s.domain.kept):
            continue
        out[f"{s.name}domain"] = role(f"{s.name}domain", [f"{s.domain_prefix}*"],
                                      [schema, f"{s.domain_prefix}*", "domain/keys", "domain/topology", "domain/members",
                                       "domain/shared", "platform/*", *units])
    return out
