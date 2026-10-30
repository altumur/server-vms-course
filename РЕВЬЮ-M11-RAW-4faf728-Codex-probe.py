"""Wire and lifecycle controls; run only in the CT 103 queue. No implementation/SUT."""
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
from types import SimpleNamespace

BASE = 'e5f3bfdbb28b5492cdab0d4432b80330ece9d143'
HEAD = '4faf72867250887f13a7c81de4db272bb52b107e'
MANIFEST = 'b7e014faec9cf5ca3cf73e8e3abb4abcac0f22a3a2908aa1db0342bd18ed5176'
INPUT = 'd9364b991b275ab102ce6fc34c8a7af5a39f7a7ab72ac7d1dad3ccdf5524910c'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def files(root):
    return {str(p.relative_to(root)): sha(p) for p in root.rglob('*')
            if p.is_file() and '.git' not in p.relative_to(root).parts}


def extract(archive, dest, commit=None):
    dest.mkdir()
    with tarfile.open(archive) as stream:
        if commit:
            assert stream.pax_headers.get('comment') == commit
        stream.extractall(dest, filter='data')


def blobs(root, listing):
    count = 0
    for entry in filter(None, listing.read_bytes().split(b'\0')):
        metadata, name = entry.split(b'\t', 1)
        mode, kind, wanted = metadata.split()
        assert kind == b'blob'
        p = root / name.decode()
        data = os.readlink(p).encode() if mode == b'120000' else p.read_bytes()
        assert hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest() == wanted.decode()
        count += 1
    return count


def receive(conn):
    data = b''
    while b'\r\n\r\n' not in data:
        chunk = conn.recv(65536)
        if not chunk:
            return None
        data += chunk
    raw_head, body = data.split(b'\r\n\r\n', 1)
    lines = raw_head.split(b'\r\n')
    headers = [line.decode('latin1').split(':', 1) for line in lines[1:]]
    headers = [(k.lower(), v.strip()) for k, v in headers]
    length = int(next(v for k, v in headers if k == 'content-length'))
    while len(body) < length:
        chunk = conn.recv(65536)
        if not chunk:
            break
        body += chunk
    return headers, body


def fixture_bench(module, address, process, launched):
    bench = module.Bench.__new__(module.Bench)
    bench.clusters = {'m2': SimpleNamespace(find=lambda name: process, store_role='acc',
                     store=lambda role=None: module.HttpDoor(address, timeout=2))}
    bench.agent_copies = {'m2': [{'number': 1, 'process': process, 'launched': launched}]}
    bench.ac = lambda c: SimpleNamespace(token_door='unix:{agent_tokens}/{role}.sock')
    bench.fmt = lambda *a, **k: address
    return bench


