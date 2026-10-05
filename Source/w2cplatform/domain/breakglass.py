"""The emergency account of a cluster: its hash set and rotated at the holder, carried home sealed.

Lesson 4's honest residue — one local account per cluster, for when the domain is away, which is the only time it is
for. Its password's HASH (scrypt, `identity._hash`) is set at the holder (`domain/break_glass/<cluster>`, field
`pwhash_secret`: sealed under the holder's ring at rest), carried home by that cluster's agent through the domain's door
— sealed to the member's key on the way, sealed with the member's ring at home — and checked by the cluster's console
(`access.ClusterAccess.glass`). Every use is an alarm; the domain rotates the password when it sees one. The course had
no writer of it but a test (DOMAIN-PLATFORM.md, «Course check of domain secrets»); now there are two:

    python3 -m w2cplatform.domain.breakglass <cluster>        on the holder (PLATFORM_STORE, SECRETS_KEY): the password
                                                               read from stdin, its hash written, the change journalled
    PUT /domain/break-glass/<cluster> {"password"}               the domain's door, for an admin of the domain
"""
from __future__ import annotations

import time

from .agent import BREAK_GLASS_PATH


def set_password(holder_vars, cluster: str, password: str, now: float, sealer=None, journal=None, by: str | None = None) -> None:
    """Hash `password` and keep the hash for `cluster`, sealed under the holder's ring; never the password."""
    from .carry import seal_row
    from .identity import _hash
    if not password:
        raise ValueError("an emergency password is not empty")
    path = f"{BREAK_GLASS_PATH}/{cluster}"
    _, idx = holder_vars.get(path)
    holder_vars.put(path, seal_row(sealer, {"pwhash_secret": _hash(password), "set_at": str(now)}, path), cas=idx)
    if journal is not None:
        journal.say("domain.break_glass.set", user=by or "?", target=cluster)   # that it was set — never what to


def main(argv: list[str]) -> int:
    import getpass
    import os
    import sys

    from w2cplatform.sealing import Sealer
    from w2cplatform.variables import open_vars
    if len(argv) != 1:
        print("usage: python3 -m w2cplatform.domain.breakglass <cluster>   (the password on stdin)", file=sys.stderr)
        return 2
    password = getpass.getpass("emergency password: ") if sys.stdin.isatty() else sys.stdin.readline().rstrip("\n")
    set_password(open_vars(os.environ["PLATFORM_STORE"]), argv[0], password, time.time(), Sealer.from_env(os.environ))
    print(f"{argv[0]}: emergency password set — its agent carries the hash home on its next pass")
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv[1:]))
