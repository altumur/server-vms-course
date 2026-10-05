"""Collecting blobs nothing names any more — the one thing in the platform that deletes an object.

A blob key is the digest of its bytes, so every edit of a `blob` field makes a
NEW permanent object. That is what makes blobs different from everything else
in the object store: a heartbeat's key is reused by the next instance of the
slot, so stale heartbeats are bounded by the number of slot names and are kept
on purpose (a worker reads the previous instance's heartbeat to measure its own
failover). Blobs grow with the number of EDITS over the system's lifetime, and
until now nothing ever reclaimed them.

The obvious implementation is wrong: "delete every blob no row names" races
with `put_blob`, which writes the object BEFORE the row that names it. These
tests are mostly about that race.
"""
import json

from w2cplatform.console import SpecConsole
from w2cplatform.variables import Conflict
from tests.conftest import Box, controller, testsub2

MASK_A, MASK_B, MASK_C = b"a" * 900, b"b" * 900, b"c" * 900


def _tallies(box):
    """testsub2's controller — its tally has a `blob` field (`mask`) — and its console."""
    ctl = controller(box, spec=testsub2())
    return ctl, SpecConsole(ctl)


def _blobs(box):
    return sorted(k.rsplit("/", 1)[1] for k in box.objects.list("testsub2/blobs/"))


def test_a_blob_nothing_names_is_collected_but_never_on_the_pass_that_noticed_it():
    """The shape of the whole thing: noticing and deleting are different passes,
    because a blob created between them must survive, and the only way to know it
    was created between them is that it is not on the list."""
    box = Box()
    ctl, _ = _tallies(box)
    ctl.create({"name": "t7", "of": "c7"})
    ctl.update("t7", {"mask": ctl.put_blob(MASK_A)})
    ctl.update("t7", {"mask": ctl.put_blob(MASK_B)})     # A is now an orphan
    assert len(_blobs(box)) == 2

    first = ctl.sweep_blobs()
    assert first == {"marked": 1, "deleted": 0, "waiting": 0}
    assert len(_blobs(box)) == 2, "the pass that noticed also deleted"

    assert ctl.sweep_blobs() == {"marked": 0, "deleted": 0, "waiting": 1}   # inside the grace period

    box.wall.advance(301)
    assert ctl.sweep_blobs() == {"marked": 0, "deleted": 1, "waiting": 0}
    assert _blobs(box) == [ctl.put_blob(MASK_B)], "the referenced blob went too, or the orphan stayed"
    assert ctl.blob(ctl.put_blob(MASK_B)) == MASK_B                        # and it still reads


def test_a_blob_written_between_the_two_passes_survives():
    """The race the design exists for. `put_blob` writes the object first and the
    row second; a sweep that decided in one breath would delete the bytes a row is
    about to name. It cannot: the digest was not on the list."""
    box = Box()
    ctl, _ = _tallies(box)
    ctl.create({"name": "t7", "of": "c7"})
    ctl.update("t7", {"mask": ctl.put_blob(MASK_A)})
    ctl.update("t7", {"mask": ctl.put_blob(MASK_B)})
    ctl.sweep_blobs()                                              # marks A

    box.wall.advance(301)
    ctl.create({"name": "t8", "of": "c8"})
    fresh = ctl.put_blob(MASK_C)                                   # object written; the row not yet
    ctl.sweep_blobs()                                              # …and the sweep runs right here
    assert box.objects.get(f"testsub2/blobs/{fresh}") == MASK_C, "the sweep ate a blob whose row was in flight"
    ctl.update("t8", {"mask": fresh})                     # the row lands, late and intact
    assert ctl.blob(fresh) == MASK_C


