"""The domain's roles in a cluster's rights file (`storemachine.Rights`, `w2cplatform/rights.py`), from the specs.

    domain        the signer on the HOLDER's store — the one process with the domain's keys, and the holder's whole pass:
                  every row of the domain, the people among them (`domain/users/*`), and the published set's pointer
                  (`identity/*`); reads the cluster's units too, for its own copy
    domainconsole the domain's console on the holder's store (ADR-0032): no key — `domain/signer*` neither read nor
                  written, no people — and the records a person decides there with no key: admitting a member, the
                  topology, the grants, an edit kept again; it reads the rest of the domain, and the units
    domainagent   the agent, in EVERY cluster's store (the holder's included): the rows it carries home and its own key,
                  and nothing a holder alone writes — the signer's keys, the people, the list of members, the per-member
                  rows the holder keeps for the others, a subsystem's books for the others and its kept rows — DENIED by
                  name, so a grant on `domain/*` cannot reach them (the product's r23-domain note: careful with what the
                  agent writes on a member — its own copies of `domain/keys`, `root`, `grants`, `pending`, `backup-taken`, the
                  books carried home, its emergency hash under its own name (`break-glass/<cluster>`, as the holder names
                  it), its `member-key`; deny only what it writes nowhere). It reads `*` less every secret
                  row it is not a reader of (`secret_reads`) — the signer's row among them
    <sub>domain   a subsystem's worker on the domain, on the holder (`domain.books` of its spec): its own prefix
                  `domain/<sub>/*`; reads what its books are made of — the key set, the topology, the members, the
                  shared settings' pointer, the units of every subsystem and the platform's rows — and, when its spec
                  keeps a family of subjects (`domain.names`), the grants, which the platform asks on each of its
                  writes (the people it lists, never reads: `domain/users/` is `domain`'s alone)

There is no `member` role any more: a member reads NOTHING of the holder's store; what it carries comes through the
domain's door (`carry.py`).
"""
from __future__ import annotations

from . import declared

# The domain's keys (`domain/signer`, the token key and the issuing key): the signer's alone.
SIGNER_KEYS = "!domain/signer*"
# What the domain's console writes (ADR-0032): the list of members, the topology, the grants of every cluster and the
# domain's own, the edits kept for members that are off — none sealed, none signed.
CONSOLE_WRITES = ("domain/members", "domain/topology", "domain/placement*", "domain/grants/*", "domain/pending/*")


# THE TOKENS SOCKET HAS A GROUP OF ITS OWN (ADR-0031). The signer's socket for a subsystem's books (`tokendoor.py`) was
# the worker's store role's group, `<deployment>-<sub>domain` — and a role group has whoever opens that store socket for
# members, configstore among them: who could ask the domain's key for a token hung on the purity of another file. Its
# own group, by the platform's rule — written by hand nowhere — with ONE member, the subsystem's domain worker.
def tokens_group(sub: str, deployment: str) -> str:
    """The group of the signer's tokens socket for `sub`'s domain worker: `<deployment>-<sub>domaintokens`."""
    return f"{deployment}-{sub}domaintokens"


def agent_denials(specs=None) -> list[str]:
    """What only the holder writes, by name: the agent may hold `domain/*` and none of these."""
    out = [SIGNER_KEYS, "!domain/book-seal*", "!domain/placement*", "!domain/names/*", "!domain/users/*", "!domain/members", "!domain/licence", "!domain/stranded",
           "!domain/grants/*", "!domain/pending/*", "!domain/outcomes/*", "!domain/keepers/*", "!domain/ldevid/*"]
    for s in _on_domain(specs):
        out += [f"!{s.domain_prefix}{b}/*" for b in s.domain.books]       # the books the holder keeps for each member
        # what a subsystem keeps for the domain: a row, or every row of a family (`kept: [x/]`)
        out += [f"!{s.domain_prefix}{k}{'*' if k.endswith('/') else ''}" for k in s.domain.kept]
        if s.domain.books or s.domain.kept:
            out += [f"!{s.domain_prefix}worker", f"!{s.domain_prefix}heartbeat"]   # its worker's slot on the holder
    return out


