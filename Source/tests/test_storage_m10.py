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