def test_re_uploading_a_marked_blob_calls_the_whole_sweep_off():
    """The residual race, closed. The same bytes can be uploaded for a second unit
    while the first unit's copy is marked — and then the marked digest is exactly
    the one a row is about to name. `put_blob` takes it off the list, which makes
    the sweep's own CAS fail, and a sweep that loses that CAS deletes NOTHING."""
    box = Box()
    ctl, _ = _tallies(box)
    ctl.create({"name": "t7", "of": "c7"})
    ctl.update("t7", {"mask": ctl.put_blob(MASK_A)})
    ctl.update("t7", {"mask": ctl.put_blob(MASK_B)})      # A orphaned
    ctl.sweep_blobs()
    assert json.loads(box.vars.get("testsub2/sweep")[0]["digests"]) != []

    box.wall.advance(301)
    ctl.create({"name": "t8", "of": "c8"})
    again = ctl.put_blob(MASK_A)                                   # the marked digest, uploaded again
    assert json.loads(box.vars.get("testsub2/sweep")[0]["digests"]) == [], "put_blob did not take it off the list"
    ctl.update("t8", {"mask": again})

    ctl.sweep_blobs()
    assert box.objects.get(f"testsub2/blobs/{again}") == MASK_A, "the sweep deleted a blob a row names"


def test_an_upload_between_the_sweepers_last_look_and_its_delete_is_put_back():
    """The review's third pass (m5): the window left after the decision stayed on the row was two store calls wide —
    the sweeper reads "still doomed", `put_blob` takes the digest off and writes the object, the sweeper deletes it,
    and the row then names nothing. The sweeper now reads the row again after the delete: a digest that left the
    list in between is being uploaded, and its bytes — the same bytes, the key is their digest — are put back."""
    box = Box()
    ctl, _ = _tallies(box)
    ctl.create({"name": "t7", "of": "c7"})
    ctl.update("t7", {"mask": ctl.put_blob(MASK_A)})
    ctl.update("t7", {"mask": ctl.put_blob(MASK_B)})      # A orphaned
    ctl.sweep_blobs()                                              # …and marked
    box.wall.advance(301)
    ctl.create({"name": "t8", "of": "c8"})
    real, again = box.objects.delete, []

    def delete(key):                                               # the upload lands exactly in the window
        if not again:
            again.append(ctl.put_blob(MASK_A))
        return real(key)
    box.objects.delete = delete
    rep = ctl.sweep_blobs()
    ctl.update("t8", {"mask": again[0]})                  # the row lands
    assert box.objects.get(f"testsub2/blobs/{again[0]}") == MASK_A, "the sweep deleted a blob being uploaded"
    assert rep["deleted"] == 0 and ctl.blob(again[0]) == MASK_A


def test_the_sweep_is_bounded_because_its_own_bookkeeping_is_a_row():
    """`testsub2/sweep` is a Variable, and a Variable has the store's ceiling over it
    (Lesson 26). So the sweep collects at most `limit` per pass — the rule applies
    to the thing that was written under it."""
    box = Box()
    ctl, _ = _tallies(box)
    ctl.create({"name": "t7", "of": "c7"})
    for i in range(10):
        ctl.update("t7", {"mask": ctl.put_blob(bytes([i]) * 500)})
    assert len(_blobs(box)) == 10                                  # nine orphans and the current one

    assert ctl.sweep_blobs(limit=4)["marked"] == 4
    box.wall.advance(301)
    assert ctl.sweep_blobs(limit=4)["deleted"] == 4
    assert len(_blobs(box)) == 6
    # …and the rest goes in later passes, four at a time
    for _ in range(3):
        ctl.sweep_blobs(limit=4); box.wall.advance(301); ctl.sweep_blobs(limit=4)
    assert len(_blobs(box)) == 1, _blobs(box)


def test_a_subsystem_with_no_blob_field_is_not_swept_at_all():
    """testsub has no `blob` field. A sweep there must not list, not decide and not
    write a row — nothing to collect is not the same as nothing collected."""
    box = Box()
    ctl = controller(box)
    assert ctl.sweep_blobs() == {"marked": 0, "deleted": 0, "waiting": 0}
    assert box.vars.get("testsub/sweep") == (None, 0), "a subsystem with nothing to sweep wrote bookkeeping"


