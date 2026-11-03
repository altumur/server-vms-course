"""Actual c_store -> m11stand.main -> finalize -> coverage at d389cf5; no SUT."""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

runtime,spec=map(Path,sys.argv[1:3]);sys.path.insert(0,str(runtime/'runner'))
import assembly
import c_execute
import c_store
import c_targets
import diagnostic_secrets
import m11stand
pin=(runtime/'SPEC_VERSION').read_text().strip()
profiles={owner:dict(cwd='.',keys={'role':'acc'},stand={},adapters={},vectors={}) for owner in assembly.MODULES}
for target in c_targets.CONNECTED_TARGETS:
    for owner,group,key in (*target.requires,*target.requires_any):
        if group:profiles[owner][group][key]='NEVER-EXECUTE'
profiles['03-worker']['stand']['worker']='AGENT_TOKEN_DIR={agent_tokens} NEVER-EXECUTE'
profiles['09-agent']['stand']['agent']='AGENT_TOKEN_DIR={agent_tokens} NEVER-EXECUTE'
profiles['09-agent']['stand']['token-door']='unix:{agent_tokens}/{role}.sock'
composition=SimpleNamespace(parts={k:SimpleNamespace(doc=v) for k,v in profiles.items()},specs=spec,spec_version=pin)
target=next(t for t in c_targets.DOMAIN_TARGETS if t.id=='P/08.7/stand')
plan=c_targets.plan(composition,[target.id])[0]
result={}
with tempfile.TemporaryDirectory(prefix='rv-p087-') as folder:
    root=Path(folder)
    for mode in ('none','nested','json'):
        output=root/(mode+'.json'); log=root/(mode+'.log')
        secret='OWN-P087-CREDENTIAL-'+mode+'-a8f09e7c'
        registry=diagnostic_secrets.Secrets();log.write_text('early stdout '+secret+'\n')
        registry.register_log(log);registry.evidence.add(log)
        class PassRun:
            def __init__(self,args,name,**kwargs):self.last_transport=None
            def step(self,*args):
                got={'cases':{'token':secret}}
                return [],None if mode=='none' else json.dumps(got) if mode=='json' else got
            def close(self):pass
        _,args=c_store.chapter_arguments(target.driver,profiles,spec,output)
        with diagnostic_secrets.using(registry),patch.object(m11stand,'Run',PassRun),contextlib.redirect_stdout(io.StringIO()):
            code=m11stand.main(args)
        raw=output.read_text();report=json.loads(raw);coverage=c_execute.coverage(plan,report)
        if mode!='none':
            assert secret in registry.values
            assert secret not in raw and secret not in log.read_text()
            assert '<redacted>' in log.read_text()
        result[mode]=dict(safety_pass=code==0 and '01-token-and-audience' in report['scenarios'] and not coverage['errors'],
                          names=list(report['scenarios']),counts=[report['passed_steps'],report['total_steps']],
                          reported_steps=sum(map(len,report['scenarios'].values())),coverage_errors=coverage['errors'],
                          foreign_secret_learned=secret in registry.values,process_log=log.read_text() if mode!='none' else None)
    source=json.loads((Path(sys.argv[3])/'c594p-evidence/P-08.7-stand.json').read_text())
    coverage=c_execute.coverage(plan,source)
    assert '01-token-and-audience' not in source['scenarios'] and source['passed_steps']==source['total_steps']==27
    assert sum(map(len,source['scenarios'].values()))==20 and coverage['errors']
    result['c594p']=dict(names=list(source['scenarios']),counts=[27,27],reported_steps=20,coverage_errors=coverage['errors'])
Path(os.environ['CHECK_OUT'],'controls.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False))