# WHO READS A SECRET ROW IS THE SHARED TABLE AND THE SPECS, AND NOBODY ELSE (ADR-0019, ADR-0010; «Архитектор» 2026-10-11 —
# and 2026-10-07 for the specs' rows, as the product's generator does): the platform's own rows from
# `secrets.PLATFORM_SECRET_READERS` (`tests/testdata/platform_lists.tsv`, the product's bytes), a spec's from its
# `secrets.readers` and `secrets.reads` (`secrets.secret_readers`). For each such row a role is either among its readers —
# and is given its declared pattern where its other grants do not reach it — or is not, and is denied that pattern.
# Only a name ending in `/` declares a prefix (`<prefix>*`); every other name is exact, without implied descendants.
# The emergency hash
# keeps its name on the member (`domain/break-glass/<cluster>`, ADR-0003): no bare path goes with its prefix any more.
# No hand list of secret rows stands in any role: a role's reads are what it needs, and this decides the secrets in them.
def secret_reads(role: str, readers: dict[str, set], read: list[str]) -> list[str]:
    """The patterns `role` gets for the secret rows `readers` names (`secrets.secret_readers`), beside its `read`: a
    grant where it is a reader and `read` does not reach the row, a denial where it is not and a grant of `read` reaches
    any row under it (a denial nothing reaches would deny nothing: the course's roles read by grants, not `*`)."""
    from w2cplatform.rights import allowed, hit

    def reaches(row: str) -> bool:
        grants = [p for p in read if not p.startswith("!")]
        if not row.endswith("/"):
            return any(hit(p, row) for p in grants)
        return any(p[:-1].startswith(row) or row.startswith(p[:-1]) if p.endswith("*") else p.startswith(row)
                   for p in grants)
    out = []
    for row, names in sorted(readers.items()):
        pattern = row + "*" if row.endswith("/") else row
        if role in names:
            covered = (any(p.endswith("*") and not p.startswith("!") and row.startswith(p[:-1]) for p in read)
                       if row.endswith("/") else allowed(read, row))
            out += [] if covered else [pattern]
        else:
            out += [f"!{pattern}"] if reaches(row) else []
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
    from w2cplatform.secrets import secret_readers
    on = _on_domain(specs)
    every = specs if specs is not None else declared.specs()
    readers = secret_readers(every)
    units = list(dict.fromkeys([f"{s.name}/*" for s in every]))

    def reads(name: str, read: list[str]) -> list[str]:
        return [*read, *secret_reads(name, readers, read)]
    agent = ["domain/*", *agent_denials(specs)]
    out = {
        "domain": role("domain", ["domain/*", "identity/*"], reads("domain", [schema, "domain/*", "identity/*", "platform/*",
                                                                            *units])),
        # The domain's console: the keys are not its to read, and the people's rows are opened where the ring is — the
        # signer's; what it writes is plain and a person's (`console.Console`).
        "domainconsole": role("domainconsole", list(CONSOLE_WRITES),
                              reads("domainconsole", [schema, "domain/*", SIGNER_KEYS, "platform/*", *units])),
        # It reads what it carries, on a member, and on the holder what the holder's own agent reads through `answer` —
        # the holder's rows for every member included — and what a member's report carries beyond `domain/`: the epochs
        # of every subsystem (`declared.epoch_prefixes`, `<sub>/epoch/*`), whatever the catalogue holds. So `*`, less every
        # secret row it is not a reader of — the signer's keys, the people, a spec's secrets, the people's ledgers — as
        # the product's `domainagent` reads (the three-site scenario, N3: with `domain/*` alone a member's agent fell on
        # `Forbidden` at a subsystem's epoch once a listing named every key, 2cd2947a).
        "domainagent": role("domainagent", agent, reads("domainagent", ["*"])),
    }
    for s in on:
        if not (s.domain.books or s.domain.kept):
            continue
        # …and, with a family of subjects (`domain.names`), the grants the platform asks on its writes; the people it
        # does not read (`domain/users/` is the role `domain`'s alone, the shared table): it lists their keys, as every
        # role lists every prefix (`declared._person`)
        apart = [f"{declared.GRANTS_PREFIX}*"] if s.domain.names else []
        if any(b + "/" in s.domain.names for b in s.domain.merged):
            apart.append(f"domain/names/{s.name}/*")
        write = [f"{s.domain_prefix}*", *[f"!{s.domain_prefix}{b}/*" for b in s.domain.merged]]
        out[f"{s.name}domain"] = role(f"{s.name}domain", write,
                                      reads(f"{s.name}domain", [schema, f"{s.domain_prefix}*", "domain/keys", "domain/topology",
                                                                "domain/members", "domain/shared", "platform/*", *units, *apart]))
    return out
