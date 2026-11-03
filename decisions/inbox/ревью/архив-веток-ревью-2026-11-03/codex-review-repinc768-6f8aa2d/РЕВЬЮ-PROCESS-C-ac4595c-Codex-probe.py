"""Native launch/group/HTTP boundaries for C; fixtures observe, no SUT policy."""
import contextlib
import copy
import http.server
import io
import json
import os
from pathlib import Path
import shlex
import socketserver
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
from unittest.mock import patch


def controls(runtime,specs,out):
    sys.path.insert(0,str(runtime/'runner'))
    import stand,c_process,c_store,l05,l08,harness,prepare,process_start
    results={}
    with tempfile.TemporaryDirectory(prefix='rv-process-C-') as directory:
        root=Path(directory);observed=root/'observed.jsonl';script=root/'observer.py'
        script.write_text('import json,os,sys\nkeys=["BOX_ID","SERVER_NAME","INSTANCE_ID","TALLY_NAME","LABELS","OWN_EMPTY","OWN_EQUALS","OWN_PRIVATE","PYTHONPATH","CAMMETA_SPECS","AGENT_TOKEN_DIR"]\n'
                          +'with open(sys.argv[1],"a") as f:f.write(json.dumps(dict(role=sys.argv[2],name=sys.argv[3],env={k:os.environ.get(k) for k in keys}))+"\\n")\n'
                          +'sys.stdout.buffer.write(b"\\xffbinary output\\n");sys.stdout.flush();sys.exit(2)\n')
        class Mini(stand.Stand):
            def __init__(self):
                self.workdir=str(root);self.data=str(root/'data');Path(self.data).mkdir(exist_ok=True)
                self.root='testsub';self.server='srv-a';self.agent_tokens=str(root/'tokens');self.socket=str(root/'admin.sock')
                self.spec_names=('testsub','testsub2');self.procs=[];self.worker_places={};self.exited={};self.records={}
                self.lock=threading.RLock();self.env={'INSTANCE_ID':'profile-id','BOX_ID':'profile-box'}
                prefix=shlex.join([sys.executable,'-I','-B',str(script),str(observed)])
                self.a=SimpleNamespace(worker=prefix+' worker {name}',controller=prefix+' controller controller',cwd=str(root))
            def name_env(self,sub):return 'TALLY_NAME' if sub=='testsub2' else None
            def platform_env(self,*args,**kwargs):return dict(BOX_ID='layout-box',SERVER_NAME='layout-server')
            def server_place(self,server):return self.data,0
            def server_env(self,server):return dict(BOX_ID='server-box',SERVER_NAME=server or self.server)
            def fmt(self,template,**values):return template.format(**values)
            def _process_record(self,p):return self.records.setdefault(p,{})
            def close(self):
                for _,_,p in self.procs:c_process.finish(p,[p.pid],grace=.2,kill_wait=2)
        st=Mini()
        config=root/'config.json';report=out/'bridge.json'
        parts={name:dict(cwd=str(root),keys={},stand={key:'unused' for key in
               ('store','console','controller','worker','resource','manifest-put','rights','ring')})
               for name in ('01-store','02-installer','03-worker','04-controller','05-resource','06-console')}
        config.write_text(json.dumps(dict(specs=str(specs),parts=parts)))
        def engine(argv):
            assert st.directive('@start worker testsub2 t-1 on srv-b labels=x INSTANCE_ID=bad BOX_ID=bad:box SERVER_NAME=SRV-A OWN_EMPTY= OWN_EQUALS=a=b AGENT_TOKEN_DIR=/own-explicit','/unused','@exit 2')==[]
            assert st.directive('@start worker w-2','/unused','@exit 2')==[]
            assert st.directive('@start controller','/unused','@exit 2')==[]
            prepare.write(report,dict(green=True,scenarios={},total_steps=0,passed_steps=0))
            return 0
        try:
            with patch.dict(os.environ,{'OWN_PRIVATE':'ambient-private','OWN_EQUALS':'ambient','PYTHONPATH':'ambient-imports'}),patch.object(l05,'main',side_effect=engine),contextlib.redirect_stdout(io.StringIO()):
                code=c_store.main(['--driver','worker-case-2','--scenario','own','--config',str(config),'--json',str(report)])
            assert code==0 and json.loads(report.read_text())['green']
            rows=[json.loads(line) for line in observed.read_text().splitlines()]
            first,second,third=[row['env'] for row in rows]
            assert first['BOX_ID']=='bad:box' and first['SERVER_NAME']=='SRV-A' and first['INSTANCE_ID']=='bad'
            assert first['TALLY_NAME']=='t-1' and first['LABELS']=='x' and first['OWN_EMPTY']=='' and first['OWN_EQUALS']=='a=b'
            assert first['AGENT_TOKEN_DIR']=='/own-explicit' and st.agent_tokens!=first['AGENT_TOKEN_DIR']
            for env in (second,third):
                assert env['BOX_ID']=='server-box' and env['SERVER_NAME']=='srv-a' and env['INSTANCE_ID'] is None
                assert env['OWN_EMPTY'] is None and env['OWN_EQUALS'] is None and env['LABELS'] is None and env['TALLY_NAME'] is None
                assert env['AGENT_TOKEN_DIR']==st.agent_tokens
            assert all(row['env'][key] is None for row in rows for key in ('OWN_PRIVATE','PYTHONPATH','CAMMETA_SPECS'))
            results['bridge_launch_env']=dict(safety_pass=True,rows=rows,ambient_grant_leaked=False)

            # Actual common dispatcher and default ten-second budget, with a live
            # descendant after a leader exits 2. Observation must not signal it.
            child=root/'descendant.py'
            child.write_text('import subprocess,sys\nsubprocess.Popen([sys.executable,"-I","-B","-c","import time; time.sleep(30)"])\nsys.exit(2)\n')
            st.a.worker=shlex.join([sys.executable,'-I','-B',str(child)])
            started=time.monotonic();why=st.directive('@start worker w-child','/unused','@exit 2');elapsed=time.monotonic()-started
            proc=st.procs[-1][2];members,error=c_process.group_members([proc.pid])
            assert why and proc.poll()==2 and error is None and c_process.active(members[proc.pid])
            assert elapsed<11.5 and not any(str(item).startswith('transport:') for item in why)
            results['live_descendant_deadline']=dict(safety_pass=True,seconds=elapsed,leader_code=proc.poll(),why=why,live_group_after_observation=True)
        finally:st.close()

        # Admin wire bytes traverse a real Unix HTTP door before either engine.
        state={'body':b'{"index":"9"}'};calls=[]
        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                payload=self.rfile.read(int(self.headers.get('Content-Length','0')));calls.append(payload)
                body=state['body'];self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        class Server(socketserver.ThreadingMixIn,socketserver.UnixStreamServer):daemon_threads=True
        socket_path=root/'wire.sock';server=Server(str(socket_path),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        selected=[]
        def door(role):selected.append(role);return harness.HttpDoor('unix:'+str(socket_path))
        proxy=SimpleNamespace(as_store=lambda req:('testsubworker',req),store=door)
        req='admin POST /v1/write {"op":"put","key":"own","items":{}}'
        forms=[]
        try:
            for raw in (b'{"index":"9"}',b'{}',b'',b'not-json',b'\xff',b'null',b'[]',b'{"index":9}',b'{"index":"9","extra":1}'):
                state['body']=raw
                for name,engine in [('l05',l05),('l08',l08)]:
                    code,got=engine.do_request(proxy,req) if name=='l05' else engine.request(proxy,req,'own')[:2]
                    if name=='l05':why=engine.check(code,got,'200',{},req,'P/03.2')
                    else:why=[];engine.full_form('P/03.6',req,code,got,why)
                    want=raw!=b'{"index":"9"}'
                    assert bool(why)==want,(name,raw,why)
                    forms.append(dict(engine=name,body_hex=raw.hex(),rejected=bool(why)))
            assert all(role is None for role in selected)
            assert all(json.loads(payload)==dict(op='put',key='own',items={}) for payload in calls)
        finally:server.shutdown();server.server_close();thread.join(3)
        results['admin_full_form_wire']=dict(safety_pass=True,cases=forms,privileged_calls=len(selected))

        # A start/wait deadline is shared, not restarted when its observer begins.
        p=subprocess.Popen([sys.executable,'-I','-B','-c','import time;time.sleep(5)'],start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            begin=time.monotonic();why=process_start.wait_exit(p,0,begin-.18,budget=.2);elapsed=time.monotonic()-begin
            assert why and elapsed<.15 and p.poll() is None
            results['remaining_budget']=dict(safety_pass=True,seconds=elapsed,why=why,process_not_killed=True)
        finally:c_process.finish(p,[p.pid],grace=.1,kill_wait=2)
    (out/'controls.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
    return results

if __name__=='__main__':
    result=controls(Path(sys.argv[1]),Path(sys.argv[2]),Path(os.environ['CHECK_OUT']))
    print(json.dumps({name:value['safety_pass'] for name,value in result.items()}))
