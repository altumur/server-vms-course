"""P01.370: recheck the published OBSH.75 pin against exact-C vectors.

No candidate, sandbox, shared cache or module source is changed. Run once in a
new evidence directory with /home/pilot/venv-spec/bin/python -B verify.py.
"""
from pathlib import Path
import base64
import hashlib
import json
import os
import shutil
import subprocess
import time

B = Path(__file__).resolve().parent
COURSE = Path('/home/pilot/wt-task-P01.370')
C = 'cde92cf79905c18a064732cde7917f52068c2cca'
PIN_C = '1b60bf7ad6141e5d5cc49d185a16ee30fcf8c66c'
MODULE_C = 'e19621128ad83f7e50267d58cfe1a2f029e70a28'
VERSION = 'v0.0.0-20261113215911-e19621128ad8'
MODULE = 'servervms.local/common/log-mask'
PREVIOUS = Path('/home/pilot/obsh75-evidence')
ZIP = PREVIOUS / 'proxy' / MODULE / '@v' / (VERSION + '.zip')


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def dump(p, x):
    Path(p).write_text(json.dumps(x, ensure_ascii=False, indent=1) + '\n')


def blob(ref, p):
    return subprocess.check_output(['git', '-C', str(COURSE), 'show', ref + ':' + p])


def run(name, argv, env=None, cwd=B):
    started = time.monotonic()
    p = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, timeout=300)
    (B / (name + '.out')).write_bytes(p.stdout)
    (B / (name + '.err')).write_bytes(p.stderr)
    dump(B / (name + '.run.json'), {'argv': argv, 'cwd': str(cwd),
         'exit': p.returncode, 'seconds': time.monotonic() - started,
         'stdout_sha256': sha(B / (name + '.out')), 'stderr_sha256': sha(B / (name + '.err'))})
    return p


assert sha(ZIP) == '29b52c538fca20a31edd8ff9b55a05b2f4dbcea3871125d6e97bfaf43ca6cf52'
spec = B / 'source'
inputs = ['Platform/common/vectors/wire.tsv',
          'Platform/common/vectors/log-mask/cases.tsv',
          'Platform/common/vectors/secret-in/fields.yaml']
for name in inputs:
    p = spec / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(blob(C, name))
consumer = B / 'consumer'
consumer.mkdir(exist_ok=True)
for name in ('go.mod', 'go.sum'):
    (consumer / name).write_bytes(blob(PIN_C, 'Platform/common/versions/' + name))
assert (MODULE + ' ' + VERSION).encode() in (consumer / 'go.mod').read_bytes()
dump(B / 'INPUTS.json', {'C': C, 'course_pin_commit': PIN_C, 'module_commit': MODULE_C,
     'module': MODULE, 'version': VERSION, 'zip_sha256': sha(ZIP),
     'inputs': {name: sha(spec / name) for name in inputs},
     'consumer_pins': {name: sha(consumer / name) for name in ('go.mod', 'go.sum')}})
env = os.environ.copy()
env.update({'GOTOOLCHAIN': 'local', 'GOENV': 'off', 'GOSUMDB': 'off',
            'GOPROXY': 'file://' + str(PREVIOUS / 'proxy') + ',file:///home/pilot/owner-receipts/OBSH.74-common-modules-20261113T1934Z/proxy,file:///opt/minimax-judge/gomodcache/cache/download',
            'GOMODCACHE': str(B / 'cache/mod'), 'GOCACHE': str(B / 'cache/build'),
            'GOPATH': str(B / 'cache/gopath')})
