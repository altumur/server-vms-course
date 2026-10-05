"""The domain's pass over the books — one place that writes every per-cluster book, in the order they depend
on each other. The console's pass reads (the view, `domain/view`, kept edits); this one mints tokens, so it
runs where the signer's key is: `domain.signer_service`, when it is given CLUSTERS.

    sources      Lesson 13   for each recording cluster: where its cameras of other clusters were last seen
    primaries    Lesson 13   for each camera cluster: who records it, whether written, and where to push (16)
    poll         Lesson 16   for a pushing camera nobody records: the ingest it polls for asks
    upstream     Lesson 17   for each relay: the centre's ingest, per camera, when there is a centre
    asks         Lesson 16   for each camera a scenario of the shared document makes a trigger: whom it may
                             ask, by which roads — built last, because it reads what the others decided

EACH BOOK IS A STEP OF ITS OWN (the review's eighth pass; the seventh left "the steps of `Books.pass_once`" open).
The pass was one call for everything: a member's object that raised in the first read stopped all five books, and
the stream tokens and the tokens to ask that they carry are re-issued only here — within a day every camera of the
domain was refused at its ingest. Now each step runs in `Steps`: one that raises is logged once until it works
again, counted, and named in what the pass returns (`failing`); its book is the one written last, which is what a
book is for; and the steps after it run. A step that reads what another decided reads the books as they are.
"""
from __future__ import annotations

import logging

from .chain import publish_upstream
from .ingest import publish_asks
from .scenario import pairs, refusals, unchecked
from w2cplatform.domain.shared import published
from w2cplatform.domain.steps import Steps

log = logging.getLogger("domain.books")


class Books:
    def __init__(self, crossings, domain_objects, members=None):
        """`members`: the domain's list of members (`domain/members.py`) — followed first, every pass."""
        self.crossings, self.objects, self.members = crossings, domain_objects, members
        self.steps = Steps("the pass over the books", log=log)

    def pass_once(self) -> dict[str, int]:
        c = self.crossings
        got = self.steps.run(
            ("following the members", self._follow_members),
            ("following the topology", self._follow_topology),
            ("the read view's pass", c.view.refresh),
            ("sources", lambda: len(c.publish())),
            ("primaries", lambda: len(c.publish_primaries())),
            ("poll", lambda: len(c.publish_polls())),
            ("upstream", lambda: len(publish_upstream(c, c.centre, star=c.star)) if c.centre else None),
            ("the shared settings", lambda: published(c.vars, self.objects)))
        out = {k: got[k] for k in ("sources", "primaries", "poll", "upstream") if got.get(k) is not None}
        if "the shared settings" in got:                 # a document nobody can read writes no book of asks: the last stays
            settings = got["the shared settings"]
            more = self.steps.run(
                ("asks", lambda: len(publish_asks(c, pairs(settings)))),
                # Checked at writing; a camera can still leave the domain afterwards. Such a scenario is SAID, every
                # pass, never skipped in silence.
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
        c = self.crossings
        return follow_members(c.view.fed, self.members, self.objects, c.topology, wall=c.wall)

    def _follow_topology(self) -> list:
        c = self.crossings
        if c.topology is None:                           # a member moved behind a relay, or out: read it the new way
            return []
        from w2cplatform.domain.topology import apply
        return apply(c.view.fed, c.topology, self.objects, wall=c.wall)
