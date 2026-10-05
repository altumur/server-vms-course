"""What was DONE to the system, and by whom: the `audit` family in the ordinary event log."""
# ================================================================================================
# # journal.py — who deleted it, who read it, what the policy removed
#
# A deleted unit left a tombstone and a revision number, and no name: who deleted unit 7 could not be
# answered. The retention pass said how many buckets it removed, as one number in a log. Bytes left through a
# door and nothing said so (the platform review, "deletions by policy are not journalled"; the product's
# journal, feedback BN).
#
# Not a mechanism of its own: a FAMILY OF KINDS in the event log there already is. Subsystem `audit`, the unit
# is the ROLE of the writer (`console`, `resource`), and everything an event log has comes with it — the
# timeline reads it, the retention pass keeps it, the mirror copies it, the index answers it.
#
#   unit.created/changed/deleted   console    a unit of any subsystem was created, edited, deleted: which, and who
#   door.issued               console    a holder's door was handed out with a unit's place: who, which unit, which
#                                        holder, which routes, until when (`door.py`) — the console never sees the bytes
#   schema.raised             console    the store's layout was raised: to what, from what, who
#   events.removed            resource   the retention pass removed buckets: whose, how many, of what period
#
# …and a subsystem's own kinds, under the role that wrote them: what a holder's door served a page (`door-<holder>`,
# with the name the door token was given to), a viewer admitted and gone, a row of one of its tables set or lifted —
# each its spec's and its code's words, in this same family.
#
# Kept as long as alarms are (`resource.retention_days`): the record of who deleted a camera is wanted for as
# long as that camera's alarms are.
#
# What is NOT here: what a subsystem gives up by itself, by the thousand — a ring that overwrites its oldest — where
# a line each would be the noise the journal exists to be read through. What a person needs to hear about of that is
# an ALARM in that subsystem's own events.
#
# What a line is ABOUT is in `sub` (a subsystem) and `target` (a unit). Not `subsystem` and `unit`: those are
# the line's own — `audit`, and the role that wrote it — and a field of the same name would answer for them
# in every reader. Nor `of`, which is the index's own column (`events.OF`, `<sub>/<id>`): the field was `of` until
# the index took the name (the boundary's step 2; the product's journal says `sub` too).
#
# "Who" is `X-User` — the name the caller gave, OR the name the console's gate proved from a token and wrote
# over the header (`access.py`: a cluster in a domain holds a key set; a console that cannot check is shut).
# Outside a domain there is no authentication, and the journal does not pretend there is. The domain (М12) writes the same
# family, as role `domain`: who created, disabled or deleted a person, who changed the grants, who admitted a
# member — the history that a row holding only its last editor loses (feedback CL).
# ================================================================================================
import logging

from .events import OBSERVATION, EventLog

AUDIT = "audit"
log = logging.getLogger("w2cplatform.journal")


class Journal:
    """One role's line into `audit/<role>/e1/…` on this server's resource. With no resource: the log only."""

    def __init__(self, root: str | None, role: str, wall):
        self.role, self.wall = role, wall
        self.log = EventLog(root, AUDIT, role, 1) if root else None

    # Never raises: what was done has been done, and a journal that cannot be written must not undo it or
    # hide it — it says so in the process's own log.
    def say(self, kind: str, cls: str = OBSERVATION, **fields) -> str | None:
        log.info("%s: %s %s", self.role, kind, fields)
        if self.log is None:
            return None
        try:
            return self.log.append(self.wall(), kind, cls, durable=True, **fields)
        except OSError:
            log.exception("%s: %s could not be written to the journal", self.role, kind)
            return None
