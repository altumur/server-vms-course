"""Lesson 9 — an edit for a cluster that is off.

Lesson 3 forwarded an edit to the owning cluster and answered 503 when the cluster did not answer. That is
right where a whole cluster is rarely unreachable, and wrong where a cluster is ONE BOX — a member that is
its own cluster, off for its power, its switch, its maintenance, and edited in bulk with forty-nine others.

So the domain keeps the edit, and keeps it the way it keeps everything a cluster needs from it: in the domain
holder's Variables, under `domain/pending/<cluster>`, beside `domain/grants/<cluster>`, carried home by that
cluster's agent when it is back. The cluster's own console applies it. Nothing about ownership moves: the
cluster's console is still the only writer of its rows, and the agent still writes nothing but `domain/*`.

    what is kept     per FIELD, the value the domain last saw (`old`), the value wanted (`new`), and any value
                     it wanted before that may already be on the unit (`via`)
    when it lands    a field that still holds `old` — or a `via` — takes `new`; one that holds `new` is done;
                     one that holds anything else moved underneath the edit — a CONFLICT, shown, not decided
    as whom          the operator who made it, with that operator's grant checked when it is applied
    how it returns   the agent writes the outcome in its own cluster's `domain/outcomes`; the domain reads
                     it the way it reads a snapshot, and clears what landed
"""
from __future__ import annotations

import json
import time

from w2cplatform.variables import Conflict, Variables

from w2cplatform.rows import PARSE_ERRORS
from w2cplatform.secrets import hide_in_reply

from .api import ApiError
from .federation import MEMBER_OBJECTS, Unreachable

PENDING_PATH, OUTCOMES_PATH = "domain/pending", "domain/outcomes"


# ONE ITEM THAT DOES NOT PARSE IS THAT ITEM'S (the review's eighth pass, major). A row of kept edits or of outcomes was
# loaded whole with a bare `json.loads` per item: one member's outcome that did not parse raised out of
# `PendingEdits.collect` on every pass, and the edits of every member after it were never reconciled — applied, and
# still shown as waiting. Now each item is read alone (`MEMBER_OBJECTS`, counted once by `<where>#<unit>`, logged
# once): what does not parse is left out of what is read, and an item of the domain's own row that does not parse is
# written back AS IT WAS by whoever writes the row (`_unread`) — never dropped by a write about another unit.
def _load(items: dict | None, where: str = PENDING_PATH) -> dict[str, dict]:
    out = {}
    for k, v in (items or {}).items():
        e = MEMBER_OBJECTS.read(f"{where}#{k}", lambda v=v: _an_object(json.loads(v)))
        if e is not None:
            out[k] = e
    return out


def _an_object(v):
    if not isinstance(v, dict):
        raise TypeError(f"not an object: {type(v).__name__}")
    return v


def _unread(items: dict | None) -> dict[str, str]:
    """The items of `items` that `_load` could not read: kept as they are."""
    def parses(v) -> bool:
        try:
            _an_object(json.loads(v))
        except PARSE_ERRORS:
            return False
        return True
    return {k: v for k, v in (items or {}).items() if not parses(v)}


# NO PASSWORD IS KEPT HERE, NOR IN AN OUTCOME (the twelfth review, blocker 9, and the product's cross-check): the
# door refuses an address with a credential in it (`ConsoleAPI._refuse_secrets`), and this is the floor under it — every
# write of a row of kept edits, and every outcome a member reports, says each address in it as a page does
# (`secrets.hide_in_reply`): an entry kept by an older domain, a conflict's `current` read off a row stored before the
# rule. A hidden value applied is still refused at the member (`pwd=***` is a credential pair), as the edit's outcome.
def _dump(entries: dict[str, dict], unread: dict[str, str] | None = None) -> dict[str, str]:
    return {**(unread or {}), **{k: json.dumps(hide_in_reply(v), ensure_ascii=False, sort_keys=True)
                                 for k, v in entries.items()}}