def test_nothing_but_the_sweep_leans_on_objects_going_away():
    """The invariant Lesson 4 stated as "nothing deletes" is now narrower, and the
    narrower one has to be checked: the READERS still assume an object stays. A
    worker reads the heartbeat its previous instance left to measure failover, and
    `builds()` answers "what is running here" from heartbeats of any age — sweep
    those and both go quiet. So the sweep touches `blobs/` and nothing else."""
    box = Box()
    ctl, _ = _tallies(box)
    box.objects.put("testsub2/heartbeats/d-1", b'{"worker": "d-1", "ts": 0, "status": []}')
    box.objects.put("testsub2/snapshot/d-1", b'{"cluster": "c", "worker": "d-1", "ts": 0, "units": []}')
    ctl.create({"name": "t7", "of": "c7"})
    ctl.put_blob(MASK_A)                                           # an orphan from the first breath

    ctl.sweep_blobs(); box.wall.advance(301); ctl.sweep_blobs()
    assert _blobs(box) == []
    assert box.objects.get("testsub2/heartbeats/d-1") is not None, "the sweep took a heartbeat"
    assert box.objects.get("testsub2/snapshot/d-1") is not None, "the sweep took a snapshot shard"


def test_the_backlog_is_on_metrics_and_costs_two_reads():
    """A gauge scraped every fifteen seconds must not walk every unit's row, so the
    backlog is reported as what IS there and what is marked — a prefix listing and
    one row — and not as `blobs_referenced()`, which is a full scan."""
    box = Box()
    ctl, con = _tallies(box)
    ctl.create({"name": "t7", "of": "c7"})
    ctl.update("t7", {"mask": ctl.put_blob(MASK_A)})
    ctl.update("t7", {"mask": ctl.put_blob(MASK_B)})
    assert "testsub2_blobs_total 2" in con.metrics_text()
    assert "testsub2_blobs_marked 0" in con.metrics_text()

    ctl.sweep_blobs()
    assert "testsub2_blobs_marked 1" in con.metrics_text()
    box.wall.advance(301); ctl.sweep_blobs()
    assert "testsub2_blobs_total 1" in con.metrics_text() and "testsub2_blobs_marked 0" in con.metrics_text()


def test_a_subsystem_without_blobs_has_no_blob_gauges():
    """testsub has no `blob` field: a gauge that is always zero is noise on every
    screen it reaches."""
    box = Box()
    text = SpecConsole(controller(box)).metrics_text()
    assert "testsub_blobs_total" not in text and "testsub_blobs_marked" not in text


def test_the_decision_to_delete_is_written_by_cas_before_anything_is_deleted():
    """The ordering argument, exercised where it actually lives: INSIDE one pass.

    The sweeper reads the list, checks, writes its decision on the row by CAS (`state: deleting`, the doomed
    digests), and only then removes the bytes. If somebody re-uploads a marked blob after that read, the CAS fails —
    and because the decision is written FIRST, nothing has been deleted when it does. Delete first and the same
    interleaving destroys bytes a row is already naming.

    The interleaving is made deterministic by acting from inside `blobs_referenced`,
    which the sweeper calls after reading the row and before writing it."""
    box = Box()
    ctl, _ = _tallies(box)
    other, _ = _tallies(box)                                  # a second console, same store
    ctl.create({"name": "t7", "of": "c7"})
    ctl.update("t7", {"mask": ctl.put_blob(MASK_A)})
    ctl.update("t7", {"mask": ctl.put_blob(MASK_B)})
    ctl.sweep_blobs()                                     # A is marked
    box.wall.advance(301)

    real = ctl.blobs_referenced
    def racing():
        ctl.blobs_referenced = real                       # once, in the middle of the pass
        # The real interleaving: the OBJECT is written and the row naming it is still in flight, so the
        # digest is genuinely unreferenced at the re-check — and the only thing between it and deletion
        # is that `put_blob` took it off the list, which the CAS is about to notice.
        other.put_blob(MASK_A)
        return real()
    ctl.blobs_referenced = racing

    try:
        ctl.sweep_blobs()
        raise AssertionError("the sweeper wrote over a decision something had contradicted")
    except Conflict:
        pass
    from w2cplatform.blobs import digest
    assert box.objects.get(f"testsub2/blobs/{digest(MASK_A)}") == MASK_A, \
        "the CAS was lost AFTER the delete: the bytes of a row still in flight are gone"


