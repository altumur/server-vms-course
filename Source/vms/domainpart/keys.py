"""Secret opening helpers for the remaining VMS domain console diagnostics."""
from __future__ import annotations

import os

from vms.config import SPEC


def _book(name: str) -> str:
    if name not in SPEC.domain.books:
        raise ValueError(f"cam.subsystem.yaml declares no book {name!r} (domain.books: {list(SPEC.domain.books)})")
    return SPEC.domain_prefix + name


# THE TOKENS IN THE BOOKS ARE SECRETS AT REST (DOMAIN-PLATFORM.md, «Course check of domain secrets»: a day's bearer
# token to push, poll or ask lay in the clear in every book, in the holder's store and on every member). An entry names
# its token `token_secret`, so the platform seals it wherever the row lies — at the holder under its ring when this
# package's worker writes the book, on the way to a member sealed to the member's key, at the member under the member's
# ring (`w2cplatform.domain.carry.seal_row`). What reads a book opens it with its process's ring (`opened`).
TOKEN = "token_secret"


def ring():
    """This process's key ring (`SECRETS_KEY`), or None."""
    from w2cplatform.sealing import Sealer
    path = os.environ.get("SECRETS_KEY", "")
    if path not in _RINGS:
        _RINGS[path] = Sealer.from_file(path) if path else None
    return _RINGS[path]


_RINGS: dict = {}


def opened(items, path: str, sealer=None):
    """The items of a book row with their secrets opened by `sealer` (or this process's ring)."""
    if not items:
        return items
    from w2cplatform.domain.carry import open_row
    return open_row(sealer if sealer is not None else ring(), items, path)


class OpenedVars:
    """A store as the books' writer and readers see it: a row read is opened, a row written is sealed — and a row is
    written only when what it SAYS changed (a seal is new each time)."""

    def __init__(self, inner, sealer=None):
        self.inner, self.sealer = inner, sealer if sealer is not None else ring()

    def get(self, path):
        items, idx = self.inner.get(path)
        return opened(items, path, self.sealer), idx

    def put(self, path, items, cas=None):
        from w2cplatform.domain.carry import seal_row
        return self.inner.put(path, seal_row(self.sealer, items, path), cas=cas)

    def list(self, prefix):
        return self.inner.list(prefix)

    def delete(self, path, cas=None):
        return self.inner.delete(path, cas=cas)

    def __getattr__(self, name):
        return getattr(self.inner, name)