class PendingEdits:
    """The domain's side. One row per cluster, one item per unit in it, by the DOMAIN's name for the
    unit (its `ref`) — a cluster's own id is the cluster's."""

    def __init__(self, domain_vars: Variables, wall=time.time):
        self.vars, self.wall = domain_vars, wall

    def _path(self, cluster: str) -> str:
        return f"{PENDING_PATH}/{cluster}"

    def of(self, cluster: str) -> dict[str, dict]:
        items, _ = self.vars.get(self._path(cluster))
        return _load(items, self._path(cluster))

    # Keep an edit for a unit whose cluster did not answer.
    #
    # Per FIELD, and merged, because the unit needs the last value of each field, not a replay of every
    # edit made while it was off: a field already waiting keeps the value it was based on — while the unit
    # is off that is what the domain last saw, and nothing new arrives to move it — takes the latest wanted
    # value, and remembers the ones it wanted in between (`via`), because one of those may already be on the
    # unit, applied and not yet reported back. A field the member reported as a conflict is different — an edit to it
    # now is a person resolving it, "apply again", and it is measured against what the unit now holds,
    # or it would conflict for ever.
    #
    # `rev` counts the edits to this unit's entry. The outcome the agent reports names the `rev` it
    # applied, and only an outcome for the CURRENT rev clears anything: comparing the agent's clock with the
    # domain's would be comparing two machines' clocks, and an old outcome must never clear a newer edit.
    def add(self, cluster: str, ref, fields: dict, base: dict, subject: str | None, retries: int = 20) -> dict:
        ref = str(ref)
        for _ in range(retries):
            items, idx = self.vars.get(self._path(cluster))
            entries = _load(items, self._path(cluster))
            e = entries.get(ref) or {"fields": {}, "rev": 0}
            for f, new in fields.items():
                have = e["fields"].get(f)
                if have is None:
                    e["fields"][f] = {"old": base.get(f), "new": new}
                elif "conflict" in have:
                    e["fields"][f] = {"old": have["conflict"], "new": new}
                elif have["new"] != new:
                    # The value this field wanted until now may already be on the unit — applied and
                    # reported, but not yet read back here. Remember it: a unit holding it holds a value the
                    # domain itself sent, which is a base for the next edit and not somebody else's change.
                    via = have.get("via", [])
                    have["via"] = via if have["new"] in via else via + [have["new"]]
                    have["new"] = new
            e.update(rev=e["rev"] + 1, subject=subject, since=self.wall())
            e.pop("refused", None)                           # a new edit is a new decision; the old refusal was about the old one
            entries[ref] = e
            try:
                self.vars.put(self._path(cluster), _dump(entries, _unread(items)), cas=idx)
                return e
            except Conflict:                                 # somebody kept another edit meanwhile: read again
                continue
        raise RuntimeError(f"could not keep an edit for {ref} in {cluster}: {retries} CAS conflicts")

    # Fold one cluster's outcomes into what is waiting for it. Applied and already-there fields go; a
    # conflict stays, annotated with what the unit holds, until a person decides; a refusal stays with its
    # reason; a unit that is no longer in the cluster takes its edit with it.
    #
    # Each outcome is the member's word about one unit, and one that does not fit — `applied` not a list, a
    # conflict without `current` — is that unit's: its edit stays waiting, counted, and the others are folded
    # in (the review's eighth pass). The fold is made on a copy, so half an outcome changes nothing.
    def reconcile(self, cluster: str, outcomes: dict[str, dict]) -> None:
        import copy
        items, idx = self.vars.get(self._path(cluster))
        entries, changed = _load(items, self._path(cluster)), False
        for ref, out in outcomes.items():
            e = entries.get(ref)
            try:
                if e is None or out.get("rev") != e.get("rev"):
                    continue                                 # about an edit that is gone, or an older one
                if out.get("gone"):
                    entries.pop(ref)
                    changed = True
                    continue
                if out.get("refused"):
                    e["refused"] = str(out["refused"])
                    changed = True
                    continue
                e = copy.deepcopy(e)
                for f in list(out.get("applied", [])) + list(out.get("already", [])):
                    e["fields"].pop(f, None)
                for f, c in dict(out.get("conflicts", {})).items():
                    if f in e["fields"]:
                        e["fields"][f]["conflict"] = c["current"]
            except PARSE_ERRORS as err:
                MEMBER_OBJECTS.garbled(f"{cluster}/{OUTCOMES_PATH}#{ref}", err)
                continue
            MEMBER_OBJECTS.parsed(f"{cluster}/{OUTCOMES_PATH}#{ref}")
            changed = True
            if e["fields"]:
                entries[ref] = e
            else:
                entries.pop(ref)
        if changed:
            self.vars.put(self._path(cluster), _dump(entries, _unread(items)), cas=idx)

    # Read every cluster that has something waiting, the way the directory reads a snapshot, and fold in what
    # it says happened. A cluster that does not answer keeps its edits waiting — which is what they were
    # doing anyway.
    #
    # One member at a time (the review's eighth pass, major): its outcomes read item by item, and whatever its fold
    # still raises is that member's — logged once, counted — and the members after it are read.
    def collect(self, fed) -> None:
        for name, c in fed.clusters.items():
            try:
                if not self.of(name):
                    continue
                items, _ = c.vars.get(OUTCOMES_PATH)
                self.reconcile(name, _load(items if isinstance(items, dict) else None, f"{name}/{OUTCOMES_PATH}"))
            except Unreachable:
                continue
            except PARSE_ERRORS as e:
                MEMBER_OBJECTS.garbled(f"{name}/{OUTCOMES_PATH}", e)


