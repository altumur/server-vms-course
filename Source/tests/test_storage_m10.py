"""Independent normative witnesses from the М10/1 mutation trial."""
import os
import tempfile
import json
from contextlib import ExitStack
from unittest.mock import patch
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


def test_native_list_names_foreign_rows_and_omits_a_concurrent_delete(monkeypatch):
    from tests.storage_acceptance import NativeAPI
    for factory in (lambda root: FileVariables(root, volatile=True), lambda root: MemVariables()):
        with tempfile.TemporaryDirectory() as root:
            store = factory(root)
            version = store.put('other/row', {'secret': 'hidden'})
            handle = store.as_writer('acceptance', ['acc/*'])
            api = NativeAPI(handle)
            assert api.request('GET', '/v1/get?key=other/row', b'')[0] == 403
            assert api.request('GET', '/v1/list?prefix=other/', b'') == (200, {'keys': {'other/row': str(version)}})
            original_list = handle.list
            def delete_after_list(prefix):
                names = original_list(prefix)
                for key in names:
                    store.delete(key)
                return names
            monkeypatch.setattr(handle, 'list', delete_after_list)
            assert api.request('GET', '/v1/list?prefix=other/', b'') == (200, {'keys': {}})


def test_memory_accepts_300_byte_keys_and_a_1024_byte_utf8_guard_not_a_file_limit():
    store = MemVariables()
    key = 'acc/' + 'k' * 296
    guard_key = 'acc/' + 'я' * 510
    assert len(key.encode()) == 300 and len(guard_key.encode()) == 1024
    guard_index = store.put(guard_key, {})
    version = store.put(key, {'v': 'one'}, guard={'key': guard_key, 'index': guard_index})
    assert store.get(key) == ({'v': 'one'}, version)
    for cmd in ({'op': 'put', 'key': guard_key + 'x', 'items': {}},
                {'op': 'put', 'key': key, 'items': {}, 'guard': {'key': guard_key + 'x', 'index': 0}}):
        try:
            store.write(cmd)
            raise AssertionError('key beyond 1024 raw bytes accepted')
        except ValueError:
            pass
    from tests.storage_acceptance import NativeAPI
    api = NativeAPI(store.as_writer('acceptance', ['acc/*']))
    assert api.request('GET', '/v1/get?key=' + key, b'') == (200, {'items': {'v': 'one'}, 'index': str(version)})


def test_the_wire_client_roundtrips_300_and_1024_byte_keys_and_guard_over_unix_http():
    from tests.test_configstorevars import Daemon, url
    from w2cplatform.variables import open_vars
    with Daemon() as daemon:
        store = open_vars(url(daemon.dir))
        key = 'acc/' + 'k' * 296
        guard_key = 'acc/' + 'я' * 510
        at = store.put(guard_key, {})
        version = store.put(key, {'v': 'one'}, guard={'key': guard_key, 'index': at})
        assert store.get(key) == ({'v': 'one'}, version)
        assert store.get(guard_key) == ({}, at)
        assert store.list(key) == [key]        # prefix itself longer than File's bound
        for path, guard in ((guard_key + 'x', None), (key, {'key': guard_key + 'x', 'index': at})):
            try:
                store.put(path, {}, guard=guard)
                raise AssertionError('wire key beyond 1024 raw bytes accepted')
            except ValueError:
                pass
        assert store.get(key) == ({'v': 'one'}, version)


def test_file_retains_its_encoded_filename_limit_for_target_and_guard():
    from w2cplatform.variables import KeyTooLong
    with tempfile.TemporaryDirectory() as root:
        store = FileVariables(root, volatile=True)
        long_key = 'acc/' + 'k' * 296
        for cmd in ({'op': 'put', 'key': long_key, 'items': {}},
                    {'op': 'delete', 'key': long_key},
                    {'op': 'put', 'key': 'acc/row', 'items': {}, 'guard': {'key': long_key, 'index': 0}}):
            try:
                store.write(cmd)
                raise AssertionError('File accepted an encoded filename beyond its own limit')
            except KeyTooLong as error:
                assert error.limit == 246
        assert store.get('acc/row') == (None, 0)