def test_a_blob_uploaded_again_while_the_sweep_is_deleting_is_not_deleted():
    """The review's second pass, m5. The row was cleared BEFORE the deletes, so a `put_blob` of a marked digest in
    the seconds they took found an empty list, took nothing off it, and its bytes went under a row about to name
    them. The decision now stays on the row while the bytes go — `state: deleting` — and `put_blob` takes the
    digest off it as before the decision; the sweeper reads the row back before each delete and leaves what is
    gone from it alone."""
    box = Box()
    ctl, _ = _tallies(box)
    other, _ = _tallies(box)
    ctl.create({"name": "t7", "of": "c7"})
    ctl.update("t7", {"mask": ctl.put_blob(MASK_A)})
    ctl.update("t7", {"mask": ctl.put_blob(MASK_B)})
    ctl.sweep_blobs()                                     # A is marked
    box.wall.advance(301)

    class Store:                                          # the sweeper's own store, with one read intercepted
        def __init__(self, real): self._r = real; self.raced = False
        def __getattr__(self, n): return getattr(self._r, n)
        def get(self, path):
            items, idx = self._r.get(path)
            if path == "testsub2/sweep" and (items or {}).get("state") == "deleting" and not self.raced:
                self.raced = True                         # the decision is written; the bytes are about to go
                other.create({"name": "t8", "of": "c8"})
                other.update("t8", {"mask": other.put_blob(MASK_A)})
                return self._r.get(path)
            return items, idx
    ctl.vars = Store(box.vars)

    assert ctl.sweep_blobs() == {"marked": 0, "deleted": 0, "waiting": 0} and ctl.vars.raced
    from w2cplatform.blobs import digest
    assert box.objects.get(f"testsub2/blobs/{digest(MASK_A)}") == MASK_A and other.blob(digest(MASK_A)) == MASK_A
    assert json.loads(box.vars.get("testsub2/sweep")[0]["digests"]) == [] and "state" not in box.vars.get("testsub2/sweep")[0]

    # …and a sweeper that died with the decision written leaves nothing undone: the next pass reads it as marked
    other.update("t8", {"mask": other.put_blob(MASK_C)})          # A is an orphan again
    box.vars.put("testsub2/sweep", {"at": str(box.wall() - 301), "digests": json.dumps([digest(MASK_A)]), "state": "deleting"},
                 cas=box.vars.get("testsub2/sweep")[1])
    assert other.sweep_blobs() == {"marked": 0, "deleted": 1, "waiting": 0} and box.objects.get(f"testsub2/blobs/{digest(MASK_A)}") is None


def test_the_console_process_actually_runs_the_sweep():
    """The bug this catches is the one that was actually made: `sweep_blobs` was
    written, tested, and left UNCALLED in the Go port for a day — every test green,
    and not one blob collected on a running cluster.

    It reads the source, which is a weak kind of test and worth being honest about:
    it would not notice a loop that starts and immediately returns. What it does
    notice is the whole class of "we built it and forgot to plug it in", and that
    class is not hypothetical here."""
    import inspect
    from w2cplatform import host
    src = inspect.getsource(host.console)                            # the platform's console since the boundary's step 6
    assert "sweep_loop" in src, "the console process does not start the blob sweep"
    # and every subsystem the console fronts is handed to it: any of them may declare a blob field
    assert "list(ctls.values())" in src, "the sweep was started for some subsystems, not all"
    loop = inspect.getsource(host.sweep_loop) + inspect.getsource(host.sweep_turn) + inspect.getsource(host.step)
    assert "sweep_blobs()" in loop and "except Exception" in loop, \
        "the sweep runs without its own failure handling — Lesson 28, made twice"