# The cluster's side, run by its agent: apply what was carried home, per field, through the cluster's own
# console, as the operator who made the edit. `current(ref)` gives `(cluster id, row)` for the unit the
# domain calls `ref`, or None if the cluster no longer holds it.
#
# The console's refusal is the grant check, made NOW — an edit can wait a week and an operator can lose
# the right to make it within it — and it is recorded as a refusal, not retried and not forced. Any other
# failure is not a refusal and is left to raise: the agent's loop logs it and tries again next pass.
#
# An entry carried home that does not fit — `fields` not an object, a field without `new` — is that unit's: no
# outcome is written for it (there is no `rev` to name), it is counted once, and the other units are applied (the
# review's eighth pass: the agent's pass raised on it, and stopped before its report).
def apply_pending(entries: dict[str, dict], current, console, now: float) -> dict[str, dict]:
    outcomes: dict[str, dict] = {}
    for ref, e in entries.items():
        try:
            rev = e["rev"]
            found = current(ref)
            if found is None:
                outcomes[ref] = {"rev": rev, "at": now, "gone": True}
                continue
            cid, row = found
            apply, already, conflicts = {}, [], {}
            for f, d in dict(e["fields"]).items():
                cur = row.get(f)
                if cur == d["new"]:
                    already.append(f)                        # carried home twice before the domain cleared it
                elif cur == d["old"] or cur in list(d.get("via", [])):
                    apply[f] = d["new"]                      # what the edit was based on, or a value the domain sent before
                else:
                    conflicts[f] = {"old": d["old"], "new": d["new"], "current": cur}
        except PARSE_ERRORS as err:
            MEMBER_OBJECTS.garbled(f"{PENDING_PATH}#{ref}", err)
            continue
        MEMBER_OBJECTS.parsed(f"{PENDING_PATH}#{ref}")
        out = {"rev": rev, "at": now, "applied": [], "already": sorted(already), "conflicts": conflicts}
        if apply:
            try:
                console.update_unit(cid, apply, e.get("subject"))
                out["applied"] = sorted(apply)
            except ApiError as err:
                out["refused"] = err.detail
        outcomes[ref] = hide_in_reply(out)                   # a conflict's `current` is the member's row (see `_dump`)
    return outcomes