def test_key_validation_precedes_weight_and_weight_precedes_write_acl():
    from tests.storage_acceptance import NativeAPI
    from w2cplatform.storemachine import Rights
    machine = StoreMachine()
    rights = Rights.parse({'roles': {'acceptance': {'read': ['acc/*'], 'write': ['acc/*'], 'delete': ['acc/*']}}})
    calls = [lambda method, target, raw: answer(method, target, raw, 'acceptance', rights, machine.apply)]
    with tempfile.TemporaryDirectory() as root:
        stores = (FileVariables(root, max_bytes=524288, volatile=True), MemVariables(max_bytes=524288))
        calls += [NativeAPI(store.as_writer('acceptance', ['acc/*'])).request for store in stores]
        for call in calls:
            cmd = {'op': 'put', 'key': 'other/row', 'items': {'blob': 'x' * 524288}}
            code, body = call('POST', '/v1/write', json.dumps(cmd).encode())
            assert code == 413 and body['kind'] == 'toolarge' and body['limit'] == 524288
            cmd['key'] = 'other/../row'
            code, body = call('POST', '/v1/write', json.dumps(cmd).encode())
            assert code == 400 and body['kind'] == 'badkey'
            cmd['key'] = 'other/row'
            cmd['guard'] = {'key': 'acc/../guard', 'index': ''}
            code, body = call('POST', '/v1/write', json.dumps(cmd).encode())
            assert code == 400 and body['kind'] == 'badkey'


def test_published_put_and_delete_retry_original_receipts_after_guard_and_cas_change(monkeypatch):
    from w2cplatform import variables
    from w2cplatform.configstorevars import StoreAmbiguous
    for kind in ('file', 'mem'):
        for operation in ('put', 'delete'):
            with tempfile.TemporaryDirectory() as root:
                store = FileVariables(root, volatile=False) if kind == 'file' else MemVariables()
                slot = store.put('acc/slot', {'owner': 'a'})
                at = store.put('acc/row', {'v': 'old'})
                cmd = {'op': operation, 'key': 'acc/row', 'cas': at, 'id': 'abc',
                       'guard': {'key': 'acc/slot', 'index': slot}}
                if operation == 'put':
                    cmd['items'] = {'v': 'one'}
                original, calls, failed = variables.durable_dir, [], [False]
                def late(path):
                    calls.append(path)
                    if path == store.dir and not failed[0]:
                        failed[0] = True
                        raise OSError('after publication')
                    original(path)
                with ExitStack() as patches:
                    patches.enter_context(patch.object(variables, 'durable_dir', late))
                    if kind == 'file':
                        try:
                            store.write(cmd)
                            raise AssertionError('unconfirmed durability reported success')
                        except StoreAmbiguous:
                            pass
                        assert store.get('acc/row')[0] == ({'v': 'one'} if operation == 'put' else None)
                        with open(store.index_file) as f:
                            published = int(f.read())
                    else:
                        published = store.write(cmd)['index']
                    later = store.put('acc/row', {'v': 'later'})
                    store.put('acc/slot', {'owner': 'b'})
                    retrying = FileVariables(root, volatile=True) if kind == 'file' else store.as_writer('reader', ['acc/*'])
                    assert retrying.write(cmd) == {'index': published, 'again': True}
                    assert store.get('acc/row') == ({'v': 'later'}, later)
                    if kind == 'file':
                        assert calls.count(store.dir) == 4
                    else:
                        assert calls == []