dump(B / 'ENVIRONMENT.json', {k: env[k] for k in ('GOTOOLCHAIN', 'GOENV', 'GOSUMDB', 'GOPROXY', 'GOMODCACHE', 'GOCACHE', 'GOPATH')})
assert run('GO-VERSION', ['go', 'version'], env, consumer).returncode == 0
assert run('BUILD', ['go', 'build', '-mod=readonly', '-o', str(B / 'vectors'), MODULE + '/cmd/vectors'], env, consumer).returncode == 0
modules = run('MODULES', ['go', 'list', '-mod=readonly', '-m', '-json', MODULE], env, consumer)
assert modules.returncode == 0
module = json.loads(modules.stdout)
assert module['Version'] == VERSION and 'Replace' not in module
download = run('MODULE-SUM', ['go', 'mod', 'download', '-json', MODULE + '@' + VERSION], env, consumer)
assert download.returncode == 0
downloaded = json.loads(download.stdout)
assert downloaded['Sum'] == 'h1:+1LNxwz/zTP7SfgJp/FbbPLYD4kKoSJpKfzxCHUokJo='
assert sha(downloaded['Zip']) == sha(ZIP)
for name in ('go.mod', 'go.sum'):
    assert (consumer / name).read_bytes() == blob(PIN_C, 'Platform/common/versions/' + name)
shutil.copyfile(PREVIOUS / 'scripts/vecrun.py', B / 'vecrun.py')
full = run('ALL-VECTORS', ['/home/pilot/venv-spec/bin/python', '-B', str(B / 'vecrun.py'), str(spec), 'common/log-mask', str(B / 'vectors') + ' {input}', str(B / 'ALL-VECTORS.json')], env)
assert full.returncode in (0, 1)
all_vectors = json.loads((B / 'ALL-VECTORS.json').read_text())
fields = base64.b64encode((spec / inputs[2]).read_bytes()).decode('ascii')
fresh = []
for line_no, line in enumerate((spec / inputs[1]).read_text().split('\n'), 1):
    if not line or line.startswith('#'):
        continue
    raw, masked, note = line.split('\t')
    if not note.startswith('utf8-regex-'):
        continue
    key = note.split(':', 1)[0]
    request = {'format': 1, 'package': 'common/log-mask', 'table': 'cases.tsv',
               'case': key, 'variant': '', 'cells': {'raw': raw}, 'files': {'fields.yaml': fields}}
    input_path = B / (key + '.input.json')
    dump(input_path, request)
    p = run(key, [str(B / 'vectors'), str(input_path)], env)
    result = {'case': key, 'line': line_no, 'raw': raw, 'expected': masked,
              'outer_exit': p.returncode, 'expected_utf8_hex': masked.encode().hex(), 'ok': False}
    try:
        assert p.returncode == 0
        frame = json.loads(p.stdout)
        assert set(frame) == {'exit_code', 'stdout_b64', 'stderr_b64'}
        native = base64.b64decode(frame['stdout_b64'], validate=True)
        got = json.loads(native)
        result.update({'native_exit': frame['exit_code'], 'actual': got,
                       'native_stdout_hex': native.hex(), 'actual_utf8_hex': got.encode('utf-8').hex(),
                       'ok': frame['exit_code'] == 0 and type(got) is str and got.encode('utf-8') == masked.encode('utf-8')})
    except (ValueError, UnicodeError, AssertionError) as e:
        result['error'] = str(e)
    fresh.append(result)
assert len(fresh) == 11
fresh_lines = {r['line'] for r in fresh}
old_red = [r for r in all_vectors['red'] if r['line'] not in fresh_lines]
summary = {'task': 'P01.370', 'C': C, 'course_pin_commit': PIN_C, 'module_commit': MODULE_C,
           'module': MODULE, 'version': VERSION, 'zip_sha256': sha(ZIP),
           'all': {'rows': all_vectors['rows'], 'green': all_vectors['green'], 'red': len(all_vectors['red'])},
           'new_B03': {'rows': len(fresh), 'green': sum(r['ok'] for r in fresh),
                       'red': sum(not r['ok'] for r in fresh), 'results': fresh},
           'old': {'rows': all_vectors['rows'] - len(fresh), 'red': old_red},
           'finding_scope': 'shared module log-mask, not only candidate 8.3'}
dump(B / 'RESULT.json', summary)
print(json.dumps({k: summary[k] for k in ('C', 'module_commit', 'all', 'old')}, ensure_ascii=False))
print('New B03: %d/%d green' % (summary['new_B03']['green'], len(fresh)))
