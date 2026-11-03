"""Independent E controls; own peers only, no implementation under test."""
import contextlib
import itertools
import json
import os
from pathlib import Path
import socket
import sys
import threading
from types import SimpleNamespace
from unittest.mock import patch

runtime, specs = map(Path, sys.argv[1:3])
sys.path.insert(0, str(runtime/'runner'))
import console
import harness
import l03
import l08
import l09

expect = {}
for line in (specs/'Platform/06-console/acceptance/5/scenarios.tsv').read_text().splitlines()[1:]:
    cells = line.split('\t')
    if len(cells) >= 4 and cells[0].startswith(('20-', '21-')) and cells[2].endswith('GET /metrics'):
        expect[cells[0][:2]] = cells[3]
assert set(expect) == {'20','21'}
stand = SimpleNamespace(url='http://127.0.0.1:1', as_store=lambda request:(None, request))
labels = ['kind="last"', 'worker="w-1"']
rows = []
def check(request, body, want):
    with patch.object(l09, 'http', return_value=(200, {'content-type':['text/plain']}, body.encode())), \
         patch.object(l08, 'request', return_value=(200, body.encode(), {'content-type':'text/plain'})):
        return console.attempt(stand, 'own', '1', request, want, {})[0]
for request in ('GET /metrics', 'console GET /metrics'):
    for order in itertools.permutations(labels):
        first = 'testsub_failover_seconds{' + ','.join(order) + '} -1\n'
        base = 'testsub_failovers_unmeasured 1\n' + first
        assert not check(request, base, expect['21'])
        assert not check(request, base.replace('unmeasured 1', 'unmeasured 0').replace(' -1', ' 2.5'), expect['20'])
        for other in itertools.permutations(labels):
            for value in ('-1','0'):
                duplicate = 'testsub_failover_seconds{' + ','.join(other) + '} '+value+'\n'
                why = check(request, base+duplicate, expect['21'])
                rows.append(dict(request=request, reordered=order!=other, second_value=value,
                                 rejected=bool(why), why=why))
        for bad in (base.replace('unmeasured 1','unmeasured 0'), base.replace(' -1',' 0'),
                    base.replace('worker="w-1"','worker="w-2"'), base.replace('kind="last"','kind="worst"')):
            assert check(request, bad, expect['21'])
        assert not check(request, base, expect['21']), 'seen state leaked to the next response'

# A different name or label set remains a distinct series; raw keys and values are retained.
legal = ('x{a="one",b="two"} -1\nx{b="different",a="one"} 0\n'
         'y{b="two",a="one"} 1\nx 2\n')
why=[]; parsed=l09.metrics(legal.encode(), why)
assert not why and len(parsed)==4 and parsed[('x','{a="one",b="two"}')]==-1
why=[]; malformed=l09.metrics(b'x{kind=last} 1\n',why)
legacy_malformed=dict(accepted=not why, parsed=[[list(k),v] for k,v in malformed.items()])

writer_controls=[]
NativeThread=threading.Thread
for fail in (False, True):
    ready=threading.Event(); release=threading.Event(); events=[]
    class Writer(NativeThread):
        def join(self,timeout=None):
            events.append('join'); assert timeout==5
            release.set(); super().join(timeout)
            assert not self.is_alive()
    class Peer:
        def sendall(self,wire):
            ready.set(); assert release.wait(3)
            events.append('writer_done')
        def makefile(self,*args):return contextlib.nullcontext(None)
        def shutdown(self,how):assert how==socket.SHUT_RDWR;events.append('shutdown')
        def close(self):events.append('close')
    def read(*args):
        assert ready.wait(1)
        if fail:raise harness.TransportError('own no reply')
        return SimpleNamespace(status=413,body=b'',headers={})
    with patch.object(l03.socket,'create_connection',return_value=Peer()), \
         patch.object(l03.threading,'Thread',Writer),patch.object(harness,'_read_http_response',side_effect=read):
        if fail:
            try:l03.http('http://127.0.0.1:1','PUT','/own',b'x')
            except OSError:pass
            else:raise AssertionError('missing response became success')
        else:assert l03.http('http://127.0.0.1:1','PUT','/own',b'x')==(413,b'')
    assert events[0]=='shutdown'
    writer_controls.append(dict(read_failed=fail,events=events,
                               correct_order=events==['shutdown','join','writer_done','close']))

native=[]
for reply in (True,False):
    errors=[]
    with socket.socket() as listener:
        listener.bind(('127.0.0.1',0));listener.listen();listener.settimeout(5)
        def peer():
            try:
                conn,_=listener.accept()
                with conn:
                    conn.settimeout(5); got=b''
                    while b'\r\n\r\n' not in got:got+=conn.recv(4096)
                    if reply:
                        conn.sendall(b'HTTP/1.1 413 Content Too Large\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
                        conn.shutdown(socket.SHUT_WR)
                        while conn.recv(65536):pass
            except (ConnectionResetError,BrokenPipeError):pass
            except BaseException as exc:errors.append(repr(exc))
        worker=NativeThread(target=peer);worker.start()
        url='http://127.0.0.1:%d'%listener.getsockname()[1]
        try:
            result=l03.http(url,'PUT','/own',b'x'*(2*1024*1024))
            assert reply and result==(413,b''),result
            outcome='413'
        except OSError:
            assert not reply
            outcome='transport'
        worker.join(6);assert not worker.is_alive() and not errors,errors
        native.append(dict(reply=reply,outcome=outcome))

out=dict(duplicate_controls=rows,legal_distinct_series=4,legacy_malformed=legacy_malformed,
         writer_controls=writer_controls,native=native)
Path(os.environ['CHECK_OUT'],'controls.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out))
