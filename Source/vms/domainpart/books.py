"""Remaining domain-side console diagnostics until ADR-0074 C7.

All books are collected by the platform from signed member reports. This pass
only follows membership/topology and computes scenario diagnostics for the
remaining console endpoints; it issues no token and writes no book.
"""
from __future__ import annotations

import logging

from .scenario import refusals, unchecked
from w2cplatform.domain.shared import published
from w2cplatform.domain.steps import Steps

log = logging.getLogger("domain.books")


class Books:
    def __init__(self, inputs, domain_objects, members=None):
        """`members`: the domain's list of members (`domain/members.py`) — followed first, every pass."""
        self.inputs, self.objects, self.members = inputs, domain_objects, members
        self.steps = Steps("the pass over the books", log=log)

    def pass_once(self) -> dict[str, int]:
        c = self.inputs
        got = self.steps.run(
            ("following the members", self._follow_members),
            ("following the topology", self._follow_topology),
            ("the read view's pass", c.view.refresh),
            ("the shared settings", lambda: published(c.vars, self.objects)))
        out = {}
        if "the shared settings" in got:                 # unreadable settings cannot produce fresh diagnostics
            settings = got["the shared settings"]
            more = self.steps.run(
                # What a scenario means is checked here, not where the document is signed (the signer asks no
                # subsystem's code, ADR-0032) — and a camera can leave the domain afterwards: such a scenario is SAID,
                # every pass, never skipped in silence.
                ("refused", lambda: refusals(settings, c)),
                ("unchecked", lambda: unchecked(settings, c)))    # accepted, and nobody could vouch for it: said too
            out.update(more)
        out["moved"] = got.get("following the topology", [])
        out["members"] = got.get("following the members", {"joined": [], "left": []})
        out["failing"] = sorted(self.steps.failing)
        return out

    def _follow_members(self) -> dict:
        if self.members is None:                         # who the members are: the record, not the configuration
            return {"joined": [], "left": []}
        from w2cplatform.domain.members import apply as follow_members
        c = self.inputs
        return follow_members(c.view.fed, self.members, self.objects, c.topology, wall=c.wall)

    def _follow_topology(self) -> list:
        c = self.inputs
        if c.topology is None:                           # a member moved behind a relay, or out: read it the new way
            return []
        from w2cplatform.domain.topology import apply
        return apply(c.view.fed, c.topology, self.objects, wall=c.wall)
