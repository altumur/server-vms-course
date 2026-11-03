"""Adversarial forward_one traces; only fake SSH and runner-owned temporary files."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root / 'portable'))
spec = importlib.util.spec_from_file_location('review_test_check', root / 'tests/test_check.py')
tests = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tests)
check = tests.check
import remote


def trace(mode):
    case = tests.RemoteCheck('runTest')
    case.setUp()
    try:
        job = case.submit('./run.sh', 'own', name=mode)['id']
        fake, machine = case.fake_machine()
        events = []
        at_clean = []
        outbox = machine / 'checks/outbox' / (job + '.tar.gz')
        active_marker = machine / 'checks/work' / job / 'active-proof'
        with fake as mocked, patch.object(check, 'ARCHIVE_ROOT', case.root / 'archive'), \
                contextlib.redirect_stdout(io.StringIO()):
            base = mocked.side_effect

            def ssh(user, command, **kwargs):
                if command.startswith('systemd-run'):
                    events.append('launch')
                    if mode == 'late_launch':
                        raise RuntimeError('SSH lost: launch outcome unknown')
                    result = base(user, command, **kwargs)
                    if mode.startswith('recovered_'):
                        raise RuntimeError('SSH wait lost after the unit completed')
                    return result
                if command.startswith('systemctl show'):
                    events.append('status')
                    if mode == 'late_launch':
                        return subprocess.CompletedProcess([], 4,
                            b'ActiveState=inactive\nLoadState=not-found\n', b'')
                    return subprocess.CompletedProcess([], 0,
                        b'ActiveState=inactive\nResult=success\nLoadState=loaded\n', b'')
                if command.startswith('test -f '):
                    events.append('outbox-probe')
                    if mode == 'late_launch':
                        # The original uncertain launch takes effect after the status read.
                        # It is still the first launch; the forwarder must not delete its work.
                        events.append('original-launch-takes-effect')
                        active_marker.parent.mkdir(parents=True, exist_ok=True)
                        active_marker.write_text('unit is executing; no outbox yet\n')
                        return subprocess.CompletedProcess([], 1, b'', b'')
                if '/checks/outbox/' in command and command.startswith('sha256sum '):
                    events.append('sha')
                    if mode == 'normal_sha':
                        assert outbox.is_file()
                        raise RuntimeError('SSH lost while reading result SHA')
                if '/checks/outbox/' in command and command.startswith('cat '):
                    events.append('fetch')
                    if mode in ('normal_fetch', 'recovered_fetch'):
                        assert outbox.is_file()
                        kwargs['stdout'].write(outbox.read_bytes()[:32])
                        raise RuntimeError('SSH lost after a partial result download')
                    if mode == 'normal_short':
                        assert outbox.is_file()
                        kwargs['stdout'].write(outbox.read_bytes()[:32])
                        return subprocess.CompletedProcess([], 0, None, b'')
                if command.startswith('rm -rf '):
                    events.append('clean')
                    at_clean.append(dict(outbox=outbox.is_file(), active=active_marker.is_file(),
                                         archived=(case.root / 'archive' / job / 'result.tar.gz').is_file()))
                return base(user, command, **kwargs)

            mocked.side_effect = ssh
            check.forward_one(case.queue / 'spool' / job)
        failed = case.queue / 'failed' / job / 'forward-error.txt'
        published = case.queue / 'results' / job / 'result.json'
        value = dict(mode=mode, events=events, at_clean=at_clean,
                     outbox_retained=outbox.is_file(), active_work_retained=active_marker.is_file(),
                     input_retained=(machine / 'checks/inbox' / (job + '.tar.gz')).is_file(),
                     failed=failed.exists(), reason=failed.read_text() if failed.exists() else None,
                     published=json.loads(published.read_text())['exit_code'] if published.exists() else None)
        if mode == 'normal':
            assert value['published'] == 3 and value['at_clean'][0]['archived']
            value['safety_pass'] = True
        elif mode == 'recovered_fetch' and hasattr(check, 'recover_unit'):
            assert value['outbox_retained'] and 'clean' not in events
            value['safety_pass'] = True
        elif mode == 'late_launch' and hasattr(check, 'recover_unit'):
            assert events.count('launch') == 1
            assert 'original-launch-takes-effect' in events
            value['safety_pass'] = value['active_work_retained'] and 'clean' not in events
        elif mode.startswith('normal_'):
            assert value['failed']
            value['safety_pass'] = value['outbox_retained'] and 'clean' not in events
        else:
            value['safety_pass'] = value['input_retained'] and 'clean' not in events
        return value
    finally:
        case.doCleanups()


values = [trace(mode) for mode in ('normal', 'normal_fetch', 'normal_sha', 'normal_short',
                                  'recovered_fetch', 'late_launch')]
Path(sys.argv[2]).write_text(json.dumps(values, indent=2) + '\n')
print(json.dumps(dict(snapshot=root.name, traces=len(values), observations=values), indent=2))