def controls(runtime):
    sys.path.insert(0, str(runtime / 'runner'))
    import m11stand
    process = SimpleNamespace(poll=lambda: None)

    def wire(req, expected_body, content_type):
        with tempfile.TemporaryDirectory(prefix='raw-wire-', dir='/tmp') as directory:
            path = str(Path(directory) / 'door.sock')
            server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            server.bind(path)
            server.listen(4)
            server.settimeout(3)
            captured = []
            def serve():
                try:
                    conn, _ = server.accept()
                    with conn:
                        conn.settimeout(3)
                        captured.append(receive(conn))
                        conn.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
                except BaseException as error:
                    captured.append(repr(error))
            thread = threading.Thread(target=serve, daemon=True)
            thread.start()
            run = m11stand.Run(SimpleNamespace(json=None), 'wire-review')
            run.b = fixture_bench(m11stand, 'unix:' + path, process, time.time() - 60)
            run.bearer = lambda: None
            try:
                why, _ = run.step('1', req, '200')
                assert not why, why
            finally:
                thread.join(4)
                server.close()
            assert len(captured) == 1 and isinstance(captured[0], tuple), captured
            headers, body = captured[0]
            types = [v for k, v in headers if k == 'content-type']
            lengths = [v for k, v in headers if k == 'content-length']
            try:
                json.loads(body)
                valid_json = True
            except (ValueError, UnicodeError):
                valid_json = False
            return {'safety_pass': body == expected_body and types == [content_type]
                    and lengths == [str(len(expected_body))],
                    'body_matches': body == expected_body, 'body_length': len(body),
                    'expected_length': len(expected_body), 'content_types': types, 'content_lengths': lengths,
                    'body_prefix': body[:160].decode('utf8', 'replace'), 'valid_json': valid_json}

    body = '{"request_id": "j1", "ref": "value @raw tail"}'
    result = {
        'published_4097': wire('token m2 testsubworker POST /tokens/testsub/tally @raw @big(4097)',
                              b'x' * 4097, 'application/octet-stream'),
        'json_literal_marker': wire('token m2 testsubworker POST /tokens/testsub/tally ' + body,
                                    body.encode(), 'application/json'),
        'store_raw': wire('member m2 store POST /v1/write @raw abc def',
                          b'abc def', 'application/octet-stream'),
        'raw_utf8_spaces': wire('token m2 testsubworker POST /tokens/testsub/tally @raw Привет  мир  ',
                               'Привет  мир  '.encode(), 'application/octet-stream'),
        'custom_type': wire('token m2 testsubworker @header cOnTeNt-TyPe: application/custom POST /tokens/testsub/tally {}',
                            b'{}', 'application/custom'),
    }
    # The fixture listener is owned by the exact tracked process and opens late.
    with tempfile.TemporaryDirectory(prefix='ready-wire-', dir='/tmp') as directory:
        path = str(Path(directory) / 'door.sock')
        code = '''import socket,sys,time
time.sleep(.25)
s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);s.bind(sys.argv[1]);s.listen(4);s.settimeout(3)
while True:
 c,_=s.accept();c.settimeout(2)
 with c:
  data=c.recv(65536)
  if not data:continue
  c.sendall(b'HTTP/1.1 200 OK\\r\\nContent-Length: 0\\r\\nConnection: close\\r\\n\\r\\n')
  break
s.close()
'''
        launched = time.time()
        child = subprocess.Popen([sys.executable, '-I', '-B', '-c', code, path],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            bench = fixture_bench(m11stand, 'unix:' + path, child, launched)
            try:
                status, _, _ = bench.door(['token', 'm2', 'testsubworker', 'POST', '/tokens/testsub/tally', '{}'],
                                          'review', {}, None)
                result['delayed_listener'] = {'safety_pass': status == 200, 'status': status}
            except m11stand.TransportError as error:
                result['delayed_listener'] = {'safety_pass': False, 'transport': str(error).split(': ')[0]}
        finally:
            if child.poll() is None:
                child.terminate()
            child.communicate(timeout=4)
    return result


def main():
    root = Path(__file__).resolve().parent
    out = Path(os.environ['CHECK_OUT'])
    package = root / 'package'
    assert sha(package / 'MANIFEST.json') == MANIFEST
    manifest = json.loads((package / 'MANIFEST.json').read_text())
    for name, wanted in manifest['files'].items():
        assert sha(package / name) == wanted, name
    assert sha(root / 'author-input.tar.gz') == INPUT
    with tempfile.TemporaryDirectory(prefix='review-m11raw-') as directory:
        work = Path(directory)
        extract(root / 'author-input.tar.gz', work / 'author')
        author = work / 'author/in'
        original = files(author)
        verified = {}
        for label, commit in (('before', BASE), ('after', HEAD)):
            extract(root / (label + '.tar'), work / label, commit)
            verified[label] = blobs(work / label, root / (label + '.ls-tree'))
        old, new = files(work / 'before'), files(work / 'after')
        assert {p for p in old.keys() | new.keys() if old.get(p) != new.get(p)} == {
            'runner/m11stand.py', 'runner/harness.py', 'tests/test_m11_raw_and_agent_door.py'}
        assert new == files(author / 'runner')
        for name in ('runner/m11stand.py', 'runner/harness.py', 'tests/test_m11_raw_and_agent_door.py'):
            assert sha(package / 'files' / name) == sha(work / 'after' / name)
        os.environ.update(CAMMETA_SPECS=str(author / 'specs'), PYTHONDONTWRITEBYTECODE='1')
        results = {}
        for label in ('before', 'after'):
            p = subprocess.run([sys.executable, '-I', '-B', str(Path(__file__).resolve()), '--controls', str(work / label)],
                               capture_output=True, text=True, timeout=40)
            assert p.returncode == 0, (label, p.stdout, p.stderr)
            results[label] = json.loads(p.stdout)
        tests = {}
        for name in ('test_m11_raw_and_agent_door', 'test_c_domain_stand', 'test_runner'):
            p = subprocess.run([sys.executable, '-I', '-B', '-m', 'unittest', 'discover', '-s', 'tests', '-p', name + '.py'],
                               cwd=work / 'after', capture_output=True, text=True, timeout=90)
            (out / (name + '.txt')).write_text(p.stdout + p.stderr)
            assert p.returncode == 0, (name, p.stdout, p.stderr)
            tests[name] = p.stderr.strip()
        assert files(author) == original
        findings = [name for name, value in results['after'].items() if not value['safety_pass']]
        result = {'green': not findings, 'findings': findings, 'SUT': 0, 'controls': results, 'tests': tests,
                  'package_files': len(manifest['files']), 'manifest_sha256': MANIFEST,
                  'author_input_sha256': INPUT, 'author_input_files': len(original),
                  'inputs_unchanged': True, 'git_blobs': verified}
        (out / 'review-evidence.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps(result, ensure_ascii=False), flush=True)
        return int(bool(findings))


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--controls':
        print(json.dumps(controls(Path(sys.argv[2])), ensure_ascii=False))
    else:
        raise SystemExit(main())
