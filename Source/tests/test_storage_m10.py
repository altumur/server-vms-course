"""Independent normative witnesses from the М10/1 mutation trial."""
import os
import tempfile
import json
from w2cplatform.variables import FileVariables, Conflict, Corrupt
from w2cplatform.memvariables import MemVariables
from w2cplatform.storemachine import StoreMachine, Rights, answer


def test_deleted_row_never_reuses_a_version_or_accepts_its_old_cas():
    with tempfile.TemporaryDirectory() as root:
        for store in (FileVariables(root, volatile=True), MemVariables()):
            a = store.put('acc/row', {'n': '1'}, cas=0)
            store.delete('acc/row', cas=a)
            b = store.put('acc/row', {'n': '2'}, cas=0)
            assert a != b
            try:
                store.put('acc/row', {'n': 'late'}, cas=a)
                raise AssertionError('old CAS accepted after delete and recreation')
            except Conflict:
                pass
            assert store.get('acc/row') == ({'n': '2'}, b)


def test_delete_cannot_erase_the_last_row_before_validating_the_counter():
    with tempfile.TemporaryDirectory() as root:
        store = FileVariables(root, volatile=True)
        version = store.put('acc/row', {'n': '1'})
        os.remove(store.index_file)
        try:
            store.delete('acc/row', cas=version)
            raise AssertionError('delete restarted numbering after counter loss')
        except Corrupt:
            pass
        assert store.get('acc/row') == ({'n': '1'}, version)


def test_the_normative_ceiling_is_512_kib_independent_of_the_implementation_constant():
    machine = StoreMachine()
    for length, expected in ((524284, 200), (524285, 413)):
        code, body = answer('POST', '/v1/write', json.dumps({'op': 'put', 'key': 'acc/row', 'items': {'blob': 'x'*length}}).encode(), 'admin', Rights(), machine.apply)
        assert code == expected
        if expected == 413:
            assert body['limit'] == 524288 and body['size'] == 524289


def test_a_counter_reservation_is_durable_before_the_last_row_is_removed(monkeypatch):
    from w2cplatform import variables
    with tempfile.TemporaryDirectory() as root:
        store = FileVariables(root, volatile=True)
        store.put('acc/row', {'n': '1'})
        store.volatile = False
        events = []
        remove = variables.os.remove
        monkeypatch.setattr(variables, 'durably', lambda f: events.append('file'))
        monkeypatch.setattr(variables, 'durable_dir', lambda path: events.append(path))
        def unlink(path):
            assert root in events, 'counter rename not durable before deletion'
            events.append('unlink')
            remove(path)
        monkeypatch.setattr(variables.os, 'remove', unlink)
        store.delete('acc/row')
        assert events.index(root) < events.index('unlink')


def test_a_counter_below_its_initial_floor_refuses_instead_of_reusing_versions():
    with tempfile.TemporaryDirectory() as root:
        store = FileVariables(root, volatile=True)
        store.put('acc/row', {'n': '1'})
        with open(store.index_file, 'w') as f:
            f.write('-1')
        try:
            store.put('acc/row', {'n': 'late'})
            raise AssertionError('counter below its initial floor accepted')
        except Corrupt:
            pass


def test_the_unchanged_shared_acceptance_passes_through_a_separate_daemon_process():
    from pathlib import Path
    import subprocess
    import sys
    runner = Path(__file__).with_name('storage_acceptance.py')
    with tempfile.TemporaryDirectory() as output:
        result = subprocess.run([sys.executable, str(runner), output], text=True,
                                capture_output=True, timeout=45)
        assert result.returncode == 0, result.stdout + result.stderr


def test_native_shared_acceptance_uses_each_real_backend_without_a_door():
    from pathlib import Path
    import subprocess
    import sys
    runner = Path(__file__).with_name("storage_acceptance.py")
    for backend in ("file", "mem"):
        with tempfile.TemporaryDirectory() as output:
            result = subprocess.run([sys.executable, str(runner), output, "--backend", backend],
                                    text=True, capture_output=True, timeout=45)
            assert result.returncode == 0, backend + result.stdout + result.stderr
            metadata = json.loads((Path(output) / "backend.json").read_text())
            assert metadata["door"] is False and metadata["backend"] == backend
            calls = json.loads((Path(output) / "api-calls.json").read_text())
            prefix = "variables.py:FileVariables" if backend == "file" else "memvariables.py:MemVariables"
            assert calls[prefix + ".write"] > 0 and calls[prefix + "._apply_write"] > 0
            assert not (Path(output) / "daemon.json").exists()


