"""The holder's generic book pass, from admitted members' pinned reports.

Even the holder's own member contributes through its signed report. Lost reports
withdraw contributions; unknown ones during grace are missing. Each book is
replaced independently, and its declared names index is written last.
"""
from __future__ import annotations

import json

from . import bookmerge, booknames, booksecrets, declared
from .federation import Unreachable
from .members import Members
from .reports import pinned


def collect(holder, spec, book):
    with booknames.MUTATIONS:
        if holder.term is not None:
            holder.term.guard()
        return _collect(holder, spec, book)


def _collect(holder, spec, book):
    rule = spec.domain.merged[book]
    now = holder.wall()
    members = sorted(Members(holder.vars).read()["members"])
    grace = holder.view.lost_after if holder.view is not None else 45.0
    lost, observations, diagnostics = set(), {}, []
    for member in members:
        try:
            snap = pinned(member, holder.objects)
        except Unreachable:
            since = holder.view.cluster_down_since.get(member) if holder.view is not None else None
            if since is not None and now - since > grace:
                lost.add(member)
            observations[member] = None
            continue
        if now - snap.mark["received_at"] > grace:
            lost.add(member)
            continue
        source = {}
        try:
            for path, row in snap.document()["rows"].items():
                if path == rule.source or rule.source.endswith("/") and path.startswith(rule.source):
                    items = booksecrets.incoming(member, path, row["items"], holder.signer.book_key)
                    if holder.sealer is None:
                        def refuse(field, value):
                            raise booksecrets.Unavailable("the holder has no book result sealing ring")
                        for raw in items.values():
                            booksecrets._deep(json.loads(raw), refuse)
                    source[path] = items
        except booksecrets.Unavailable:
            source = None
            diagnostics.append((member, "", "", "invalid secret input"))
        observations[member] = source
    collected = bookmerge.collect(rule, observations, members, lost=lost)
    collected.diagnostics += tuple(diagnostics)
    for member, items in collected.rows.items():
        dest = f"{spec.domain_prefix}{book}/{member}"
        items = booknames.delivery(holder.vars, dest, member, items, now)
        previous = holder.vars.get(dest)[0]
        kept = booknames.delivery(holder.vars, dest, member, previous, now) if previous else previous
        from .carry import open_row
        try:
            opened = open_row(holder.sealer, kept, dest) if kept is not None else None
            normalized = {k: bookmerge._json(booknames._parse(v)) for k, v in opened.items()} if opened else opened
            unchanged = normalized == items
        except Exception:
            unchanged = False                     # damaged ciphertext is replaced, never logged or reused
        collected.rows[member] = kept if unchanged else booksecrets.at_rest(items, holder.sealer, dest)
    if holder.term is not None:
        holder.term.guard()
    booknames.publish(holder.vars, spec, book, collected, now)
    return collected


def steps(holder):
    return [(f"collecting {spec.name}/{book}", lambda s=spec, b=book: collect(holder, s, b))
            for spec in declared.specs() for book in spec.domain.merged]
