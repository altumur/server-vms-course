"""Report identity versus response-field provenance; unchanged old/new control."""
import json
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0,str(Path(sys.argv[1])/'runner'))
import diagnostic_secrets as ds
out=Path(os.environ['CHECK_OUT'])
result={}

# Legitimate report identifiers must not teach unrelated step strings as secrets.
with tempfile.TemporaryDirectory(prefix='rv-identities-') as directory:
    root=Path(directory);path=root/'report.json'
    wanted={'01-token-and-audience':[dict(step=str(i),line=i+2,ok=True,got=None,why=[]) for i in range(1,8)],
            '02-refusals':[dict(step='1',line=20,ok=True,got=None,why=[])]}
    path.write_text(json.dumps(dict(scenarios=wanted,green=True,passed_steps=8,total_steps=8)))
    secrets=ds.Secrets();secrets.finalize([root]);got=json.loads(path.read_text())
    result['report_identity']=dict(safety_pass=list(got['scenarios'])==list(wanted) and '1' not in secrets.values,
                                    keys=list(got['scenarios']),learned=sorted(secrets.values))

# These four names are ordinary untrusted response fields, not report maps.
# Boundary B promises exact substitution of a value learned from token fields.
for field in ('scenarios','cases','variants','probes'):
    for encoded in (False,True):
        secret='own-issued-'+field+'-credential-042'
        body={field:{'token':secret}}
        response=json.dumps(body) if encoded else body
        with tempfile.TemporaryDirectory(prefix='rv-response-') as directory:
            root=Path(directory);report=root/'report.json';log=root/'native.log'
            report.write_text(json.dumps(dict(scenarios={'safe-case':[dict(step='4',line=6,ok=True,why=[],got=response)]})))
            log.write_text('native echo: '+secret+'\n')
            secrets=ds.Secrets();secrets.register_log(log)
            secrets.learn_received(dict(got=response))
            before=secret in secrets.values
            secrets.finalize([root])
            result[field+('-json' if encoded else '-object')]=dict(
                safety_pass=before and secret in secrets.values and secret not in log.read_text(),
                learned_before_finalize=before,learned_after_finalize=secret in secrets.values,
                log=log.read_text(),body_exported=secret in report.read_text())

# The exception must not weaken the original short-value or Authorization rule.
for label,body,secret in [('ordinary-token',{'token':'denied'},'denied'),
                          ('ordinary-auth',{'Authorization':'Bearer a.b/c~d'},'a.b/c~d')]:
    secrets=ds.Secrets();secrets.learn(body)
    result[label]=dict(safety_pass=secret in secrets.values,learned=sorted(secrets.values))
(out/'controls.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({key:value['safety_pass'] for key,value in result.items()}))
