"""A field too big for a row: the bytes in the object store, the digest in the row.

Some units carry one opaque lump — a per-pixel mask, a panel's
firmware, a model. It belongs to exactly one unit, the platform never reads
inside it, and it does not belong in a row: a row is small, and a store may
say how small (`limits.py`; the cluster's store refuses a row past `storemachine.MAX_VALUE`), while a per-pixel
mask for 1920x1080 is 345 KB as base64.

Moving such configuration wholesale into the object store is the obvious fix
and the wrong one: an object has no CAS, no one writer and no `revision`, so
the reconciler never learns it changed. These tests are about the shape that
keeps the mechanism — the row holds a DIGEST, and everything else follows from
that one choice.
"""
import base64
import json

from w2cplatform.blobs import BlobMismatch, digest, is_digest
from w2cplatform.console import SpecConsole
from w2cplatform.objects import FsObjectStore
from w2cplatform.spec import Refused, SpecController, SubsystemSpec
from tests.conftest import Box, testsub2

MASK = base64.b64encode(bytes(1920 * 1080 // 8))       # 345 600 bytes: the real thing, not a stand-in


def _tallies(box, objects=None):
    """testsub2's controller — its tally has a `blob` field (`mask`) — and its console."""
    ctl = SpecController(testsub2(), box.vars, objects or box.objects, wall=box.wall)
    return ctl, SpecConsole(ctl)


def test_the_row_takes_a_digest_and_says_so_when_it_is_handed_the_bytes():
    """The obvious thing for a client to do is paste the lump into the row, and that
    is also what puts a row over the store's ceiling. The refusal names the route
    instead of just saying no."""
    box = Box()
    ctl, _ = _tallies(box)
    ctl.create({"name": "t7", "of": "c7"})
    try:
        ctl.update("t7", {"mask": MASK.decode()})
        raise AssertionError("the bytes went into the row")
    except Refused as e:
        assert "takes a digest, not the bytes" in str(e)
        assert "/tallies/<id>/mask" in str(e)                   # where to put them instead


def test_the_bytes_go_to_the_object_store_under_their_own_name():
    box = Box()
    ctl, _ = _tallies(box)
    ctl.create({"name": "t7", "of": "c7"})
    d = ctl.put_blob(MASK)                                       # 1. the object
    row = ctl.update("t7", {"mask": d})                 # 2. the row that names it
    assert is_digest(d) and d == digest(MASK)
    assert row["mask"] == d
    assert box.objects.get(f"testsub2/blobs/{d}") == MASK
    assert ctl.blob(d) == MASK
    # the row stayed a row: the lump is not in it, by three orders of magnitude
    assert len(json.dumps(testsub2().items(row)).encode()) < 500 < len(MASK)


def test_the_same_bytes_are_one_object_however_many_units_name_them():
    """Content addressed, so this is true without anyone arranging it — and it is
    also why writing a blob twice is safe: the second write writes the same bytes
    to the same key."""
    box = Box()
    ctl, _ = _tallies(box)
    for i in (7, 8, 9):
        ctl.create({"name": f"t{i}", "of": f"c{i}"})
        ctl.update(f"t{i}", {"mask": ctl.put_blob(MASK)})
    assert len(box.objects.list("testsub2/blobs/")) == 1
    assert len(ctl.blobs_referenced()) == 1


def test_changing_the_blob_moves_the_revision():
    """The whole reason the digest is in the row. Nothing here is a new mechanism:
    a different lump is a different digest is a different row, a revision moved —
    and a worker that restarts a unit whose revision moved picks the new lump up
    with nothing added (a subsystem's own worker does, in a test of its own).

    Put the bytes in the object store alone and this test is impossible to write —
    the object changes, the row does not, and the worker goes on with the old lump
    until something else restarts it."""
    box = Box()
    ctl, _ = _tallies(box)
    ctl.create({"name": "t7", "of": "c7"})
    r1 = ctl.update("t7", {"mask": ctl.put_blob(MASK)})
    other = base64.b64encode(b"\xff" + bytes(1920 * 1080 // 8 - 1))
    r2 = ctl.update("t7", {"mask": ctl.put_blob(other)})
    assert r2["mask"] != r1["mask"] and r2["revision"] == r1["revision"] + 1
    assert ctl.unit("t7")["revision"] == r2["revision"]          # what a worker reads is the moved revision


def test_a_blob_may_not_be_in_the_snapshot():
    """Refused at LOAD time, like a secret — and for a plainer reason: the snapshot
    is one object per worker under a ceiling, and a blob is by definition what did
    not fit in a row."""
    base = {"name": "panel", "unit": {"rows": "panels", "fields": {"host": {"type": "string"},
                                                                   "firmware": {"type": "blob"}}}, "placement": {"capacity": {"from": "capacity", "default": 4}}}
    spec = SubsystemSpec.from_dict(base)
    assert spec.snapshot == ["host"]                              # the default leaves it out rather than refusing
    try:
        SubsystemSpec.from_dict({**base, "snapshot": ["host", "firmware"]})
        raise AssertionError("a blob was accepted into the snapshot")
    except ValueError as e:
        assert "a blob may not be in the snapshot" in str(e)
    assert "mask" not in testsub2().snapshot


def test_the_console_takes_the_bytes_on_their_own_route():
    box = Box()
    ctl, con = _tallies(box)
    st, row = con.create({"name": "t7", "of": "c7"})
    assert st == 201
    st, body = con.put_blob("t7", "mask", MASK)
    assert st == 200 and body["mask"] == digest(MASK) and body["bytes"] == len(MASK)
    assert ctl.unit("t7")["mask"] == digest(MASK)
    # a field that is not a blob, and a unit that is not there, are both 404 and not a stack trace
    assert con.put_blob("t7", "rule", b"x")[0] == 404
    assert con.put_blob("t9", "mask", b"x")[0] == 404


def test_a_blob_over_the_stores_ceiling_names_the_store():
    """The one place where "change the object store" is the right answer, and the
    message says so: a blob is the class of data an object store exists for, unlike
    the snapshot, which was a shape problem."""
    box = Box()
    ctl, con = _tallies(box, objects=FsObjectStore(box.root + "/capped", max_bytes=65536 - len("data")))
    con.create({"name": "t7", "of": "c7"})
    st, body = con.put_blob("t7", "mask", MASK)
    assert st == 413
    assert "declares a ceiling" in body["detail"] and "OBJECTS=cluster://" in body["detail"]
    assert ctl.unit("t7")["mask"] == ""                 # nothing was written, and the row is untouched


def test_what_a_sweep_would_keep_and_the_sweep_that_does_not_exist():
    """`blobs_referenced` is the honest half. Nothing in the platform deletes an
    object, so a replaced mask stays in the store forever and this is the list that
    would tell a collector which ones to keep. Written down rather than implied."""
    box = Box()
    ctl, _ = _tallies(box)
    ctl.create({"name": "t7", "of": "c7"})
    old = ctl.put_blob(MASK)
    ctl.update("t7", {"mask": old})
    new = ctl.put_blob(base64.b64encode(b"\x01" + bytes(99)))
    ctl.update("t7", {"mask": new})
    stored = {k.rsplit("/", 1)[1] for k in box.objects.list("testsub2/blobs/")}
    assert stored == {old, new}                                  # both still there
    assert ctl.blobs_referenced() == {new}                       # one of them referenced
    assert stored - ctl.blobs_referenced() == {old}              # and this is the garbage nobody collects


def test_a_poisoned_blob_is_caught_on_the_read_and_not_trusted():
    """The property an ACL cannot give.

    Whoever can write `testsub2/blobs/<digest>` can put other bytes there — on a cluster
    that is anyone the policy lets near the object prefix, and the policy is static
    text written by a person. The digest is the only thing that says what those bytes
    ARE, and it is worth nothing until someone checks it.

    Checked on the READ, where the bytes are about to be used. Checking only on the
    write would be trusting the writer again, which is the thing being replaced."""
    box = Box()
    ctl, _ = _tallies(box)
    ctl.create({"name": "t7", "of": "c7"})
    d = ctl.put_blob(MASK)
    ctl.update("t7", {"mask": d})
    assert ctl.blob(d) == MASK

    box.objects.put(f"testsub2/blobs/{d}", b"not the mask at all")      # the write an ACL is supposed to stop
    try:
        ctl.blob(d)
        raise AssertionError("the poisoned bytes were handed to the caller")
    except BlobMismatch as e:
        assert d in str(e) and digest(b"not the mask at all") in str(e)

    # …and it holds for reasons that have nothing to do with a writer: a truncated
    # object, a bad disk, a copy between stores that lost a byte.
    box.objects.put(f"testsub2/blobs/{d}", MASK[:-1])
    try:
        ctl.blob(d)
        raise AssertionError("a truncated object was handed to the caller")
    except BlobMismatch:
        pass