def test_receipts_and_wrappers_share_real_replay_after_guard_changes():
    for factory in (lambda root: FileVariables(root, volatile=True), lambda root: MemVariables()):
        with tempfile.TemporaryDirectory() as root:
            store = factory(root)
            writer = store.as_writer("acceptance", ["acc/*"])
            slot = store.put("acc/slot", {"owner": "a"})
            cmd = {"op": "put", "key": "acc/row", "items": {"v": "one"}, "cas": 0,
                   "guard": {"key": "acc/slot", "index": slot}, "id": "a1"}
            first = writer.write(cmd)
            assert first["again"] is False
            store.put("acc/slot", {"owner": "b"}, cas=slot)
            assert store.write(cmd) == {"index": first["index"], "again": True}
            assert writer.put("acc/row", {"v": "one"}, cas=0, guard=cmd["guard"], id="a1") == first["index"]
            deleted = writer.delete("acc/row", cas=first["index"], id="d1")
            assert deleted != first["index"]
            assert store.write({"op": "delete", "key": "acc/row", "cas": first["index"], "id": "d1"}) == {"index": deleted, "again": True}
            first["index"] = "caller changed receipt"
            cmd["items"]["v"] = "caller changed command"
            try:
                store.write(cmd)
                raise AssertionError("changed write reused an id")
            except ValueError:
                pass
            assert store.get("acc/row") == (None, 0)


def test_a_refused_id_remembers_its_original_conflict_not_the_later_row():
    for factory in (lambda root: FileVariables(root, volatile=True), lambda root: MemVariables()):
        with tempfile.TemporaryDirectory() as root:
            store = factory(root)
            first = store.put("acc/row", {"v": "one"})
            cmd = {"op": "put", "key": "acc/row", "items": {}, "cas": 0, "id": "b1"}
            for _ in range(2):
                try:
                    store.write(cmd)
                    raise AssertionError("create-only on an existing row succeeded")
                except Conflict as error:
                    assert error.index == first
                store.put("acc/row", {"v": "later"})


def test_replay_keeps_two_minutes_and_fifty_thousand_answers(monkeypatch):
    from w2cplatform import variables
    clock = [0.0]
    monkeypatch.setattr(variables.time, "monotonic", lambda: clock[0])
    memory = variables._Replay()
    applied = [0]
    def apply():
        applied[0] += 1
        return {"index": applied[0], "again": False}
    for n in range(50001):
        memory.run({"id": format(n, "x")}, apply)
    assert memory.run({"id": "0"}, apply) == {"index": 1, "again": True}
    clock[0] = 119.999
    memory.run({"id": "fffff"}, apply)
    assert memory.run({"id": "0"}, apply)["again"] is True
    clock[0] = 120.0
    memory.run({"id": "ffffe"}, apply)
    assert len(memory.done) == 50000
    assert memory.run({"id": "0"}, apply)["again"] is False
    clock[0] = 10000.0
    assert memory.run({"id": "ffffe"}, apply)["again"] is True


def test_file_replay_is_process_memory_and_creates_no_new_disk_records():
    from pathlib import Path
    import subprocess
    import sys
    with tempfile.TemporaryDirectory() as root:
        store = FileVariables(root, volatile=True)
        first = store.put("acc/row", {"v": "one"}, id="f1")
        reopened = FileVariables(root, volatile=True)
        assert reopened.write({"op": "put", "key": "acc/row", "items": {"v": "one"}, "id": "f1"}) == {"index": first, "again": True}
        code = "from w2cplatform.variables import FileVariables; import sys; print(FileVariables(sys.argv[1],volatile=True).put('acc/row',{'v':'one'},id='f1'))"
        result = subprocess.run([sys.executable, "-c", code, root], text=True, capture_output=True, timeout=15)
        assert result.returncode == 0, result.stderr
        assert int(result.stdout) != first
        store.delete("acc/row")
        assert sorted(str(p.relative_to(root)) for p in Path(root).rglob("*") if p.is_file()) == ["index", "lock"]


def test_two_handles_retrying_one_id_apply_it_only_once():
    import concurrent.futures
    import threading
    for factory in (lambda root: FileVariables(root, volatile=True), lambda root: MemVariables()):
        with tempfile.TemporaryDirectory() as root:
            store = factory(root)
            handles = [store.as_writer("writer", ["acc/*"]) for _ in range(4)]
            barrier = threading.Barrier(len(handles))
            def write(handle):
                barrier.wait(timeout=5)
                return handle.write({"op": "put", "key": "acc/row", "items": {"v": "one"}, "cas": 0, "id": "c1"})
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(handles)) as pool:
                receipts = list(pool.map(write, handles))
            assert len({r["index"] for r in receipts}) == 1
            assert sum(r["again"] is False for r in receipts) == 1
            assert store.get("acc/row")[1] == receipts[0]["index"]
