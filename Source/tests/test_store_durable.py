"""The file store after a power cut, and two writers of one object (the platform review of 29 September; the
product's store, feedback BD).

A row written with write + rename and no barrier is in the page cache. The row may be an epoch: after a power
cut the old number is back, and `next_epoch` hands out one that was already given. A counter that cannot be
read must not read as "start again". And an object's file in flight needs a name of its own.
"""
import os

import w2cplatform.objects as objects_mod
from w2cplatform.objects import FsObjectStore
from w2cplatform.variables import Corrupt, FileVariables
from tests.conftest import Box


def _count_barriers(under: str):
    """Barriers on files and directories under `under` — other tests' threads write to stores of their own.
    Patched where `FileVariables` itself looks them up: another test may have imported the module afresh."""
    calls = {"file": 0, "dir": 0}
    g = FileVariables._durable.__globals__
    real = g["durably"], g["durable_dir"]

    def on_file(f):
        if str(f.name).startswith(under):
            calls["file"] += 1
        return real[0](f)

    def on_dir(p):
        if str(p).startswith(under):
            calls["dir"] += 1
        return real[1](p)

    g["durably"], g["durable_dir"] = on_file, on_dir
    return calls, lambda: g.update(durably=real[0], durable_dir=real[1])


def test_a_row_reaches_the_medium_before_it_is_renamed_into_place_unless_the_store_says_it_is_a_test():
    box = Box()
    calls, restore = _count_barriers(box.root)
    try:
        durable = FileVariables(os.path.join(box.root, "durable"), volatile=False)
        durable.put("testsub/epoch/7", {"epoch": 5})
        assert calls == {"file": 2, "dir": 2}                     # the counter and the row; their two directories
        durable.as_writer("w-1", ["testsub/*"]).put("testsub/epoch/8", {"epoch": 1})
        assert calls["file"] == 4                                 # another identity on the same store: as durable
        calls.update(file=0, dir=0)
        FileVariables(os.path.join(box.root, "volatile"), volatile=True).put("testsub/epoch/7", {"epoch": 5})
        assert calls == {"file": 0, "dir": 0}
    finally:
        restore()
    assert os.environ.get("STORE_VOLATILE") == "1" and box.vars.volatile     # what `tests/run.py` said for the suite


def test_a_store_with_nothing_said_is_durable():
    old = os.environ.pop("STORE_VOLATILE", None)
    try:
        assert FileVariables(os.path.join(Box().root, "plain")).volatile is False
    finally:
        if old is not None:
            os.environ["STORE_VOLATILE"] = old


def test_a_counter_that_cannot_be_read_is_an_error_not_a_new_beginning():
    """An empty counter file is what a power cut leaves of a file that was never flushed. It read as 1000, and so
    did a missing one beside rows that exist: numbering started again, and a CAS remembered from before the cut
    could match a row it was never read from."""
    box = Box()
    v = FileVariables(os.path.join(box.root, "store"), volatile=True)
    assert v.put("testsub/counters/1", {"name": "gate"}) == 1001       # a store with no rows: 1000, and up
    for left in ("", "12a4"):
        with open(v.index_file, "w") as f:
            f.write(left)
        try:
            v.put("testsub/counters/2", {"name": "dock"})
            raise AssertionError("an unreadable counter must not be read as 1000")
        except Corrupt as e:
            assert "refusing to number again" in str(e)
    os.remove(v.index_file)
    try:
        v.put("testsub/counters/2", {"name": "dock"})
        raise AssertionError("a missing counter beside rows must not be read as 1000")
    except Corrupt:
        pass
    assert v.get("testsub/counters/2") == (None, 0) and v.get("testsub/counters/1")[1] == 1001   # nothing half-written


def test_two_writers_of_one_object_do_not_share_the_file_in_flight():
    """`<path>.tmp` was one name for every writer of a key. A zombie and its replacement writing the same heartbeat
    wrote into the same file, and what was renamed into place could be the two interleaved."""
    box = Box()
    store = FsObjectStore(os.path.join(box.root, "objects2"))
    seen, real = [], objects_mod.os.replace

    def watching(src, dst):
        seen.append(os.path.basename(src))
        return real(src, dst)

    objects_mod.os.replace = watching
    try:
        store.put("testsub/heartbeats/w-1", b'{"a": 1}')
        store.put("testsub/heartbeats/w-1", b'{"a": 2}')
    finally:
        objects_mod.os.replace = real
    assert len(set(seen)) == 2 and all(n.startswith("w-1.") and n.endswith(".tmp") for n in seen)
    assert store.get("testsub/heartbeats/w-1") == b'{"a": 2}'
    assert store.list("testsub/heartbeats/") == ["testsub/heartbeats/w-1"]            # nothing left in flight, nothing listed


def test_a_command_mark_is_on_the_medium_before_its_name_and_its_name_after():
    """The review's third pass (minor). `put_new` is the mark a worker writes BEFORE it calls its target; written with
    no barrier, the power going after the call took the mark with it, and the next holder opened the door a second
    time. The bytes reach the medium before the name is made, the directory entry after it — and a mark that loses
    the race pays for the bytes only."""
    box = Box()
    store = FsObjectStore(os.path.join(box.root, "objects"))
    mark = os.path.join(box.root, "objects", "testsub", "commands", "r1")
    g = FsObjectStore.put_new.__globals__
    real, calls = (g["durably"], g["durable_dir"]), []
    g["durably"] = lambda f: calls.append(("file", os.path.exists(mark)))
    g["durable_dir"] = lambda p: calls.append(("dir", os.path.exists(os.path.join(p, "r1"))))
    try:
        assert store.put_new("testsub/commands/r1", b'{"instance": "a"}')
        assert calls == [("file", False), ("dir", True)]                   # bytes before the name, the entry after
        calls.clear()
        assert not store.put_new("testsub/commands/r1", b'{"instance": "b"}') and [c[0] for c in calls] == ["file"]
    finally:
        g["durably"], g["durable_dir"] = real
    assert store.get("testsub/commands/r1") == b'{"instance": "a"}'
