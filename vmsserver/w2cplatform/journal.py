"""What was DONE to the system, and by whom: the `audit` family in the ordinary event log."""
# ================================================================================================
# # journal.py — who deleted it, who read it, what the policy removed
#
# A deleted unit left a tombstone and a revision number, and no name: who deleted camera 7 could not be
# answered. The retention pass said how many buckets it removed, as one number in a log. Footage left through
# the console and nothing said so (the platform review, "deletions by policy are not journalled"; the product's
# journal, feedback BN).
#
# Not a mechanism of its own: a FAMILY OF KINDS in the event log there already is. Subsystem `audit`, the unit
# is the ROLE of the writer (`console`, `resource`), and everything an event log has comes with it — the
# timeline reads it, the retention pass keeps it, the mirror copies it, the index answers it.
#
#   unit.deleted              console    a camera, a recording, any unit was deleted: which, and who
#   archive.read              console    a piece of footage was served through the console: who, which, from where
#   live.view / live.view.ended  console  a viewer was admitted to a camera's live stream, and hung up: who, which, where from (feedback CL)
#   archive.keep.made/lifted  console    a keep was set or lifted: who
#   archive.volume.shrunk/withdrawn  console    a volume's quota was lowered, or the volume withdrawn: who
#   events.removed            resource   the retention pass removed buckets: whose, how many, of what period
#
# Kept as long as alarms are (`resource.retention_days`): the record of who deleted a camera is wanted for as
# long as that camera's alarms are.
#
# What is NOT here: footage a ring overwrote. A volume gives up its oldest minutes by itself, by the thousand,
# and a line each would be the noise the journal exists to be read through. What a person needs to hear about
# — kept footage the incidents ring took, a recording shallower than it was promised — is an ALARM in the
# recorder's own events (`archive.keep.lost`, `archive.shallow`).
#
# What a line is ABOUT is in `of` (a subsystem) and `target` (a unit). Not `subsystem` and `unit`: those are
# the line's own — `audit`, and the role that wrote it — and a field of the same name would answer for them
# in every reader.
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