def test_repeated_barrier_failure_stays_ambiguous_and_retries_only_missing_barriers(monkeypatch):
    from w2cplatform import variables
    from tests.storage_acceptance import NativeAPI
    for kind in ('file', 'mem'):
        with tempfile.TemporaryDirectory() as root:
            store = FileVariables(root, volatile=False) if kind == 'file' else MemVariables()
            api = NativeAPI(store)
            cmd = {'op': 'put', 'key': 'acc/row', 'items': {'v': 'one'}, 'id': 'abc'}
            original, calls, failures = variables.durable_dir, [], [2]
            def barrier(path):
                calls.append(path)
                if path == root and store.get('acc/row')[0] is not None and failures[0]:
                    failures[0] -= 1
                    raise OSError('late root barrier')
                original(path)
            with ExitStack() as patches:
                patches.enter_context(patch.object(variables, 'durable_dir', barrier))
                raw = json.dumps(cmd).encode()
                if kind == 'file':
                    assert api.request('POST', '/v1/write', raw) == (503, {'kind': 'ambiguous'})
                    at = store.get('acc/row')[1]
                    assert api.request('POST', '/v1/write', raw) == (503, {'kind': 'ambiguous'})
                    assert store.get('acc/row')[1] == at
                    assert api.request('POST', '/v1/write', raw) == (200, {'index': str(at), 'again': True})
                    assert calls == [root, store.dir, root, root, root]
                else:
                    code, receipt = api.request('POST', '/v1/write', raw)
                    assert code == 200
                    assert api.request('POST', '/v1/write', raw) == (200, {**receipt, 'again': True})
                    assert calls == []


def test_failure_before_publication_does_not_register_a_phantom_receipt(monkeypatch):
    from w2cplatform import variables
    for kind in ('file', 'mem'):
        with tempfile.TemporaryDirectory() as root:
            store = FileVariables(root, volatile=False) if kind == 'file' else MemVariables()
            cmd = {'op': 'put', 'key': 'acc/row', 'items': {'v': 'one'}, 'id': 'abc'}
            with ExitStack() as patches:
                if kind == 'file':
                    original = variables.os.replace
                    def replace(source, target):
                        if target == store._file('acc/row'):
                            raise OSError('before row rename')
                        return original(source, target)
                    patches.enter_context(patch.object(variables.os, 'replace', replace))
                else:
                    def apply(cmd):
                        raise OSError('before memory publication')
                    patches.enter_context(patch.object(store, '_apply_write', apply))
                try:
                    store.write(cmd)
                    raise AssertionError('prepublication failure was swallowed')
                except OSError:
                    pass
                assert store.get('acc/row') == (None, 0)
            receipt = store.write(cmd)
            assert receipt['again'] is False
            assert store.get('acc/row') == ({'v': 'one'}, receipt['index'])
            assert store.write(cmd) == {**receipt, 'again': True}


def test_pending_replay_checks_payload_and_callers_permissions_before_finishing(monkeypatch):
    from w2cplatform import variables
    from tests.storage_acceptance import NativeAPI
    for kind in ('file', 'mem'):
        with tempfile.TemporaryDirectory() as root:
            store = FileVariables(root, volatile=False) if kind == 'file' else MemVariables()
            slot = store.put('acc/slot', {})
            cmd = {'op': 'put', 'key': 'acc/row', 'items': {'v': 'one'}, 'id': 'abc',
                   'guard': {'key': 'acc/slot', 'index': str(slot)}}
            original, calls, broken = variables.durable_dir, [], [True]
            def barrier(path):
                calls.append(path)
                if path == store.dir and broken[0]:
                    raise OSError('unconfirmed row')
                original(path)
            with ExitStack() as patches:
                patches.enter_context(patch.object(variables, 'durable_dir', barrier))
                api = NativeAPI(store)
                raw = json.dumps(cmd).encode()
                code, body = api.request('POST', '/v1/write', raw)
                assert code == (503 if kind == 'file' else 200)
                count = len(calls)
                changed = {**cmd, 'items': {'v': 'changed'}}
                assert api.request('POST', '/v1/write', json.dumps(changed).encode())[0] == 400
                forbidden = NativeAPI(store.as_writer('denied', []))
                assert forbidden.request('POST', '/v1/write', raw) == (403, {'kind': 'forbidden'})
                handle = store.as_writer('limited', {'limited': {'write': ['acc/row'], 'read': []}})
                assert NativeAPI(handle).request('POST', '/v1/write', raw) == (403, {'kind': 'forbidden'})
                assert len(calls) == count
                broken[0] = False
                code, receipt = api.request('POST', '/v1/write', raw)
                assert code == 200 and receipt['again'] is True
                assert receipt['index'] == str(store.get('acc/row')[1])
