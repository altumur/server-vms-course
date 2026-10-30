"""Independent boundary controls for B. Controlled doors/argv observers, no SUT."""
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import shlex
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

FIXTURE = r'''
import http.server,json,pathlib,socketserver,sys,threading
admin,ceiling,mode,log,literal=sys.argv[1:]
ceiling=int(ceiling)
def record(value):
    with open(log,'a') as stream:stream.write(json.dumps(value)+'\n')
record(dict(launch=True,ceiling=ceiling,mode=mode,literal=literal))
class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        record(dict(method='GET',path=self.path))
        if mode=='transport':self.connection.close();return
        self.reply(200,dict(max_value=ceiling+1 if mode=='status' else ceiling))
    def do_POST(self):
        data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        event=dict(method='POST',op=data['op'],key=data['key'])
        if data['op']=='delete':record(event);self.reply(200,{});return
        weight=sum(len(k.encode())+len(v.encode()) for k,v in data['items'].items())
        event.update(weight=weight);record(event)
        code=413 if weight>ceiling else 200
        if mode=='at' and weight==ceiling:code=413
        if mode=='over' and weight>ceiling:code=200
        self.reply(code,dict(kind='toolarge',limit=ceiling+(mode=='limit'),key=data['key'],size=weight)
                   if code==413 else dict(index='1'))
    def reply(self,code,value):
        body=json.dumps(value).encode();self.send_response(code)
        self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)))
        self.end_headers();self.wfile.write(body)
class Server(socketserver.ThreadingMixIn,socketserver.UnixStreamServer):daemon_threads=True
servers=[Server(str(path),Handler) for path in (pathlib.Path(admin),pathlib.Path(admin).with_name('acc.sock'))]
for server in servers:threading.Thread(target=server.serve_forever,daemon=True).start()
threading.Event().wait()
'''


