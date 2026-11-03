"""New published relay case reaches the real Bench preparation/start_agent; no SUT."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
OUT = Path(os.environ['CHECK_OUT'])
HEAD = '017195d3919019d62e1e68c0eb1f586e7ce6e4df'
PIN = 'a4d0d926c9e5579fe55dca978c5f670e900d51b6'


def blobs(root, listing):
    count = 0
    for entry in filter(None, listing.read_bytes().split(b'\0')):
        meta, name = entry.split(b'\t', 1); mode, kind, wanted = meta.split(); assert kind == b'blob'
        path = root / name.decode(); data = os.readlink(path).encode() if mode == b'120000' else path.read_bytes()
        assert hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest() == wanted.decode(), name
        count += 1
    return count


with tempfile.TemporaryDirectory(prefix='rv-p08-relay-') as directory:
    work = Path(directory)
    for name, commit in (('runtime', HEAD), ('specs', PIN)):
        target = work / name; target.mkdir()
        with tarfile.open(ROOT / (name + '.tar')) as stream:
            assert stream.pax_headers['comment'] == commit
            stream.extractall(target, filter='data')
    verified = {name: blobs(work / name, ROOT / (name + '.ls-tree')) for name in ('runtime', 'specs')}
    os.environ['CAMMETA_SPECS'] = str(work / 'specs')
    sys.path.insert(0, str(work / 'runtime/runner'))
    import c_targets
    import m11stand

    rows = c_targets.table(work / 'specs/Platform/08-domain/acceptance/3/scenarios.tsv')
    first = next(cells for _, cells in rows if cells[:2] == ['21-view-relay-refused', '1'])
    assert first[2:] == ['@domain m1 relay', 'ok']

    class Proxy:
        def __init__(self, *args, **kwargs): self.port = 23456

    class Prepared(m11stand.Bench):
        # Native implementation commands are outside this property control.
        # Constructor selection, cluster/proxy registries and start_agent are the actual runner code.
        def make_cluster(self, name, env, preparation): self.clusters[name] = SimpleNamespace()
        def _launch_agent(self, *args): return True

    cases = {}
    with patch.object(m11stand, 'Proxy', Proxy), patch.object(m11stand.standmod, 'free_port', return_value=23456):
        for scenario in ('15-topology', '16-second-road', first[0]):
            bench = Prepared(SimpleNamespace(lesson='P/08.3'), scenario=scenario)
            try:
                failure = None
                try: started = bench.start_agent('relay')
                except KeyError as error: started, failure = False, 'KeyError: ' + str(error)
                cases[scenario] = dict(clusters=list(bench.clusters), started=started, failure=failure)
            finally:
                shutil.rmtree(bench.root)
    result = dict(safety_pass=all('relay' in row['clusters'] and row['started'] for row in cases.values()),
                  head=HEAD, pin=PIN, SUT=0, git_blobs=verified, published_first_step=first, cases=cases,
                  probe_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (OUT / 'relay-evidence.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False), flush=True)
