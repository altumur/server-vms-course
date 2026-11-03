from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import sys,json,subprocess,tempfile
root=Path(sys.argv[1]);sys.path[:0]=[str(root/'runner'),str(root/'tests')]
import m11stand,m11,diagnostic_secrets as ds,c_execute
rows=[]
def row(name,why,env):
 safe=ds.Secrets().clean({'why':why})
 report={'green':not why,'scenarios':{'case':[safe]}}
 return dict(name=name,ok=not why,bound=env.get('bound'),classification=c_execute.classification(report,0 if not why else 1,False))
with tempfile.TemporaryDirectory(prefix='cli-oracle-') as temp:
 work=Path(temp)
 moves=[('empty',b'',0,'200 {}'),('whitespace',b' \n',0,'200 {}'),('not_utf8',b'\xff',0,'200 {}'),('no_prefix',b'failed',2,'200 {}'),('short_code',b'20 {}',0,'200 {}'),('bad_json',b'200 {',0,'200 {}'),('array',b'200 []',0,'200 {}'),('ok_exit_ignored',b'200 {}',7,'200 {}'),('semantic',b'200 {"x":1}',0,'200 {"x":2}'),('binding',b'200 {"x":7}',0,'200 {"x":"$bound"}'),('raw_token',b'200 {"token":"review-private-value"}',0,'200 {}'),('refusal',b'400 {"error":"declined"}',0,'400 {"error":"declined"}')]
 for n,raw,exit_code,expect in moves:
  run=m11stand.Run(SimpleNamespace(cwd=str(work)),'fixture');run.secrets.remember('review-private-value')
  run.b=SimpleNamespace(clusters={'m1':SimpleNamespace(workdir=str(work),port=1234,env={})},recovery='recovery',private_copy=lambda x:x,url=lambda p:'http://localhost:1234',ac=lambda c:SimpleNamespace(move='fixture'))
  run.bearer=lambda:None
  original=m11stand.check;seen=[]
  def judge(*args):
   seen.append(args[:2])
   return original(*args)
  with patch.object(m11stand.subprocess,'run',return_value=subprocess.CompletedProcess('fixture',exit_code,raw,b'fixture stderr')),patch.object(m11stand,'check',side_effect=judge):
   why=run.move('m1','',expect)
  if n=='raw_token':assert seen[0][1]['token']=='review-private-value'
  rows.append(row('move_'+n,why,run.env))
 vectors=[('ok',0,b'{"x":1}','ok {"x":1}'),('semantic',0,b'{"x":1}','ok {"x":2}'),('duplicate',0,b'{"x":1,"x":2}','ok {"x":2}'),('not_object',0,b'[]','ok {}'),('exit_ok',7,b'not JSON','@exit 7'),('exit_wrong',3,b'{}','@exit 0'),('timeout',None,b'partial','@exit 0')]
 for n,code,raw,expect in vectors:
  run=m11stand.Run(SimpleNamespace(cwd=str(work),json=str(work/'case.json'),token='fixture {input}'),'fixture')
  if code is None:effect=dict(side_effect=subprocess.TimeoutExpired('fixture',120,output=raw,stderr=b'partial error'))
  else:effect=dict(return_value=subprocess.CompletedProcess('fixture',code,raw,b'fixture stderr'))
  with patch.object(m11.subprocess,'run',**effect):why,got=run.run_vector('token','input',expect)
  rows.append(row('vector_'+n,why,run.env))
print(json.dumps(rows))