def controls(runtime, specs, out):
    sys.path.insert(0, str(runtime/'runner'))
    import c_store
    import c_installer as checker
    import c_installer_data as data
    import c_execute
    import harness
    import scenario_status
    results = {}
    with tempfile.TemporaryDirectory(prefix='review-B-') as directory:
        root = Path(directory)
        fixture = root/'boundary-door.py'; fixture.write_text(FIXTURE)
        log = root/'door.jsonl'
        def profile(mode):
            return dict(cwd=str(root), keys={}, stand=dict(store1=shlex.join([sys.executable,'-I','-B',str(fixture)])
                        +' {socket} {row_ceiling} '+shlex.join([mode,str(log)])+" '{{row_ceiling}}'"))
        for mode, ceiling in [('ok',976),('ok',977),('status',976),('at',976),('over',976),('limit',976),('transport',976)]:
            label=mode+'-'+str(ceiling); log.unlink(missing_ok=True)
            p=profile(mode)
            template=checker.ceiling_command(c_store.command(p,'store1'),ceiling)
            inst=c_store.instance_class(harness)(template,cwd=p['cwd'])
            try:
                try: checker.prove_ceiling(inst,ceiling)
                except checker.NotExecuted: observed='not_executed'
                except harness.TransportError: observed='transport'
                else: observed='proven'
                events=[json.loads(line) for line in log.read_text().splitlines()]
                want='proven' if mode=='ok' else 'transport' if mode=='transport' else 'not_executed'
                launch=events[0]
                assert observed==want and launch['ceiling']==ceiling and launch['literal']=='{row_ceiling}',label
                if mode=='ok':
                    assert [e['weight'] for e in events if 'weight'in e]==[ceiling,ceiling+1]
                    assert events[-1].get('op')=='delete'
                results[label]=dict(safety_pass=True,observed=observed,events=events)
            finally:inst.close()

        # Run the actual bridge and final evidence scrubber, not only checker.main.
        selected=[case for case in data.data(specs,'installer-canonical-put') if 'ceiling'in case]
        assert len(selected)==2
        marker=root/'installer-was-called'
        installer=dict(cwd=str(root),keys={},stand={'manifest-put':'touch '+shlex.quote(str(marker))})
        config=root/'config.json'; report_file=out/'bridge.json'
        config.write_text(json.dumps(dict(specs=str(specs),parts={'01-store':profile('status'),'02-installer':installer})))
        with patch.object(data,'data',return_value=selected), patch.dict(os.environ), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code=c_store.main(['--driver','installer-canonical-put','--config',str(config),'--json',str(report_file)])
        report=json.loads(report_file.read_text())
        assert code==1 and report['green'] is False and report['classification']=='stand' and report['cases']==[0,2]
        assert not marker.exists()
        assert all(r['ok'] is None and r['executed'] is False and r['not_executed']==scenario_status.reason('installer_ceiling_unproven') for r in report['vectors'])
        target=dict(driver='installer-canonical-put',inputs=[dict(path=selected[0]['source'])],execution_cases=selected)
        coverage=c_execute.coverage(target,report)
        assert not coverage['errors'],coverage
        negative={}
        for label in ('green','ordinary','code','no_ceiling'):
            bad, plan=copy.deepcopy(report),copy.deepcopy(target)
            if label=='green':bad['green']=True
            elif label=='ordinary':plan['driver']='installer-put'
            elif label=='code':bad['vectors'][0]['not_executed']['reason']='unpublished'
            else:
                for case in plan['execution_cases']:del case['ceiling']
            errors=c_execute.coverage(plan,bad)['errors'];assert errors,label;negative[label]=errors
        results['bridge_finalize']=dict(safety_pass=True,code=code,cases=report['cases'],coverage=coverage,negative=negative)

        # Native argv/file observer: inspect preparation only. No installer or
        # expected policy is implemented; final stored-row judgement is excluded.
        observer=root/'observe.py'; file_log=root/'files.jsonl'
        observer.write_text('import json,pathlib,sys\np=pathlib.Path(sys.argv[1]);s=p.with_name(p.name.replace(".subsystem.yaml",".shell.html"))\n'
                            +'with open(sys.argv[2],"a") as f:f.write(json.dumps(dict(path=str(p),yaml=list(p.read_bytes()),shell=list(s.read_bytes()) if s.exists() else None))+"\\n")\n')
        installer['stand']['manifest-put']=shlex.join([sys.executable,'-I','-B',str(observer)])+' {file} '+shlex.quote(str(file_log))
        cases=data.data(specs,'installer-put')
        shell=next(c for c in cases if c['case']=='shell_changed')
        plain=dict(shell,tokens=['pagedok'])
        native_evidence=out/'native-commands';native_evidence.mkdir()
        with patch.object(harness,'Instance',c_store.instance_class(harness)),patch.object(checker,'installed_errors',return_value=[]):
            for case in (shell,plain):
                assert checker.put_case(case,installer,profile('ok'),specs,native_evidence)==[]
        calls=[json.loads(line) for line in file_log.read_text().splitlines()]
        base=specs/data.ROOT/'acceptance/3/puts'
        wanted=[None,list((base/'pagedok.shell.html').read_bytes()),list((base/'pagedok-alt.shell.html').read_bytes()),None]
        assert [c['shell'] for c in calls]==wanted
        assert all(bytes(c['yaml'])==(base/'pagedok.subsystem.yaml').read_bytes() for c in calls)
        assert Path(calls[0]['path']).parent!=Path(calls[-1]['path']).parent
        assert all(not Path(c['path']).is_relative_to(specs) for c in calls)
        results['native_shell_bytes']=dict(safety_pass=True,calls=len(calls),shell_sizes=[None if v is None else len(v) for v in wanted])

        # A conflicting CAS during rev-max cannot fall through to final install.
        case=next(c for c in cases if c['case']=='rev_max_same')
        writes=[]; installs=[]
        keys=['platform/manifest/revmax'+s for s in ('','/rev','/canonical/1')]
        rows={key:dict(index=str(10+i),items={'rev':'1','untouched':'  exact bytes\n'}) for i,key in enumerate(keys)}
        class Door:
            def request(self,method,path,body=None):
                from urllib.parse import unquote
                if method=='GET':value=copy.deepcopy(rows[unquote(path.split('key=',1)[1])]);code=200
                else:
                    value=json.loads(body);writes.append(value)
                    assert value['cas']==rows[value['key']]['index']
                    assert value['items']==dict(rows[value['key']]['items'],rev='9007199254740991')
                    code=409 if len(writes)==2 else 200
                    value={}
                return SimpleNamespace(status=code,body=json.dumps(value).encode())
        inst=SimpleNamespace(socket='/own',door=SimpleNamespace(admin=Door()),close=lambda:None)
        def install(*args,**kwargs):installs.append(kwargs['file']);return 0,b'',b''
        conflict_evidence=out/'cas-conflict';conflict_evidence.mkdir()
        with patch.object(harness,'Instance',return_value=inst),patch.object(checker,'command',side_effect=install):
            try:checker.put_case(case,installer,profile('ok'),specs,conflict_evidence)
            except harness.TransportError:pass
            else:raise AssertionError('rev-max CAS conflict was hidden')
        assert len(writes)==2 and len(installs)==1
        results['rev_max_conflict']=dict(safety_pass=True,writes=writes,install_count=len(installs))
    (out/'controls.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
    return results

if __name__=='__main__':
    result=controls(Path(sys.argv[1]),Path(sys.argv[2]),Path(os.environ['CHECK_OUT']))
    print(json.dumps({name:value['safety_pass'] for name,value in result.items()}))
